# Publishing this skill

Owner: publishing a skill as an installable package


One commit, forced push, version frozen at 1.0, and release notes that describe the state rather than a delta.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 15. Publishing this skill

This directory is also the public repo. Repo shape, the `.gitignore` that keeps heavy sample media out, the publish/tag/release commands, the footprint-scrub procedure (including the orphan-branch history rewrite) and the one licence line that must stay: `references/publishing.md`.

**Only when the user asks to publish.** History is always ONE commit, rewritten on every update (`references/publishing.md` §2b) — the version stays `1.0` and the tag stays `v1.0`, then `scripts/publish-squash.sh <skill dir> <message file>`, then prove it: remote SHA equals local HEAD and `gh api repos/<owner>/<repo>/commits --jq 'length'` prints 1.

**Release notes are a technical changelog — `Fixed` / `Changed` / `Added` / `Verified`, one line per change.** The body says what moved in the tree and names the file or command that moved it; it does not argue policy. A licence decision, an attribution choice or a rationale never belongs in a release body — the legal text lives in `LICENSE` and the notices file, and the note says only that the notices file was added or the copyright line shortened. Notes that editorialise come back to be rewritten even when the change behind them was accepted, so write the changelog first. Verify the body after publishing by fetching it back (`gh release view <tag> --json body --jq .body`) and grepping it for the words that should not be in it.

**The message argument is a FILE, and passing it inline strands the repo.** The script checks out a commitless orphan branch (`__single`) first, so when the second argument is a string instead of a path, `git commit -F "<that string>"` fails on a too-long filename and leaves the working tree on `__single` with **zero commits** — `git checkout main` then aborts on the dirty tree and nothing is pushed. The script now validates the file before it touches the branch; if you inherit the broken state, recover with `git add -A && git commit -F <msgfile> && git branch -M main && git push -f origin main`, then re-tag: `git tag -fa v1.0 -m "…" && git push -f origin v1.0`. Do the work in the same turn as the edit once publishing is wanted; say that the force push invalidates existing clones, and that old commits stay reachable by SHA until GitHub's GC runs.

**The repo carries no per-file credit marks; the prose is English-only** (`references/publishing.md` §1b). A credit stamped into every source file is noise in a skill people read — it pushes real content down a line on every page and makes the repository look like a concatenation of other people's files — so the owner's mark lives on the delivered film (`scripts/add_watermark.py`), in the `LICENSE` copyright line and in the notices file, and `scripts/stamp_credit.py` runs only when the owner explicitly asks. When asked to remove the stamps, delete only standalone credit comments and keep the functional mentions (a default `--text` value, a docstring, a table row documenting the stamper); match line-by-line, then prove it: `git grep` for the three comment forms must return zero and every `.py` must still compile. Foreign-language words survive only as a tool's own data (a detector's stopword list, an expander's spoken-digit table), and every such block needs a comment saying so. When the user says the repo must contain no foreign language, they mean the prose — rewrite quoted examples in English and describe the incident instead of repeating the quote.

**A one-commit history is a reason to delete superseded docs, not to archive them.** An `_archive/` or
`references/_history/` folder keeps an old router or an outdated contract inside the shipped tree, and the
justification for it ("preserve the lineage") does not survive the squash: there is no history in the repo for
the archive to sit on top of, so it preserves nothing and ships a dead instruction set. Moving it out of
`references/` is not enough — a link audit only proves that **nothing links to it**, while the way an agent
actually reads a repo is a free-text search, which lands on the archived page and follows its rules. Keep the
file outside the repo if it must exist at all, then prove the published tree:

```sh
git ls-tree -r --name-only HEAD | grep -ci archive     # must print 0
```

**Merging another library in, or translating this one, is a procedure — follow it from the sourcing skill.** `agent-skill-sourcing` §6 plus its `agent-skill-sourcing:references/rebrand-and-translate.md` — in that skill's tree, not this repo — carry the order (namespace each source, write the routing index yourself, neutralise vendor upsells, rebrand minimally, scrub prose but keep the copyright notice, rewrite history, verify from a fresh clone) and the bulk-translation wave recipe (measure the volume, ~10 subagents one directory each with a numeric-token diff, then one parent-owned rename-and-relink pass, then `node --check` / `ast.parse` / `json.load` over the whole tree). Two failures from doing it casually: a blind token replacement turned an identifier into a syntax error, and a renamed asset left a dangling `src`.
