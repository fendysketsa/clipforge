"""Renderer-agnostic art-direction hints for editorial prompts.

Inspired by the general techniques catalogued in the optional
``docs/pulupulu-motion`` skill. This module is deliberately prompt-only:

* no artist, franchise or named character is reproduced;
* no coordinates, props, compositions or sample frames are copied;
* no rights, QC approval, publication or measurement is claimed;
* the owning renderer and all existing QC gates remain unchanged.
"""
from __future__ import annotations

import hashlib
import re

VERSION = 1
TEXT_LIMIT = 240
PALETTE_LIMIT = 6

# General techniques only. Palette values are suggestions for an art director,
# not evidence of a source licence or of a rendered result.
PROFILES = {
    "flat_primary": dict(
        label="Geometri primer",
        prompt="Flat geometric shapes with clean edges, a small primary-colour palette and generous negative space; calm, readable silhouettes.",
        palette=("#E8DCC4", "#2F6F63", "#D9813B", "#335B8E"),
        motion_hint="Shapes slide or scale on clear beats; no camera drift for its own sake.",
    ),
    "paper_cutout": dict(
        label="Kertas potong hangat",
        prompt="Layered paper cut-out shapes with soft scissor edges, gentle drop shadows and a warm muted palette; tactile, friendly, matte.",
        palette=("#F4EAD6", "#C9835F", "#6E8F6B", "#3F5148"),
        motion_hint="Paper layers settle one at a time with a short overshoot, then hold.",
    ),
    "watercolor_wash": dict(
        label="Sapuan air",
        prompt="Soft translucent watercolour washes with uneven paper edges, limited blended colour and quiet line work; gentle and legible.",
        palette=("#F6F1E3", "#86A99B", "#D2A679", "#5D6E62"),
        motion_hint="Colour bleeds and drifts slowly behind stable, readable text.",
    ),
    "ink_line": dict(
        label="Garis tinta",
        prompt="Expressive variable-width ink lines, high contrast and restrained hatching; outlines stay open so the scene never becomes a solid block.",
        palette=("#F7F3E7", "#263B35", "#B4553F", "#9AA48F"),
        motion_hint="A few confident strokes arrive first, then the rest of the scene follows.",
    ),
    "halftone_pop": dict(
        label="Pop berhati-hati",
        prompt="Bold simple shapes, a limited bright palette, thick dark outlines and a sparse halftone dot texture on one plane only.",
        palette=("#F5E9C9", "#2D3A32", "#E2B23C", "#C5594A"),
        motion_hint="One accent plane changes on the spoken beat; captions remain still.",
    ),
    "soft_flat": dict(
        label="Flat kontemporer",
        prompt="Contemporary flat illustration with unoutlined colour blocks, subtle grain and damped secondary motion; clear faces and hands.",
        palette=("#F3F0E6", "#4B8A73", "#E0A458", "#40586B"),
        motion_hint="A single responsive gesture per beat, then a steady hold.",
    ),
    "neon_grid": dict(
        label="Grid neon",
        prompt="Two-tone neon glow over a simple perspective grid on a dark field; restrained bloom, no full-frame flashing.",
        palette=("#15212A", "#54D6C0", "#E07BA6", "#E8E3CF"),
        motion_hint="The grid recedes steadily; labels stay outside the glow.",
    ),
    "pixel_blocks": dict(
        label="Blok piksel",
        prompt="Chunky pixel-grid stepping with a small fixed palette and one-pixel outlines; shapes read clearly at thumbnail size.",
        palette=("#1F2A2E", "#7BC4A4", "#F1C56B", "#E07B6A"),
        motion_hint="Motion steps at a low, deliberate frame rate; captions do not step.",
    ),
    "warm_dark": dict(
        label="Cahaya hangat",
        prompt="One warm key light, deep but detailed shadows and a restrained dust haze; faces stay readable and never disappear into black.",
        palette=("#202A26", "#E3C187", "#9C6A45", "#D9D2B6"),
        motion_hint="Light shifts slowly while the subject holds still.",
    ),
    "mosaic_tiles": dict(
        label="Mozaik sederhana",
        prompt="Small matte tiles tessellated along simple shapes, warm stone palette and clear mortar gaps; no fine facial detail at small scale.",
        palette=("#E7D9B8", "#A8674C", "#4F7368", "#3D4A44"),
        motion_hint="Tiles settle into place from one edge; the pattern stays still afterwards.",
    ),
}


def validate_profile(raw):
    if not isinstance(raw, dict):
        raise ValueError('Profil gaya wajib berupa objek.')
    for key in ('label', 'prompt', 'motion_hint'):
        text = raw.get(key)
        if not isinstance(text, str) or not 3 <= len(text.strip()) <= TEXT_LIMIT:
            raise ValueError('Teks profil gaya tidak valid.')
    palette = raw.get('palette')
    if (not isinstance(palette, (list, tuple)) or not 2 <= len(palette) <= PALETTE_LIMIT
            or any(not isinstance(row, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', row) for row in palette)):
        raise ValueError('Palet gaya tidak valid.')
    return dict(label=raw['label'].strip(), prompt=raw['prompt'].strip(),
                motion_hint=raw['motion_hint'].strip(), palette=list(palette))


for _key, _value in tuple(PROFILES.items()):
    PROFILES[_key] = validate_profile(_value)
del _key, _value


def catalog():
    return dict(version=VERSION, scope='prompt_hint_only', rights_reference=False,
                renderer_neutral=True, profiles={key: dict(value) for key, value in PROFILES.items()})


def style_for(topic, preferred=None):
    """Deterministic, bounded choice so the same topic keeps the same art direction."""
    if preferred is not None:
        if preferred not in PROFILES:
            raise ValueError('Profil gaya tidak dikenal.')
        return preferred
    seed = hashlib.sha256(str(topic or '').strip().casefold().encode('utf-8')).digest()
    return tuple(PROFILES)[int.from_bytes(seed[:8], 'big') % len(PROFILES)]


def prompt_hint(topic, preferred=None, *, max_length=TEXT_LIMIT):
    """A short add-on for an existing director prompt; never a full instruction set."""
    style_id = style_for(topic, preferred)
    profile = PROFILES[style_id]
    text = f"Art direction: {profile['prompt']} {profile['motion_hint']}"
    if len(text) > max_length:
        text = text[:max_length].rstrip() + '…'
    return dict(style=style_id, label=profile['label'], palette=list(profile['palette']), text=text)


def enrich_prompt(prompt, topic, preferred=None, *, max_length=TEXT_LIMIT):
    """Append a bounded hint to an existing prompt without replacing its gates."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('Prompt dasar tidak valid.')
    hint = prompt_hint(topic, preferred, max_length=max_length)
    return dict(**hint, prompt=f"{prompt.strip()}\n{hint['text']}")
