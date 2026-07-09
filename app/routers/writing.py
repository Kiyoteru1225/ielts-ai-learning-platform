from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.writing_scorer import score_essay

import os

router = APIRouter(prefix="/writing", tags=["writing"])

# 使用绝对路径避免运行时 CWD 不一致
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def format_result_markdown(result: dict) -> str:
    """Convert the scoring result dict into a formatted Markdown string."""
    lines = []

    scores = result.get("scores", {})
    overall = result.get("overall", "N/A")

    lines.append("## 📊 评分结果")
    lines.append("")
    lines.append("| 评分标准 | 分数 |")
    lines.append("|----------|------|")
    criteria_labels = {
        "task_response": "任务完成度 (TR)",
        "coherence_cohesion": "连贯与衔接 (CC)",
        "lexical_resource": "词汇资源 (LR)",
        "grammatical_range": "语法范围与准确性 (GRA)",
    }
    for key, label in criteria_labels.items():
        band = scores.get(key, "N/A")
        lines.append(f"| {label} | {band} |")

    lines.append("")
    lines.append(f"**总分：{overall}**")
    lines.append("")

    strengths = result.get("strengths", [])
    if strengths:
        lines.append("## ✅ 优点")
        lines.append("")
        for s in strengths:
            lines.append(f"- {s}")
        lines.append("")

    weaknesses = result.get("weaknesses", [])
    if weaknesses:
        lines.append("## ⚠️ 不足")
        lines.append("")
        for w in weaknesses:
            lines.append(f"- {w}")
        lines.append("")

    suggestions = result.get("suggestions", [])
    if suggestions:
        lines.append("## 💡 改进建议")
        lines.append("")
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)


@router.get("/", response_class=HTMLResponse)
async def writing_page(request: Request):
    return templates.TemplateResponse(request=request, name="writing.html")


@router.post("/score", response_class=HTMLResponse)
async def score_essay_endpoint(
    request: Request,
    essay: str = Form(...),
    task_type: str = Form(default="task2"),
):
    if not essay or len(essay.strip()) < 50:
        return templates.TemplateResponse(
            request=request,
            name="writing.html",
            context={"error": "作文内容太短，请至少输入 50 个字符。"},
        )

    result = score_essay(essay.strip(), task_type)

    if "error" in result:
        error_messages = {
            "essay_text must be a non-empty string": "作文内容不能为空。",
            "essay_text must be at least 50 characters": "作文内容太短，请至少输入 50 个字符。",
            "task_type must be 'task1' or 'task2'": "任务类型无效，请选择 Task 1 或 Task 2。",
            "DEEPSEEK_API_KEY environment variable is not set": "API 密钥未配置，请联系管理员。",
            "API request timed out after 60 seconds": "评分请求超时，请稍后重试。",
            "An unexpected error occurred during essay scoring": "评分过程中发生未知错误，请稍后重试。",
        }
        user_message = error_messages.get(
            result["error"],
            f"评分失败：{result['error']}",
        )
        return templates.TemplateResponse(
            request=request,
            name="writing.html",
            context={"error": user_message},
        )

    result_md = format_result_markdown(result)
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "result_md": result_md,
            "original_essay": essay,
            "task_type": task_type,
        },
    )
