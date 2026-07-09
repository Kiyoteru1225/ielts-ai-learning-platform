import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI, APIError, APITimeoutError

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

IELTS_SYSTEM_PROMPT = """You are an experienced IELTS examiner. Score the following essay according to the official IELTS Writing band descriptors across four criteria:

1. Task Response (TR) — how well the essay addresses the prompt, develops a position, and supports ideas.
2. Coherence and Cohesion (CC) — logical organisation, paragraphing, and use of cohesive devices.
3. Lexical Resource (LR) — range, accuracy, and appropriacy of vocabulary.
4. Grammatical Range and Accuracy (GRA) — variety and correctness of sentence structures.

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{
  "scores": {
    "task_response": <band score 0-9 in 0.5 increments>,
    "coherence_cohesion": <band score 0-9 in 0.5 increments>,
    "lexical_resource": <band score 0-9 in 0.5 increments>,
    "grammatical_range": <band score 0-9 in 0.5 increments>
  },
  "overall": <overall band score, average of the four rounded to nearest 0.5>,
  "strengths": ["<specific strength 1>", "<specific strength 2>"],
  "weaknesses": ["<specific weakness 1>", "<specific weakness 2>"],
  "suggestions": ["<actionable suggestion 1>", "<actionable suggestion 2>"]
}"""


def _validate_input(essay_text: str, task_type: str) -> str | None:
    if not essay_text or not isinstance(essay_text, str):
        return "essay_text must be a non-empty string"
    if len(essay_text.strip()) < 50:
        return "essay_text must be at least 50 characters"
    if task_type not in ("task1", "task2"):
        return "task_type must be 'task1' or 'task2'"
    return None


def _strip_markdown_code_blocks(text: str) -> str:
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def score_essay(essay_text: str, task_type: str) -> dict:
    validation_error = _validate_input(essay_text, task_type)
    if validation_error:
        return {"error": validation_error}

    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    task_label = "Task 1 (diagram/data description)" if task_type == "task1" else "Task 2 (opinion/discussion essay)"

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": IELTS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Essay type: {task_label}\n\nEssay text:\n{essay_text}",
                },
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            return {"error": "API returned empty response"}

        cleaned = _strip_markdown_code_blocks(raw_content)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse scoring response as JSON",
                "raw_response": raw_content[:500],
            }

        return result

    except APITimeoutError:
        return {"error": "API request timed out after 60 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during essay scoring"}
