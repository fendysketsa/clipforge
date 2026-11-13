"""One local, transparent RYUUNDY emblem shared by the video renderers."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path


WATERMARK_STYLE_VERSION = 2
WATERMARK_ASSET = Path(__file__).resolve().parent / "assets" / "branding" / "ryuundy-watermark-v2.svg"
CHANNEL_URL = "https://www.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ"


def watermark_size(output_format: str) -> int:
    return 216 if output_format == "landscape_compilation" else 208


def watermark_filter(output_format: str) -> str:
    """Overlay one still at 46% of the frame; repeat its final frame to EOF.

    A single decoded SVG keeps the full timeline and avoids a looping image
    source that could extend a render. Alpha is authored in the asset, so
    FFmpeg and browser renders have the same restrained appearance.
    """
    if not WATERMARK_ASSET.is_file():
        raise FileNotFoundError(f"Logo watermark RYUUNDY tidak ditemukan: {WATERMARK_ASSET}")
    asset = str(WATERMARK_ASSET).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    size = watermark_size(output_format)
    return (
        "null[ryuundy_brand_base];"
        # librsvg returns premultiplied RGB. Convert it to straight alpha
        # before overlay, otherwise the champagne ink becomes a dark stamp.
        f"movie=filename='{asset}',format=rgba,unpremultiply=inplace=1,"
        f"scale={size}:{size}:flags=lanczos,format=rgba[ryuundy_brand_ink];"
        "[ryuundy_brand_base][ryuundy_brand_ink]overlay="
        "x='(main_w-overlay_w)/2':y='(main_h-overlay_h)*0.46':"
        "eof_action=repeat:repeatlast=1:format=auto"
    )


@lru_cache(maxsize=1)
def watermark_data_uri() -> str:
    # Self-contained manifests do not depend on a network URL or a mutable
    # channel avatar during rendering. All templates use the same local SVG.
    return "data:image/svg+xml;base64," + base64.b64encode(WATERMARK_ASSET.read_bytes()).decode("ascii")


def watermark_metadata(output_format: str) -> dict:
    return {
        "style_version": WATERMARK_STYLE_VERSION,
        "style": "channel_monogram_champagne_seal",
        "asset": WATERMARK_ASSET.name,
        "channel_url": CHANNEL_URL,
        "position": "center_46_percent",
        "size_px": watermark_size(output_format),
        "opacity": 0.24,
        "wordmark_opacity": 0.34,
        "backplate_opacity": 0.0,
        "ornament": "original_channel_r_crescent_ring",
        "animated": False,
        "source_ownership_claimed": False,
    }
