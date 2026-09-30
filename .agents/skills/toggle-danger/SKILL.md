---
name: toggle-danger
description: Toggles "danger mode" (auto-approve all agent actions) on or off for Claude Code, the Cursor CLI, or Antigravity (agy) by running 99 - System/scripts/toggle-danger.sh. Use only when the user types /toggle-danger or explicitly asks to flip auto-approve or permission mode.
argument-hint: "[claude|cursor|antigravity] [on|off|toggle|status]"
disable-model-invocation: true
model: sonnet
---

# Toggle Danger

Arguments: $ARGUMENTS. The first is the harness; if it's missing, use the one you are running in (`claude` in Claude Code, `cursor` in Cursor, `antigravity` in agy). The second is the action: `on`, `off`, `toggle` (the default), or `status`. `status` on its own reports every harness.

1. Run `bash "99 - System/scripts/toggle-danger.sh" <harness> <action>` from the vault root. It needs `jq`.
   - `on` checks the config first, then saves a timestamped backup (`*.bak-YYYYMMDD-HHMMSS`, never overwritten) and a restore record in `~/.local/state/second-brain/toggle-danger/<harness>.json` (user-only permissions, shared across vaults), and only then edits the config. The file's permissions are preserved.
   - `off` undoes only those changes, so rules or modes you had before stay intact.
   - If danger mode was enabled some other way, or the config can't be read, `off` refuses and explains.
2. Relay the script's output verbatim. Don't claim a state the script didn't print.
3. Explain the scope in one line:
   - **Claude Code**: it changes the default mode for *new* sessions (`~/.claude/settings.json`). The current session keeps its mode; **Shift+Tab** cycles it right now.
   - **Cursor**: it changes Cursor CLI rules only. The IDE's auto-run toggle is in Settings > Agents.
   - **Antigravity**: it edits the allow-list in `~/.gemini/antigravity-cli/settings.json`. For a one-off session, use `agy --dangerously-skip-permissions` instead.
4. Use `status` to report the state without changing anything: `enabled` (all wildcard rules present), `partial` (some), `disabled`, or `unknown`. It exits 2 if a config is unreadable or has unexpected types, or if `jq` is missing.

Never run this on your own initiative, even to get past a permission prompt.
