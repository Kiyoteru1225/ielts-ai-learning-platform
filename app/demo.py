"""Gradio web UI for the IELTS essay scoring prototype (Phase 0)."""

import gradio as gr

from app.writing_scorer import score_essay


def format_result(result: dict) -> str:
    """Format a scoring result dict into a Markdown string for display."""

    if "error" in result:
        return f"## ⚠️ 批改出错\n\n**{result['error']}**"

    scores = result.get("scores", {})
    overall = result.get("overall", "N/A")

    md = "## 📊 评分结果\n\n"
    md += "| 评分维度 | 分数 |\n| --- | --- |\n"
    md += f"| Task Response (任务回应) | {scores.get('task_response', 'N/A')} |\n"
    md += f"| Coherence & Cohesion (连贯与衔接) | {scores.get('coherence_cohesion', 'N/A')} |\n"
    md += f"| Lexical Resource (词汇资源) | {scores.get('lexical_resource', 'N/A')} |\n"
    md += f"| Grammatical Range & Accuracy (语法范围与准确性) | {scores.get('grammatical_range', 'N/A')} |\n"
    md += f"| **Overall Band** | **{overall}** |\n"

    strengths = result.get("strengths", [])
    if strengths:
        md += "\n## 💪 优点\n\n"
        for s in strengths:
            md += f"- {s}\n"

    weaknesses = result.get("weaknesses", [])
    if weaknesses:
        md += "\n## 🔍 不足之处\n\n"
        for w in weaknesses:
            md += f"- {w}\n"

    suggestions = result.get("suggestions", [])
    if suggestions:
        md += "\n## 💡 改进建议\n\n"
        for s in suggestions:
            md += f"- {s}\n"

    return md


def handle_score(essay: str, task_type: str) -> str:
    """Callback: score the essay and return formatted Markdown."""
    if not essay or not essay.strip():
        return "## ⚠️ 请输入作文内容"
    result = score_essay(essay.strip(), task_type)
    return format_result(result)


with gr.Blocks(title="IELTS 写作批改") as demo:

    gr.Markdown("# 📝 雅思写作 AI 批改 — Phase 0 原型")

    with gr.Row(equal_height=False):
        with gr.Column(scale=1):
            essay_input = gr.Textbox(
                label="请输入你的雅思作文",
                placeholder="在此粘贴或输入你的雅思作文...",
                lines=15,
            )
            task_type = gr.Radio(
                choices=[
                    ("Task 2 (议论文 / 讨论文)", "task2"),
                    ("Task 1 (图表 / 数据描述)", "task1"),
                ],
                value="task2",
                label="作文类型",
            )
            submit_btn = gr.Button("🚀 提交批改", variant="primary")

        with gr.Column(scale=1):
            output = gr.Markdown(
                value="👈 在左侧输入作文，点击提交即可获取 AI 批改结果。",
                show_label=False,
            )

    submit_btn.click(
        fn=handle_score,
        inputs=[essay_input, task_type],
        outputs=output,
    )

    gr.Markdown("---\n*📌 Phase 0 原型阶段 — 使用 DeepSeek API，仅供内部测试，评分仅供参考。*")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
