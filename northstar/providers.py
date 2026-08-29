from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .config import settings
from .schemas import ProviderConfig


class ProviderError(RuntimeError):
    pass


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise ProviderError("Model did not return valid JSON")


class OpenAICompatibleProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        base_url = (self.config.base_url or settings.default_base_url).rstrip("/")
        key = self.config.api_key.get_secret_value() if self.config.api_key else settings.api_key
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            raise ProviderError(f"Provider HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected OpenAI-compatible response: {data}") from exc
        return self._extract_json(text)


class AnthropicProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        base_url = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
        key = self.config.api_key.get_secret_value() if self.config.api_key else settings.api_key
        if not key:
            raise ProviderError("Anthropic provider requires an API key")
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": 4096,
            "temperature": self.config.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user + "\nReturn JSON only."}],
        }
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(f"{base_url}/messages", headers=headers, json=payload)
        if response.status_code >= 400:
            raise ProviderError(f"Provider HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        try:
            text = "".join(part["text"] for part in data["content"] if part.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"Unexpected Anthropic response: {data}") from exc
        return self._extract_json(text)


class OllamaProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        base_url = (self.config.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": self.config.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.config.temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
        if response.status_code >= 400:
            raise ProviderError(f"Ollama HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        try:
            text = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"Unexpected Ollama response: {data}") from exc
        return self._extract_json(text)


def build_provider(config: ProviderConfig) -> LLMProvider:
    if config.provider == "openai_compatible":
        return OpenAICompatibleProvider(config)
    if config.provider == "anthropic":
        return AnthropicProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    raise ValueError(f"Unsupported provider: {config.provider}")
