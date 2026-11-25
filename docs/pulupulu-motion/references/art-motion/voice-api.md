# Volcengine Doubao Voice Cloning 2.0 · endpoint details and measured results

The historical endpoint record dates from 2026-09-13; the query section was updated 2026-09-18. New users configure per capabilities.md first; service limits follow whatever the service actually returns at call time. Official docs: Volcengine Documentation Center, "Doubao Speech" library (LibraryID 6561).

## Authentication

Legacy console (APP ID + Access Token):

```
X-Api-App-Id:      {APPID}
X-Api-Access-Key:  {Access Token}
X-Api-Resource-Id: volc.megatts.voiceclone   # training / query
                   seed-icl-2.0              # synthesis
X-Api-Request-Id:  {uuid}
Content-Type:      application/json
```

The new console uses `X-Api-Key` instead (obtained from API Key management). The legacy version is officially slated for gradual retirement.

## The three endpoints

| Purpose | Path |
|---|---|
| Train a voice | `POST /api/v3/tts/voice_clone` |
| Query status | `POST /api/v3/tts/get_voice` |
| Synthesize | `POST /api/v3/tts/unidirectional` (HTTP chunked streaming) |

Host is always `https://openspeech.bytedance.com`.

### Training

```json
{
  "speaker_id": "S_xxxxxxxx",
  "audio": { "data": "<base64>", "format": "wav" },
  "source": 2,
  "language": 0,
  "model_type": 5
}
```

- **Only `model_type: 5` gives cloning 2.0.** Omit it or pass any other value and the voice trains as 1.0.
- **The request body takes a single `audio` object, not an `audios` array.** The v1 endpoint used an array; v3 changed it.
  Passing an array returns `45000000 add unmapped key audios`.
- Optional: `text` (the text spoken in the reference audio; the server runs a WER check and returns `45001109` if it is too far off),
  `enable_audio_denoise` (denoising; costs similarity),
  `disable_volume_normalization` (turn off volume normalisation; synthesized volume then tracks the reference audio more closely).
- Returned `status`: 0 NotFound / 1 Training / 2 Success / 3 Failed / 4 Active.
  **Both 2 and 4 can synthesize directly.**
- In the response `speaker_status` is an array holding both the 1.0 and the 2.0 version;
  the entry with `model_type: 5` is the 2.0 one. Each carries a `demo_audio` preview link valid for one hour.

### Query (measured 2026-09-18)

The v3 `get_voice` request body uses the singular `{"speaker_id":"S_xxxxxxxx"}`, not a `speaker_ids` array. Query multiple slots one at a time; HTTP errors must be reported explicitly and must not be treated as the voice not existing. `koubo.py voices` has been corrected accordingly.

### Synthesis

```json
{
  "user": { "uid": "koubo" },
  "req_params": {
    "text": "...",
    "speaker": "S_xxxxxxxx",
    "model": "seed-tts-2.0-expressive",
    "tone_fidelity": true,
    "audio_params": { "format": "wav", "sample_rate": 48000, "speech_rate": -20 }
  }
}
```

The response is streamed, one JSON object per line; audio arrives base64-chunked in the `data` field — concatenate the chunks and you have the complete file.

## Two counter-intuitive parameter positions

1. **`speech_rate` must sit inside `audio_params`.** Put it at the top level of `req_params` and it is **silently ignored** —
   no error, HTTP 200, normal audio, but the rate does not budge.
   Measured: `audio_params.speech_rate = -50` took the same sentence from 10.36 s to 21.53 s (exactly 2×).
   Range `[-50, 100]`, 0 is the default, 100 = 2.0× speed, -50 = 0.5× speed, linear.
   Also silently ignored: `speed_ratio` (at whatever level) — that is a parameter name from another product line.

2. **`tone_fidelity` goes at the top level of `req_params`**, not inside `audio_params`. Only takes effect on 2.0 voices.

## Sample rate

`sample_rate` supports `[8000, 16000, 22050, 24000, 32000, 44100, 48000]`; **the default is 24000 only**.
To drop the audio back into a 48k editing project you must pass 48000 explicitly, or it sounds muffled.
`ogg_opus` supports 48000 only. For streaming scenarios the official recommendation is pcm, not wav.

## Other limits

- The **10MB cap on reference audio counts the original file, not the base64 payload** (a 9.16MB wav passed in testing).
  Supported: wav / mp3 / ogg / m4a / aac / pcm; pcm only at 24k mono.
- Keep synthesis text under 300 characters per request (about 60 s of audio); split long text yourself and concatenate.
- Each voice slot gets 15 training attempts, and you can retrain over the same slot repeatedly.
- The "voice upgrade" endpoint (`/api/v3/tts/upgrade_voice`) is only a V1→V3 migration;
  it **cannot append reference audio to an existing voice**. To change the reference audio you must retrain the same slot.

## Common error codes

| Code | Meaning | What to do |
|---|---|---|
| `45000000` | Wrong field in the request body | Read the unmapped key in the message |
| `45001122` | `no speaker detected` | No human voice in the reference audio. Check the average level first; below -36dB it is basically noise floor |
| `45001109` | `WERError` | The `text` you passed does not match the audio content; drop the text or fix it |
| `45000030` | `resource not granted` | The service behind that Resource-Id is not enabled for this account |

## Network

`openspeech.bytedance.com` is a mainland-China endpoint. If the local machine runs a socks proxy,
**passing `proxies=None` to requests does not block it** — it still reads `ALL_PROXY` from the environment,
showing up as intermittent `SSL: UNEXPECTED_EOF_WHILE_READING`.
Affected environments can set `bindings.volcengine.trust_env=false`; the default honours the environment proxy and does not force a bypass on every user.

## On "how long should the reference audio be"

In the historical listening sessions, a longer clean voice-over reference sounded more like the original than thirty seconds. That is one voice's experience, not a universal default for every voice; defer to your own sample listening and to the current service limits.

I ran one duration-gradient test here (nested samples at 15/30/60/120/200/400 s, 3 syntheses per step),
comparing median fundamental frequency and spectral centroid against the real voice; the per-step differences (1.7%–8.5%) and the
standard deviation across the three runs of the same step (1.7–9.5) are the same order of magnitude,
**so on these two metrics the steps cannot be told apart**.

That is not a refutation, though — these two metrics cover only the pitch and the brightness of the timbre;
**they do not cover prosody, pauses, breath points or tone at all**, and those are precisely the main ingredient of "does it sound like the person."
A metric that fails to detect a difference does not mean there is no difference. Trust your ears.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
