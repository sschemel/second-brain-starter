---
name: freddie-learn
description: "Logs a behavior correction, failure mode, or lesson. Global agent-behavior rules go to 00 - Inbox/Learnings.md (folded into AGENTS.md at the next /eod); lessons specific to one project go to that project's Learnings.md. Use when the user types /freddie-learn, corrects how the agent did something (\"don't do it that way\", \"always…\", \"never…\"), edits the agent's output to fix a mistake, or a non-obvious project gotcha is discovered."
argument-hint: "[rule or correction]"
model: sonnet
---

# Freddie-Learn: Capture a Correction

Correction or rule: $ARGUMENTS (if empty, infer it from the user's most recent correction in this conversation).

1. Distill it into a **failure mode** (what went wrong, specifically) and a **corrected rule** (an imperative that is reusable beyond this one case).
2. **Route it.** Pick one destination:
   - **Global** (how agents should behave anywhere: workflow, tone, tooling habits): `00 - Inbox/Learnings.md`. The next `/eod` (or, if that is missed, the next `/sod` catch-up) promotes it into `AGENTS.md` §7.
   - **Project** (true only for one codebase or project, e.g. "this repo's dev server serves stale CSS; restart with a clean build folder"): `10 - Projects/<P>/Learnings.md`. Create the file with a `# <Project> Learnings` heading if it doesn't exist. These stay in the project and are read when working on it. `/eod` only copies a general version into `AGENTS.md` when the lesson holds beyond the project.
   - If it's unclear, prefer **project**. A project lesson that keeps recurring elsewhere can be promoted later.
3. Read the destination file and check for an existing entry on the same topic. If one exists, sharpen that entry instead of adding a duplicate.
4. Append the entry (get the date from `date +%F`):
   ```markdown
   ### 📅 YYYY-MM-DD - <Topic>
   - **Failure Mode**: <what happened>
   - **Rule**: <the corrected instruction>
   ```
5. Scrub anything secret-shaped (keys, tokens, customer data) before writing.
6. If invoked automatically mid-task, do it silently and keep working. If invoked by `/freddie-learn`, confirm in one line where it went (the Inbox for the next `/eod` sweep, or the project's `Learnings.md`).
