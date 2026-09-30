---
name: freddie-learn
description: Logs a behavior correction, failure mode, or new workflow rule to 00 - Inbox/Learnings.md so it is folded into AGENTS.md at the next /eod. Use when the user types /freddie-learn, corrects how the agent did something ("don't do it that way", "always…", "never…"), or edits the agent's output to fix a mistake.
argument-hint: "[rule or correction]"
model: sonnet
---

# Freddie-Learn: Capture a Correction

Correction or rule: $ARGUMENTS (if empty, infer it from the user's most recent correction in this conversation).

1. Distill it into a **failure mode** (what went wrong, specifically) and a **corrected rule** (an imperative that is reusable beyond this one case).
2. Read `00 - Inbox/Learnings.md` and check for an existing entry on the same topic. If one exists, sharpen that entry instead of adding a duplicate.
3. Append the entry (get the date from `date +%F`):
   ```markdown
   ### 📅 YYYY-MM-DD - <Topic>
   - **Failure Mode**: <what happened>
   - **Rule**: <the corrected instruction>
   ```
4. Scrub anything secret-shaped (keys, tokens, customer data) before writing.
5. If invoked automatically mid-task, do it silently and keep working. If invoked by `/freddie-learn`, confirm in one line that it is stashed for the next `/eod` sweep.
