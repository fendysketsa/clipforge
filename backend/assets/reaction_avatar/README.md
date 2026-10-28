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
animation is authored locally: periodic blink, subtle head bob, and mouth motion
inside transcript speech windows. It is intentionally described as approximate
speech-window animation, not phoneme-perfect lip sync or a real recording.
