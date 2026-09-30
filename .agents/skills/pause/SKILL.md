---
name: pause
description: Context stash. Saves a precise checkpoint of the current work state and next steps to 99 - System/memory/Working_Context.md so work can resume in a new session or a different tool. Use when the user types /pause or /stash, says they need to step away, or asks to save or checkpoint context before a reset or handoff.
argument-hint: "[optional note]"
model: sonnet
---

# Pause / Context Stash

Capture the working state so any agent (Claude Code, Cursor, or other) can resume cold. Extra note from the user: $ARGUMENTS

1. **Capture state**: identify the active project, the repo and branch if code is involved (`git branch --show-current`), the files being edited, what was just done, and what was about to happen next. Include any uncommitted-change caveats.
2. **Write the checkpoint**: overwrite `99 - System/memory/Working_Context.md`. It holds only the latest checkpoint; history lives in daily notes.
   ```markdown
   # Working Context
   **Stashed**: YYYY-MM-DD HH:MM (from `date "+%F %H:%M"`) · **Project**: [[10 - Projects/<P>/_Dashboard]]

   <2–3 sentences: exact current state, then the explicit next step, specific enough to act on without this chat>

   **Open files**: `path`, `path`
   **Repo**: `<path>` @ `<branch>` (omit if n/a)
   ```
3. **Log it**: append a one-line `- ⏸️ HH:MM paused: <topic>` under `## 💬 Sessions` in today's `01 - Daily Chats/YYYY-MM-DD.md` (create the note if needed).
4. **Confirm** in one line. `/sod` will surface this checkpoint automatically.
