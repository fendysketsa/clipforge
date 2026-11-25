# Briefing from a reference film or channel

Owner: resolving a named reference into a style

"Make a sample like <channel>" is a common request and the most expensive one to misread: the wrong reading
costs a whole agent run. Resolve the reference into artefacts, then write the brief from what you observed.

## 1. Resolve the name into a concrete artefact

A channel *name* is not a style. Before briefing anything:

- **Video URL → metadata.** `https://www.youtube.com/oembed?url=<video-url>&format=json` returns title, channel
  name, channel URL and a thumbnail URL. One `curl -s -A "Mozilla/5.0"`; no scraping.
- **Channel → its recent titles.** Pull the channel id out of the channel page (`"channelId":"UC…"`), then fetch
  `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` for the last ~15 titles. Titles expose the story
  engine: a run of "What If…", "Why Did…", "One Mistake…" is a formula you can state in the brief.
- **Thumbnail → visual system.** Download `https://i.ytimg.com/vi/<id>/maxresdefault.jpg` and read it with
  vision. Ask for the specific dimensions — character construction, line weight, palette, lighting, overlay type,
  composition — not "describe this image", or the answer comes back as adjectives.
- **Search for a third-party breakdown.** Someone has often counted a popular channel frame by frame, and their
  numbers beat your impression of one thumbnail: "camera never static, 6–10 s moves, ≤2 cuts, snap into a pose in
  3–5 frames then hold, one idea per shot". Use those as the spec.

**Do not brief from the name alone.** A name that resolves to a different style than you assumed turns into two
wasted runs — one killed mid-build, one relaunched. If two readings are plausible, resolve first, launch second.
A user-supplied URL is the fastest way out of the ambiguity: fetch it and ask nothing.

## 2. Turn the observations into rules a renderer can be checked against

Adjectives ("vibrant", "snappy") cannot be verified; the following can, so the brief states these and the
verification quotes them back:

- **Character construction:** head as a fraction of body height, line caps and joint radius, how many accessories,
  whether faces are stickers on a body.
- **Palette and light:** dominant hue per era or chapter, key direction, contrast ceiling.
- **Text system:** words per card, display weight and outline, hold duration, how many times per film.
- **Cutting and camera:** cut count, whether the camera is ever static, per-move duration.
- **Story shape as beats with timestamps:** cold open, the object, escalation, reveal, button.
- **What must not be copied:** characters, episodes, wording, logo, channel name, music.

Then keep the sample short — 40–70 seconds. A style test does not need a documentary, and a short clip is what
proves whether the system works.

## 3. Rights belong in the brief

Style is not copyrightable; expression is. Reuse the **system** — era iconography, camera language, character
construction, pacing — and invent the **content**: your own character and accessory, your own story, your own
wording, your own music.

- Never reproduce a commercial song, its melody, its lyrics or its audio. Synthesise an original track in the
  same idiom and export the beat grid, so the animation's timing can be audited against the music it was cut to.
- Never reproduce a real person's likeness; a reference channel's character is also off-limits — the style is
  the deliverable, not the character.
- Write the prohibition into the brief explicitly. Left implicit, a delegated agent will paste the reference's
  red beanie and cape onto its own stickman and call it a style match.
