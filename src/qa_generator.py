"""
Q&A Generator — uses Google Gemini to extract Q&A pairs from text chunks.
"""

import json
import re
import uuid
from google import genai
from google.genai import types
from src.config import settings
from src.document_processor import Chunk

_client = genai.Client(api_key=settings.gemini_api_key)

GEMINI_MODEL = "gemini-2.5-flash"

QA_PROMPT = """You are an expert at reading documents and creating FAQ question-answer pairs.

Given the text chunk below, generate between 2 and 5 clear, specific question-answer pairs.

Rules:
- Questions must be answerable directly from the text — do NOT make up information
- Questions should be natural, as a user would ask them
- Answers should be concise (1-4 sentences) and self-contained
- Skip questions that are too vague or duplicate

Return your response as a JSON object with exactly this structure:
{{
  "qa_pairs": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ]
}}

Text chunk:
\"\"\"{chunk}\"\"\"
"""


def _call_gemini(prompt: str, temperature: float = 1.0) -> str:
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    return response.text.strip()


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    return json.loads(match.group())


def generate_qa_from_chunk(chunk: Chunk) -> list[dict]:
    prompt = QA_PROMPT.format(chunk=chunk.text)
    raw = _call_gemini(prompt)
    parsed = _extract_json(raw)
    qa_list = parsed.get("qa_pairs", [])

    results = []
    for item in qa_list:
        if not isinstance(item, dict):
            continue
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()
        if q and a:
            results.append({
                "faq_id": f"faq_{uuid.uuid4().hex[:8]}",
                "question": q,
                "answer": a,
                "source": chunk.source,
                "chunk_index": chunk.index,
            })
    return results


def generate_qa_from_document(
    chunks: list[Chunk],
    progress_callback=None,
) -> list[dict]:
    all_qa: list[dict] = []
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        try:
            qa_pairs = generate_qa_from_chunk(chunk)
            all_qa.extend(qa_pairs)
        except Exception as e:
            print(f"[qa_generator] Chunk {i} failed: {e}")

        if progress_callback:
            progress_callback(i + 1, total)

    return all_qa
