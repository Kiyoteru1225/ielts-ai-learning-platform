import json
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.models import SpeakingRecord, User
from app.services.speaking_service import generate_topic, score_speaking_response

router = APIRouter(prefix="/speaking", tags=["speaking"])

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def _build_topic_card_text(topic: dict) -> str:
    """Build a plain-text topic card string from the topic dict for storage."""
    lines = [topic.get("topic_title", "IELTS Speaking Part 2")]
    lines.append("")
    for point in topic.get("bullet_points", []):
        lines.append(f"- {point}")
    instruction = topic.get("instruction", "")
    if instruction:
        lines.append("")
        lines.append(instruction)
    return "\n".join(lines)


@router.get("/", response_class=HTMLResponse)
async def speaking_page(request: Request):
    """Show the speaking practice page with an AI-generated topic card."""
    topic = generate_topic()
    return templates.TemplateResponse(
        request=request,
        name="speaking.html",
        context={"topic": topic},
    )


@router.post("/score", response_class=HTMLResponse)
async def score_speaking_endpoint(
    request: Request,
    response_text: str = Form(...),
    topic_card: str = Form(...),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a speaking response for AI scoring."""
    if not response_text or len(response_text.strip()) < 30:
        topic = generate_topic()
        return templates.TemplateResponse(
            request=request,
            name="speaking.html",
            context={
                "error": "回答内容太短，请至少输入 30 个字符。",
                "topic": topic,
            },
        )

    result = score_speaking_response(response_text.strip(), topic_card)

    if "error" in result:
        error_messages = {
            "response_text must be a non-empty string": "回答内容不能为空。",
            "response_text must be at least 30 characters": "回答内容太短，请至少输入 30 个字符。",
            "DEEPSEEK_API_KEY environment variable is not set": "API 密钥未配置，请联系管理员。",
            "API request timed out after 60 seconds": "评分请求超时，请稍后重试。",
            "An unexpected error occurred during speaking scoring": "评分过程中发生未知错误，请稍后重试。",
        }
        user_message = error_messages.get(
            result["error"],
            f"评分失败：{result['error']}",
        )
        topic = generate_topic()
        return templates.TemplateResponse(
            request=request,
            name="speaking.html",
            context={"error": user_message, "topic": topic},
        )

    # Save to history if user is logged in
    if user is not None:
        scores = result.get("scores", {})
        record = SpeakingRecord(
            user_id=user.id,
            topic_card=topic_card,
            user_response=response_text.strip(),
            score_fluency=scores.get("fluency"),
            score_lexical=scores.get("lexical"),
            score_grammar=scores.get("grammar"),
            score_pronunciation=scores.get("pronunciation"),
            overall=result.get("overall"),
            feedback_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(record)
        await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="speaking_result.html",
        context={
            "scores": result.get("scores", {}),
            "overall": result.get("overall"),
            "strengths": result.get("strengths", []),
            "weaknesses": result.get("weaknesses", []),
            "suggestions": result.get("suggestions", []),
            "original_response": response_text,
            "topic_card": topic_card,
            "response_preview": response_text[:120]
            + ("..." if len(response_text) > 120 else ""),
        },
    )


@router.get("/history", response_class=HTMLResponse)
async def speaking_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show the speaking practice history for the logged-in user."""
    result = await db.execute(
        select(SpeakingRecord)
        .where(SpeakingRecord.user_id == current_user.id)
        .order_by(SpeakingRecord.created_at.desc())
        .limit(20)
    )
    records = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="speaking_history.html",
        context={"records": records},
    )
