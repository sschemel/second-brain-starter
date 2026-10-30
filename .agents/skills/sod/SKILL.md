---
name: sod
description: "Start of Day routine for the Second Brain vault. Runs a catch-up harvest if the last /eod was missed, resumes paused context, builds an Eisenhower-matrix briefing from #p1/#p2/overdue dashboard tasks, and sets up today's daily note in 01 - Daily Chats/. Use when the user types /sod, asks to start their day or for a morning briefing of their vault tasks, or the daily-routine hook says /sod hasn't run today."
argument-hint: "[optional focus, e.g. 'job search only']"
model: sonnet
---

# SOD (Start of Day)

Bootstrap the day. Optional focus from the user: $ARGUMENTS

## 1. Establish dates
Run `date +%F` for TODAY and `date +%A` for the weekday. Never guess the date.

## 1b. Catch-up harvest (only when the last /eod was missed)
Run this step when the daily-routine hook says a catch-up is owed, or when any of these is true: `00 - Inbox/Learnings.md` has entries below its heading, the most recent earlier daily note has no `## 🌙 EOD Summary`, or backup is enabled (`99 - System/memory/backup.md`) and the last vault commit (`git log -1 --format=%cr`) is more than a day old. Do these parts of the `eod` skill (`.agents/skills/eod/SKILL.md`), and nothing else:
- **§3 Learnings harvest** (`Learnings.md` entries only, plus the project-learnings and harness-memory scans). Leave `Ideas_Backlog.md` and `Raw_Captures.md` for the next real `/eod`.
- **§5 Backup**, with its secret gate and private-repo check, if backup is enabled. Use the commit message `SOD TODAY: catch-up harvest`.
- Skip the summary and the rollover question. Overdue tasks surface in the matrix below instead, and the missed day's note gets no retroactive summary.
Report it in one line of the briefing ("Caught up: N learnings → AGENTS.md §7, M → project files, backup <hash or skipped>").

## 2. Resume context
- Read `99 - System/memory/Working_Context.md`. If it holds a `/pause` checkpoint, it is the first thing in the briefing ("Resume: …").
- Find the most recent daily note in `01 - Daily Chats/` dated before TODAY (it may not be yesterday). Read its `## 🌙 EOD Summary` and `## 🔭 Tomorrow` sections for continuity. If none exist, say so and continue.

## 3. Discover tasks
Tasks live in each project's `_Dashboard.md` (SSOT), plus `00 - Inbox/` and `20 - Areas/`. Search only those. Specs and plans carry acceptance-criteria checkboxes, often tagged and dated, and they would flood the matrix:
```bash
grep -n -H -e '- \[ \]' "10 - Projects"/*/_Dashboard.md "00 - Inbox"/*.md 2>/dev/null; grep -rn --include='*.md' -e '- \[ \]' "20 - Areas" 2>/dev/null
```
Drop tasks that sit under a heading containing "Archived". Keep a task if any of these is true: tagged `#p1` or `#p2`, has a `📅` date on or before TODAY (overdue or due today), or is tagged `@waiting`. Note each task's project (from its folder) and file:line. Compute "overdue" from each task's own `📅` date against TODAY, never from an earlier note's wording.

**Stale check**: a task is a stale suspect when it is more than 7 days overdue, or when it is `#p1` and undated but its project's recent notes (`Working_Context.md`, the dashboard's newest Staging lines) show the work moved on (merged, superseded, replaced). Collect these into the 🧹 list rather than the 🔥 quadrant.

## 4. Build the Eisenhower matrix
| Quadrant | Rule |
| :--- | :--- |
| 🔥 **Do now** (urgent + important) | `#p1`, or any task that is overdue or due today |
| 📅 **Schedule** (important, not urgent) | `#p2` with a future or missing date |
| ⏳ **Waiting / Delegate** | `@waiting` (show how long it has been waiting when the date allows) |
| 🧹 **Later / stale** | overdue `#p3`, untagged overdue tasks that aren't clearly important, and the stale suspects from step 3. Show a count per project and the 3–5 most suspicious, and offer one batch cleanup (close, re-date, or move under the dashboard's Archived heading). |

If a focus was given, filter to it. Cap 🔥 **Do now** at about 5 items, ranked by what is due soonest and what the active checkpoints in `Working_Context.md` are blocked on. If more qualify, say how many and that the rest are in the dashboards. Do not modify task lines during SOD unless the user accepts the stale-cleanup offer; rescheduling otherwise happens at `/eod` or on request.

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
- **If it exists**, replace only the `## 🎯 Priorities` section and leave everything else untouched. If the note has no section headings yet (sessions often append bare bullets), put `## 🎯 Priorities` under the title and a `## 💬 Sessions` heading above the existing bullets.
- Reference tasks rather than copying them as new checkboxes (SSOT): write plain bullets, not `- [ ]` lines, so the Tasks plugin doesn't double-count them.

## 6. Brief the user
In chat, give a crisp briefing: the catch-up line and the resume line (if any), the matrix, and one recommended first move. Keep it scannable, around 15 lines.
