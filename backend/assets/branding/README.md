# RYUUNDY video watermark v2

The original R/crescent/ring artwork was downloaded from the owner's current
public YouTube channel on 2026-11-13, at the owner's explicit request:
https://www.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ

`ryuundy-brand.json` records its source URL, channel ID, current public handle,
and the avatar's SHA-256. `ryuundy-channel-avatar.jpg` is the unchanged download.

`ryuundy-watermark-v2.svg` embeds that original artwork, derives transparent
ink from its bright logo pixels, and adds the RYUUNDY wordmark and
KISAH · HIKMAH · MAKNA line. No artwork from the style reference is included.
It has no opaque backplate, remote dependency, animation or script.

`channel_branding.py` shares this asset across FFmpeg and Remotion. Ink alpha
is authored in the SVG. FFmpeg unpremultiplies librsvg's output before overlay
so it matches the browser renderer instead of producing a dark stamp.
The logo is decoded once and held to the end of the existing timeline.

Changing any branding asset invalidates deployment source verification, so
the application must be rebuilt using its standard Compose deployment command.
