# Publishing this skill as a GitHub repo

Owner: publishing this skill repository

The skill directory **is** the repository. This is the procedure for putting it on GitHub, and for
re-publishing it after a rebrand without leaking anything that should not be public.

## 1. Repo shape

```
SKILL.md          the entry point an agent loads
README.md         what it is, three layers, requirements, quick start, repo map
LICENSE           MIT text, one copyright line per rights holder
NOTICE.md         provenance of merged work (only if the rights holders must be named)
.gitignore        heavy sample media, render output, TTS cache
references/       topical depth (art-motion, ui-motion, narration, 2d-vector-motion, …)
scripts/          runnable helpers (tts-prosody, lang-audit, art-motion gates + engine)
```

`.gitignore` essentials — a skill repo should clone in seconds:

```gitignore
.om/
out/
assets/mix.wav
assets/voice.wav
.tts-cache/
__pycache__/
*.mp4
*.mov
*.webm

# sample films: keep the code, drop the heavy media
scripts/art-motion/engine/demos/**/*.png
scripts/art-motion/engine/demos/**/*.jpg
scripts/art-motion/engine/demos/**/*.wav
scripts/art-motion/engine/reference_films/**/*.png
scripts/art-motion/engine/reference_films/**/*.jpg
scripts/art-motion/engine/reference_films/**/*.wav
```

Keep `engine/lib/` (the vendored JS the style recipes render with) and keep the *code* inside `demos/`
and `reference_films/` — the reference documents cite files there (`demos/long_scroll/lib/acts.js`,
`reference_films/<name>/render.py`), so a directory-wide ignore publishes a repo whose docs point at
nothing. Sample *media* is what gets cut, not directories:

## 1b. One credit line, in LICENSE — never a stamp on every file

**Do not put a `by <owner>` comment on line 1 of every source file.** A repository-wide stamp pass is the
default this user has explicitly reversed; treat their absence as the standing shape.

| Credit carrier | What it holds |
|---|---|
| `LICENSE` | the copyright line (owner + year) and the MIT text — the file nobody reads for branding |
| `README.md` | one line under `## Licence` pointing at `LICENSE` |
| the *delivered film* | a rendered watermark, `scripts/add_watermark.py`, inside the delivery encode |

Why the stamps are worse than nothing: they push real content down a line in every reference page, make
the repository read like a concatenation of other people's files, and restate a fact `LICENSE` already
carries once. A mark in the wrong place on a frontmatter file can also silently unregister the skill.

`scripts/stamp_credit.py` stays in the repo because the owner may want per-file marks on a specific
project — but only when they ask for it, never as a publish step.

**Removing them without collateral damage.** Match only a line that is *nothing but* the comment
(`^\s*(//|#)\s*by <owner>\s*$`, `^\s*<!--\s*by <owner>\s*-->$`). These are **behaviour, not stamps**, and
deleting them breaks a script or a doc:

- a default argument value (`default="by <owner>"`) and the docstring that documents it;
- a table row in `SKILL.md` describing the stamper script;
- a generated marker file an installer writes.

Then prove nothing moved: `git grep -c` the marker and read every remaining hit, no shebang lost line 1,
every `.py` compiles, every `.json` parses, no file now starts with a blank line.

**Prose is English; only a tool's data may stay in the target language.** An Indonesian film is not an
Indonesian repository: examples, beat tables, post-mortem quotes and UI sample copy in the docs all get
rewritten in English, describing the incident instead of quoting it. What legitimately remains is the
*data a tool needs in order to work* — a stopword list inside a language detector, a spoken-digit table
inside a TTS expander, a `{lang: "oh" | "kosong"}` mapping. Two consequences:

1. Give each such block a comment that says what it is and why it must stay, or a later "clean the
   language" pass deletes the detector and the tool fails silently on the next film.
2. Grep for a short list of unmistakable function words rather than trusting your ear — sweep `.md .py
   .js .sh .html .css` for whole-word matches, then read every hit: quoted foreign copy is a real hit and
   needs rewriting, while `film`, `video`, `data` and a person named `Dan` are false positives that must
   survive the sweep.

## 1c. The README that gets a beginner to a first film

The README is an install guide, not a brochure. Its reader has never seen the skill, does not know a CLI
exists, and will copy the first command block verbatim. Order that works:

1. one paragraph saying what this is, in plain nouns;
2. what it can do **and the refusal list** — a beginner must learn the tool cannot show a real face or
   footage *before* commissioning one, not after a rejection;
3. requirements, each with the command that checks it;
4. install the renderer/CLI;
5. install the skill into each agent;
6. the preflight command and what a failure means;
7. one first task small enough to finish in minutes;
8. copyable example prompts;
9. what a good brief contains;
10. prompts that fail, and why;
11. troubleshooting, keyed to the symptom the reader sees;
12. repo map; 13. licence.

### Resolve every command before you write it down

A dead command in step 4 costs the reader the whole tool. Check the source resolves:

```sh
npm view <package> version        # 404 means nothing exists under that name
npm view <package> bin engines    # what it installs, and the runtime it needs
npm view <package> versions       # is the version you are about to pin real?
```

**A rebranded or forked CLI installs under its upstream's name, not the rebrand's.** Read the vendored
build's `package.json` (`description`, `homepage`, `author`) and its `THIRD_PARTY.md` — those three name the
real package and every licence it carries. Then the README says plainly: this skill drives `<upstream>`, the
in-repo documents call the command `<rebrand>` because the author runs a rebranded local build, and both
names run the same program with the same flags. Pin the version the commands were tested against, and point
at `--help` as the authority for anything newer.

### Enumerate capabilities from the tool, never from memory

Template, subcommand and flag names invented from memory publish as examples that cannot run, and a novice
blames themselves for it. Ask the binary (`<cli> templates`, `<cli> --help`, `--version`), then write the
list into the README only where it matches what the tool prints. Re-check it whenever the version moves: a
renamed template turns every example prompt in the file into a dead end.

### A support list is a claim about the files, not a benchmark

An owner may want the README to name the models or platforms the skill is optimised for. Write the list, then
**say what "optimised" consists of in terms a reader can check** — a router small enough that the whole skill is
never held in context at once, imperative rules instead of description, a proving command named per step, gates
covering the failure modes taste would miss. Never invent scores, deltas or "validated on N films" to support
the list: a fabricated number in a README is worse than no number, and the file properties are the honest reason
the claim is plausible at all. Close with what a reader whose model is *not* on the list should do — run the
cheap verification gate before trusting a long job — instead of implying support you have not measured.

### The per-agent install table

Each tool loads skills from a different place. Put the path the tool actually reads in its own row — a
skills directory that does not exist in the reader's tool is the second most common way an install guide
fails.

| tool | where the skill goes | how it is invoked |
|---|---|---|
| Claude Code | `~/.claude/skills/<name>/` (personal), `.claude/skills/` (project) | `/name`, or by description |
| Codex CLI | `~/.agents/skills/<name>/`; also `.agents/skills/` from cwd up to repo root | by description; disable a skill in `~/.codex/config.toml` with `[[skills.config]]` |
| Gemini CLI | `~/.gemini/commands/<name>.toml` (command) + a `GEMINI.md` pointer | `/name` |
| Cursor | `.cursor/rules/<name>.mdc`, or root `AGENTS.md` | always-on rule, or `AGENTS.md` |
| Windsurf | `.windsurf/rules/` | workspace rules |
| Cline | `.clinerules/` | rules directory |
| GitHub Copilot | `.github/copilot-instructions.md`, or `AGENTS.md` | instructions |
| Hermes | `<data dir>/hermes/skills/<category>/<name>` — `%LOCALAPPDATA%\hermes\skills\…` on Windows | discovered automatically |

For tools with no skill concept (Cursor, Windsurf, Cline, Copilot, Gemini) the install is a three-line
pointer file — *for any `<task class>`, read `<path>/SKILL.md` and follow it* — plus the folder somewhere in
the repo. Say that out loud, and give the pointer text verbatim; otherwise the reader hunts for a skills
directory their tool does not have.

### Prove the file before publishing it

- **Every path named in the README exists** — `test -f` each script and reference it points at. A README
  that promises a file the repo does not ship is worse than a short one.
- **Every anchor resolves under GitHub's slug rule:** lowercase, drop everything except alphanumerics,
  spaces, `-` and `_`, then replace *each* space with one `-`. An em dash therefore leaves a double hyphen,
  and collapsing `\s+` to a single `-` produces a false "broken anchor" report — build the checker to the
  rule, not to intuition.
- **Re-fetch the published file** from `raw.githubusercontent.com` and grep it: the number of examples, the
  install command, and zero hits for the command you removed.

## 1d. Audit the tree for secrets and machine paths before every publish

A rebrand scrub checks for other projects' names; it does not check for **your own** leaks. Two of them ship
silently:

```sh
python scripts/publish_audit.py . --env ~/.env --md README.md --online
```

- **Credentials.** The script sweeps secret *patterns* and, more reliably, matches the tree against the exact
  secret values in your environment file. Compare values, never print them — a key echoed into build output is
  a second leak in a log that is often public too. Because history here is a single commit, `git log -S <value>`
  is cheap proof that a key was never committed.
- **Machine paths.** The local username, the home directory and per-machine install locations (`C:\<tool>\pkg`,
  a scoop shims directory, a dot-directory under the user profile) are not credentials and scan clean under any
  key pattern, but they publish who the author is and exactly where their tooling lives. Fix by **rewriting the
  section, not deleting the sentence**: a "Local install (this machine)" block becomes "Installing the CLI" with
  the portable steps (`npm install -g <upstream>@<pinned>`, `npm prefix -g`, the per-user state directory).

Sweep the whole tree, including `references/_history/` and any archived SKILL.md — historical copies keep old
paths forever, and they are the ones a reader greps when puzzled by a stale instruction.

**But do not ship an archive directory at all.** Keep every superseded page *outside* the repository, in a
sibling folder on disk (`skills/media/_skill-archive/<skill>/`), and let the tree contain only pages a reader
may act on. Two reasons, and the second is the one that bites:

- history here is a **single squashed commit**, so there is no git history for an archive to preserve — the
  folder is a copy of the working directory, which is also in the squash. Nothing is gained.
- a routing audit checks **links**, not content. An `_archive/references-history/skill-md-before-router.md`
  raises no audit failure because nothing points at it, yet any agent that greps the repo — which is exactly
  how a stale instruction gets found — lands on a dead router with its own fifteen outbound rules. Removing it
  from `references/` fixed the link graph and left the actual hazard in place.

When asked why an archive folder exists, that is the honest answer: the move was half right, and the fix is
deletion plus a copy kept locally, not a link sweep.

## 2. Publish

```sh
cd <skill dir>
git init -b main
git add -A
git commit -m "pulupulu-motion 1.0"
gh repo create <name> --public --source=. --remote=origin --push \
  --description "one line that matches README's first sentence"

git tag -a v1.0 -m "<name> 1.0" && git push origin v1.0
gh release create v1.0 --title "<name> 1.0" --notes "what is in the release"
```

Verify from a **fresh clone**, never from the working tree: `git ls-files | wc -l`, and open one file
that matters (`SKILL.md`, `LICENSE`) to confirm the content that landed is the content you wrote.

Before cloning, prove `.gitignore` is not eating referenced files — compare the working tree with the
index, per extension:

```sh
for ext in py md js json; do
  echo "$ext: worktree $(find . -name "*.$ext" -not -path './.git/*' | wc -l) tracked $(git ls-files | grep -c "\.$ext$")"
done
```

A gap with zero untracked files means the ignore rules took them; `git check-ignore -v <file>` names the
rule. And when you `cd` into the clone inside a compound command, that `cd` can fail quietly and leave the
next checks running against the source tree — `cd` as its own step and print `pwd` before trusting the
numbers.

## 2b. Every update: one commit, rewritten (standing rule)

History in this repo is **always a single commit**. Each update re-states the whole tree as the first
commit and force-pushes it — no "Add …" follow-ups, no merge commits, no tags left on dead commits.
Publishing is part of the edit, not a follow-up request: after changing `SKILL.md` or a reference,
commit and push in the same turn without being asked.

**Version and tag never move.** This repo is always `version: "1.0"` / tag `v1.0` / release "1.0" — do
not bump the number on updates. A new update rewrites the commit, re-points the same `v1.0` tag at it,
and **edits** the existing release; the number only changes if the user asks for it.

Recipe — scripted, `scripts/publish-squash.sh <skill-dir> <message-file>` (tag defaults to `v1.0`):

```sh
cd <skill dir>
git checkout --orphan single          # keeps the index, drops the parents
git add -A
git commit -F <message-file>          # message describes the STATE of the skill, not a delta
git branch -M single main
git push -f origin main

git tag -d v1.0 2>/dev/null; git tag -a v1.0 -m "pulupulu-motion 1.0"
git push -f origin v1.0
gh release edit v1.0 --notes "<updated notes>"    # edit, never create a new release
```

Then verify — a force push that printed no error can still leave the repo wrong:

```sh
git ls-remote origin refs/heads/main | cut -f1      # must equal git rev-parse HEAD
git ls-remote --tags origin                        # ONLY the current tag, plus its ^{} line
gh api repos/<owner>/<repo>/commits --jq 'length'  # must print 1
gh release list                                    # old releases gone, current one Latest
```

### The release notes are a changelog, not a commentary

The squashed commit message and the release notes are the same text, and they are **a technical changelog**:
a title line naming the change, then `Fixed` / `Changed` / `Added` / `Removed` / `Verified`, each entry naming
a file, a command or a number.

What never belongs in them: licence or attribution reasoning, why a licence text was chosen, the provenance
story of a rebrand, apologies, and any meta commentary about the process. That material lives in `LICENSE`,
`NOTICE.md` and the README's licence line, where a reader who cares goes looking; repeating it on every
release page buries the three lines a user actually reads. When a change *is* a licence fix, state it as one
technical clause — *"LICENSE: hedge paragraph removed, copyright line reduced to owner and year"* — and stop
there.

Grep the message file before publishing, with word boundaries so `commit` does not count as `MIT`:

```sh
grep -icE '\blicen[cs]|\bMIT\b|copyright|attribution' <message-file>     # want 0
```

What actually goes wrong here:

- **A stale tag keeps an old commit alive and visible.** Deleting the branch ref is not enough —
  enumerate remote tags, delete each one explicitly (`git push origin --delete <tag>`), then re-run
  `git ls-remote --tags`. A batched delete can drop one silently (its stderr was swallowed), and the
  surviving tag drags the pre-rewrite commit back into view.
- **Delete the releases too:** `gh release delete <old-tag> --yes` for every release whose commit no
  longer exists, otherwise the Releases page keeps advertising the old history.
- **Force push rewrites every SHA.** Anyone who cloned must `git fetch && git reset --hard origin/main`.
  State that in the reply instead of presenting the history as merely "updated".
- **Old commits remain reachable by SHA until GitHub's GC runs** — same caveat as §3.4. Do not claim a wipe.
- **Never let the tag and the frontmatter drift.** Frontmatter stays `version: "1.0"` and the tag stays
  `v1.0` forever; if you see `v1.0.3` anywhere, it is a leftover from before this rule.
- **Align the frontmatter version with the tag in the same commit.** A tag reading v1.0.3 over a
  `metadata.version: 1.0.2` is a half-finished publish.

## 3. Removing third-party footprints (rebranding for publication)

When the user wants no trace of the projects a skill was assembled from, scrub in this order. Do the
whole pass in one script so nothing is caught by hand-editing fatigue:

1. **Delete credit-only files:** provenance/NOTICE documents, author bios, per-directory copies of the
   upstream licence.
2. **Rename assets and namespaces that carry a name:** `lib/rig_<vendor>.js` → `scripts/art-motion/engine/lib/rig_legacy.js`,
   `<VENDOR>_CONFIG_HOME` → `<SKILL>_CONFIG_HOME`, config dirs, demo folder defaults. Then update every
   reference to them (`engine/index.html`, docs) — a renamed file with stale references is a broken skill.
3. **Mass-substitute the remaining prose** across `.md .py .js .json .txt .html .css`: project names →
   your skill name, repo URLs → your repo URL, author names → neutral wording. Then **read the result**:
   substitution leaves garbage like "merged from `<own name>` 1.3.1" or "the author / the author", and
   those sentences must be rewritten by hand, not patched again.
4. **Scrub the history, not only the tree.** A clean tree with a dirty log still publishes the names:
   ```sh
   git checkout --orphan clean
   git add -A && git commit -m "<name> v1.0.0"
   git branch -D main && git branch -m main
   git push -f origin main
   git tag -d v1.0.0 && git push origin :refs/tags/v1.0.0
   gh release delete v1.0.0 --yes        # then recreate tag + release on the new commit
   ```
   Note: old commits stay reachable by SHA on GitHub until its garbage collection runs — force-push
   removes them from the branch, not from existence. Say that plainly instead of claiming a wipe.
5. **Verify:** fresh clone, then `grep -ril -E '<terms>' . --exclude-dir=.git | wc -l` must be the
   count you intend (usually 0).

### The licence line you do not remove

MIT requires the copyright notice and permission text to travel with copies and substantial portions.
So: scrub every *name, URL and marketing mention*, and keep **one** copyright line per rights holder
in `LICENSE` (the file nobody reads for branding). Say why, in one sentence, and offer the only
option that removes it entirely: drop the merged directories so the repo contains only your own work.
Stripping the notice while keeping the code is a licence violation, not a rebrand — do not do it
because a user asked for "zero footprint".

**Do not write a hedge in place of the notice.** A line such as *"portions of this repository are derived
from MIT-licensed work; the original authors' notices are on record with the repository owner and are
available on request"* is not part of MIT, cannot be verified by anyone who reads the repository, and
contradicts the licence's own condition that the notice travel with the software. Two honest states only:

1. the repo really does contain upstream work → name each project in `NOTICE.md` with its copyright line; or
2. it contains only the owner's own work → plain MIT with owner and year, and no derivation claim at all.

If which one is true cannot be established from the tree, ask the owner for the upstream names instead of
papering over it — but read the obvious places first, because the tree usually does answer it: a vendored or
rebranded build names its upstream in `package.json` (`description`, `homepage`, `author`) and lists every
bundled licence in its `THIRD_PARTY.md`. Those two files are also where a **not-reusable** component hides —
a bundled cartoon likeness, an NC-licensed plate — and a skill that relaunches such an asset under a plain
MIT licence passes on a restriction it never owned. Name that component as excluded in `NOTICE.md` and in the
README's prompt examples. Keep the copyright line free of project branding (`Copyright (c) <year> <owner>`), and
make `README`'s licence section say the same thing in one line — a README claiming notices "travel with
the licence" while no such file exists is the same defect as the hedge.

## 4. Pitfalls

- **`git tag -d` has no `-q`.** `git tag -d v1.0.0 -q` fails and, inside a `&&` chain, silently skips
  the re-tag — you then push the old tag back and wonder why the release points at the dirty commit.
- **Do not `rm -rf` a directory the shell is currently inside** on Windows: the shell's cwd holds a
  lock and the delete fails with `Device or resource busy`. `cd` out first, or clone the verification
  copy under a fresh name.
- **Git's `LF will be replaced by CRLF` warnings are noise.** They flood the output of a large commit
  and hide the one line that matters; read the last lines, not the middle.
- **A first `gh repo create --source=. --push` also sets upstream tracking.** After a force-push rewrite,
  `git log --oneline origin/main` still shows one clean commit — check that, not `git log` alone.
- **Never publish renders.** `*.mp4` belongs in `.gitignore`; sample films go out as release assets or
  not at all.
- **`git branch -M <name>` force-renames over the existing branch, which is what the orphan rewrite needs;**
  deleting the old branch first is what loses the ref if the push then fails.
- **After a squash publish, compare `git ls-files | wc -l` with the count before it.** `--orphan` keeps the
  index, so `git add -A` re-stages the whole tree; a `.gitignore` that grew since the last publish silently
  drops files from the new single commit.
- **A pre-publish syntax sweep must not write into the tree.** `py_compile.compile(f, cfile=f + ".tmpc")`
  leaves one artifact per file, and the squash commits them if the cleanup ran before the check. Compile to
  a scratch directory outside the repo (`tempfile.mkdtemp()`, or `PYTHONPYCACHEPREFIX`). After every
  publish, `git ls-tree -r HEAD --name-only` and look for anything that is not source.
- **Clean those artifacts by unlinking files, not by a recursive delete.** A `rm -rf` / `find … -exec rm -rf`
  sweep can be refused by the agent runtime's hardline blocklist, which kills the whole compound command before
  the publish runs. Walk with `pathlib` and `unlink()` each `*.pyc`, then `rmdir()` the emptied directories.
- **Run `publish-squash.sh` from the shell tool, not from a Python `subprocess`.** On Windows a bare `bash`
  resolves to the WSL launcher, which prints a UTF-16 help banner about `wsl.exe --list` and exits 0 without
  touching git: the publish looks attempted and nothing was pushed. Invoke it as a shell command; confirm
  afterwards by comparing `git rev-parse HEAD` with `git ls-remote origin refs/heads/main` rather than trusting
  the exit status.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../SKILL.md) · [Art library index](art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
