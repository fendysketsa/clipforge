# Optional voice: configuration, skipping, and existing assets

This page covers optional voice: existing audio, macOS system voices, and Volcengine clone. For the image channel, see the [image capabilities guide](images.md). Configuration shares one external file; no service or plugin is installed.

## Before you start

Check only when the task needs voice; silent animations go straight into the visual pipeline. If the user already supplied a suitable audio track, use it as-is unless they explicitly ask for re-recording. Audio-only tasks do not start animation design or review.

`S` means the skill directory actually read for this run; it is not fixed to the author's machine or to any one agent's private directory. Claude Code, Codex, and Kimi all call the same CLI and do not depend on proprietary hooks.

```sh
python "$S/scripts/art-motion/capabilities.py" status --explain
# Add --project only when preferences from a trusted project must be read
python "$S/scripts/art-motion/capabilities.py" status --project <project> --explain
```

The check reads only this tool's configuration, the designated credential source of the selected adapter, and required local dependencies; it does not verify anything over the network. `configured_unverified` means the call is possible, not that the account or audio quality has been verified; `needs_configuration` is the only case that requires choosing a voice method, and `prompt:false` means the user previously chose to configure manually, so do not ask again unprompted. Actual request success is judged by the artifact and the receipt.

On first run with missing configuration, ask only for the one item this run needs: reuse a recording, system voice, your own clone, or skip. If the user has already specified, execute that choice directly; for any new cloud call, paid call, or training, use the authorization already granted for this run, and state the gap if there is none. Never ask the user to paste a key into chat.

## Save scope and skipping

An ordinary choice applies to this run only; save it as a user default only when the user says "from now on / default / remember". Ordinary configuration lives outside the install directory: on macOS/Linux at `$XDG_CONFIG_HOME/pulupulu-motion/media.json` (`~/.config/pulupulu-motion/media.json` when unset), on Windows at `%APPDATA%/pulupulu-motion/media.json`. `PULUPULU_CONFIG_HOME` overrides the directory; `--config` replaces the default user file.

The agent collects the choice, generates non-sensitive JSON, and hands it to the script to write; the script never blocks waiting for interactive stdin.

```sh
# Example JSON: {"preferences":{"voice":{"mode":"system"}}}
python "$S/scripts/art-motion/capabilities.py" configure --scope user --input <choice.json>
python "$S/scripts/art-motion/capabilities.py" skip --scope task  # not persisted; skipped for this run
python "$S/scripts/art-motion/capabilities.py" skip --scope user  # enable manually later; do not ask repeatedly
python "$S/scripts/art-motion/capabilities.py" reset --field preferences.voice
python "$S/scripts/art-motion/capabilities.py" reset --field onboarding.voice
```

"Skip for this run" is recorded in the current task state; the questionnaire must not reopen on the next action. No answer is not consent, and `configure` is not run without it. When a batch job is missing required configuration, it returns a non-zero exit code with the reason; a silent preview may be delivered only when the user accepts a basic preview, and it must not be called a finished voice-over cut.

Precedence: this run's parameters → project preferences → user preferences → public defaults. A project's `<project>/.pulupulu-motion/media.json` accepts only limited preferences and the `deny` policy; it may not carry credentials, private voice bindings, or permission grants. `status --explain` marks the source of each field; writes take a cross-process lock, and `--expected-revision` keeps a whole-file edit based on stale configuration from overwriting newer configuration.

## The three voice paths

```sh
# 1. Reuse existing audio: preserved byte for byte, with metadata generated; reference the original track directly if no copy is needed
python "$S/scripts/art-motion/capabilities.py" use-audio --audio original-recording.wav --out <project>/audio/voiceover.wav
# 2. System voice: macOS only, fixed 48kHz WAV; Chinese defaults to a choice among installed Mandarin voices
python "$S/scripts/art-motion/capabilities.py" say "text to speak" --mode system --out <project>/audio/voiceover.wav
# 3. Volcengine clone, configured and authorized
python "$S/scripts/art-motion/capabilities.py" say "text to speak" --mode clone --out <project>/audio/voiceover.wav
# Legacy calls stay compatible and share the same configuration
python "$S/scripts/art-motion/koubo.py" say "confirmed replacement line" --out <project>/audio/pickup.wav \
  --fit 3.5 --match original-track.wav --match-ss 10 --match-t 3.5
```

Existing output is never overwritten. On success, an adjacent `audio-file.json` is written recording duration, sample rate, SHA, and source; clone results record the requested model and never claim the actual model reported by the server. Raw PCM is first accepted as container audio, then exported as s16le, with sample rate and mono format written into the sidecar. System voices do not support Volcengine's model and rate parameters.

The public default is "no voice method chosen", not the author's voice. The recommended Volcengine defaults are expressive, restoration mode, speed 0; the user can adjust these under `provider_options.volcengine`. Private configuration may keep different speech rates and timbres. For the full field list see `schemas/media.schema.json`; do not guess field names.

Existing platform voices do not need retraining:

```sh
python "$S/scripts/art-motion/capabilities.py" bind --name narrator --speaker-id S_xxx --default
```

`bind` only registers a local alias: it does not call the platform, does not modify the existing `~/.koubo/voices.json`, and does not enable cloud calls automatically. `--default` changes only the default reference; generation still requires selecting `clone`.

## Volcengine configuration and authorization

Credentials are read from process environment variables; an existing file may also be specified in the private `bindings.volcengine.env_file`, or pointed at temporarily with `KOUBO_ENV`. Environment variables win; the tool never walks the current directory, home directory, or author workspace looking for `.env`. Configuration stores the variable name or file reference, never the key value.

Enabling cloud clone requires: `preferences.voice.mode=clone`, a resolvable voice, and both `policy.cloud` and `policy.paid_api` set to allow, or explicit authorization granted by the user for this run. `--allow-cloud` and `--allow-paid-api` only express authorization already granted for this run; they are not a way for the tool to bypass rules and cannot override `deny`. When the user changes their own prohibitions, change the corresponding configuration explicitly first; host and organizational restrictions still apply. A project can only tighten, never authorize.

The network proxy is controlled by the private `bindings.volcengine.trust_env`; the public default follows the environment. Do not impose one machine's proxy failure experience on every installation. Basic configuration and existing audio need only the Python standard library; audio acceptance needs `ffprobe`; system voice and fitting need `ffmpeg`; Volcengine additionally needs `requests`. Report missing dependencies; do not install them automatically.

Training is a separate operation and requires an explicit voice slot and authorization for this training; `--force` skips only the low-level check, not authorization. Only passing `--default` sets the training result as the registry default.

```sh
python "$S/scripts/art-motion/koubo.py" train --audio my-recording.wav --speaker S_xxx --name my-voice \
  --allow-cloud --allow-paid-api --allow-voice-training
```

Training changes the remote voice. The authorization flags in the example may be used only after the user has actually agreed; do not treat them as a routine prerequisite for synthesis.

## Acceptance and failure

Fitting keeps the existing coarse adjustment plus `atempo` and generates at most 3 takes; each take may be billed. A final difference beyond ±0.05 seconds returns failure and keeps the `.unfitted` candidate; never claim the duration passed. Synthesis must receive the server's end-of-stream success message; near-empty, silent, or error responses are not submitted as final artifacts. A network timeout may already have been accepted server-side; mark the result as indeterminate and do not blindly repeat the request.

A production cut still requires a word-by-word read-back and a listen-through of proper nouns; the CLI does not run three-candidate listening or ASR automatically. Replacement lines should be checked for seams, subtitles, and the visual timeline; if `video-pipeline` is in use, follow its paste-back and subtitle flow, and standalone users may use their own editing project.

## Maintenance and evolution

Source: 2026-10-08, P0/P1 capability configuration implementation. Read this page and the related API notes before use; for a reproducible interface failure, add a test before fixing the code. Public parameter rules go on this page or in `voice-api.md`, with the date and scope stated; personal listening preferences go into private configuration or private feedback and must not become public hard requirements. Correcting an old conclusion means editing the original text; upgrading configuration must not clear preferences or silently enable new capabilities.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
