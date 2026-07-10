"""Vocabulary service: seeding, spaced repetition, quiz generation, and stats."""

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, OpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.vocabulary_seed import SEED_WORDS
from app.models import UserVocabulary, Vocabulary

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

EBBINGHAUS_INTERVALS = {0: 1, 1: 2, 2: 4, 3: 7, 4: 15}


def _strip_markdown_code_blocks(text: str) -> str:
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _next_review_date(review_count: int) -> date:
    """Calculate next review date based on Ebbinghaus intervals."""
    days = EBBINGHAUS_INTERVALS.get(review_count, 30)
    return date.today() + timedelta(days=days)


async def seed_vocabulary(db: AsyncSession) -> int:
    """Seed the vocabulary table if empty. Returns count of inserted words."""
    result = await db.execute(select(func.count(Vocabulary.id)))
    count = result.scalar()
    if count and count > 0:
        return 0

    inserted = 0
    for item in SEED_WORDS:
        existing = await db.execute(select(Vocabulary).where(Vocabulary.word == item["word"]))
        if existing.scalar_one_or_none() is None:
            db.add(
                Vocabulary(
                    word=item["word"],
                    pos=item["pos"],
                    definition_cn=item["definition_cn"],
                    example_sentence=item["example_sentence"],
                    synonyms=json.dumps(item["synonyms"], ensure_ascii=False),
                    topic=item["topic"],
                    difficulty=item["difficulty"],
                )
            )
            inserted += 1

    if inserted > 0:
        await db.commit()
    return inserted


async def get_due_reviews(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    """Get words due for review today for a given user.

    Returns user_vocabulary records joined with the vocabulary table.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    user_words = await db.execute(
        select(UserVocabulary, Vocabulary)
        .join(Vocabulary, UserVocabulary.word_id == Vocabulary.id)
        .where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.next_review_at < tomorrow,
        )
        .order_by(UserVocabulary.next_review_at.asc())
        .limit(50)
    )
    rows = user_words.all()

    results: list[dict[str, Any]] = []
    for uv, v in rows:
        results.append(
            {
                "id": uv.id,
                "word_id": v.id,
                "word": v.word,
                "pos": v.pos,
                "definition_cn": v.definition_cn,
                "example_sentence": v.example_sentence,
                "synonyms": json.loads(v.synonyms),
                "topic": v.topic,
                "difficulty": v.difficulty,
                "status": uv.status,
                "review_count": uv.review_count,
                "next_review_at": uv.next_review_at,
            }
        )
    return results


async def get_all_words_for_review(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    """Get all vocab words with user progress for flashcard mode.

    Words without a user_vocabulary record are considered new.
    Returns words ordered: due reviews first, then new words, then mastered.
    """
    due = await get_due_reviews(db, user_id)
    due_word_ids = {d["word_id"] for d in due}

    # Get all vocabulary entries
    all_words_result = await db.execute(select(Vocabulary).order_by(Vocabulary.topic, Vocabulary.word))
    all_words = all_words_result.scalars().all()

    # Build a full list: due first, then unstarted, then the rest
    results: list[dict[str, Any]] = list(due)

    for v in all_words:
        if v.id not in due_word_ids:
            results.append(
                {
                    "id": None,
                    "word_id": v.id,
                    "word": v.word,
                    "pos": v.pos,
                    "definition_cn": v.definition_cn,
                    "example_sentence": v.example_sentence,
                    "synonyms": json.loads(v.synonyms),
                    "topic": v.topic,
                    "difficulty": v.difficulty,
                    "status": "new",
                    "review_count": 0,
                    "next_review_at": None,
                }
            )

    return results


async def update_review_status(
    db: AsyncSession, user_id: int, word_id: int, status: str
) -> dict[str, Any]:
    """Update review status for a user-word pair.

    status: 'mastered' or 'review'
    If 'mastered': advance to next interval, eventually mark mastered.
    If 'review': reset review_count to 0, set next_review for tomorrow.
    """
    result = await db.execute(
        select(UserVocabulary).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.word_id == word_id,
        )
    )
    uv = result.scalar_one_or_none()

    now = datetime.utcnow()
    today = date.today()

    if uv is None:
        uv = UserVocabulary(
            user_id=user_id,
            word_id=word_id,
            status="learning",
            review_count=0,
            last_review_at=now,
            next_review_at=datetime(today.year, today.month, today.day),
        )
        db.add(uv)

    if status == "mastered":
        new_count = uv.review_count + 1
        uv.review_count = new_count
        uv.last_review_at = now
        next_days = EBBINGHAUS_INTERVALS.get(new_count, 30)
        uv.next_review_at = datetime(today.year, today.month, today.day) + timedelta(
            days=next_days
        )
        if new_count >= 6:
            uv.status = "mastered"
        else:
            uv.status = "learning"
    else:
        # review again — reset
        uv.review_count = 0
        uv.last_review_at = now
        uv.next_review_at = datetime(today.year, today.month, today.day) + timedelta(days=1)
        uv.status = "review"

    await db.commit()
    await db.refresh(uv)

    return {
        "id": uv.id,
        "status": uv.status,
        "review_count": uv.review_count,
        "next_review_at": uv.next_review_at.strftime("%Y-%m-%d") if uv.next_review_at else None,
    }


async def get_dashboard_stats(db: AsyncSession, user_id: int) -> dict[str, Any]:
    """Get vocabulary dashboard stats for a user."""
    # Total words in vocabulary table
    total_result = await db.execute(select(func.count(Vocabulary.id)))
    total_words = total_result.scalar() or 0

    # User's stats
    mastered_result = await db.execute(
        select(func.count(UserVocabulary.id)).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.status == "mastered",
        )
    )
    mastered = mastered_result.scalar() or 0

    # Due today
    today = date.today()
    tomorrow = today + timedelta(days=1)
    due_result = await db.execute(
        select(func.count(UserVocabulary.id)).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.next_review_at < tomorrow,
        )
    )
    due_today = due_result.scalar() or 0

    # Learning count
    learning_result = await db.execute(
        select(func.count(UserVocabulary.id)).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.status == "learning",
        )
    )
    learning = learning_result.scalar() or 0

    # Streak: count consecutive days with at least one review
    # Simplified: just count distinct review dates
    streak_result = await db.execute(
        select(UserVocabulary.last_review_at)
        .where(UserVocabulary.user_id == user_id)
        .order_by(UserVocabulary.last_review_at.desc())
        .limit(30)
    )
    dates = streak_result.scalars().all()
    streak = 0
    check_date = today
    reviewed_dates = {d.date() for d in dates if d is not None}
    while check_date in reviewed_dates:
        streak += 1
        check_date -= timedelta(days=1)

    return {
        "total_words": total_words,
        "mastered": mastered,
        "learning": learning,
        "due_today": due_today,
        "streak": streak,
    }


async def generate_quiz(
    db: AsyncSession, user_id: int, quiz_type: str
) -> dict[str, Any]:
    """Generate an AI-powered quiz question.

    quiz_type: 'multiple-choice', 'fill-blank', or 'sentence'
    Uses user's due review words if available, otherwise picks random words.
    """
    if not DEEPSEEK_API_KEY:
        return _fallback_quiz(quiz_type)

    # Pick a word to quiz on
    due_words = await get_due_reviews(db, user_id)
    if due_words:
        word = due_words[0]
    else:
        result = await db.execute(select(Vocabulary).order_by(func.random()).limit(1))
        row = result.scalar_one_or_none()
        if row is None:
            return {"error": "No vocabulary words available"}
        word = {
            "word_id": row.id,
            "word": row.word,
            "pos": row.pos,
            "definition_cn": row.definition_cn,
            "example_sentence": row.example_sentence,
            "synonyms": json.loads(row.synonyms),
            "topic": row.topic,
            "difficulty": row.difficulty,
        }

    synonyms_str = ", ".join(word["synonyms"][:3])

    prompts = {
        "multiple-choice": f"""You are an IELTS vocabulary tutor. Create a multiple-choice question for the word "{word['word']}" ({word['pos']}, topic: {word['topic']}).

The question should ask for the correct meaning or synonym of the word.
Provide 4 options (A, B, C, D), exactly one correct, and a brief explanation.

Return ONLY valid JSON, no markdown:
{{
  "question": "What does the word '{word['word']}' mean?",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "correct_index": 0,
  "explanation": "..."
}}""",
        "fill-blank": f"""You are an IELTS vocabulary tutor. Create a fill-in-the-blank question for the word "{word['word']}" ({word['pos']}, meaning: {word['definition_cn']}, topic: {word['topic']}).

Write a sentence with a blank where the word should go. Provide the correct answer.

Return ONLY valid JSON, no markdown:
{{
  "question": "Complete the sentence: The government introduced new ______ to tackle air pollution.",
  "blank_word": "{word['word']}",
  "hint": "..."
}}""",
        "sentence": f"""You are an IELTS vocabulary tutor. Create a sentence-writing exercise for the word "{word['word']}" ({word['pos']}, meaning: {word['definition_cn']}, synonyms: {synonyms_str}, topic: {word['topic']}).

Provide a prompt asking the student to create their own sentence, and include an example answer.

Return ONLY valid JSON, no markdown:
{{
  "question": "Write a sentence using the word '{word['word']}' in the context of {word['topic']}.",
  "example_answer": "...",
  "key_points": ["...", "..."]
}}""",
    }

    prompt = prompts.get(quiz_type, prompts["multiple-choice"])

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the quiz question."},
            ],
            temperature=0.7,
            max_tokens=1200,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            return {"error": "API returned empty response"}

        cleaned = _strip_markdown_code_blocks(raw_content)
        try:
            result = json.loads(cleaned)
            result["word"] = word["word"]
            result["quiz_type"] = quiz_type
            result["word_id"] = word["word_id"]
            return result
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse quiz response",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "Quiz generation timed out. Please try again."}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return _fallback_quiz(quiz_type)


def _fallback_quiz(quiz_type: str) -> dict[str, Any]:
    """Return a fallback quiz when API is unavailable."""
    if quiz_type == "fill-blank":
        return {
            "question": "Complete the sentence: Protecting the ______ is a shared responsibility of all nations.",
            "blank_word": "environment",
            "hint": "自然环境",
            "word": "environment",
            "quiz_type": quiz_type,
            "word_id": 1,
        }
    elif quiz_type == "sentence":
        return {
            "question": "Write a sentence using the word 'environment' in the context of environmental protection.",
            "example_answer": "We must take immediate action to protect the environment for future generations.",
            "key_points": ["Use the word correctly", "Show understanding of meaning"],
            "word": "environment",
            "quiz_type": quiz_type,
            "word_id": 1,
        }
    else:
        return {
            "question": "What does the word 'environment' mean?",
            "options": [
                "A. 环境；自然环境",
                "B. 经济；财政",
                "C. 教育；教学",
                "D. 技术；工艺",
            ],
            "correct_index": 0,
            "explanation": "'Environment' means 环境，the natural world around us.",
            "word": "environment",
            "quiz_type": quiz_type,
            "word_id": 1,
        }


async def get_vocabulary_list(
    db: AsyncSession, topic: str | None = None
) -> list[dict[str, Any]]:
    """Get vocabulary list, optionally filtered by topic."""
    if topic:
        result = await db.execute(
            select(Vocabulary)
            .where(Vocabulary.topic == topic)
            .order_by(Vocabulary.difficulty, Vocabulary.word)
        )
    else:
        result = await db.execute(
            select(Vocabulary).order_by(Vocabulary.topic, Vocabulary.difficulty, Vocabulary.word)
        )
    words = result.scalars().all()

    results: list[dict[str, Any]] = []
    for v in words:
        results.append(
            {
                "id": v.id,
                "word": v.word,
                "pos": v.pos,
                "definition_cn": v.definition_cn,
                "example_sentence": v.example_sentence,
                "synonyms": json.loads(v.synonyms),
                "topic": v.topic,
                "difficulty": v.difficulty,
            }
        )
    return results


TOPICS = ["environment", "education", "technology", "health", "society", "economy"]
TOPIC_LABELS = {
    "environment": "环境",
    "education": "教育",
    "technology": "科技",
    "health": "健康",
    "society": "社会",
    "economy": "经济",
}
