import json
import re

import httpx
from app.core.config import settings

async def complete(model: str, messages: list[dict]) -> str:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com", "X-Title": "ai-chatbot-builder"}
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(f"{settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"] or ""


async def stream_complete(model: str, messages: list[dict]):
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com", "X-Title": "ai-chatbot-builder"}
    payload = {"model": model, "messages": messages, "temperature": 0.2, "stream": True}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
        async with client.stream("POST", f"{settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload) as response:
            if response.status_code != 200:
                await response.aread()
                raise RuntimeError(f"LLM request failed: HTTP {response.status_code}")
            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                if delta:
                    yield delta


async def expand_query(model: str, question: str) -> list[str]:
    try:
        count = max(1, min(settings.multi_query_count, 5))
        prompt = (
            f"Rewrite the user question into {count} alternative search queries that would retrieve "
            f"the same information from a knowledge base. Include likely keywords and synonyms. "
            f"Keep the user's language. Respond with ONLY a JSON array of strings.\n\nQuestion: {question}"
        )
        text = await complete(model, [{"role": "user", "content": prompt}])
        match = re.search(r"\[.*\]", text, re.S)
        if not match:
            return []
        variants = json.loads(match.group(0))
        if not isinstance(variants, list):
            return []
        cleaned = [v.strip() for v in variants if isinstance(v, str) and v.strip()]
        return cleaned[:count]
    except Exception:
        return []
