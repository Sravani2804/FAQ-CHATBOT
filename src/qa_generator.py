"""
Q&A Generator — uses Azure OpenAI (gpt-4o-mini) to extract Q&A pairs from text chunks.
"""

import json
import re
import uuid
from openai import AzureOpenAI
from src.config import settings
from src.document_processor import Chunk

_client = AzureOpenAI(
    api_key=settings.prompt_subscription_key,
    api_version=settings.api_version,
    azure_endpoint=settings.prompt_generation_endpoint,
)

GPT_DEPLOYMENT = "gpt-4o-mini"

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


def _call_gpt(messages: list, temperature: float = 1.0) -> str:
    response = _client.chat.completions.create(
        model=GPT_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    return json.loads(match.group())


def generate_qa_from_chunk(chunk: Chunk) -> list[dict]:
    prompt = QA_PROMPT.format(chunk=chunk.text)
    raw = _call_gpt([{"role": "user", "content": prompt}])
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
