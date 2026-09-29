from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..core.config import get_settings

settings = get_settings()


class LLMClient:
    """OpenRouter REST adapter with graceful deterministic fallback.

    The default model is OpenRouter's free-model router so the take-home demo does
    not depend on one specific free model remaining available. Any provider/API
    failure returns None; the explicit agent policy continues operating.
    """

    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower().strip()
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.site_url = settings.openrouter_site_url
        self.app_name = settings.openrouter_app_name
        self.last_error: str | None = None
        self.last_model: str | None = None

    @property
    def enabled(self) -> bool:
        return self.provider == "openrouter" and bool(self.api_key)

    @property
    def provider_name(self) -> str:
        return "OpenRouter" if self.provider == "openrouter" else self.provider

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    async def _chat(self, prompt: str, *, json_mode: bool, max_tokens: int, temperature: float) -> str | None:
        self.last_error = None
        self.last_model = None
        if not self.enabled:
            return None

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise assistant inside a production-oriented AI calling agent. Follow the requested output format exactly.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
            data = response.json()
            self.last_model = data.get("model")
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    str(part.get("text", "")) if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content).strip()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return None

    async def generate_json(self, prompt: str) -> dict[str, Any] | None:
        text = await self._chat(prompt, json_mode=True, max_tokens=500, temperature=0.1)
        if not text:
            return None
        try:
            parsed = json.loads(strip_code_fence(text))
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            self.last_error = f"JSONDecodeError: {exc}"[:500]
            return None

    async def generate_text(self, prompt: str) -> str | None:
        return await self._chat(prompt, json_mode=False, max_tokens=220, temperature=0.25)

    async def test_connection(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "provider": self.provider_name,
                "model": self.model,
                "configured": False,
                "message": "OPENROUTER_API_KEY is not configured. The deterministic fallback still works, but add the key to demonstrate GenAI.",
            }
        text = await self._chat(
            'Reply with exactly the word "ready".',
            json_mode=False,
            max_tokens=8,
            temperature=0.0,
        )
        return {
            "ok": bool(text),
            "provider": self.provider_name,
            "model": self.model,
            "resolved_model": self.last_model,
            "configured": True,
            "message": text or self.last_error or "Unknown provider error",
        }


GeminiClient = LLMClient


def strip_code_fence(value: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.I)
