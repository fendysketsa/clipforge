# Cron Reaction Host Assets

These assets implement the disclosed virtual reaction host used only by the
scheduled ClipForge pipeline. The persistent host occupies the upper panel;
source video and original source audio remain in the lower panel.

The neutral, blink, and talk states were derived from the user-supplied portrait
with OpenAI ImageGen. The prompts preserved the person's face, cap, hoodie, and
illustrated identity while removing the wall/UI and making the background
transparent. The blink prompt changed only the eyelids. The talk prompt changed
only the lips/jaw to a small natural vowel shape. No text, logo, or watermark was
requested.

`fendy-reaction-avatar-720.png`, `fendy-reaction-avatar-blink-eyes.png`, and
`fendy-reaction-avatar-talk-mouth.png` are render-optimized derivatives. The
animation is authored locally. Version 2 adds three identity-preserving,
transparent full-expression states generated from that same reference:
`fendy-reaction-avatar-shock-v2.png`,
`fendy-reaction-avatar-laugh-v2.png`, and
`fendy-reaction-avatar-skeptical-v2.png`.

The host is a listener. Irregular deterministic blinks and subtle breathing
fill neutral passages. Transcript-grounded cues select the expression and drive
bounded head tilt, surprise recoil/double-take, damped laugh shoulders, a dry
question side-eye, or a deliberate nod. A small source-panel shake and very
brief flash are reserved for surprise, while a mild vignette keeps the split
cinematic. The mouth state is limited to laugh/surprise reactions and never
follows all source speech, so it does not impersonate the source speaker or
claim phoneme-perfect lip sync.

ImageGen v2 prompt intent: preserve the same person, backwards gray cap, black
hoodie, facial hair, semi-realistic illustration style, front head-and-shoulders
scale, and transparent alpha; change only the natural surprised double-take,
contained laugh, or skeptical side-eye expression. No text, logo, watermark,
extra props, or grotesque caricature.

Version 3 is the default cinematic host. A photorealistic transparent master
was derived from the same approved identity reference, then every expression
was edited from that master rather than generated independently:

- `fendy-reaction-avatar-real-neutral-v3.png`
- `fendy-reaction-avatar-real-blink-v3.png`
- `fendy-reaction-avatar-real-shock-v3.png`
- `fendy-reaction-avatar-real-laugh-v3.png`
- `fendy-reaction-avatar-real-skeptical-v3.png`
- `fendy-reaction-avatar-real-warm-v3.png`

The v3 prompt set locks the Indonesian man's facial structure, warm medium skin,
eye color, moustache/goatee, backwards gray cap, black hoodie, camera distance,
shoulder silhouette, soft camera-left key, cool rim light, and transparent alpha.
Only eyelids, eye direction, eyebrows, mouth, and a two-to-three-degree head
incline may change. The renderer uses irregular neutral blinks plus a blink-cut
around a 40–55 ms alpha dissolve so expression changes do not create a ghosted
double face. The UI disclosure remains `HOST VIRTUAL • REACTION`.
