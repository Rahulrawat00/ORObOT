import os
from typing import Optional

import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
OPENAI_EMBEDDING_MODEL = (
    os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    or "text-embedding-3-small"
)

_HTTP = requests.Session()


def cloud_llm_configured() -> bool:
    return bool(OPENAI_API_KEY)


def llm_backend_name() -> str:
    return "openai-compatible" if cloud_llm_configured() else "ollama"


def _cloud_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


def generate_text(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 256,
    ollama_model: str = "llama3",
    ollama_options: Optional[dict] = None,
    timeout: tuple = (8, 90),
) -> str:
    if cloud_llm_configured():
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        res = _HTTP.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=_cloud_headers(),
            json={
                "model": OPENAI_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        res.raise_for_status()
        data = res.json()
        choices = data.get("choices") or []
        message = ((choices[0] or {}).get("message") or {}) if choices else {}
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            content = "".join(text_parts)
        return (content or "").strip()

    res = _HTTP.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": ollama_options or {},
        },
        timeout=timeout,
    )
    res.raise_for_status()
    data = res.json()
    return (data.get("response") or "").strip()


def generate_embedding(text: str, *, ollama_model: str = "nomic-embed-text") -> list[float]:
    if cloud_llm_configured():
        res = _HTTP.post(
            f"{OPENAI_BASE_URL}/embeddings",
            headers=_cloud_headers(),
            json={
                "model": OPENAI_EMBEDDING_MODEL,
                "input": text,
            },
            timeout=(8, 60),
        )
        res.raise_for_status()
        data = res.json()
        items = data.get("data") or []
        embedding = (items[0] or {}).get("embedding") if items else None
        if isinstance(embedding, list) and embedding:
            return embedding
        raise ValueError("Embedding response did not include a usable vector.")

    res = _HTTP.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": ollama_model, "prompt": text},
        timeout=(5, 60),
    )
    res.raise_for_status()
    data = res.json()
    embedding = data.get("embedding")
    if isinstance(embedding, list) and embedding:
        return embedding
    raise ValueError("Embedding response did not include a usable vector.")
