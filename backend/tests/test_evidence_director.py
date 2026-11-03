import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import evidence_director as evidence


def sample():
    clip = SimpleNamespace(start=1005.05, end=1040.021, text=(
        "Admin punya masalah sama Indonesia sepertinya. "
        "Menuliskan berita paragraf pertama itu motifnya apa? "
        "Dari Instagram klubnya Emil Audero, klub itu memberikan penghormatan."))
    rows = [
        SimpleNamespace(start=943.13, end=944.9, text="Ditulis oleh Astro Awani."),
        SimpleNamespace(start=1005.13, end=1007.5, text="Admin punya masalah sama Indonesia sepertinya."),
        SimpleNamespace(start=1010.41, end=1013.45, text="Menuliskan berita paragraf pertama itu motifnya apa?"),
        SimpleNamespace(start=1025.02, end=1028.24, text="Dari Instagram klubnya Emil Audero,"),
    ]
    return clip, rows


def checked_record(root, beat):
    text = "Kutipan dari paragraf yang diperiksa. Ini konteks lengkapnya."
    snapshot = root / "source.txt"
    snapshot.write_text(text)
    return {
        "kind": beat["kind"], "utterance": beat["utterance"],
        "review_status": "source_checked", "relationship": "exact_reference",
        "source_url": "https://example.org/article", "publisher": "Media asli",
        "published_at": "2026-11-01", "checked_at": "2026-11-03", "reviewed_by": "editor",
        "excerpt": "Kutipan dari paragraf yang diperiksa.", "snapshot_text": snapshot.name,
        "snapshot_text_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
    }


def test_reference_timing_uses_full_context_without_inserting_previous_speech():
    clip, rows = sample()
    plan = evidence.build_evidence_plan(clip, rows[1:], source_segments=rows, research=False)
    assert [b["kind"] for b in plan["beats"]] == ["allegation", "written_source", "social_source"]
    assert plan["beats"][1]["start"] == 5.36
    assert "Astro Awani" in plan["beats"][1]["query"]
    assert plan["manual_context_review_required"] is True
    assert all(not b["source"] for b in plan["beats"])
    assert plan["facts_verified"] is False


def test_search_hits_never_resolve_a_claim(monkeypatch):
    clip, rows = sample()
    queries = []
    def search(query):
        queries.append(query)
        return {"status": "candidates_only", "candidates": [{"url": "https://example.org/article"}]}
    monkeypatch.setattr(evidence, "search_source_leads", search)
    plan = evidence.build_evidence_plan(clip, rows, research=True)
    assert len(queries) == 2
    assert plan["manual_context_review_required"]
    assert all(b["status"] != "source_checked" for b in plan["beats"])


@pytest.mark.parametrize("mutation", ["related", "wrong_quote", "changed_snapshot", "traversal", "wrong_utterance", "motive"])
def test_unrelated_or_invalid_records_cannot_become_proof(tmp_path, mutation):
    clip, rows = sample()
    plan = evidence.build_evidence_plan(clip, rows, research=False)
    beat = plan["beats"][0 if mutation == "motive" else 1]
    record = checked_record(tmp_path, beat)
    if mutation == "related": record["relationship"] = "related_article"
    if mutation == "wrong_quote": record["excerpt"] = "Kalimat yang tidak ada di sumber."
    if mutation == "changed_snapshot": (tmp_path / "source.txt").write_text("Berubah")
    if mutation == "traversal": record["snapshot_text"] = "../outside.txt"
    if mutation == "wrong_utterance": record["utterance"] = "Ucapan dari klip lain."
    manifest = tmp_path / "evidence.json"
    manifest.write_text(json.dumps({"references": {beat["id"]: record}}))
    result = evidence.build_evidence_plan(clip, rows, manifest_path=manifest, research=False)
    assert all(b["status"] != "source_checked" for b in result["beats"])


def test_checked_source_still_does_not_prove_motive_or_other_references(tmp_path):
    clip, rows = sample()
    beat = evidence.build_evidence_plan(clip, rows, research=False)["beats"][1]
    record = checked_record(tmp_path, beat)
    manifest = tmp_path / "evidence.json"
    manifest.write_text(json.dumps({"references": {beat["id"]: record}}))
    result = evidence.build_evidence_plan(clip, rows, manifest_path=manifest, research=False)
    assert result["beats"][1]["status"] == "source_checked"
    assert result["beats"][0]["status"] == "opinion_only"
    assert result["manual_context_review_required"]
    assert result["facts_verified"] is False


def test_network_failure_keeps_visible_unresolved_status(monkeypatch):
    def unavailable(*args, **kwargs): raise OSError("offline")
    monkeypatch.setattr(evidence.urllib.request, "urlopen", unavailable)
    result = evidence.search_source_leads("artikel yang dimaksud")
    assert result["status"] == "search_unavailable"
    assert result["facts_verified"] is False


@pytest.mark.parametrize("with_image", [False, True])
def test_real_ffmpeg_compiles_panels_with_literal_untrusted_text(tmp_path, with_image):
    # Exercise the actual filter graph, including image branching and timestamp
    # enables. Source punctuation must be read as text, never filter syntax.
    clip, rows = sample()
    plan = evidence.build_evidence_plan(clip, rows, research=False)
    beat = plan["beats"][1]
    record = checked_record(tmp_path, beat)
    if with_image:
        image = tmp_path / "source.png"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=0x124b49:s=700x300", "-frames:v", "1", "-threads", "1",
                        str(image)], check=True, capture_output=True, timeout=10)
        record.update(image=image.name, image_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    manifest = tmp_path / "evidence.json"
    manifest.write_text(json.dumps({"references": {beat["id"]: record}}))
    plan = evidence.build_evidence_plan(clip, rows, manifest_path=manifest, research=False)
    plan["beats"][0]["utterance"] = "Lihat 'kutipan': 100% [ini]; movie=rahasia, $HOME"
    vf = evidence.evidence_overlay_filter(plan, tmp_path, "test")
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-filter_complex_threads", "1", "-filter_threads", "1",
        "-f", "lavfi", "-i", "color=black:s=1080x1920:r=1:d=12",
        "-vf", vf, "-f", "null", "-",
    ], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "movie=rahasia" not in vf
    assert plan["overlays_rendered"]


def test_malformed_manifest_falls_back_to_warning(tmp_path):
    clip, rows = sample()
    manifest = tmp_path / "evidence.json"
    manifest.write_text('{"references": []}')
    plan = evidence.build_evidence_plan(clip, rows, manifest_path=manifest, research=False)
    assert plan["manifest_error"] == "invalid_manifest"
    assert plan["manual_context_review_required"]


def test_no_external_reference_does_not_add_warnings():
    clip = SimpleNamespace(start=0, end=25, text="Tarik napas, lalu lanjutkan perjalanan.")
    rows = [SimpleNamespace(start=0, end=8, text=clip.text)]
    assert not evidence.build_evidence_plan(clip, rows, research=False)["enabled"]
