# Self-healing: making the asset a shot needs

Owner: asset repair and delegation to another agent

A review that ends with "the explosion does not read" is a **missing-asset** problem as often as a
**missing-tween** problem. The skill has to be able to author that asset, validate it, wire it in and prove it,
without asking a human to draw anything.

## Decide first: regenerate, cut, or composite

| the frame is wrong because… | do this |
|---|---|
| the subject is absent (no fissure on the cone, no rock chunks, no foam) | **generate** one cut-out with `scripts/asset_gen.py` |
| the subject exists but is the wrong size, the wrong part, or needs a mirrored copy | **cut** it out of the existing plate with PIL — cheaper and guaranteed on-style |
| the subject exists and the motion is wrong (a circle where an ellipse belongs, a blob where rock belongs) | **composite**: geometry shader/primitive plus the existing texture. This is a code fix, not an asset fix |
| the palette fights the film | recolour the existing asset; a new generation will drift further |

Generating a replacement for an asset that already works is the most common wasted hour: the new art will not
match the line weight of the rest of the film, and every other shot will look like a different illustrator drew
it. Generate for **additions**, cut for **variations**, code for **behaviour**.

## The brief is a contract, not a description

`scripts/asset_gen.py` takes a JSON list of briefs and runs each through the image model, then validates the
result. A brief that omits any of these comes back unusable:

```json
{
  "name": "s6_ember_vent",
  "kind": "cutout",
  "size": [512, 512],
  "min_alpha": 0.55,
  "palette": ["#14120f", "#c8452a"],
  "prompt": "…"
}
```

Rules that every prompt must carry, because generators default to the opposite of each:

- **Name the palette in hex**, and say which colour is the outline, which is the fill, which is the highlight.
- **"NO background, NO paper card, NO rectangle, NO vignette, NO shadow under the object — everything outside
the silhouette is fully transparent (alpha 0)."** Without this sentence you get a white square with a drop
  shadow, which is the single most common reason a cut-out cannot be used.
- **State the style anchor**: "flat paper-theatre cut-out, thick ink outline, flat fills, no gradients, no
  photorealism", plus the line weight relation to the rest of the film ("the same line weight as a linocut").
- **State the size it must read at**, in output pixels: "must read clearly at 120 px wide". A generator asked for
  a 512 px asset draws detail that turns to mush at the size the film actually uses it.
- **For a sprite sheet**: one horizontal row, N equal cells, WxH each, "a 6 pixel empty margin on every side of
  every cell so they can be sliced apart", and "NO numbers, NO labels, NO grid lines".
- **Say what it will be composited onto.** "It will be overlaid on a mountain to show it splitting open" gets a
  silhouette with a clear bottom edge; without it you get a floating object.

## Validation gates (what the script refuses)

`asset_gen.py --check` re-runs only the checks, no generation:

- **alpha fraction** — a cut-out with less than `min_alpha` transparent pixels is a picture, not a cut-out.
- **corner opacity** — all four corners opaque means a background card was drawn.
- **palette presence** — every hex in `palette` must appear within a tolerance of 26 per channel. This is what
  catches "the ember is now orange-red instead of `#c8452a`", which is invisible until it sits next to the rest
  of the film.
- **size** — a mismatch is a warning in the log, not an automatic resize: downscaling a card-backed image does
  not remove the card.

A failing asset is **never** wired into a timeline. Report the failure and fix the brief.

## The loop

1. **Measure the deficiency in the frame**, not in your head: render the exact second, look at it, and name what
   is missing in the picture ("the cone has no fissure at the moment of rupture").
2. **Choose regenerate / cut / composite** from the table above.
3. **Write the brief** with every clause from the list above.
4. **Generate and validate**: `python scripts/asset_gen.py briefs.json`. Read the log; a `FAIL` line is the
   brief's fault, not the model's.
5. **Slice before the GPU** if it is a sheet — cells to separate PNGs at display size, with the alpha bbox
   trimmed (`_tight.png`), because that is what the texture budget is set against.
6. **Wire it into the timeline** with a `spriteSheet`/`layer` call, sized relative to the *subject* (a rock chunk
   on a 3.2-unit island is 0.2 units, not 0.9), and give every cell its own velocity if it is a burst.
7. **Render one still at the event's second and look at it.** The still is the only proof.
8. **Record the lesson** in this file only if it generalises; otherwise it belongs in the project's notes.

## When a new asset is the wrong answer

The complaint "it does not feel alive" is usually **not** an asset problem. Before generating anything, check
whether the existing assets already move:

- a wash over the whole frame at impact (a full-frame white quad) makes the paper look grey — that is a code
  bug and no new asset fixes it;
- a shockwave drawn as a perfect circle around a mountain reads as a hoop; the fix is an ellipse in perspective
  anchored at the waterline, again a code fix;
- a static composition gives motion nowhere to read, whatever is generated for it.

If the frame is already full of correctly-drawn assets and still feels dead, the fix is timing and staging.
Generating more art makes the diagnosis harder, not easier.

## Model-call mechanics that waste a whole attempt

- **`agy` in headless print mode** silently denies permissioned tools and exits 0 — see the network section
  below for the flag and the empty-log diagnostic, so the rule lives in one place.
- `codex exec` reads its prompt from **stdin**; `-i` is variadic and will swallow an inline prompt ("No prompt
  provided via stdin"). Put the save path in the prompt text and let the agent write the file.
- Pass the working directory as a **native** path (`C:/…`, forward slashes). An MSYS path like `/c/…` fails with
  `The system cannot find the file specified` because the binary is not an MSYS program.
- The model reports success in prose whether or not it wrote the file. Only `os.path.exists` plus the validation
  gates count.

## Launching an autonomous agent on a job that needs the network

Both CLIs default to a policy that quietly kills a networked job while reporting success at the process level:

- **`codex exec` runs `sandbox: workspace-write`, which has no network.** A TTS or API call inside it fails per
  request, the agent works around the failure by producing everything except the audio, and the run still exits
  0 with a plausible final message ("I could not test the sync without the WAVs"). Pass
  `--dangerously-bypass-approvals-and-sandbox` when the job legitimately needs the network, and check that a
  wav/mp3 actually appeared before believing the run.
- **`agy --print` auto-denies any tool that would need a permission prompt**, and `--add-dir` grants the
  workspace only. Pass `--dangerously-skip-permissions`. An empty agent log with exit 0 is a permission
  failure — read it that way before concluding the model declined the task.
- **Keep the conversation, not only the folder.** A fresh `--print` with a restated brief produces a *different*
  film, which is the wrong answer when the owner says "same episode, fix these three things" — mechanics in
  § *Continue the conversation* below.
- **A missing key and a blocked network look identical from the outside.** Confirm the key reached the process
  first (log the character count, never the value) before re-running: if the key is present, the sandbox is the
  culprit.
- **Usage capture is a flag, not a feature.** `agy --print --output-format json` emits
  `{usage: {input_tokens, output_tokens, thinking_tokens, cache_read_tokens, total_tokens}}` at the end; without
  the flag the numbers are gone for good. For `codex`, the numbers live in
  `~/.codex/sessions/<Y>/<M>/<D>/rollout-*.jsonl` as `total_token_usage` events — parse the last one per
  session file. Never ask a model how many tokens it used; it cannot know.

### Pick the model and effort deliberately, and quote the id you used

- **List what the CLI actually offers before writing a model id into a launch command.** `agy models` prints the
  ids beside their display names (`gemini-4-neon-medium` = "Gemini 4 Neon (Medium)", plus `-low`, `-high`,
  `-xhigh` and the Argon / Hydrogen / orchestrator / Claude / GPT-OSS variants). A guessed id fails the run
  instead of falling back to a default. **Effort is baked into the id for `agy`**, so raising it means choosing
  a different id, not adding a flag: `--model gemini-4-neon-medium --effort high` is refused outright with
  `invalid model selection … conflicts with --effort=high` before anything runs. `codex` takes effort
  separately as `-c model_reasoning_effort="high"`.
- **Effort follows the owner's instruction, and defaults to medium.** `gemini-4-neon-medium` is the standing
  default; when the owner asks for a stronger build, switch the id to `gemini-4-neon-high` and say which id you
  launched. Do not escalate effort on your own initiative when a film comes back weak — fix the brief, the rig
  or the gates first, because a weaker result is far more often a weak acceptance bar than an under-powered
  model.
- **A model id in a report is a fact to verify, not a label to infer.** Quote the id the run actually used, from the
  launch command or the session file, never from memory of what you think was configured.

### `input_tokens` does not mean the same thing in every CLI

Comparing two agents' usage without reading how each counts produces nonsense — one run came out with negative
fresh input because the two fields were treated as equivalent:

- **Codex** (`rollout-*.jsonl`, `total_token_usage`) counts cache reads *inside* `input_tokens`:
  fresh input = `input_tokens - cached_input_tokens`.
- **`agy --output-format json`** reports `input_tokens` *excluding* cache, with `cache_read_tokens` as its own
  counter: `total_tokens = input_tokens + output_tokens`, and `thinking_tokens` is separate from output.

Assert the arithmetic before publishing a number: `fresh + cached + output` should reconcile with the reported
total under that tool's own definition, and no component may be negative.

**Never quote a token total you did not print from the parse in this turn.** A figure carried over from
memory looks precise and is invented; that is exactly how a wrong total gets stated with confidence and has
to be retracted. Run the parse, paste its output, then talk about it — the same rule applies to any number
that ends up in a deliverable (cost, duration, file size, view count).

### Answering "what did this cost"

Asking the agent itself is a reasonable first move and a poor final answer. The unit price is the only part it
can supply and the only part you cannot verify, so:

- **Ask it for the assumption, not the total.** Require three things in the reply: the price per million tokens
  it is using for input, cached input and output; where that price came from; and whether it actually knows the
  billing rate for the model it runs on or is estimating. Its arithmetic is then worth re-running yourself.
- **Check the arithmetic and the rate in this turn.** Recompute `fresh × in + cached × cache + out × out` from
  the parsed counters, fetch the day's FX rate, and report the rupiah figure you computed — not the one you were
  handed. A stated rate 0.3 % off is normal; a total 30 % off is a wrong field.
- **Settle whether there are two prices or one.** `input_tokens + output_tokens == total_tokens` proves thinking
  is already inside output and must not be billed twice; when it differs, thinking is a separate line.
- **Say which kind of number it is.** If the run draws on a subscription or pool, a `quota reached` /
  `RESOURCE_EXHAUSTED` error on the family is the proof, and the marginal cost of the film is **zero** — the
  rupiah figure is an API-equivalent conversion, not a bill. When the model id has no public price list, say the
  unit price is the agent's assumption and that only the arithmetic and the FX were verified.
- **Cost is set by iterations, not by duration.** Seventy-one seconds of finished film came out cheaper than
  three twenty-second ones because the short films were rebuilt more often; when comparing runs, attribute the
  difference to re-runs and cache share before letting the comparison blame the model.

## When a run dies mid-build: resume it, never re-brief it

An agent can stop at any step with most of the work already on disk — one Codex run finished the narration, 50 beats
and both audits, then exited 1 at the render with `You've hit your usage limit … try again at 2:03 PM`. Treat that as
a pause, not a failed design.

- **Read the log tail and name the cause before acting.** Quota, blocked network, denied permission and a stdin
  prompt mistake all end in a non-zero exit and each needs a different response; the prose summary printed above the
  exit is not the diagnosis.
- **Never re-brief from scratch.** Write `<folder>/FOLLOWUP.md` that opens with "continue — do not redesign", lists
  the finished artifacts by path (narration wav, beats, page, passing audits), states the single remaining task and
  re-states the verification list. A fresh brief throws away the finished half and the new run will not match the art
  that already exists.
- **Make the resume idempotent:** if the deliverable already exists, the resume script exits without launching the
  agent. Schedule it after the stated reset time as a one-shot cron; do not sleep in the session waiting.
- **Exit 0 is not delivery, and exit ≠ 0 is not total loss.** Judge by the artifact: exit 1 with no MP4 is a
  failure; exit 1 with the file present is a finished job with a warning worth reading.

### Testing whether a quota limit has reset

Neither CLI exposes remaining quota — `codex --help` lists `agents, exec, review, login, logout, mcp, plugin,
app-server, remote-control, app, completion, update, doctor, sandbox, debug, apply` and no usage command, and
`agy` has none either — so an exhausted account can only be tested by calling it.

- **The failure is recorded, not inferred.** Codex writes `"codex_error_info": "usage_limit_exceeded"` plus the
  stated reset time into the session's `rollout-*.jsonl`. Grep the rollout before blaming the task or the model.
- **Probe with the cheapest possible call** — `codex exec -c model_reasoning_effort="low" "Reply with the single
  word: ok"`, or one trivial `agy --print` — and treat a successful answer, not the clock, as the signal that
  the account is usable again. The probe costs ~10k tokens; a relaunched build that dies on frame one costs the
  whole schedule.
- **Say what the number is and is not.** A day's token total is not a quota reading: report usable/not usable,
  the recorded error code, and that the cap is a subscription limit the CLI cannot see.

### Taking the build over yourself

When the owner says to finish a dead agent's job, you are inheriting a pipeline, not writing one:

1. **Run its renderer, not a new one.** Its entry script usually encodes the film's own limits (speech floor,
   intro and outro windows) — read the argument parsing and the validation block first, so a refusal reads as a
   contract violation instead of a bug.
2. **Find the artifacts its script expects that another script produces.** A render dying on
   `No such file or directory: out/audio_full.wav` is not a render bug: the project has a separate audio-assembly
   script that has to run first. Same for manifests, specs and index files. Build the missing input, then re-run.
3. **Supply what the dead run never reached** — typically the manifest and the mid-film mark. Write the manifest
   from what is on disk (the sources it recorded, the asset tables it generated, the measured beat list) rather
   than inventing provenance, and say in it that the run was taken over.
4. **Patch motion and measured defects; do not redesign the art.** Its palette, layouts and copy are what the
   owner asked for. Re-render only what a check proves is broken — `references/static-render-and-resume.md`.
5. **In any brief you write, put the manifest before the render.** A run that dies at the render otherwise takes
   the sources and the per-scene asset tables with it, and neither can be reconstructed afterwards.

## A progress ticker must tell finished from failed

When the user asks for status every N minutes on a long autonomous build, run a `no_agent` cron whose script prints
filesystem state — beat wavs, scene stills, output size, the newest touched file and its age. Two rules:

- **Parse the exit code; never grep for the word `exit`.** A ticker that reads "the log mentions `exit=`" as done
  reports a crashed run as finished. Render `GAGAL(exit N) tanpa mp4` instead, and print `diam` when no file has
  changed for a few minutes so a stalled run looks stalled rather than busy.
- **Cancel the ticker when you start verifying**, so the user is not pinged while you are the one working.


## Racing two agents on one brief

Two independent builds from one brief answer a question a single build cannot: whether the film is good or whether
one model got lucky. It is also how you choose a default for the next job.

1. **One brief file, byte-identical copies.** Write it once, copy it into each workspace, and prove it with
   `md5sum` on both before launching. A brief that drifted between folders makes the comparison worthless.
2. **One folder per agent, nothing shared** — its own `out/`, log, and `MANIFEST.md`. Never a common assets tree:
   whoever writes first silently defines the other's art.
3. **Launch both in the background**, each with the key exported inside the launch command (never in a file) and
   the full-access flag that CLI needs for network. `agy` additionally needs `--output-format json` or its usage
   is lost. Each launch logs its own exit code.
4. **Do not supervise the middle.** Look for progress signals — beat WAVs appearing, a 20 s slice rendered, `out/`
   growing — instead of reading logs: `agy`'s JSON arrives only at the end, so an empty json file mid-run is
   normal, not a stall. One agent finishing in ten minutes while the other takes thirty is not a quality signal;
   the slower one may be rendering 9000 frames.
5. **Judge from frames you extracted yourself**, at the same timestamps and same size for both: open, two body
   beats, the mid-film mark, the end card. Never from the agents' own descriptions of their work.
6. **Write `USAGE.md` and `USAGE.json` into each project folder.** The numbers must outlive the session, and the
   two CLIs count differently — see the section above.
7. **Report per-agent totals and then a rupiah table** at the current rate, labelled a conversion at tariffs, not
   a bill. Say *why* the cheaper one was cheaper — cache share, fewer re-runs — not just which number is smaller.
   A failed first run doubles that agent's total, so when the figures look lopsided, name the re-run instead of
   letting the comparison blame the model.
8. **Three or more participants: convergence is the finding, not the vote.** When independent agents propose the
   same ranked items from the same source, that agreement is evidence the answer is real rather than one model's
   taste — report the shared items as the decision and the differences as the interesting part. Do not average
   proposals into a blend nobody argued for; take each item from the run that gave the sharper mechanism, and say
   which run it came from.
9. **When a planned participant cannot be consulted, name it and proceed.** Probe a sibling model variant to tell
   an account-wide block from a per-model one, then state the missing voice plainly in the deliverable rather than
   silently substituting another agent and letting the reader believe every review happened. An absent consult
   changes what the report claims, not what the film does — finish with those available and say so.

## Splitting one film across two agents

Who does what is the owner's call and it is **not** symmetric here: the film is built by `agy` (Gemini), and
image generation is commissioned from `codex`, which is the CLI with a working internal image tool. Capability
does not decide the split — when a launch was already running on the wrong agent for the build, the right move
was to stop it and relaunch rather than argue for the substitute. Ask once, then hold the split for the rest of
the job.

The order is forced by that division, because a film agent that finds no plates will generate its own:

1. **Write the prompt set first and gate it** — `references/stickman-visual-prompts.md`, then
   `python scripts/asset_prompt_audit.py prompts.md --count N`. A set that fails the gate is minutes to fix and
   nine re-generations to discover later.
2. **Stop the film builder before commissioning art.** Generate the plates first, then launch the film agent
   once with the assets directory added. Two agents writing the same art tree in parallel is how the two halves
   stop matching.
3. **Hand the plates over with a `NOTE.md`, not just a path.** Restate in it: the directory, the file list and
   their exact size, that the set already passed its gate, the palette hexes to hold, and the sentence that
   does the work — *do not generate your own environment plates*. Without that line the film agent regenerates
   the art in its own style.
4. **Commission plates with no figures and no text when the performer is drawn in code.** A painted person in a
   plate fights the rig composited over it, and baked lettering fights the film's own type. Ask for the *space*
   the character occupies — the empty bed, the open door, the corridor — framed for a figure.
5. **Judge the plates yourself before the film run**: exact output size, no people, no glyphs, one palette and
   one light logic across the set, no melted architecture. Then look at a contact sheet, and regenerate only
   after you have seen the failure.

## Continue the conversation instead of re-briefing a live agent

A re-brief throws away everything the agent learned about the piece — the palette it settled on, the rig it built,
the jokes it already rejected. When the same agent must improve the *same* film, continue its conversation:

- **`agy` has `--continue` (`-c`) for the most recent conversation and `--conversation <id>` for a specific one.**
  `codex exec` offers no resume, so continuity there means writing `<folder>/FOLLOWUP.md` that opens with "continue —
  do not redesign" and lists the finished artifacts by path.
- **Send a follow-up, not a new project.** Same folder, same brief file, plus a `CONTINUE.md` that names the three
  things that are wrong and what to keep. A fresh folder is only correct when the concept changed.
- **Give a research task a destination file.** "Research and get better at X" produces nothing inspectable. Ask for
  `<folder>/research/<topic>.md` with the sources and the date checked, then require the deliverable to name which
  rules were applied and where they are visible. The document is reviewable; the intent is not.
- **Audit the research for citations.** One run produced 8 KB of correct animation theory headed "verified via web
  research" and **not one URL** — real knowledge from model priors, unverifiable as research. Grep the document for
  `http` before accepting it, and ask for the links if they are missing.
- **Name the numbers that must change.** "Make the character bigger" gets a shrug; "the head must be ~1/5 of the
  frame height, it is 6.6 % today" got implemented as a 5.6× scale change. A measurable target is the difference
  between a suggested edit and a completed one.
