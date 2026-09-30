---
name: eod
description: End of Day routine for the Second Brain vault. Writes an executive summary to today's daily note, reconciles and rolls over tasks, and enforces Inbox Zero by routing 00 - Inbox/ captures, learnings, and ideas to their homes. Use when the user types /eod or asks to wrap up or close out their day.
disable-model-invocation: true
model: sonnet
---

# EOD (End of Day and Inbox Zero)

Close the day so tomorrow starts clean. Run `date +%F` for TODAY and compute TOMORROW portably: `date -v+1d +%F 2>/dev/null || date -d tomorrow +%F` (BSD/macOS first, then GNU/Linux). Never guess dates.

## 1. Daily summary
- Gather evidence of today's work: this session's conversation, `01 - Daily Chats/TODAY.md`, files changed today (`git -C . log --since=midnight --stat` plus `git status --short`), and tasks completed today.
- Create `01 - Daily Chats/TODAY.md` if it is missing (same skeleton `/sod` uses).
- Under `## 🌙 EOD Summary`, write **3 bullets**: what shipped, which decisions were made, and what is blocked. Be concrete and link project dashboards with `[[...]]`. If the section already has content (a second `/eod` today), update it rather than duplicating it.

## 2. Task reconciliation
Grep open and done tasks across `10 - Projects/`, `20 - Areas/`, `00 - Inbox/`.
- **Completed**: add `✅ TODAY` to any `- [x]` task missing a done date.
- **Rollover candidates**: open tasks with `📅` ≤ TODAY. Present them as one numbered list and propose a date for each (default TOMORROW; skip weekends for work projects). Ask **once** for confirmation or edits, then apply them. Do not silently re-date tasks, because the due date is signal.
- Edit tasks where they live (SSOT). Never copy them into the daily note.

## 3. Inbox Zero
Process the capture files in `00 - Inbox/` (`Raw_Captures.md`, `Ideas_Backlog.md`, `Learnings.md`). Never touch `00 - Inbox/README.md`.

| Source | Destination |
| :--- | :--- |
| `Raw_Captures.md` | Project-specific items go to that project's `_Dashboard.md` under `## Staging / Raw Notes` (actionable items become tasks under `## Active Tasks`). Personal or area items go to the matching `20 - Areas/A-*.md`. |
| `Ideas_Backlog.md` | Project-specific ideas go to that project's `_Dashboard.md` under `## Staging / Raw Notes` as a `### Tabled: <idea>` block. Unmatched ideas go to `20 - Areas/A-Backlog.md` (create it if needed). |
| `Learnings.md` | Distill each entry into a one-line imperative rule and merge it into the relevant section of the root `AGENTS.md`. Deduplicate against existing rules. If a learning is specific to one skill, fold it into that skill's `.agents/skills/<name>/SKILL.md` instead. |

Rules:
- If an item's destination is ambiguous, ask. Don't guess, and don't drop it.
- Before purging, list what went where so the user can see it (and so nothing is lost).
- **Purge only after routing succeeded**: reset each capture file that you fully routed to its `# Heading` line and any template comment block. Leave a file untouched if any of its items couldn't be routed. Never delete or empty `README.md`.

## 4. Stage tomorrow
- Add a `## 🔭 Tomorrow` section to TODAY's note with 3–5 preliminary priorities (what `/sod` should lead with).
- If `99 - System/memory/Working_Context.md` holds a checkpoint that today's work resolved, clear it. If work is mid-flight, replace it with a fresh checkpoint (see `/pause`).

## 5. Backup (git, opt-in)
Run this last, so it captures everything above. Skip it unless **both** are true: the vault is a git repo, and `99 - System/memory/backup.md` contains the line `backup: enabled`.
1. `git status --short`. If nothing changed, skip to the report.
2. `git add -A`. `.gitignore` keeps local-only folders out (for example a confidential `10 - Projects/P-Client_X/`). Never force-add an ignored path, and never edit `.gitignore` during `/eod`.
3. **Secret gate (fails closed).** Run one scanner and check its exit status:
   ```bash
   if command -v gitleaks >/dev/null; then
     gitleaks protect --staged --redact --no-banner   # 0 = clean, 1 = leaks, other = error
   else
     set -o pipefail
     if hits="$(git diff --cached -U0 --no-color | awk '
       /^\+\+\+ b\//{f=substr($0,7); next} /^@@/{split($3,a,/[+,]/); n=a[2]; next}
       /^\+/{ if ($0 ~ /["'\'']?(api[_-]?key|secret|token|passw(or)?d)["'\'']?[[:space:]]*[:=]|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20}|BEGIN [A-Z ]*PRIVATE KEY/) print f ":" n; n++ }')"; then
       echo "${hits:-clean}"
     else
       echo "SCANNER ERROR"
     fi
   fi
   ```
   Commit **only** if the result is clean: gitleaks exits 0, or the fallback prints `clean`. For hits, a scanner error, or any other exit code, run `git reset`, report only the `file:line` locations (never the values), and stop until the user decides. This is a best-effort pattern check that can miss secrets.
4. `git commit -m "EOD TODAY: <one-line summary>"` (plus the harness's commit attribution line, if one is configured).
5. **Push only to a verified private GitHub repo.**
   - Get the push URLs with `git remote get-url --all --push origin`. It must return exactly one URL.
   - Parse `<owner>/<repo>` from `https://github.com/<owner>/<repo>(.git)` or `git@github.com:<owner>/<repo>(.git)`.
   - Run `gh repo view <owner>/<repo> --json visibility -q .visibility`. Only if it prints `PRIVATE`, run `git pull --rebase origin main` and `git push origin HEAD`.
   - In every other case (no `origin`, several push URLs, a non-GitHub or unparseable URL, `gh` missing or failing, or any visibility other than `PRIVATE`), keep the commit local and say which check failed. Never push daily notes to a public repo, and never force-push.
6. If the pull or push fails (conflict, offline, auth), leave the commit local and say so plainly.

## 6. Report
Give a short confirmation in chat: the summary bullets, how many tasks were closed or rolled, the inbox routing table, any `AGENTS.md` rules that were added, and the backup result (commit hash and pushed, or why not).
