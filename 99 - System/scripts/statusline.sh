#!/bin/bash
# Claude Code status line. Besides printing the line, it records each session's context usage in
#   ~/.claude/state/context/<session_id>.json  ({"pct": <used %>, "updated": <epoch>})
# because hooks don't receive it; context-tiers.sh reads that file. Wired in the vault's
# .claude/settings.json ("statusLine"). Needs jq.
input=$(cat)
command -v jq >/dev/null 2>&1 || { echo "statusline: jq not found"; exit 0; }

sid=$(jq -r '.session_id // empty' <<<"$input")
used=$(jq -r '.context_window.used_percentage // empty' <<<"$input")
if [ -n "$sid" ] && [ -n "$used" ]; then
  ctx_dir="$HOME/.claude/state/context"
  [ -f "$ctx_dir/$sid.json" ] || { mkdir -p "$ctx_dir"; find "$ctx_dir" -type f -mtime +7 -delete 2>/dev/null; }
  printf '{"pct": %s, "updated": %s}\n' "$used" "$(date +%s)" > "$ctx_dir/$sid.json.tmp" && mv "$ctx_dir/$sid.json.tmp" "$ctx_dir/$sid.json"
fi

cwd=$(jq -r '.workspace.current_dir // .cwd // empty' <<<"$input")
branch=$(git -C "$cwd" branch --show-current 2>/dev/null)

jq -r -j --arg branch "$branch" '
  def tier(p): if p >= 90 then "⚠️ " elif p >= 66 then "🔴" elif p >= 33 then "🟡" else "🟢" end;
  def bar(p): ((p / 10) | floor) as $f | ([range(0; $f)] | map("█") | join("")) + ([range($f; 10)] | map("░") | join(""));
  (.context_window.used_percentage // 0 | round) as $pct |
  "🧠 \(.model.display_name // "?")  │  \(tier($pct)) \(bar($pct)) \($pct)%  │  📂 \((.workspace.current_dir // .cwd // "") | split("/") | last)"
  + (if $branch != "" then " (\($branch))" else "" end)
  + (if .permission_mode == "bypassPermissions" then "  │  ⚠️  BYPASS ON" else "" end)
' <<<"$input"
