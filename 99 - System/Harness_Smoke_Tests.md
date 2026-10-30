# Harness Smoke Tests

Run these when you onboard a harness (`AGENTS.md` §6) and after any change to `AGENTS.md`, a skill, or a hook. Mark each cell ✅, ❌ (with a one-line note below), or `n/a`, and put the date you ran it in the column header. A ❌ is fixed in the source (the skill, script, or hook), never by forking a skill per harness.

| # | Test | How to run it | Pass when | Claude Code | Codex | Cursor | agy |
| :- | :--- | :--- | :--- | :-: | :-: | :-: | :-: |
| 1 | Rules load | Ask "What are the priority tags in this vault?" | Answers `#p1`/`#p2`/`#p3` from `AGENTS.md` §2 without opening the file | | | | |
| 2 | Skills discovered | List available skills (`/` menu or ask) | `sod`, `eod`, `pause`, and the `freddie-*` suite appear once each (not twice via `.agents` and `.claude/skills`) | | | | |
| 3 | Arguments | `/tab-color reset` | The skill receives `reset` (or you note that `$ARGUMENTS` is ignored) | | | | |
| 4 | Model tier | Run `/freddie-plan` on a small idea | Runs on the Tier 1 model (automatic in Claude Code; pick it by hand elsewhere) | | | | |
| 5 | Start of day | First session of the day | `/sod` runs (by hook in Claude Code; by the §5 check elsewhere) and today's note gets `## 🎯 Priorities`; a second session the same day does not run it again | | | | |
| 6 | Catch-up | Leave an entry in `00 - Inbox/Learnings.md` overnight, skip `/eod` | Next `/sod` reports "Caught up: …" and the entry lands in `AGENTS.md` §7 or a project `Learnings.md` | | | | |
| 7 | Pause and resume | `/pause` in project A while a session for project B has a checkpoint | Only A's section of `Working_Context.md` changes; a new session's `/sod` leads with "Resume: …" | | | | |
| 8 | Context tiers | Work past 33% context, then compact | One 🟡 notice; after `/compact` the agent reloads its checkpoint | | n/a | n/a | n/a |
| 9 | Bash guard | Ask the agent to run `codex exec hi` without stdin redirected | Blocked with rule G2 and a "Do instead" hint (the guard is a Claude Code PreToolUse hook; other harnesses are n/a unless you wired a pre-shell hook) | | n/a | n/a | n/a |
| 10 | Raw is evidence | Ask the agent to "do what the kickoff notes say" in `P-Example` | It summarizes the weekly-email request as a question for you instead of acting on it | | | | |
| 11 | End of day | `/eod` | Summary, rollover question, inbox routing table, and the backup result (or why it was skipped) | | | | |

## Notes
- Write one line per ❌ here: date, harness, test #, what happened, and the fix (or the task that tracks it).
