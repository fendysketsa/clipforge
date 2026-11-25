#!/usr/bin/env bash
# publish-squash.sh <repo-dir> <message-file> [tag]   (tag defaults to v1.0)
#
# Publish a skill repo as a SINGLE commit, every time (this user's standing rule).
# Re-states the whole tree as the first commit, force-pushes, keeps exactly one
# tag, and verifies that the remote actually took it.
#
#   bash scripts/publish-squash.sh . /tmp/msg.txt
#
# The message file describes the STATE of the skill, not a delta — there is no
# delta in a one-commit history.
set -euo pipefail

REPO="${1:?usage: publish-squash.sh <repo-dir> <message-file> [tag]}"
MSGFILE="${2:?path to a commit-message file}"
TAG="${3:-v1.0}"   # this repo keeps v1.0 forever

case "$(uname -s)" in
  MSYS*|MINGW*|CYGWIN*) command -v cygpath >/dev/null && MSGFILE_NATIVE="$(cygpath -w "$MSGFILE")" || MSGFILE_NATIVE="$MSGFILE" ;;
  *) MSGFILE_NATIVE="$MSGFILE" ;;
esac

cd "$REPO"
git rev-parse --is-inside-work-tree >/dev/null
git remote get-url origin >/dev/null || { echo "no 'origin' remote" >&2; exit 1; }

# Validate BEFORE touching the branch: an earlier call passed the message inline instead of as a file,
# the orphan checkout succeeded, `git commit -F` then failed on a too-long filename, and the repo was left
# sitting on a commitless __single branch.
[ -f "$MSGFILE" ] || { echo "message file not found: $MSGFILE" >&2
  echo "usage: bash scripts/publish-squash.sh <repo-dir> <message-FILE> [tag]" >&2; exit 2; }
[ "$(wc -c < "$MSGFILE")" -gt 40 ] || { echo "message file looks empty: $MSGFILE" >&2; exit 2; }

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "HEAD" ] && { echo "refusing to publish from a detached HEAD" >&2; exit 1; }

BEFORE_FILES="$(git ls-files | wc -l)"

# 1. re-state the tree as the first commit
if git show-ref --verify --quiet refs/heads/__single; then
  git branch -D __single >/dev/null
fi
git checkout --orphan __single
git add -A
git commit -F "$MSGFILE_NATIVE"
git branch -M "$BRANCH"
git push -f origin "$BRANCH"

# 2. drop every remote tag except the one about to be recreated
STALE_TAGS="$(git ls-remote --tags origin \
  | awk '{print $2}' | grep -v '\^{}' | sed 's#refs/tags/##' || true)"
for t in $STALE_TAGS; do
  [ "$t" = "$TAG" ] && continue
  git push origin --delete "$t" || echo "warn: remote tag $t survived the delete" >&2
  git tag -d "$t" >/dev/null 2>&1 || true
done

# 3. recreate this release's tag on the new commit and force-push it
git tag -d "$TAG" >/dev/null 2>&1 || true
git tag -a "$TAG" -m "$TAG"
git push -f origin "$TAG"

# 4. verify — a force push that printed no error can still leave the repo wrong
HEAD_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | cut -f1)"
printf 'local HEAD    : %s\nremote %-6s : %s\n' "$HEAD_SHA" "$BRANCH" "$REMOTE_SHA"
if [ "$HEAD_SHA" != "$REMOTE_SHA" ]; then
  echo "MISMATCH: origin did not take the force push" >&2
  exit 1
fi
echo "remote tags   : $(git ls-remote --tags origin | grep -v '\^{}' | awk '{print $2}' | tr '\n' ' ')"
echo "tracked files : $(git ls-files | wc -l) (before the squash: $BEFORE_FILES — a drop means .gitignore ate something)"

if command -v gh >/dev/null 2>&1; then
  SLUG="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
  if [ -n "$SLUG" ]; then
    echo "commit count  : $(gh api "repos/$SLUG/commits" --jq 'length')  (must be 1)"
    echo "releases      : $(gh release list 2>/dev/null | awk -F'\t' '{print $3}' | tr '\n' ' ')"
    echo "  remove every stale tag above except $TAG:  gh release delete <old-tag> --yes"
  fi
fi

echo
echo "Done. The force push rewrote all SHAs: existing clones need 'git fetch && git reset --hard origin/main'."
