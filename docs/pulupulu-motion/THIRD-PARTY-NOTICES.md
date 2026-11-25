# Third-party notices

This repository is an agent skill: documents, scripts and reference material. It does **not** bundle the renderer
or any vendor library. What it depends on, and the terms each comes with, is listed here.

## The renderer — huashu-motion (MIT)

The `om` command this skill drives is [huashu-motion](https://github.com/alchaincyf/huashu-motion), MIT, by
Huashu ([alchaincyf](https://github.com/alchaincyf)). It is installed separately with npm and **is not
redistributed in this repository**; its own `LICENSE` and `THIRD_PARTY.md` travel with the installed package and
govern it. The documents here call the command `pulupulu` in places because the author runs a rebranded local
build of the same program; the flags are identical.

## huashu-art-motion (MIT)

The art-direction material under `references/art-motion/` follows the structure and vocabulary of the
`huashu-art-motion` project, MIT, by the same author. The reference-fetching script
(`scripts/art-motion/analyze/fetch_reference.py`) identifies itself to that project's pages with a user agent
naming `alchaincyf/huashu-art-motion`.

## Components the renderer uses (not bundled here)

| Component | Terms | Note |
|---|---|---|
| GSAP 3.14 | GreenSock "no charge" licence, see the `GSAP-LICENSE.html` shipped next to `gsap.min.js` | copied into new projects by `om new`; the plugin builds are free and must stay version-matched to the core |
| three.js r186 | MIT | only the `object-3d` and `ui-space` templates use it |
| Bundled fonts (Noto Sans SC, LXGW WenKai, Inter, Playfair Display, Anton and ~22 more) | SIL Open Font License 1.1, per-font copyright in the package's `fonts/LICENSES.md` | copied into projects by `om new` / `om fonts add` |
| Kokoro voice model, whisper.cpp models | own licences, fetched on first use by `om voice` | not redistributed |
| DeepSeek TTS API | DeepSeek's terms, billed to your own key | used only if you choose `scripts/deepseek_voice.py` instead of `om voice` |

## One thing that is **not** free to reuse

The **"bean Huashu" (豆子花叔) character** — the cartoon likeness drawn in the renderer's storytime template and
its demo films — is the upstream author's personal likeness. It is included there to demonstrate the project and
is **not licensed for other uses**. If you make a storytime film, design your own character. The example prompt
in `README.md` says so explicitly for that reason.

## This repository's own content

Everything written for this skill — the router, the reference pages, the scripts, the field notes — is MIT © 2026
Alucard0x1. See `LICENSE`.

## stickman-video-director (MIT) — ideas only, no files copied

Two MIT repositories on the same subject informed the stickman performance material in this skill:

- [kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director) — the rig and directing
  contracts behind `references/stickman-performance.md` (authored pose vocabulary, action cards, contact
  ownership, coverage, the review gate).
- [CryptoYuyyy02/stickman-video-director](https://github.com/CryptoYuyyy02/stickman-video-director) — an MIT
  adaptation of the above with production logs. Three of its observations are recorded here in our own words:
  the `modern-story` style profile, the identity-reference-frame and scene-drift checks, and the TTS
  outlier-take trap in `references/narration/deepseek-tts.md` §11b.

No files from either repository are redistributed in this one; the material is rewritten as rules.
