import json
import urllib.error

import pytest

import llm
from llm import (
    AIConfig,
    LLMUnavailableError,
    _content_from_response,
    chat_completion,
    extract_json,
    normalize_openai_base_url,
    resolve_base_url,
)


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_think_tags():
    raw = '<think>reasoning {ignored}</think>\n{"clips": [{"id": 0}]}'
    assert extract_json(raw) == {"clips": [{"id": 0}]}


def test_extract_json_strips_code_fence():
    raw = '```json\n{"ok": true}\n```'
    assert extract_json(raw) == {"ok": True}


def test_extract_json_trailing_data():
    # Object followed by extra junk (e.g. SSE "data: [DONE]" leftovers).
    raw = '{"caption": "hi"}\nsome trailing text'
    assert extract_json(raw) == {"caption": "hi"}


def test_extract_json_repairs_literal_newline_in_string():
    # Models sometimes emit raw newlines inside string values (invalid JSON).
    raw = '{"caption": "line1\nline2", "tags": ["#a"]}'
    parsed = extract_json(raw)
    assert parsed["caption"] == "line1\nline2"
    assert parsed["tags"] == ["#a"]


def test_extract_json_repairs_tab_and_cr():
    raw = '{"v": "a\tb\rc"}'
    assert extract_json(raw) == {"v": "a\tb\rc"}


def test_content_from_response_plain_json():
    body = json.dumps({"choices": [{"message": {"content": "hello"}}]})
    assert _content_from_response(body) == "hello"


def test_content_from_response_sse_stream():
    inner = json.dumps({"choices": [{"message": {"content": "streamed"}}]})
    body = f"data: {inner}\ndata: [DONE]\n\n"
    assert _content_from_response(body) == "streamed"


def test_content_from_response_invalid_raises():
    with pytest.raises(ValueError):
        _content_from_response("not json at all")


def test_resolve_base_url_no_docker(monkeypatch):
    monkeypatch.delenv("IN_DOCKER", raising=False)
    assert resolve_base_url("http://localhost:20128/v1") == "http://localhost:20128/v1"


def test_resolve_base_url_in_docker(monkeypatch):
    monkeypatch.setenv("IN_DOCKER", "1")
    assert resolve_base_url("http://localhost:20128/v1") == "http://host.docker.internal:20128/v1"
    assert resolve_base_url("http://127.0.0.1:20128/v1") == "http://host.docker.internal:20128/v1"


def test_normalize_openai_base_url_adds_v1_for_local_providers():
    assert normalize_openai_base_url("http://localhost:11434") == "http://localhost:11434/v1"
    assert normalize_openai_base_url("http://localhost:1234/v1") == "http://localhost:1234/v1"


def test_offline_ollama_without_cli_uses_unavailable_error(monkeypatch):
    monkeypatch.setattr(
        llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.URLError("[Errno 111] Connection refused")
        ),
    )
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        llm.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Ollama CLI must not run when executable is missing")
        ),
    )

    with pytest.raises(LLMUnavailableError, match="fallback lokal digunakan"):
        chat_completion(
            AIConfig(
                enabled=True,
                base_url="http://127.0.0.1:11434/v1",
                model="demo",
            ),
            [{"role": "user", "content": "test"}],
        )


def test_reachable_ollama_model_error_is_not_reported_as_offline(monkeypatch):
    model_error = urllib.error.HTTPError(
        "http://127.0.0.1:11434/v1/chat/completions",
        402,
        "subscription required",
        {},
        None,
    )
    monkeypatch.setattr(
        llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(model_error),
    )
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)

    with pytest.raises(urllib.error.HTTPError) as raised:
        chat_completion(
            AIConfig(
                enabled=True,
                base_url="http://127.0.0.1:11434/v1",
                model="cloud-model",
            ),
            [{"role": "user", "content": "test"}],
        )

    assert raised.value.code == 402
