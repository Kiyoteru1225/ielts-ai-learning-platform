"""Vocabulary router: flashcard review, AI quiz, word list, and dashboard."""

import os

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.models import User
from app.services.vocabulary_service import (
    TOPIC_LABELS,
    TOPICS,
    generate_quiz,
    get_all_words_for_review,
    get_dashboard_stats,
    get_due_reviews,
    get_vocabulary_list,
    update_review_status,
)

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


@router.get("/", response_class=HTMLResponse)
async def vocabulary_dashboard(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Vocabulary dashboard with stats and action buttons."""
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    stats = await get_dashboard_stats(db, user.id)
    due_words = await get_due_reviews(db, user.id)

    return templates.TemplateResponse(
        request=request,
        name="vocabulary.html",
        context={
            "stats": stats,
            "due_words": due_words[:5],
            "due_count": len(due_words),
        },
    )


@router.get("/review", response_class=HTMLResponse)
async def vocabulary_review(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    index: int = Query(default=0, ge=0),
):
    """Flashcard review mode — show one word at a time."""
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    words = await get_all_words_for_review(db, user.id)

    if not words:
        return templates.TemplateResponse(
            request=request,
            name="vocabulary_review.html",
            context={
                "word": None,
                "total": 0,
                "index": 0,
                "complete": True,
            },
        )

    if index >= len(words):
        index = len(words) - 1

    current_word = words[index]

    return templates.TemplateResponse(
        request=request,
        name="vocabulary_review.html",
        context={
            "word": current_word,
            "total": len(words),
            "index": index,
            "complete": False,
            "is_due": current_word.get("next_review_at") is not None,
        },
    )


@router.post("/review/{word_id}/status", response_class=HTMLResponse)
async def update_word_status(
    request: Request,
    word_id: int,
    status: str = Form(...),
    index: int = Form(default=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update review status for a word, then redirect to next word."""
    if status not in ("mastered", "review"):
        status = "review"

    await update_review_status(db, user.id, word_id, status)

    return RedirectResponse(
        url=f"/vocabulary/review?index={index + 1}", status_code=302
    )


@router.get("/quiz", response_class=HTMLResponse)
async def vocabulary_quiz(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    quiz_type: str = Query(default="multiple-choice"),
):
    """Quiz page with type selector and AI-generated question."""
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    if quiz_type not in ("multiple-choice", "fill-blank", "sentence"):
        quiz_type = "multiple-choice"

    quiz = await generate_quiz(db, user.id, quiz_type)

    return templates.TemplateResponse(
        request=request,
        name="vocabulary_quiz.html",
        context={
            "quiz": quiz,
            "quiz_type": quiz_type,
            "quiz_types": [
                {"value": "multiple-choice", "label": "选择题"},
                {"value": "fill-blank", "label": "填空题"},
                {"value": "sentence", "label": "造句练习"},
            ],
        },
    )


@router.post("/quiz/check", response_class=HTMLResponse)
async def check_quiz_answer(
    request: Request,
    user_id: int = Form(default=0),
    word_id: int = Form(default=0),
    quiz_type: str = Form(...),
    user_answer: str = Form(default=""),
    correct_answer: str = Form(default=""),
    question: str = Form(default=""),
    word: str = Form(default=""),
    explanation: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check quiz answer and show result."""
    is_correct = False

    if quiz_type == "multiple-choice":
        # user_answer is the index selected (e.g., "0", "1", etc.)
        is_correct = user_answer.strip() == correct_answer.strip()
    elif quiz_type == "fill-blank":
        is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
    elif quiz_type == "sentence":
        # For sentence writing, always mark as reviewed — no strict correct/incorrect
        is_correct = len(user_answer.strip()) >= 10

    return templates.TemplateResponse(
        request=request,
        name="vocabulary_quiz.html",
        context={
            "quiz": None,
            "quiz_type": quiz_type,
            "quiz_types": [
                {"value": "multiple-choice", "label": "选择题"},
                {"value": "fill-blank", "label": "填空题"},
                {"value": "sentence", "label": "造句练习"},
            ],
            "result": {
                "is_correct": is_correct,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "question": question,
                "word": word,
                "explanation": explanation,
            },
        },
    )


@router.get("/list", response_class=HTMLResponse)
async def vocabulary_list(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    topic: str | None = Query(default=None),
):
    """Browse all vocabulary words, optionally filtered by topic."""
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    words = await get_vocabulary_list(db, topic=topic)

    return templates.TemplateResponse(
        request=request,
        name="vocabulary_list.html",
        context={
            "words": words,
            "topics": TOPICS,
            "topic_labels": TOPIC_LABELS,
            "active_topic": topic,
        },
    )
