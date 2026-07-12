from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class AIConfig:
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout: float = 120.0


def resolve_base_url(base_url: str) -> str:
    # Inside Docker, localhost points at the container, not the host. Rewrite to
    # host.docker.internal so a user-supplied localhost endpoint still works.
    base_url = normalize_openai_base_url(base_url)
    if os.environ.get("IN_DOCKER") != "1":
        return base_url
    return base_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")


def candidate_base_urls(base_url: str) -> list[str]:
    base = normalize_openai_base_url(base_url).strip().rstrip("/")
    if not base:
        return []

    candidates: list[str] = []
    for item in (
        resolve_base_url(base),
        base,
        base.replace("localhost", "127.0.0.1"),
        base.replace("127.0.0.1", "localhost"),
        base.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal"),
    ):
        cleaned = item.strip().rstrip("/")
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return candidates


def normalize_openai_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.port in {11434, 1234, 1337, 8080, 20128} and not parsed.path.rstrip("/").endswith("/v1"):
        return base + "/v1"
    return base


def chat_completion(config: AIConfig, messages: list[dict]) -> str:
    body = json.dumps(
        {
            "model": config.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    last_error: Exception | None = None
    for base_url in candidate_base_urls(config.base_url):
        url = base_url + "/chat/completions"
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        if config.api_key:
            request.add_header("Authorization", f"Bearer {config.api_key}")

        try:
            with urllib.request.urlopen(request, timeout=config.timeout) as response:
                raw = response.read().decode("utf-8")
            return _content_from_response(raw)
        except Exception as exc:
            last_error = exc
            continue
    if _is_ollama_base_url(config.base_url):
        return _ollama_cli_chat_completion(config, messages)
    if last_error is not None:
        raise last_error
    raise ValueError("LLM base_url is not set")


def _is_ollama_base_url(base_url: str) -> bool:
    return ":11434" in base_url


def _messages_to_prompt(messages: list[dict]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").upper()
        content = str(message.get("content") or "").strip()
        if content:
            parts.append(f"{role}:\n{content}")
    parts.append("ASSISTANT:\nReturn only the requested strict JSON.")
    return "\n\n".join(parts)


def _ollama_cli_chat_completion(config: AIConfig, messages: list[dict]) -> str:
    if not config.model:
        raise ValueError("Ollama model is not set")
    result = subprocess.run(
        ["ollama", "run", config.model],
        input=_messages_to_prompt(messages),
        capture_output=True,
        text=True,
        timeout=config.timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Ollama CLI failed: {detail or result.returncode}")
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", result.stdout).strip()


def _content_from_response(raw: str) -> str:
    raw = raw.strip()
    payload: dict | None = None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Some OpenAI-compatible servers always reply as text/event-stream:
        # one or more `data: {json}` lines terminated by `data: [DONE]`.
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:") :].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                payload = json.loads(chunk)
            except json.JSONDecodeError:
                continue
    if not isinstance(payload, dict):
        raise ValueError("LLM response was not valid JSON")
    return payload["choices"][0]["message"]["content"]


def _loads_lenient(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Models sometimes emit raw (unescaped) newlines/tabs inside string
        # values, which is invalid JSON. Escape control chars within strings.
        repaired: list[str] = []
        in_string = False
        escaped = False
        for char in text:
            if in_string:
                if escaped:
                    repaired.append(char)
                    escaped = False
                    continue
                if char == "\\":
                    repaired.append(char)
                    escaped = True
                    continue
                if char == '"':
                    in_string = False
                    repaired.append(char)
                    continue
                if char == "\n":
                    repaired.append("\\n")
                    continue
                if char == "\r":
                    repaired.append("\\r")
                    continue
                if char == "\t":
                    repaired.append("\\t")
                    continue
                repaired.append(char)
            else:
                if char == '"':
                    in_string = True
                repaired.append(char)
        return json.loads("".join(repaired))


def extract_json(raw: str) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"```[a-zA-Z]*\n?", "", raw).replace("```", "").strip()
    start = raw.find("{")
    if start == -1:
        return _loads_lenient(raw)

    depth = 0
    for idx in range(start, len(raw)):
        char = raw[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return _loads_lenient(raw[start : idx + 1])
    return _loads_lenient(raw[start:])
