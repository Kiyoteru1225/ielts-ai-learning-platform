import json
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.models import ReadingRecord, User
from app.services.reading_service import check_answers, generate_passage

router = APIRouter(prefix="/reading", tags=["reading"])

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

READING_TOPICS = [
    "Technology and Innovation",
    "Climate Change and Environment",
    "Health and Medicine",
    "Education and Learning",
    "History and Archaeology",
    "Psychology and Behavior",
    "Economics and Business",
    "Space Exploration",
    "Art and Culture",
    "Urban Development",
]


@router.get("/", response_class=HTMLResponse)
async def reading_page(request: Request):
    """Show the reading topic picker page."""
    return templates.TemplateResponse(
        request=request,
        name="reading.html",
        context={"topics": READING_TOPICS},
    )


@router.post("/practice", response_class=HTMLResponse)
async def reading_practice(
    request: Request,
    topic: str = Form(...),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI reading passage and questions, then show the practice page."""
    if not topic or not topic.strip():
        return templates.TemplateResponse(
            request=request,
            name="reading.html",
            context={
                "error": "Please select a topic.",
                "topics": READING_TOPICS,
            },
        )

    result = generate_passage(topic.strip())

    if "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="reading.html",
            context={
                "error": f"生成题目失败：{result['error']}",
                "topics": READING_TOPICS,
            },
        )

    passage = result.get("passage", "")
    questions = result.get("questions", [])

    return templates.TemplateResponse(
        request=request,
        name="reading_practice.html",
        context={
            "topic": topic.strip(),
            "passage": passage,
            "questions": questions,
            "questions_json": json.dumps(questions, ensure_ascii=False),
        },
    )


@router.post("/check", response_class=HTMLResponse)
async def reading_check(
    request: Request,
    topic: str = Form(...),
    passage: str = Form(...),
    questions_json: str = Form(...),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Check submitted reading answers and show results."""
    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError:
        return templates.TemplateResponse(
            request=request,
            name="reading.html",
            context={
                "error": "题目数据异常，请重新选择话题。",
                "topics": READING_TOPICS,
            },
        )

    # Collect user answers from form data
    user_answers: dict[str, str] = {}
    form_data = await request.form()
    for key, value in form_data.items():
        if key.startswith("q_"):
            qid = key[2:]  # strip "q_" prefix
            val = str(value).strip()
            if val:
                user_answers[qid] = val

    result = check_answers(passage, questions, user_answers)

    if "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="reading_practice.html",
            context={
                "error": f"批改失败：{result['error']}",
                "topic": topic,
                "passage": passage,
                "questions": questions,
                "questions_json": questions_json,
            },
        )

    score = result.get("score", 0)
    total = result.get("total", len(questions))
    results = result.get("results", [])

    # Save to history if user is logged in
    if user is not None:
        record = ReadingRecord(
            user_id=user.id,
            topic=topic,
            passage=passage,
            questions_json=questions_json,
            user_answers_json=json.dumps(user_answers, ensure_ascii=False),
            score=score,
            total=total,
            feedback_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(record)
        await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="reading_result.html",
        context={
            "topic": topic,
            "score": score,
            "total": total,
            "results": results,
            "questions": questions,
            "user_answers": user_answers,
            "passage": passage,
        },
    )


@router.get("/history", response_class=HTMLResponse)
async def reading_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show the reading practice history for the logged-in user."""
    result = await db.execute(
        select(ReadingRecord)
        .where(ReadingRecord.user_id == current_user.id)
        .order_by(ReadingRecord.created_at.desc())
        .limit(20)
    )
    records = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="reading_history.html",
        context={"records": records},
    )
