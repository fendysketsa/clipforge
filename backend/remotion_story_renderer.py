from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable


class RemotionRenderError(RuntimeError):
    pass


RENDERER_DIR = Path(__file__).resolve().parent / "remotion"

_MOTION_ACCENTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("amber", "gold", "warm", "sunset", "hangat", "emas"), "#F6C453"),
    (("red", "crimson", "danger", "merah", "tegang"), "#F06A6A"),
    (("green", "forest", "emerald", "hijau", "alam"), "#63C995"),
    (("violet", "purple", "magenta", "ungu", "mistis"), "#A98BFF"),
    (("blue", "cyan", "night", "biru", "malam", "dingin"), "#65B7FF"),
)
_FALLBACK_ACCENTS = ("#65B7FF", "#F6C453", "#A98BFF", "#63C995", "#F08AA5")


def _motion_accent(color_mood: str, seed: str) -> str:
    lowered = color_mood.casefold()
    for tokens, color in _MOTION_ACCENTS:
        if any(token in lowered for token in tokens):
            return color
    digest = sum(seed.encode("utf-8"))
    return _FALLBACK_ACCENTS[digest % len(_FALLBACK_ACCENTS)]


def _motion_transition(shot: Any, narrative_role: str, index: int) -> str:
    """Translate editorial intent into a small, consistent transition grammar."""
    if index == 1:
        return "aperture"
    raw = str(getattr(shot, "transition", "") or "").casefold()
    local_index = int(getattr(shot, "shot_index", 1) or 1)
    if local_index > 1 or any(token in raw for token in ("match", "action", "cut")):
        return "match_flash"
    if any(token in raw for token in ("iris", "aperture", "circle")):
        return "aperture"
    if any(token in raw for token in ("brush", "ink", "paint", "paper")):
        return "brush_wipe"
    if narrative_role == "payoff_conclusion":
        return "light_sweep"
    if narrative_role == "evidence_and_answer":
        return "split_wipe"
    return "directional_wipe"


def _motion_title_style(narrative_role: str) -> str:
    return {
        "cold_open": "impact",
        "evidence_and_answer": "proof",
        "payoff_conclusion": "resolve",
    }.get(narrative_role, "editorial")


def _hypit_text(value: str) -> str:
    """Escape prose while retaining Hypit's semantic Script Surface."""
    return html.escape(" ".join(value.split()), quote=False).replace("@", r"\@")


def write_hypit_script(storyboard: Any, output_path: Path) -> Path:
    """Export the generated narration as a prose-first Hypit SVML Script."""
    segments: list[str] = []
    for index, scene in enumerate(storyboard.scenes, start=1):
        narration = _hypit_text(str(scene.narration))
        if not narration:
            continue
        segment = f"scene_{index:02d}"
        segments.append(
            f"    <{segment}>\n      <NARRATOR> {narration}\n    </{segment}>"
        )
    if not segments:
        raise RemotionRenderError("Naskah Hypit tidak memiliki narasi scene yang dapat dirender.")
    source = (
        '<?svml using="@hypit/markup@1"?>\n'
        "<svml>\n"
        '  <import from="@hypit/script@1"/>\n'
        '  <script id="story">\n'
        + "\n\n".join(segments)
        + "\n  </script>\n"
        "</svml>\n"
    )
    output_path.write_text(source, encoding="utf-8")
    return output_path


def validate_hypit_script(source_path: Path) -> None:
    """Validate generated narrative through the installed Hypit 0.3 CLI."""
    cli = RENDERER_DIR / "node_modules" / ".bin" / "hypit"
    if not cli.is_file():
        raise RemotionRenderError(
            "CLI Hypit belum terpasang. Rebuild backend agar naskah SVML dapat divalidasi."
        )
    with tempfile.TemporaryDirectory(
        prefix=".clipforge-hypit-check-",
        dir=str(RENDERER_DIR),
    ) as temp_value:
        project_dir = Path(temp_value)
        (project_dir / "package.json").write_text(
            json.dumps(
                {
                    "name": "clipforge-hypit-validation",
                    "private": True,
                    "type": "module",
                    "hypit": {"project": True},
                }
            ),
            encoding="utf-8",
        )
        validation_source = project_dir / "story.svml"
        shutil.copy2(source_path, validation_source)
        completed = subprocess.run(
            [
                str(cli),
                "check",
                str(validation_source),
                "--project",
                str(project_dir),
                "--color",
                "never",
            ],
            cwd=str(RENDERER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "validasi Hypit gagal").strip()
        raise RemotionRenderError(f"Naskah Hypit tidak valid: {detail[-1600:]}")


def _link_asset(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _browser_executable() -> str:
    configured = os.environ.get("REMOTION_BROWSER_EXECUTABLE", "").strip()
    if configured and Path(configured).is_file():
        return configured
    candidates: Iterable[Path] = (
        *Path("/root/.cache/ms-playwright").glob("chromium-*/chrome-linux/chrome"),
        *Path("/root/.cache/ms-playwright").glob("chromium_headless_shell-*/chrome-linux/headless_shell"),
        *Path("/ms-playwright").glob("chromium-*/chrome-linux/chrome"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for command in ("chromium", "chromium-browser", "google-chrome"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return ""


def render_story_with_remotion(
    *,
    storyboard: Any,
    shots: list[Any],
    assets: list[Path],
    work_dir: Path,
    scene_dir: Path,
    output_path: Path,
    width: int,
    height: int,
    duration: float,
    transition_seconds: float,
    video_quality: str,
    burn_subtitles: bool,
    progress: Callable[[int, str, str], None] | None = None,
) -> tuple[Path, Path]:
    if len(shots) != len(assets):
        raise RemotionRenderError("Jumlah shot dan aset Remotion tidak sama.")
    node = shutil.which("node")
    render_script = RENDERER_DIR / "render.mjs"
    if not node or not render_script.is_file():
        raise RemotionRenderError(
            "Runtime Remotion belum terpasang di backend. Rebuild container ClipForge diperlukan."
        )
    if not (RENDERER_DIR / "node_modules" / "remotion").exists():
        raise RemotionRenderError(
            "Dependensi Remotion belum terpasang. Jalankan npm ci di backend/remotion lalu rebuild backend."
        )

    hypit_path = write_hypit_script(storyboard, work_dir / "story.hypit.svml")
    validate_hypit_script(hypit_path)
    public_dir = scene_dir / "remotion_public"
    asset_dir = public_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    cursor = 0.0
    manifest_shots: list[dict[str, Any]] = []
    scenes_by_index = {
        int(scene.index): scene for scene in storyboard.scenes
    }
    for index, (shot, asset) in enumerate(zip(shots, assets), start=1):
        if not asset.is_file():
            raise RemotionRenderError(f"Aset visual Remotion tidak ditemukan: {asset}")
        suffix = asset.suffix.lower() or ".bin"
        asset_name = f"shot_{index:03d}{suffix}"
        _link_asset(asset, asset_dir / asset_name)
        next_cursor = (
            cursor + float(shot.duration) - transition_seconds
            if index < len(shots)
            else duration
        )
        effective_duration = max(1 / 30, next_cursor - cursor)
        scene_index = int(getattr(shot, "scene_index", index) or index)
        source_scene = scenes_by_index.get(scene_index)
        narrative_role = str(
            getattr(source_scene, "narrative_role", "development") or "development"
        )
        accent_color = _motion_accent(
            str(getattr(shot, "color_mood", "") or ""),
            f"{index}|{getattr(shot, 'title', '')}|{narrative_role}",
        )
        manifest_shots.append(
            {
                "id": f"shot-{index:03d}",
                "start": round(cursor, 6),
                "duration": round(effective_duration, 6),
                "asset": asset_name,
                "kind": "video" if suffix in {".mp4", ".mov", ".webm", ".mkv"} else "image",
                "cameraMotion": str(shot.camera_motion or "push_in"),
                "framing": str(shot.framing or "medium"),
                "subjectPlacement": str(
                    getattr(shot, "subject_placement", "center") or "center"
                ),
                "cameraAngle": str(
                    getattr(shot, "camera_angle", "eye_level") or "eye_level"
                ),
                "onScreenText": str(shot.on_screen_text or shot.title or "").strip()[:120],
                "narration": str(shot.narration or "").strip(),
                "colorMood": str(shot.color_mood or "").strip(),
                "narrativeRole": narrative_role,
                "motionDesign": {
                    "transition": _motion_transition(shot, narrative_role, index),
                    "accentColor": accent_color,
                    "titleStyle": _motion_title_style(narrative_role),
                    "intensity": 1.12 if narrative_role == "cold_open" else 0.88
                    if narrative_role == "payoff_conclusion" else 1.0,
                },
            }
        )
        cursor = next_cursor

    # AnimateScene owns a measured duration, not a mutable start field.  Derive
    # starts from the authoritative allocated durations so the Remotion
    # manifest cannot drift from TTS timing (and does not depend on test-only
    # attributes that are absent in production).
    scene_cursor = 0.0
    manifest_scenes: list[dict[str, Any]] = []
    for scene in storyboard.scenes:
        scene_duration = max(1 / 30, float(scene.duration))
        manifest_scenes.append(
            {
                "id": f"scene-{scene.index:03d}",
                "start": round(scene_cursor, 6),
                "duration": round(scene_duration, 6),
                "narration": str(scene.narration or "").strip(),
                "role": str(scene.narrative_role or "").strip(),
            }
        )
        scene_cursor += scene_duration
    manifest = {
        "schema": "clipforge-remotion-story-v1",
        "hypit": {
            "scriptSurface": "@hypit/script@1",
            "source": hypit_path.name,
            "timingModel": "semantic-scenes-projected-to-measured-tts",
            "validatedByCli": True,
        },
        "publicDir": str(public_dir.resolve()),
        "composition": {
            "width": width,
            "height": height,
            "fps": 30,
            "durationSeconds": round(duration, 6),
            "shots": manifest_shots,
            "scenes": manifest_scenes,
            "watermark": "@ryuundy",
            "captionsEnabled": burn_subtitles,
            "motionDesign": {
                "deterministic": True,
                "timelineSource": "measured-tts",
                "transitionGrammar": [
                    "aperture",
                    "directional_wipe",
                    "split_wipe",
                    "match_flash",
                    "light_sweep",
                    "brush_wipe",
                ],
                "kineticTypography": True,
                "safeAreaPercent": 7,
            },
        },
    }
    manifest_path = work_dir / "remotion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    env = os.environ.copy()
    browser = _browser_executable()
    if browser:
        env["REMOTION_BROWSER_EXECUTABLE"] = browser
    env["REMOTION_CRF"] = {
        "standard": "19",
        "high": "16",
        "max": "14",
    }.get(video_quality, "16")
    env.setdefault("REMOTION_CONCURRENCY", "25%")
    if progress:
        progress(82, "render", "Remotion merakit kamera, animasi, overlay, dan caption")
    completed = subprocess.run(
        [node, str(render_script), str(manifest_path), str(output_path)],
        cwd=str(RENDERER_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=max(300, int(os.environ.get("LONG_ANIMATE_REMOTION_TIMEOUT_SECONDS", "7200"))),
        check=False,
    )
    if completed.returncode != 0 or not output_path.is_file():
        detail = (completed.stderr or completed.stdout or "Remotion tidak menghasilkan video").strip()
        raise RemotionRenderError(f"Render Remotion gagal: {detail[-2000:]}")
    return output_path, manifest_path
