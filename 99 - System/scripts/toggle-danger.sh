#!/bin/bash
# Reversibly switch "danger mode" (auto-approve agent actions) for one harness.
#
# Usage: toggle-danger.sh [claude|cursor|antigravity] [on|off|toggle|status]
#        toggle-danger.sh status          # every harness
# Defaults: claude, toggle. Requires jq.
#
#   claude      ~/.claude/settings.json                  permissions.defaultMode = "bypassPermissions"
#   cursor      ~/.cursor/cli-config.json                wildcard permissions.allow rules
#   antigravity ~/.gemini/antigravity-cli/settings.json  wildcard permissions.allow rules
#
# `on` validates the config, saves a timestamped backup and a restore record, and only
# then edits the config. `off` undoes exactly what `on` changed. Restore records are per
# user: ${XDG_STATE_HOME:-~/.local/state}/second-brain/toggle-danger/<harness>.json
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/second-brain/toggle-danger"
TMP=""
trap '[ -z "$TMP" ] || rm -f "$TMP"' EXIT

die() { echo "error: $*" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || die "jq is required (brew install jq / apt install jq)."

config_for() {
  case "$1" in
    claude)      echo "$HOME/.claude/settings.json" ;;
    cursor)      echo "$HOME/.cursor/cli-config.json" ;;
    antigravity) echo "$HOME/.gemini/antigravity-cli/settings.json" ;;
    *) return 1 ;;
  esac
}

rules_for() {
  case "$1" in
    claude)      echo '[]' ;;
    cursor)      echo '["Shell(*)","Read(**/*)","Write(**/*)","WebFetch(*)","Mcp(*:*)"]' ;;
    antigravity) echo '["command(*)","read_file(*)","write_to_file(*)","replace_file_content(*)"]' ;;
  esac
}

# Valid = a JSON object whose permission fields have the expected types.
valid_config() {
  jq -e 'type == "object"
    and ((.permissions // {}) | type == "object")
    and ((.permissions.allow // []) | type == "array" and all(type == "string"))
    and ((.permissions.defaultMode // "") | type == "string")' "$1" >/dev/null 2>&1
}

file_mode() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null || echo 600; }

# write_json <file> <mode> <jq args...>: atomic write via a temp file in the same dir.
write_json() {
  local file="$1" mode="$2"; shift 2
  TMP="$(mktemp "$(dirname "$file")/.toggle-danger.XXXXXX")" || return 1
  jq "$@" > "$TMP" || return 1
  chmod "$mode" "$TMP" || return 1
  mv "$TMP" "$file" || return 1
  TMP=""
}

# Prints enabled|partial|disabled|unknown; returns 2 for unknown.
status_of() {
  local h="$1" file present total
  file="$(config_for "$h")"
  [ -e "$file" ] || { echo disabled; return 0; }
  if [ ! -r "$file" ] || ! valid_config "$file"; then echo unknown; return 2; fi
  if [ "$h" = claude ]; then
    if [ "$(jq -r '.permissions.defaultMode // ""' "$file")" = bypassPermissions ]; then echo enabled; else echo disabled; fi
    return 0
  fi
  present="$(jq --argjson r "$(rules_for "$h")" '[(.permissions.allow // [])[] | select(. as $x | $r | index($x))] | unique | length' "$file")"
  total="$(rules_for "$h" | jq length)"
  if [ "$present" -eq "$total" ]; then echo enabled
  elif [ "$present" -gt 0 ]; then echo partial
  else echo disabled; fi
}

state_file() { echo "$STATE_DIR/$1.json"; }

# Prints the restore record, or nothing if there is none. A corrupt record is an error.
state_get() {
  local f; f="$(state_file "$1")"
  [ -e "$f" ] || return 0
  jq -e 'type == "object" and has("file")' "$f" >/dev/null 2>&1 || die "restore record $f is unreadable or invalid."
  cat "$f"
}

turn_on() {
  local h="$1" file st status created=false mode bak="" record
  file="$(config_for "$h")"
  st="$(state_get "$h")"
  if [ -n "$st" ]; then echo "$h: danger mode is already on (enabled by this script)."; return 0; fi
  status="$(status_of "$h")" || die "$file is unreadable or has unexpected types; fix it first."
  if [ "$status" = enabled ]; then echo "$h: already enabled outside this script; nothing changed."; return 0; fi

  # 1. Preflight: every check happens before anything is written.
  mkdir -p "$(dirname "$file")" 2>/dev/null || die "can't create $(dirname "$file")."
  [ -w "$(dirname "$file")" ] || die "$(dirname "$file") isn't writable."
  if [ -e "$file" ]; then
    [ -w "$file" ] || die "$file isn't writable."
    mode="$(file_mode "$file")"
  else
    created=true; mode=600
  fi

  # 2. Record exactly what will change.
  record="$( { if $created; then echo '{}'; else cat "$file"; fi; } | jq -c \
    --arg h "$h" --arg f "$file" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson created "$created" \
    --argjson r "$(rules_for "$h")" '
    (.permissions.allow // []) as $cur
    | { harness: $h, file: $f, enabledAt: $t, created: $created,
      priorModeExisted: ((.permissions // {}) | has("defaultMode")),
      priorMode: (.permissions.defaultMode // null),
      addedRules: [ $r[] | select(. as $x | ($cur | index($x)) == null) ] }')"

  # 3. Backup and restore record first (user-only permissions), then 4. edit the config.
  if ! $created; then
    bak="$file.bak-$(date +%Y%m%d-%H%M%S)"
    [ ! -e "$bak" ] || bak="$bak-$$"
    cp -p "$file" "$bak"
  fi
  (umask 077; mkdir -p "$STATE_DIR"; chmod 700 "$STATE_DIR")
  (umask 077; jq -n --argjson rec "$record" --arg b "$bak" '$rec + {backup: $b}' > "$(state_file "$h")")

  $created && (umask 077; echo '{}' > "$file")
  local edit_ok=true
  if [ "$h" = claude ]; then
    write_json "$file" "$mode" '.permissions.defaultMode = "bypassPermissions"' "$file" || edit_ok=false
  else
    write_json "$file" "$mode" --argjson a "$(jq -c .addedRules <<<"$record")" \
      '.permissions.allow = ((.permissions.allow // []) + $a)' "$file" || edit_ok=false
  fi
  if ! $edit_ok; then
    if $created; then rm -f "$file"; else cp -p "$bak" "$file"; fi
    rm -f "$(state_file "$h")"
    die "editing $file failed; it has been restored and nothing changed."
  fi

  echo "⚠️ $h: danger mode ON."
  [ "$h" != claude ] || echo "   New Claude Code sessions start in bypassPermissions (Shift+Tab changes a running one)."
  [ -z "$bak" ] || echo "   Backup: $bak"
}

turn_off() {
  local h="$1" st status file mode
  st="$(state_get "$h")"
  file="$(config_for "$h")"
  status="$(status_of "$h")" || { echo "$h: status unknown ($file is unreadable or has unexpected types); refusing to change it." >&2; exit 2; }
  if [ -z "$st" ]; then
    if [ "$status" = disabled ]; then echo "$h: danger mode is already off."; return 0; fi
    echo "$h: $status, but not by this script (no restore record). Not changing it; edit $file by hand." >&2
    return 1
  fi
  if [ -e "$file" ]; then
    mode="$(file_mode "$file")"
    if [ "$h" = claude ]; then
      if [ "$(jq -r .priorModeExisted <<<"$st")" = true ]; then
        write_json "$file" "$mode" --argjson p "$(jq -c .priorMode <<<"$st")" '.permissions.defaultMode = $p' "$file"
      else
        write_json "$file" "$mode" 'del(.permissions.defaultMode) | if .permissions == {} then del(.permissions) else . end' "$file"
      fi
    else
      write_json "$file" "$mode" --argjson a "$(jq -c .addedRules <<<"$st")" \
        '.permissions.allow = ((.permissions.allow // []) - $a)
         | if .permissions.allow == [] then del(.permissions.allow) else . end
         | if .permissions == {} then del(.permissions) else . end' "$file"
    fi
    if [ "$(jq -r .created <<<"$st")" = true ] && [ "$(jq -c . "$file")" = "{}" ]; then rm -f "$file"; fi
  fi
  rm -f "$(state_file "$h")"
  echo "🔒 $h: danger mode OFF. Restored the settings from before it was enabled."
}

show_status() {
  local h s rc=0
  for h in "$@"; do
    s="$(status_of "$h")" || rc=2
    echo "$h: $s"
  done
  return "$rc"
}

usage() { echo "Usage: $0 [claude|cursor|antigravity] [on|off|toggle|status]  |  $0 status" >&2; exit 1; }

HARNESS="${1:-claude}"
ACTION="${2:-toggle}"
if [ "$HARNESS" = status ]; then show_status claude cursor antigravity; exit $?; fi
config_for "$HARNESS" >/dev/null || usage

case "$ACTION" in
  on)     turn_on "$HARNESS" ;;
  off)    turn_off "$HARNESS" ;;
  status) show_status "$HARNESS" ;;
  toggle)
    st="$(state_get "$HARNESS")"
    if [ -n "$st" ]; then turn_off "$HARNESS"; else turn_on "$HARNESS"; fi ;;
  *) usage ;;
esac
