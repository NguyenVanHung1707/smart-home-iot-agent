from types import SimpleNamespace

from src.services import llm


def test_get_llm_disables_client_retries(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(llm, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            model_name="test-model",
            openai_api_key="",
            llama_base_url="http://llama:8080/v1",
            llm_temperature=0.1,
            llm_timeout_seconds=12.0,
            llm_max_retries=0,
        ),
    )

    llm.get_llm()

    assert captured["max_retries"] == 0
