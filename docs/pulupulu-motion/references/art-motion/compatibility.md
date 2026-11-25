# Compatibility and verification scope

Verification date: 2026-10-08. The following separates installation and configuration, host execution with the model online, and actual media generation; a pass at one level is not substituted for another.

## Installation and configuration upgrade

In an isolated Git workspace, actually ran the official skills CLI with `skills add <local release package> --skill pulupulu-motion --agent <host> --yes --copy`, installing twice in a row for each target. All three targets — claude-code, codex, kimi-code-cli — succeeded, and media.json outside the install directory was byte-for-byte unchanged. What is verified here is preference retention across an overwriting reinstall; this does not claim to have fully simulated every historical version or every installer's update implementation.

An existing voice configuration merges the new default fields without being rewritten; the newly added image capability is still unselected and unauthorised. The CLI in the Codex installed copy read the original system preference and revision, and did not fall back to the public defaults.

## Host execution online

- Codex CLI 0.160.1: a real session loaded the installed skill and guide, and ran the unconfigured state, generation disabled, no tools, importing an existing image, and saving a private system preference; the output image was byte-for-byte identical to the source, and the configuration provenance matched expectations.
- Claude Code 2.1.287: installation and the local CLI work; the online session returned 429 on the current test environment's weekly quota, so the model-execution regression was not completed. This cannot be marked as an online pass, nor used to conclude that the skill is incompatible.
- Kimi Code CLI 0.38.0: installation and the local CLI work; the online session returned 403 on the current test account's access rights, so the model-execution regression was not completed. In that version the non-interactive `--prompt` cannot be combined with `--auto` or `--yolo`; the retry command was corrected and still returned an account 403.

These sessions used isolated workspaces and media configurations while reusing logins already on this machine; they are not three brand-new accounts. Once the Claude/Kimi account conditions are restored, the online cases still have to be re-run. Tool capability depends on the actual session; you cannot infer that image generation is present from the host's name.

## Actual media and automated tests

macOS system speech and Volcengine cloning have completed real short-sentence generation; the current Codex session actually invoked the built-in image generation and produced a 1536×1024 PNG with transparent pixels, passing plan → tool call → receipt → project copy and SHA acceptance. The image tool calls were made by the agent; the CLI did not call on its behalf. This test proves only the integration path and the file properties, not art quality.

The automated tests cover configuration merging, permission tightening, concurrent writes, legacy PCM output, incomplete speech streams, image feature and billing selection, cross-session plans, configuration rollback, concurrent image replacement, and release artifact checks. CI runs on Linux; real system speech was verified on macOS only — the system speech backends for Windows/Linux are not implemented yet.

## Minimum reproducible checks

```sh
python scripts/art-motion/capabilities.py status --config <an empty JSON file> --explain
python scripts/art-motion/capabilities.py image-status --config <JSON with image generation disabled> --mode generate
python scripts/art-motion/capabilities.py use-image --file <existing PNG> --out <project>/illustrations/new-file.png
python -m unittest discover -s tests -v
```

Real image-tool verification forms a snapshot from the current tool schema per images.md; with no tool present it returns unavailable explicitly, and a fabricated tool must not be passed off as success. CI without credentials or authorisation does not call paid media services.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
