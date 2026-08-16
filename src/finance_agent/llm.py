"""Thin chat wrapper for Ollama, OpenAI, Agnes AI, and Google."""

from __future__ import annotations

import base64

import httpx
from openai import OpenAI

from finance_agent.config import (
    AGNES_BASE_URL,
    AGNES_MODEL,
    GOOGLE_MODELS,
    OLLAMA_HOST,
    OPENAI_EFFORT,
    OPENAI_MODELS,
    env,
)


def list_ollama_models() -> list[str]:
    try:
        resp = httpx.get(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=2.0)
        resp.raise_for_status()
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        return sorted(n for n in names if n)
    except httpx.HTTPError:
        return []


def models_for(provider: str) -> list[str]:
    if provider == "Ollama":
        return list_ollama_models()
    if provider == "OpenAI":
        return list(OPENAI_MODELS)
    if provider == "Agnes AI":
        return [AGNES_MODEL]
    if provider == "Google":
        return list(GOOGLE_MODELS)
    return []


def missing_key(provider: str) -> str | None:
    if provider == "OpenAI" and not env("OPENAI_API_KEY"):
        return "OPENAI_API_KEY"
    if provider == "Agnes AI" and not env("AGNES_API_KEY"):
        return "AGNES_API_KEY"
    if provider == "Google" and not env("GOOGLE_API_KEY"):
        return "GOOGLE_API_KEY"
    return None


def _image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def complete(
    provider: str,
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    image: bytes | None = None,
) -> str:
    from finance_agent.db import is_local_only

    if is_local_only() and provider != "Ollama":
        msg = "Local-first mode blocks cloud providers."
        raise PermissionError(msg)
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if image:
        mime = _image_mime(image)
        b64 = base64.standard_b64encode(image).decode("ascii")
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        )
    else:
        messages.append({"role": "user", "content": prompt})

    if provider == "Google":
        return _google(model, messages)
    return _openai_compat(provider, model, messages)


def _openai_compat(provider: str, model: str, messages: list[dict]) -> str:
    if provider == "OpenAI":
        client = OpenAI(api_key=env("OPENAI_API_KEY") or None, base_url=env("OPENAI_BASE_URL") or None)
        extra = {"reasoning_effort": OPENAI_EFFORT}
    elif provider == "Agnes AI":
        client = OpenAI(api_key=env("AGNES_API_KEY") or None, base_url=AGNES_BASE_URL)
        extra = {}
    elif provider == "Ollama":
        client = OpenAI(api_key="ollama", base_url=f"{OLLAMA_HOST.rstrip('/')}/v1")
        extra = {}
    else:
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    kwargs: dict = {"model": model, "messages": messages, **extra}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        if extra:
            kwargs.pop("reasoning_effort", None)
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    return (resp.choices[0].message.content or "").strip()


def _google(model: str, messages: list[dict]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env("GOOGLE_API_KEY") or None)
    parts: list = []
    system = None
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
            continue
        content = msg["content"]
        if isinstance(content, str):
            parts.append(content)
        else:
            for item in content:
                if item.get("type") == "text":
                    parts.append(item["text"])
                elif item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    header, raw = url.split(",", 1)
                    mime = "image/png"
                    if header.startswith("data:") and ";base64" in header:
                        mime = header[5:].split(";", 1)[0] or mime
                    parts.append(
                        types.Part.from_bytes(data=base64.standard_b64decode(raw), mime_type=mime)
                    )
    config = types.GenerateContentConfig(system_instruction=system) if system else None
    resp = client.models.generate_content(model=model, contents=parts, config=config)
    return (resp.text or "").strip()
