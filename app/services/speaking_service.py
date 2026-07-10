import json
import os
import re

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, OpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

TOPIC_GENERATION_PROMPT = """You are an experienced IELTS examiner. Generate a random IELTS Speaking Part 2 cue card topic.

The topic should be realistic and match authentic IELTS exam questions. Include:
- A clear topic title (e.g., "Describe a memorable trip you have taken")
- 3-4 bullet points that guide the candidate on what to talk about (what, when, where, why, how, explain, etc.)
- A concluding instruction like "You should say:" or similar

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{
  "topic_title": "<the cue card topic title>",
  "bullet_points": ["<point 1>", "<point 2>", "<point 3>", "<point 4>"],
  "instruction": "<concluding instruction>"
}"""

SPEAKING_SCORING_PROMPT = """You are an experienced IELTS examiner. Score the following IELTS Speaking Part 2 response according to the official IELTS Speaking band descriptors across four criteria:

1. Fluency & Coherence (FC) — ability to speak at length without noticeable effort, use of discourse markers, coherent organization of ideas.
2. Lexical Resource (LR) — range of vocabulary, use of less common and idiomatic items, effective paraphrasing.
3. Grammatical Range & Accuracy (GRA) — use of a range of structures, frequency of error-free sentences.
4. Pronunciation (P) — would the response be easy to understand if spoken aloud? Are individual sounds, word stress, and intonation appropriate?

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{
  "scores": {
    "fluency": <band score 0-9 in 0.5 increments>,
    "lexical": <band score 0-9 in 0.5 increments>,
    "grammar": <band score 0-9 in 0.5 increments>,
    "pronunciation": <band score 0-9 in 0.5 increments>
  },
  "overall": <overall band score, average of the four rounded to nearest 0.5>,
  "strengths": ["<specific strength 1>", "<specific strength 2>"],
  "weaknesses": ["<specific weakness 1>", "<specific weakness 2>"],
  "suggestions": ["<actionable suggestion 1>", "<actionable suggestion 2>"]
}"""


def _strip_markdown_code_blocks(text: str) -> str:
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_topic() -> dict:
    """Generate a random IELTS Speaking Part 2 cue card topic using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return {
            "error": "DEEPSEEK_API_KEY environment variable is not set",
            "topic_title": "Describe a memorable trip you have taken",
            "bullet_points": [
                "where you went",
                "who you went with",
                "what you did there",
                "and explain why it was memorable"
            ],
            "instruction": "You should say:",
        }

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": TOPIC_GENERATION_PROMPT},
                {
                    "role": "user",
                    "content": "Generate a random IELTS Speaking Part 2 cue card topic. Vary the topic type — it could be about a person, place, object, event, experience, or activity.",
                },
            ],
            temperature=0.9,
            max_tokens=800,
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
                "error": "Failed to parse topic response",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "API request timed out after 60 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during topic generation"}


def score_speaking_response(response_text: str, topic_card: str) -> dict:
    """Score an IELTS Speaking Part 2 response using DeepSeek."""
    if not response_text or not isinstance(response_text, str):
        return {"error": "response_text must be a non-empty string"}
    if len(response_text.strip()) < 30:
        return {"error": "response_text must be at least 30 characters"}

    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SPEAKING_SCORING_PROMPT},
                {
                    "role": "user",
                    "content": f"Topic:\n{topic_card}\n\nCandidate's response:\n{response_text}",
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
            return result
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse scoring response as JSON",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "API request timed out after 60 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during speaking scoring"}
