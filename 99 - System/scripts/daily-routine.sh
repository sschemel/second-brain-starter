#!/bin/bash
# Daily rhythm for Claude Code: makes /sod (and the catch-up harvest of a missed /eod) run on its own.
# Wired in the vault's .claude/settings.json:
#   daily-routine.sh session   SessionStart (startup|resume|clear)
#   daily-routine.sh prompt    UserPromptSubmit (catches long-running sessions that cross midnight)
# Fires at most once per day across all sessions: the first session to see a day without
# "## 🎯 Priorities" in today's note claims a lock and is told to run /sod. If that session never
# writes the note, the lock expires after LOCK_TTL and the next session gets the nudge instead.
# Never blocks anything; exits 0 silently when there is nothing to do or data is missing.
set -uo pipefail

MODE="${1:-session}"
VAULT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE_DIR="$HOME/.claude/state/daily"
LOCK_TTL=7200 # seconds

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }  # GNU first: GNU stat -f means file system

command -v jq >/dev/null 2>&1 || exit 0
input="$(cat)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
case "$cwd" in "$VAULT"|"$VAULT"/*) ;; *) exit 0 ;; esac   # vault sessions only

today="$(date +%F)"
note="$VAULT/01 - Daily Chats/$today.md"
grep -q '^## 🎯 Priorities' "$note" 2>/dev/null && exit 0  # SOD already ran today

mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
lock="$STATE_DIR/$today.sod"
if ! mkdir "$lock" 2>/dev/null; then
  age=$(( $(date +%s) - $(mtime "$lock") ))
  [ "$age" -gt $LOCK_TTL ] || exit 0  # another session owns today's SOD
  touch "$lock"
fi
find "$STATE_DIR" -maxdepth 1 -name '*.sod' -mtime +7 -exec rmdir {} + 2>/dev/null

# Is a catch-up harvest owed? (missed /eod: unharvested learnings, no EOD summary, or a stale backup)
reasons=()
# Count entries outside the template's HTML comment block.
learn=$(awk '/<!--/{c=1} !c && /^(### |- \*\*Failure Mode)/{n++} /-->/{c=0} END{print n+0}' "$VAULT/00 - Inbox/Learnings.md" 2>/dev/null)
[ "${learn:-0}" -gt 0 ] && reasons+=("$learn unharvested entries in 00 - Inbox/Learnings.md")
prev="$(ls "$VAULT/01 - Daily Chats/" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | sort | awk -v t="$today.md" '$0 < t' | tail -1)"
if [ -n "$prev" ] && ! grep -q '^## 🌙 EOD Summary' "$VAULT/01 - Daily Chats/$prev" 2>/dev/null; then
  reasons+=("no EOD summary in ${prev%.md}")
fi
if grep -q '^backup: enabled' "$VAULT/99 - System/memory/backup.md" 2>/dev/null; then
  last="$(git -C "$VAULT" log -1 --format=%ct 2>/dev/null)"
  if [ -n "$last" ] && [ $(( $(date +%s) - last )) -gt 129600 ]; then
    reasons+=("last vault backup $(git -C "$VAULT" log -1 --format=%cr 2>/dev/null)")
  fi
fi

catchup=""
if [ ${#reasons[@]} -gt 0 ]; then
  joined="$(printf '%s; ' "${reasons[@]}")"
  catchup=" A catch-up is owed (${joined%; }), so include the SOD skill's step 1b (catch-up harvest)."
fi

ctx="DAILY ROUTINE: this is the first vault session of $today and /sod has not run yet. Run the sod skill (.agents/skills/sod/SKILL.md) now, briefly, before or alongside the user's request.${catchup} If you are mid-operation on something time-critical, finish that step first, then run it. Skip it only if the user's message says to."
jq -n --arg msg "☀️ First session of $today: running /sod${catchup:+ + catch-up harvest}" --arg ctx "$ctx" \
  --arg ev "$([ "$MODE" = prompt ] && echo UserPromptSubmit || echo SessionStart)" \
  '{systemMessage: $msg, hookSpecificOutput: {hookEventName: $ev, additionalContext: $ctx}}'
exit 0
