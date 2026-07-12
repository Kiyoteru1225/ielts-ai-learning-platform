import json
import os
import re

from dotenv import load_dotenv
from openai import APIError, APITimeoutError, OpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

PASSAGE_GENERATION_PROMPT = """You are an experienced IELTS examiner. Generate an IELTS Academic Reading practice set on the given topic.

1. Write an academic passage (700-900 words) in authentic IELTS Academic style: dense but clear, with topic sentences, supporting evidence, and academic vocabulary.
2. Generate exactly 10 questions covering four IELTS Reading question types:
   - 3 True/False/Not Given questions
   - 3 Multiple Choice questions (each with 4 options A-D)
   - 2 Sentence Completion questions (fill in the blank with NO MORE THAN TWO WORDS)
   - 2 Matching Headings questions (match paragraph headings to paragraphs)

For Matching Headings, list 5 heading options (A-E) and ask which heading fits which of 2 specified paragraphs.

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{
  "passage": "<full passage text, 700-900 words>",
  "questions": [
    {
      "id": 1,
      "type": "true_false_not_given",
      "question_text": "<the statement to judge>",
      "correct_answer": "<True | False | Not Given>"
    }
  ]
}

For true_false_not_given type, correct_answer must be exactly "True", "False", or "Not Given".
For multiple_choice type, include an "options" key with a list of 4 objects: [{"key": "A", "text": "..."}, ...], and correct_answer is the correct key letter like "B".
For sentence_completion type, question_text ends with a blank (e.g. "The experiment showed that ___ can affect memory."), correct_answer is the exact one or two words.
For matching_headings type, question_text gives the paragraph reference (e.g. "Paragraph A"), include an "options" key with 5 heading choices [{"key": "A", "text": "..."}, ...], and correct_answer is the correct key letter like "C"."""

CHECK_ANSWERS_PROMPT = """You are an IELTS examiner. Compare the student's answers with the correct answers for an IELTS Reading practice set.

For each question, determine if the answer is correct. Be lenient with minor variations:
- For True/False/Not Given: accept "T", "True", "F", "False", "NG", "Not Given" interchangeably.
- For Multiple Choice and Matching Headings: the letter must match exactly.
- For Sentence Completion: accept minor spelling variations or alternative phrasings that convey the same meaning.

Return ONLY a single JSON object with no additional text, no markdown formatting, and no code fences. The JSON must use exactly this structure:

{
  "score": <number of correct answers>,
  "total": <total number of questions>,
  "results": [
    {
      "question_id": 1,
      "is_correct": true,
      "user_answer": "<what the student wrote>",
      "correct_answer": "<the correct answer>",
      "explanation": "<brief explanation in Chinese, 1-2 sentences>"
    }
  ]
}"""


def _strip_markdown_code_blocks(text: str) -> str:
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def generate_passage(topic: str) -> dict:
    """Generate an IELTS Academic Reading passage and 10 questions using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    if not topic or not isinstance(topic, str) or not topic.strip():
        topic = "general academic interest"

    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=120,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": PASSAGE_GENERATION_PROMPT},
                {
                    "role": "user",
                    "content": f'Generate an IELTS Academic Reading passage and questions on the topic: "{topic}". Make the passage 700-900 words, authentic academic style.',
                },
            ],
            temperature=0.7,
            max_tokens=4000,
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
                "error": "Failed to parse passage response as JSON",
                "raw_response": raw_content[:500],
            }

    except APITimeoutError:
        return {"error": "API request timed out after 120 seconds"}
    except APIError as e:
        return {"error": f"API error: {str(e)}"}
    except Exception:
        return {"error": "An unexpected error occurred during passage generation"}


def check_answers(passage: str, questions: list, user_answers: dict) -> dict:
    """Check user answers against correct answers using DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY environment variable is not set"}

    if not questions:
        return {"error": "questions must be a non-empty list"}

    # Build a simple answer comparison for the AI
    questions_text = []
    for q in questions:
        qid = q.get("id", "")
        qtype = q.get("type", "")
        qtext = q.get("question_text", "")
        correct = q.get("correct_answer", "")
        user = user_answers.get(str(qid), "")
        options = ""
        if q.get("options"):
            options = " | Options: " + ", ".join(
                f'{o.get("key","")}. {o.get("text","")}' for o in q["options"]
            )
        questions_text.append(
            f"Q{qid} [{qtype}]: {qtext}{options}\nCorrect: {correct}\nStudent: {user}"
        )

    comparison = "\n\n".join(questions_text)

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
