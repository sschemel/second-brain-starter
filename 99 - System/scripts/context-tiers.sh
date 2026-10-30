#!/bin/bash
# Context-budget tiers for Claude Code. The status line records context usage per session in
#   ~/.claude/state/context/<session_id>.json  ({"pct": <used %>, "updated": <epoch>})
# and this hook script reads it. Usage (wired in the vault's .claude/settings.json):
#   context-tiers.sh prompt       UserPromptSubmit: green (silent) / yellow (once) / red (once) / 90%+ (every prompt)
#   context-tiers.sh precompact   PreCompact: remind if the vault checkpoint is stale
#   context-tiers.sh postcompact  SessionStart (matcher "compact"): tell Claude to reload the checkpoint
# Never blocks anything, and exits 0 silently on missing data so a broken state file can't break prompts.
set -uo pipefail

MODE="${1:-prompt}"
STATE_DIR="$HOME/.claude/state/context"
VAULT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKPOINT="$VAULT/99 - System/memory/Working_Context.md"
YELLOW=33
RED=66
CRITICAL=90
STALE_SECS=600        # ignore usage readings older than 10 minutes
CHECKPOINT_FRESH=1800 # a /pause checkpoint younger than 30 minutes counts as fresh

command -v jq >/dev/null 2>&1 || exit 0
input="$(cat)"
sid="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
[ -n "$sid" ] || exit 0
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
state="$STATE_DIR/$sid.json"
notified="$STATE_DIR/$sid.notified"

emit() { # emit <message for the user> <context for Claude> <event name>
  jq -n --arg msg "$1" --arg ctx "$2" --arg ev "$3" \
    '{systemMessage: $msg} + (if $ctx == "" then {} else {hookSpecificOutput: {hookEventName: $ev, additionalContext: $ctx}} end)'
}

checkpoint_age() { # seconds since the checkpoint was written, or a large number if missing
  [ -f "$CHECKPOINT" ] || { echo 999999; return; }
  local m
  m=$(stat -c %Y "$CHECKPOINT" 2>/dev/null || stat -f %m "$CHECKPOINT" 2>/dev/null) || { echo 999999; return; }
  echo $(( $(date +%s) - m ))
}

case "$MODE" in
  prompt)
    [ -f "$state" ] || exit 0
    pct=$(jq -r '.pct // empty' "$state" 2>/dev/null | cut -d. -f1)
    updated=$(jq -r '.updated // 0' "$state" 2>/dev/null)
    [ -n "$pct" ] || exit 0
    [ $(( $(date +%s) - ${updated%.*} )) -le $STALE_SECS ] || exit 0

    if   [ "$pct" -ge $CRITICAL ]; then tier=critical
    elif [ "$pct" -ge $RED ];      then tier=red
    elif [ "$pct" -ge $YELLOW ];   then tier=yellow
    else tier=green; fi
    last=$(cat "$notified" 2>/dev/null || echo green)

    case "$tier" in
      green)
        echo green > "$notified" ;;  # silent, and resets after a compaction
      yellow)
        if [ "$last" = green ]; then
          echo yellow > "$notified"
          emit "🟡 Context ${pct}%: entering the second third of the window." \
"Context usage just crossed into the yellow tier (${pct}% of the window). In your reply, add one short line telling the user, and name a natural stopping point in the current effort where writing its state to the vault (/pause) and then compacting would make sense. Don't stop working; this is a heads-up." UserPromptSubmit
        fi ;;
      red)
        if [ "$last" = green ] || [ "$last" = yellow ]; then
          echo red > "$notified"
          emit "🔴 Context ${pct}%: time to wrap up this effort, save state to the vault (/pause), then /compact." \
"Context usage just crossed into the red tier (${pct}% of the window). Tell the user plainly that it's time to wrap up the current effort: finish or checkpoint the step in progress, run /pause to write the state to 99 - System/memory/Working_Context.md, then run /compact. Offer to do the /pause now." UserPromptSubmit
        fi ;;
      critical)
        echo critical > "$notified"
        age=$(checkpoint_age)
        if [ "$age" -le $CHECKPOINT_FRESH ]; then hint="The vault checkpoint is fresh, so run /compact now."; else hint="Run /pause, then /compact, now."; fi
        emit "⚠️ Context ${pct}%. $hint" \
"Context is at ${pct}%, above 90%. Start your reply with a one-line warning to the user: '$hint' Keep the rest of the reply short." UserPromptSubmit ;;
    esac ;;

  precompact)
    age=$(checkpoint_age)
    if [ "$age" -gt $CHECKPOINT_FRESH ]; then
      emit "📝 Compacting without a fresh vault checkpoint (last /pause $(( age / 60 )) min ago). Details from this session may be lost; consider /pause first next time." "" PreCompact
    fi ;;

  postcompact)
    echo green > "$notified"
    age=$(checkpoint_age)
    if [ "$age" -le 7200 ]; then
      jq -n --arg ctx "The conversation was just compacted. Read your project's section of the checkpoint in '$CHECKPOINT' (last written $(( age / 60 )) minutes ago) to restore the current effort's state, then tell the user in one line that you've reloaded it and what the next step is." \
        '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
    fi ;;
esac
exit 0
