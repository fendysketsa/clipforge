import importlib.util
import json
from pathlib import Path


GATEWAY_PATH = Path(__file__).resolve().parents[2] / "scripts" / "local-image-gateway.py"
SPEC = importlib.util.spec_from_file_location("local_image_gateway", GATEWAY_PATH)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


def _strengthened(prompt: str) -> dict[str, object]:
    payload = json.dumps({"prompt": prompt, "negative_prompt": "blurry"}).encode()
    return json.loads(gateway.GatewayHandler._strengthen_generation_request(payload))


def test_object_gateway_prompt_never_seeds_hands_or_people():
    result = _strengthened(
        "Visible moment: Tower crane lifts steel. VISIBLE OBJECT SCOPE: architecture and machinery."
    )

    positive = str(result["prompt"]).casefold()
    negative = str(result["negative_prompt"]).casefold()
    assert "hand" not in positive
    assert "person" not in positive
    assert "human" not in positive
    assert "hand" in negative
    assert "human" in negative


def test_people_gateway_prompt_demands_clean_portrait_detail():
    result = _strengthened("Visible moment: Seorang anak sedang makan bakso di warung.")

    positive = str(result["prompt"]).casefold()
    negative = str(result["negative_prompt"]).casefold()
    assert "strict portrait quality" in positive
    assert "clean readable face" in positive
    assert "melted face" in negative
    assert "tiny face" in negative


def test_gateway_treats_reference_edits_as_generation_requests(monkeypatch):
    handler = object.__new__(gateway.GatewayHandler)
    handler.path = "/v1/images/edits"
    forwarded = []
    monkeypatch.setattr(gateway, "release_ollama", lambda: None)
    handler._forward = lambda **kwargs: forwarded.append(kwargs)

    handler.do_POST()

    assert forwarded == [{"enhance_images": True, "strengthen_request": False}]
