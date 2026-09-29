import asyncio

import app.agent.llm as llm_module
from app.agent.llm import LLMClient


def run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.request_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.request_json = json
        return FakeResponse({
            "model": "example/free-model",
            "choices": [{"message": {"content": '{"location":"Bangalore","ro_capacity":"500 LPH"}'}}],
        })


def test_openrouter_json_adapter_parses_structured_response(monkeypatch):
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", FakeAsyncClient)
    client = LLMClient()
    client.provider = "openrouter"
    client.api_key = "test-key-not-real"
    client.model = "openrouter/free"
    result = run(client.generate_json("extract"))
    assert result == {"location": "Bangalore", "ro_capacity": "500 LPH"}
    assert client.last_model == "example/free-model"


def test_openrouter_client_disabled_without_key():
    client = LLMClient()
    client.provider = "openrouter"
    client.api_key = None
    assert client.enabled is False
    status = run(client.test_connection())
    assert status["ok"] is False
    assert status["configured"] is False
    assert "OPENROUTER_API_KEY" in status["message"]
