# pulupulu CLI and the page contract

Owner: CLI commands, project contract and the page contract


Every command, what it proves, and the HTML page contract the renderer expects.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 2. CLI Reference (`pulupulu`)

Invoke the self-hosted CLI (`pulupulu <cmd>`, or `om <cmd>`); if it is genuinely absent, install it once and never fall back to `npx` per command (§ below). `om check`, `om still`, `om look`, `om sound`, and `om render` drive the user's installed Chrome locally (no cloud API). If your sandbox blocks starting Chrome or a local server (`127.0.0.1`), request permission to run outside the sandbox rather than skipping visual checks.

```sh
# Material & Setup
om grab <url|folder> [dir]          # Collect screenshots, logo, images, CSS colours & fonts into <dir>/materials/
om templates                        # List starter templates (blank, ui-space, object-3d, talking-head, + 8 grammars)
om new <dir> [--template t]         # Create contract-ready project
om demo [dir]                       # Copy showcase film and open in studio
om fonts [add <family> [dir]]       # List bundled typefaces (CJK 500-900, serif, display) or install into project

# Studio & Point-to-Edit Loop
om studio [dir] [--no-open] [--lang zh|en|es]  # Live preview + direct variable edits + frame comments
om inbox [dir] [--wait] [--timeout 540]        # Block until user comments, claim & print context + source line
om look <id|--at sec> [dir]         # Save frame PNG + close-up of clicked spot
om done <id> [dir] --note "…"       # Resolve comment with one-line summary in user's language
om vars [dir] · om set k=v… [dir]   # List or update composition variable defaults in index.html
om scan [dir] · om undo [dir]       # JSON map of vars/objects/scenes · restore previous version in .om/history

# Audio & Narration
om samples [build [ids…]]           # Status / one-time install (~55 MB) of real-instrument samples (piano, strings, drums)
om voice <dir> --text <file|"text"> | --audio <file> [--voice say:Tingting|zf_xiaobei] [--fit]
om sound [dir] [--list] [--off]     # Render assets/sound.wav from om-score / OM.music / OM.sfx; prints energy curve

# Visual Checks, Render & Share
om still <page.html|dir> [--at 0,2.5] [--out file]  # Render PNG(s) of any page or composition
om swatch [directions.md] [--out file]              # Render direction card palettes + contrast/house-look warnings
om check [dir] [--samples n] [--source] [--json]    # Validate scripts, motion rules, layout/contrast, seek determinism
om render [dir] [--format mp4|mov|webm|gif] [--fps 30] [--blur [n]] [--transparent] [--silent]
om qa [dir|video] [--loop] [--sheet [fps]]          # Check pops, dead time, hard cuts, motion curve, loop seam, contact sheet
om fork <dir> <newdir> --size 1080x1920             # Copy to new aspect ratio; queues re-layout task in inbox
om share [dir] [--from s] [--to s]                  # Generate <=10 MB GIF + out/share/share.md
om export html [dir] [--out folder]                 # Standalone share page (player, Remix prompt, source.zip)
om learn [topics…] · om learn harvest [dir]         # Read/extract user preferences & film lessons
om doctor                                           # Check Node (>=22), FFmpeg, and Chrome renderer
```

---

## Installing the CLI

The renderer is `huashu-motion` (npm, MIT). The documents here call the command `pulupulu` because a rebranded
local build is what they were written against; the upstream command is `om`, and both accept the same flags.

```sh
npm install -g huashu-motion@0.5.1     # puts `om` on PATH
om --version
```

- **Never call `npx` per command.** A network round trip on every `check`, `still`, `sound` and `render` is the
  most common self-inflicted slowdown in this workflow; a 60 s film makes dozens of those calls.
- **If a shell has not picked the binary up:** `npm prefix -g` prints the install prefix — the binaries are in
  that folder on Windows and in its `bin/` on macOS and Linux. `node <prefix>/cli/om.js <cmd>` runs it directly.
- **State:** the CLI writes per-user state under `~/.<cli-name>/` (for example `soundtracks.jsonl`). Renders and
  stills use the Chrome already installed on the machine; nothing is uploaded.
- **Pinning:** versions up to and including 0.6.x accept the flags documented in this skill. If a flag is
  rejected, `om --help` for that install is the authority.
