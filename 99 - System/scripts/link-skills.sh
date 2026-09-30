#!/bin/bash
# Expose the vault's skills (SSOT: .agents/skills/) to Claude Code via per-skill
# symlinks in .claude/skills/. Codex, Cursor, and Antigravity read .agents/skills/
# natively when the vault is the open workspace.
#
# Usage: link-skills.sh [--cursor]
#   --cursor  also link the Freddie suite into ~/.cursor/skills/ so it works in
#             every repo Cursor opens (opt-in: it writes outside the vault).
#
# Safe to re-run after adding or removing a skill. It never overwrites a real
# file or directory, and it warns and skips when a destination already exists
# and points somewhere else.
set -euo pipefail

WITH_CURSOR=false
for arg in "$@"; do
  case "$arg" in
    --cursor) WITH_CURSOR=true ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)" >&2; exit 1 ;;
  esac
done

VAULT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS="$VAULT/.agents/skills"

# link_one <target> <link-path> <label>
link_one() {
  local target="$1" link="$2" label="$3"
  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$target" ]; then
      echo "ok ($label): $(basename "$link")"
    else
      echo "warn ($label): $link already links to $(readlink "$link"); skipped" >&2
    fi
  elif [ -e "$link" ]; then
    echo "warn ($label): $link is a real file or directory; skipped" >&2
  else
    ln -s "$target" "$link"
    echo "linked ($label): $(basename "$link")"
  fi
}

# remove_dangling <dir> <glob> <label>: remove broken symlinks that point into this
# vault's .agents/skills/. Broken links pointing anywhere else are left alone, with a warning.
remove_dangling() {
  local dir="$1" pattern="$2" label="$3" link target
  for link in "$dir"/$pattern; do
    [ -L "$link" ] && [ ! -e "$link" ] || continue
    target="$(readlink "$link")"
    case "$target" in /*) ;; *) target="$dir/$target" ;; esac
    case "$target" in
      "$SKILLS"/*|"$VAULT/.claude/skills/../../.agents/skills/"*)
        rm "$link"; echo "removed stale ($label): $(basename "$link")" ;;
      *) echo "warn ($label): $link is broken and points outside this vault ($(readlink "$link")); left alone" >&2 ;;
    esac
  done
}

# Claude Code: vault-local links.
mkdir -p "$VAULT/.claude/skills"
remove_dangling "$VAULT/.claude/skills" "*" "claude"
for dir in "$SKILLS"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue
  if [ -e "$HOME/.claude/skills/$name" ] || [ -L "$HOME/.claude/skills/$name" ]; then
    echo "skip (global ~/.claude/skills has $name)"; continue
  fi
  link_one "../../.agents/skills/$name" "$VAULT/.claude/skills/$name" "claude"
done

# Cursor (opt-in): global links for the Freddie suite only.
if $WITH_CURSOR; then
  mkdir -p "$HOME/.cursor/skills"
  remove_dangling "$HOME/.cursor/skills" "freddie-*" "cursor"
  for dir in "$SKILLS"/freddie-*/; do
    name="$(basename "$dir")"
    [ -f "$dir/SKILL.md" ] || continue
    link_one "${dir%/}" "$HOME/.cursor/skills/$name" "cursor"
  done
else
  echo "(Cursor global links skipped; re-run with --cursor to add them.)"
fi
