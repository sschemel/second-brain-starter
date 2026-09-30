---
name: tab-color
description: Changes the background color of the iTerm2 session this agent is running in (not whichever tab has focus) as a visual cue for which project or context that session is working on (e.g. /tab-color cloudflare orange, /tab-color reset). Use when the user asks to change the tab, session, background, or terminal color, or names a brand or theme color for their terminal. Not for editor or syntax themes.
argument-hint: "[context or color | reset]"
disable-model-invocation: true
model: sonnet
---

# Tab Color

Requested: $ARGUMENTS

Color **this agent's own session**, never "the current session": that's whichever tab has focus, which may be a different project. Agent shells aren't attached to the visible pty, so ANSI/OSC escape sequences never reach the window. The bundled script finds this session's tty and sets that iTerm2 session's color through AppleScript.

1. Resolve the color: a brand ("Cloudflare orange", "AWS blue"), a theme, a project name (pick a stable, distinct hue for it), or `reset`/`default` (use `0 0 0`).
2. Convert it to a **dark, readable 16-bit RGB** (0–65535 per channel). Keep every channel under about 15000 so light text stays legible. Examples: dark orange `15000 5000 0`, dark red `14000 1500 1500`, dark blue `0 4000 10000`.
3. Run `set-color.sh`, which sits next to this `SKILL.md`. From the vault root:
   ```bash
   bash ".agents/skills/tab-color/set-color.sh" R G B
   ```
   If the skill is linked globally (for example `~/.claude/skills/tab-color`), use that folder's copy of the script instead.
4. Relay the script's one-line output. If it exits non-zero (no terminal, iTerm2 not running, or the session lives in another terminal such as Cursor's), say so plainly and don't claim success.
