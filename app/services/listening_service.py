import json
import os
import re

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, OpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

SCRIPT_GENERATION_PROMPT = """You are an experienced IELTS examiner. Generate an IELTS Listening practice script for a gap-fill exercise.

Scene type: {scene_type}

Instructions:
1. Write a realistic listening script of about 200-300 words suitable for an IELTS Listening gap-fill exercise.
2. For "Conversation": write a dialogue between two people (label speakers A and B).
3. For "Lecture": write a monologue in academic lecture style.
4. For "Announcement": write a public announcement or broadcast.
5. For "Travel": write a travel guide or tour commentary.
6. Mark 5-8 gaps in the script with exactly THREE underscores: ___
7. Each gap should test a specific piece of information (names, numbers, dates, places, key facts).
8. Generate corresponding questions that prompt the student to fill each gap.

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{{
  "script": "<full listening script with ___ marking each gap>",
  "questions": [
    {{
      "id": 1,
      "gap_text": "___",
      "question_text": "<what the student needs to listen for, e.g. 'The meeting is scheduled at ___'>",
      "correct_answer": "<the exact word or short phrase that fills the blank>"
    }}
  ],
  "answers": ["<answer1>", "<answer2>", ...]
}}"""

CHECK_ANSWERS_PROMPT = """You are an IELTS examiner. Compare the student's answers with the correct answers for an IELTS Listening gap-fill exercise.

For each question, determine if the answer is correct. Be lenient with:
- Spelling variations (e.g. "centre" vs "center", "organize" vs "organise")
- Case differences (e.g. "London" vs "london")
- Minor word variations that convey the same meaning
- Extra or missing articles ("the library" vs "library") unless it changes the meaning

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{{
  "score": <number of correct answers>,
  "total": <total number of questions>,
  "results": [
    {{
      "question_id": 1,
      "is_correct": true,
      "user_answer": "<what the student wrote>",
      "correct_answer": "<the correct answer>",
      "explanation": "<brief explanation in Chinese, 1-2 sentences>"
    }}
  ]
}}"""


def _strip_markdown_code_blocks(text: str) -> str:
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_script(scene_type: str) -> dict:
    """Generate an IELTS Listening gap-fill script and questions using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    valid_types = ["Conversation", "Lecture", "Announcement", "Travel"]
    if scene_type not in valid_types:
        return {"error": f"Invalid scene type: {scene_type}. Must be one of {valid_types}"}

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=120,
        )

        system_prompt = SCRIPT_GENERATION_PROMPT.format(scene_type=scene_type)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f'Generate an IELTS Listening gap-fill script of type "{scene_type}" with 5-8 gaps. Make it 200-300 words, realistic, and suitable for listening practice.',
                },
            ],
            temperature=0.7,
            max_tokens=3000,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            return {"error": "API returned empty response"}

        cleaned = _strip_markdown_code_blocks(raw_content)
        try:
            result = json.loads(cleaned)
            return result
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse script response as JSON",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "API request timed out after 120 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during script generation"}


def check_answers(
    script: str,
    questions: list,
    answers: list,
    user_answers: dict,
) -> dict:
    """Check user answers against correct answers using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    if not questions:
        return {"error": "questions must be a non-empty list"}

    comparison_parts = []
    for q in questions:
        qid = q.get("id", "")
        qtext = q.get("question_text", "")
        correct = q.get("correct_answer", "")
        user = user_answers.get(str(qid), "")
        comparison_parts.append(
            f"Q{qid}: {qtext}\nCorrect: {correct}\nStudent: {user}"
        )

    comparison = "SCRIPT:\n" + script + "\n\nANSWERS:\n" + "\n\n".join(comparison_parts)

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": CHECK_ANSWERS_PROMPT},
                {"role": "user", "content": comparison},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            return {"error": "API returned empty response"}

        cleaned = _strip_markdown_code_blocks(raw_content)
        try:
            result = json.loads(cleaned)
            return result
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse checking response as JSON",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "API request timed out after 60 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during answer checking"}
