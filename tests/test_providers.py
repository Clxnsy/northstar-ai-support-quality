import asyncio
import json

import httpx
import pytest

from northstar.providers import LLMProvider, ProviderError, build_provider
from northstar.schemas import ProviderConfig


@pytest.mark.parametrize(
    "provider,path,envelope",
    [
        (
            "openai_compatible",
            "/v1/chat/completions",
            {"choices": [{"message": {"content": '{"ok":true}'}}]},
        ),
        ("anthropic", "/v1/messages", {"content": [{"type": "text", "text": '{"ok":true}'}]}),
        ("ollama", "/api/chat", {"message": {"content": '{"ok":true}'}}),
    ],
)
def test_provider_wire_contract(provider, path, envelope, monkeypatch):
    original_client = httpx.AsyncClient

    def handle(req):
        assert req.url.path == path
        body = json.loads(req.content)
        assert body["model"] == "test-model"
        if provider == "anthropic":
            assert req.headers["x-api-key"] == "ephemeral-test-key"
        elif provider == "openai_compatible":
            assert req.headers["authorization"] == "Bearer ephemeral-test-key"
        else:
            assert body["stream"] is False
        return httpx.Response(200, json=envelope)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    config = ProviderConfig(provider=provider, model="test-model", api_key="ephemeral-test-key")
    assert asyncio.run(build_provider(config).complete_json("system", "user")) == {"ok": True}


def test_provider_errors_do_not_expose_body(monkeypatch):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: httpx.Response(401, text="secret-key-123"))
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs)
    )
    provider = build_provider(ProviderConfig(model="x", api_key="secret-key-123"))
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.complete_json("system", "user"))
    assert "secret-key-123" not in str(error.value)


@pytest.mark.parametrize("text", ["[]", "null", "bad {x}", None])
def test_invalid_model_json_is_controlled(text):
    with pytest.raises(ProviderError):
        LLMProvider._extract_json(text)


def test_fenced_json():
    assert LLMProvider._extract_json('```json\n{"ok": true}\n```') == {"ok": True}


@pytest.mark.parametrize(
    "provider,path", [("openai", "/v1/responses"), ("openrouter", "/api/v1/chat/completions")]
)
def test_current_model_endpoints_and_optional_temperature(provider, path, monkeypatch):
    original_client = httpx.AsyncClient

    def handler(req):
        assert req.url.path == path
        payload = json.loads(req.content)
        assert "temperature" not in payload
        assert payload["model"] == "current-model-id"
        if provider == "openai":
            assert payload["store"] is False
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": '{"ok":true}'}],
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert asyncio.run(
        build_provider(ProviderConfig(provider=provider, model="current-model-id")).complete_json(
            "JSON", "JSON"
        )
    ) == {"ok": True}


@pytest.mark.parametrize(
    "provider,path",
    [
        ("openai", "/v1/models"),
        ("openrouter", "/api/v1/models"),
        ("anthropic", "/v1/models"),
        ("ollama", "/api/tags"),
    ],
)
def test_live_catalog_contract(provider, path, monkeypatch):
    original_client = httpx.AsyncClient

    def handler(req):
        assert req.method == "GET"
        assert req.url.path == path
        return httpx.Response(
            200,
            json={"models": [{"name": "local-model"}]}
            if provider == "ollama"
            else {"data": [{"id": "latest-model", "name": "Latest"}]},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    models = asyncio.run(
        build_provider(ProviderConfig(provider=provider, model="discovery")).list_models()
    )
    assert models[0]["id"] == ("local-model" if provider == "ollama" else "latest-model")
