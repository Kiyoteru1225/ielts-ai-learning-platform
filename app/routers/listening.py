import json
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.models import ListeningRecord, User
from app.services.listening_service import check_answers, generate_script
from app.services.tts_service import TTS_VOICES, generate_audio

router = APIRouter(prefix="/listening", tags=["listening"])

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

SCENE_TYPES = [
    {"value": "Conversation", "label": "Conversation", "desc": "Daily dialogue between two speakers on everyday topics."},
    {"value": "Lecture", "label": "Lecture", "desc": "Academic monologue on a subject such as science, history, or society."},
    {"value": "Announcement", "label": "Announcement", "desc": "Public announcement or broadcast with factual details."},
    {"value": "Travel", "label": "Travel", "desc": "Tourist guide, travel commentary, or orientation talk."},
]


@router.get("/", response_class=HTMLResponse)
async def listening_page(request: Request):
    """Show the listening scene type and voice picker page."""
    return templates.TemplateResponse(
        request=request,
        name="listening.html",
        context={
            "scene_types": SCENE_TYPES,
            "voices": TTS_VOICES,
        },
    )


@router.post("/practice", response_class=HTMLResponse)
async def listening_practice(
    request: Request,
    scene_type: str = Form(...),
    voice: str = Form(...),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI listening script, TTS audio, and show the practice page."""
    if not scene_type or not scene_type.strip():
        return templates.TemplateResponse(
            request=request,
            name="listening.html",
            context={
                "error": "Please select a scene type.",
                "scene_types": SCENE_TYPES,
                "voices": TTS_VOICES,
            },
        )

    if voice not in TTS_VOICES:
        voice = "en-US-JennyNeural"

    result = generate_script(scene_type.strip())

    if "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="listening.html",
            context={
                "error": f"生成题目失败：{result['error']}",
                "scene_types": SCENE_TYPES,
                "voices": TTS_VOICES,
            },
        )

    script = result.get("script", "")
    questions = result.get("questions", [])
    answers = result.get("answers", [])

    # Generate audio asynchronously
    audio_path = ""
    tts_error = None
    try:
        audio_path = await generate_audio(script, voice)
    except Exception as e:
        tts_error = str(e)

    return templates.TemplateResponse(
        request=request,
        name="listening_practice.html",
        context={
            "scene_type": scene_type.strip(),
            "voice": voice,
            "voice_label": TTS_VOICES.get(voice, voice),
            "script": script,
            "questions": questions,
            "questions_json": json.dumps(questions, ensure_ascii=False),
            "answers_json": json.dumps(answers, ensure_ascii=False),
           "audio_path": audio_path,
            "tts_error": tts_error,
       },
    )


@router.post("/check", response_class=HTMLResponse)
async def listening_check(
    request: Request,
    scene_type: str = Form(...),
    voice: str = Form(...),
    script: str = Form(...),
    questions_json: str = Form(...),
    answers_json: str = Form(...),
    audio_path: str = Form(...),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Check submitted gap-fill answers and show results."""
    try:
        questions = json.loads(questions_json)
        answers = json.loads(answers_json)
    except json.JSONDecodeError:
        return templates.TemplateResponse(
            request=request,
            name="listening.html",
            context={
                "error": "题目数据异常，请重新选择场景。",
                "scene_types": SCENE_TYPES,
                "voices": TTS_VOICES,
            },
        )

    user_answers: dict[str, str] = {}
    form_data = await request.form()
    for key, value in form_data.items():
        if key.startswith("q_"):
            qid = key[2:]
            val = str(value).strip()
            if val:
                user_answers[qid] = val

    result = check_answers(script, questions, answers, user_answers)

    if "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="listening_practice.html",
            context={
                "error": f"批改失败：{result['error']}",
                "scene_type": scene_type,
                "voice": voice,
                "voice_label": TTS_VOICES.get(voice, voice),
                "script": script,
                "questions": questions,
                "questions_json": questions_json,
                "answers_json": answers_json,
                "audio_path": audio_path,
            },
        )

    score = result.get("score", 0)
    total = result.get("total", len(questions))
    results = result.get("results", [])

    if user is not None:
        record = ListeningRecord(
            user_id=user.id,
            scene_type=scene_type,
            voice=voice,
            script=script,
            questions_json=questions_json,
            user_answers_json=json.dumps(user_answers, ensure_ascii=False),
            score=score,
            total=total,
            audio_path=audio_path,
            feedback_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(record)
        await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="listening_result.html",
        context={
            "scene_type": scene_type,
            "voice_label": TTS_VOICES.get(voice, voice),
            "score": score,
            "total": total,
            "results": results,
            "questions": questions,
            "user_answers": user_answers,
            "script": script,
            "audio_path": audio_path,
        },
    )


@router.get("/history", response_class=HTMLResponse)
async def listening_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show the listening practice history for the logged-in user."""
    result = await db.execute(
        select(ListeningRecord)
        .where(ListeningRecord.user_id == current_user.id)
        .order_by(ListeningRecord.created_at.desc())
        .limit(20)
    )
    records = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="listening_history.html",
        context={
            "records": records,
            "voices": TTS_VOICES,
        },
    )
