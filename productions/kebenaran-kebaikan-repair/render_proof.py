"""Generate one local breakfast keyframe and a short review clip; preserve master."""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "backend"))
import long_animate as film

HERE = Path(__file__).resolve().parent
SOURCE = PROJECT / "backend/outputs/36a225c2e1c9493bac98e12d760f9bc2/judul-kebenaran-kebaikan"
MASTER = SOURCE / "clips/long_animate_kebenaran-kebaikan.mp4"
START, END = 35.522, 49.652


def stamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    whole, fraction = divmod(millis, 1000)
    minutes, second = divmod(whole, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02}:{minute:02}:{second:02},{fraction:03}"


def seconds(value: str) -> float:
    h, m, sec = value.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def main() -> None:
    plan = json.loads((SOURCE / "video_plan.json").read_text(encoding="utf-8"))
    original = plan["scenes"][3]
    visual = (
        "Two people on a morning market pavement: Dimas, a young Indonesian man in a charcoal-gray T-shirt, "
        "holds a brown takeaway breakfast packet while turning toward a 75-year-old Indonesian grandmother "
        "with two shopping bags and a wooden walking cane."
    )
    identity = "Dimas is a young Indonesian man with short black hair and a charcoal-gray T-shirt. The grandmother is 75 with a beige headscarf and taupe clothes."
    props = (
        "A takeaway breakfast packet visibly belongs to Dimas. Two shopping bags hang from the grandmother's "
        "left hand and her right hand grips a wooden cane resting on the pavement. The packet, cane, bags, "
        "market stalls, curb and road are readable together."
    )
    direction = (
        "Medium-wide eye-level side view. Dimas is on the left looking toward the grandmother on the right "
        "at the curb. He holds his breakfast packet at waist height. Morning light falls across both people."
    )
    with film.output_aspect_ratio("9:16"):
        shot = film.AnimateShot(
            index=1, scene_index=4, shot_index=1, shot_count=1, title="Dimas Membawa Sarapan",
            narration=original["narration"],
            visual_prompt=film._compose_visual_prompt(
                visual, original["narration"], "cinematic realistic documentary photograph",
                identity, "An Indonesian traditional market pavement beside the same road in the morning",
                visual_locked=True, director_direction=direction, property_direction=props,
            ),
            on_screen_text="", camera_motion="push_in", color_mood="soft morning daylight",
            duration=END - START, framing="medium_wide", subject_placement="left_third",
            director_direction=direction, property_direction=props,
        )
        prompt = film._focused_image_generation_prompt(shot)
        (HERE / "breakfast-direction.json").write_text(json.dumps({
            "source_interval": [START, END], "narration": original["narration"],
            "visible": visual, "director": direction, "properties": props, "prompt": prompt,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        image = HERE / "breakfast-corrected.png"
        if not image.exists():
            print("Generating one corrected breakfast image with the configured local service…", flush=True)
            film.require_real_image_provider()
            film.generate_shot_image_with_qa(shot, image, "cinematic realistic documentary photograph")

    subtitles = (SOURCE / "clips/long_animate_kebenaran-kebaikan.srt").read_text(encoding="utf-8")
    cues = []
    for block in re.split(r"\n\s*\n", subtitles.strip()):
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        a, b = map(seconds, lines[1].split(" --> "))
        if a < END and b > START:
            cues.append(f"{len(cues)+1}\n{stamp(max(0, a - START))} --> {stamp(min(END, b) - START)}\n" + "\n".join(lines[2:]))
    (HERE / "breakfast-caption.srt").write_text("\n\n".join(cues) + "\n", encoding="utf-8")
    frames = math.ceil((END - START) * 30)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(image),
        "-ss", str(START), "-i", str(MASTER), "-t", str(END - START),
        "-vf", f"zoompan=z='min(zoom+0.00008,1.035)':d={frames}:s=720x1280:fps=30,"
               "subtitles=breakfast-caption.srt:force_style='FontName=DejaVu Sans,FontSize=10,Alignment=2,MarginV=24,BorderStyle=3,Outline=1,Shadow=0'",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(HERE / "breakfast-review.mp4"),
    ], cwd=HERE, check=True)
    print(f"Review sample ready: {HERE / 'breakfast-review.mp4'}", flush=True)


if __name__ == "__main__":
    main()
