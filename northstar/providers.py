from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .config import settings
from .schemas import ProviderConfig


class ProviderError(RuntimeError):
    pass


BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434",
}


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    async def _post(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        return await self._request("POST", url, payload, headers)

    async def _request(
        self, method: str, url: str, payload: dict | None = None, headers: dict | None = None
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.request(method, url, headers=headers, json=payload)
        except httpx.HTTPError:
            raise ProviderError(
                "Provider connection failed or timed out; check the endpoint"
            ) from None
        if response.status_code >= 400:
            # Provider error bodies may echo authorization headers or other secrets.
            raise ProviderError(
                f"Provider HTTP {response.status_code}; check credentials, model, and endpoint"
            )
        try:
            data = response.json()
        except ValueError:
            raise ProviderError("Provider returned an invalid JSON response") from None
        if not isinstance(data, dict):
            raise ProviderError("Provider response must be a JSON object")
        key = self.config.api_key.get_secret_value() if self.config.api_key else settings.api_key
        if key:
            # Prevent an endpoint echoing a supplied key into persisted model output.
            data = json.loads(json.dumps(data).replace(json.dumps(key)[1:-1], "[REDACTED]"))
        return data

    @property
    def base_url(self) -> str:
        return (
            self.config.base_url or BASE_URLS.get(self.config.provider, settings.default_base_url)
        ).rstrip("/")

    def headers(self) -> dict:
        key = self.config.api_key.get_secret_value() if self.config.api_key else settings.api_key
        headers = {"Content-Type": "application/json"}
        if self.config.provider == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
            if key:
                headers["x-api-key"] = key
        elif key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    async def list_models(self) -> list[dict]:
        path = "/api/tags" if self.config.provider == "ollama" else "/models"
        data = await self._request("GET", self.base_url + path, headers=self.headers())
        items = data.get("models" if self.config.provider == "ollama" else "data", [])
        if not isinstance(items, list):
            raise ProviderError(
                "Provider returned an invalid model list; enter the model ID manually"
            )
        return [
            {
                "id": item.get("id") or item.get("name"),
                "name": item.get("display_name") or item.get("name") or item.get("id"),
            }
            for item in items
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ]

    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise ProviderError("Model response must contain text")
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start : end + 1])
                except ValueError:
                    raise ProviderError("Model did not return valid JSON") from None
            else:
                raise ProviderError("Model did not return valid JSON") from None
        if not isinstance(result, dict):
            raise ProviderError("Model must return a JSON object")
        return result


class OpenAICompatibleProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        base_url = self.base_url
        key = self.config.api_key.get_secret_value() if self.config.api_key else settings.api_key
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        data = await self._post(f"{base_url}/chat/completions", payload, headers)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected OpenAI-compatible response structure") from exc
        return self._extract_json(text)


class OpenAIResponsesProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "store": False,
            "instructions": system,
            "input": user,
        }
        if self.config.json_mode:
            payload["text"] = {"format": {"type": "json_object"}}
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.reasoning_effort:
            payload["reasoning"] = {"effort": self.config.reasoning_effort}
        data = await self._post(self.base_url + "/responses", payload, self.headers())
        if data.get("status") in {"failed", "incomplete"}:
            raise ProviderError("OpenAI response was incomplete; retry or choose a different model")
        try:
            text = "".join(
                part["text"]
                for item in data["output"]
                if item.get("type") == "message"
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
        except (KeyError, TypeError):
            raise ProviderError("Unexpected OpenAI Responses structure") from None
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
            "system": system,
            "messages": [{"role": "user", "content": user + "\nReturn JSON only."}],
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        data = await self._post(f"{base_url}/messages", payload, headers)
        try:
            text = "".join(part["text"] for part in data["content"] if part.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ProviderError("Unexpected Anthropic response structure") from exc
        return self._extract_json(text)


class OllamaProvider(LLMProvider):
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        base_url = (self.config.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": self.config.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.config.temperature is not None:
            payload["options"] = {"temperature": self.config.temperature}
        data = await self._post(f"{base_url}/api/chat", payload)
        try:
            text = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("Unexpected Ollama response structure") from exc
        return self._extract_json(text)


def build_provider(config: ProviderConfig) -> LLMProvider:
    if config.provider == "openai":
        return OpenAIResponsesProvider(config)
    if config.provider in {"openai_compatible", "openrouter"}:
        return OpenAICompatibleProvider(config)
    if config.provider == "anthropic":
        return AnthropicProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    raise ValueError(f"Unsupported provider: {config.provider}")
