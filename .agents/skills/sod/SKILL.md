---
name: sod
description: "Start of Day routine for the Second Brain vault. Resumes paused context, builds an Eisenhower-matrix briefing from #p1/#p2/overdue tasks, and sets up today's daily note in 01 - Daily Chats/. Use when the user types /sod or asks to start their day or for a morning briefing of their vault tasks."
argument-hint: "[optional focus, e.g. 'job search only']"
disable-model-invocation: true
model: sonnet
---

# SOD (Start of Day)

Bootstrap the day. Optional focus from the user: $ARGUMENTS

## 1. Establish dates
Run `date +%F` for TODAY and `date +%A` for the weekday. Never guess the date.

## 2. Resume context
- Read `99 - System/memory/Working_Context.md`. If it holds a `/pause` checkpoint, it is the first thing in the briefing ("Resume: …").
- Find the most recent daily note in `01 - Daily Chats/` dated before TODAY (it may not be yesterday). Read its `## 🌙 EOD Summary` and `## 🔭 Tomorrow` sections for continuity. If none exist, say so and continue.

## 3. Discover tasks
Search `10 - Projects/`, `20 - Areas/`, and `00 - Inbox/` for open tasks (`- [ ]`), using grep rather than reading every file:
```bash
grep -rn --include='*.md' -e '- \[ \]' "10 - Projects" "20 - Areas" "00 - Inbox"
```
Keep a task if any of these is true: tagged `#p1` or `#p2`, has a `📅` date on or before TODAY (overdue or due today), or is tagged `@waiting`. Note each task's project (from its folder) and file:line.

## 4. Build the Eisenhower matrix
| Quadrant | Rule |
| :--- | :--- |
| 🔥 **Do now** (urgent + important) | `#p1`, or any task that is overdue or due today |
| 📅 **Schedule** (important, not urgent) | `#p2` with a future or missing date |
| ⏳ **Waiting / Delegate** | `@waiting` (show how long it has been waiting when the date allows) |
| 🧹 **Later** | overdue `#p3` or untagged overdue tasks that aren't clearly important. List them briefly and suggest re-dating or dropping them. |

If a focus was given, filter to it. Cap 🔥 **Do now** at about 5 items. If more qualify, rank them and flag the overload. Do not modify any task lines during SOD; rescheduling happens at `/eod` or on request.

## 5. Write today's note
Target: `01 - Daily Chats/TODAY.md`.
- **If it doesn't exist**, create it:
  ```markdown
  # TODAY (Weekday)

  ## 🎯 Priorities
  <matrix from step 4, each item as "task text — [[Project/_Dashboard]]">

  ## 💬 Sessions

  ## 🌙 EOD Summary
  ```
- **If it exists**, replace only the `## 🎯 Priorities` section and leave everything else untouched.
- Reference tasks rather than copying them as new checkboxes (SSOT): write plain bullets, not `- [ ]` lines, so the Tasks plugin doesn't double-count them.

## 6. Brief the user
In chat, give a crisp briefing: the resume line (if any), the matrix, and one recommended first move. Keep it scannable, around 15 lines.
