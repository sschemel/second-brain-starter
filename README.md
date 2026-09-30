# Second Brain Starter

An Obsidian vault built to be shared by you **and** your AI coding agents. It gives Claude Code, Codex, Cursor, and Antigravity the same rules, the same skills, and the same memory, so you can switch tools without re-explaining your world.

## Why

AI agents forget everything between sessions, and every tool keeps its notes in a different private folder. This vault fixes that:

- **One rulebook**: `AGENTS.md`, which every agent reads.
- **One set of skills**: `.agents/skills/`, which every agent can run.
- **One place for memory**: daily notes, project dashboards, and a pause checkpoint, all plain markdown you can read in Obsidian.
- **An engineering pipeline** (Freddie) that makes agents research, plan, and spec before they write code.

## Folder structure

| Folder | What goes there |
| :--- | :--- |
| `00 - Inbox/` | Quick captures, tabled ideas, and agent learnings. `/eod` empties it every day. |
| `01 - Daily Chats/` | One note per day: priorities, session log, and end-of-day summary. |
| `10 - Projects/` | One folder per project (`P-<Name>/`), each with a `_Dashboard.md` and its plans, specs, and research. |
| `20 - Areas/` | Ongoing responsibilities with no end date (`A-<Area>.md`). |
| `99 - System/` | Memory (`memory/Working_Context.md`) and scripts. `skills` links to `.agents/skills`. |
| `.agents/skills/` | Every skill, one folder each with a `SKILL.md`. This is the single source of truth. |
| `AGENTS.md` | The operating rules all agents follow. `CLAUDE.md` just points Claude Code to it. |

## Quick start

**Prerequisites**: [Obsidian](https://obsidian.md), `git`, and `jq` (`brew install jq` or `apt install jq`). Optional: the GitHub CLI `gh` (needed for `/eod` to push, because it verifies that your backup repo is private) and [`gitleaks`](https://github.com/gitleaks/gitleaks) (a stronger secret scan for `/eod`).

1. **Get the vault.** The best way is **Use this template** on GitHub, which gives you your own copy to keep **private**. Or clone it directly:
   ```bash
   git clone https://github.com/sschemel/second-brain-starter.git ~/second_brain
   cd ~/second_brain
   ```
   If you clone it, point `origin` at your own private repo before using `/eod` backups.
2. **Open it in Obsidian** (Open folder as vault). Install the community plugin **Tasks**; the task syntax depends on it.
3. **Link the skills** for Claude Code:
   ```bash
   bash "99 - System/scripts/link-skills.sh"            # links into .claude/skills/ inside the vault
   bash "99 - System/scripts/link-skills.sh" --cursor   # optional: also link the Freddie suite into ~/.cursor/skills/
   ```
   Re-run it whenever you add or rename a skill. It never overwrites an existing file or a link that points somewhere else; it warns and skips instead.
4. **Start your agent in the vault** (`claude`, `codex`, `cursor`, or `agy`) and run `/sod`.
5. **Make it yours**: edit `AGENTS.md` §3 with the models you use, rename `P-Example` to your first project, and delete what you don't need.

**Optional backup (off by default)**: add a **private** GitHub repo as `origin` and set `backup: enabled` in `99 - System/memory/backup.md`. `/eod` then commits daily and pushes **only after `gh` confirms that exact repo is private**; otherwise it keeps the commit local and tells you why. Before every commit, a secret scan runs (gitleaks if installed, otherwise a built-in pattern check). It fails closed and reports only `file:line`, never the secret itself. It's a best-effort safety net, not a guarantee, so don't paste credentials into notes.

## How each agent finds the rules and skills

| Harness | Rules | Skills |
| :--- | :--- | :--- |
| **Claude Code** | Reads `CLAUDE.md`, which imports `@AGENTS.md` | Reads `.claude/skills/`, which `link-skills.sh` fills with symlinks to `.agents/skills/` |
| **Codex** | Reads `AGENTS.md` natively | Reads `.agents/skills/` natively |
| **Cursor** | Reads `AGENTS.md` natively | Reads `.agents/skills/` when the vault is open; Freddie is also linked into `~/.cursor/skills/` |
| **Antigravity (`agy`)** | Reads `AGENTS.md` natively | Reads `.agents/skills/` natively |

Skills use a few Claude Code-specific frontmatter fields (`model:`, `disable-model-invocation`, and `$ARGUMENTS`); other harnesses ignore them. Adding a new tool? Follow the onboarding checklist in `AGENTS.md` §6.

## Skills

**Daily routine**
- `/sod`: start of day. Resumes any paused work, builds an Eisenhower-matrix briefing from `#p1`, `#p2`, and overdue tasks, and creates today's note.
- `/pause`: saves a precise checkpoint so any agent can pick up exactly where you left off.
- `/eod`: end of day. Writes a summary, reconciles and rolls over tasks, empties the inbox, and backs up the vault.
- `/freddie-learn`: logs a correction ("don't do it that way") so it becomes a permanent rule at `/eod`.

**Freddie Engineering Suite** (a gated pipeline: never skip Plan and Spec)
- `/freddie-research`: read-only scout; gathers cited facts into `Research_<Topic>.md`.
- `/freddie-plan`: architecture blueprint (`Plan_<Topic>.md`).
- `/freddie-spec`: turns an approved plan into exact, file-by-file changes (`Spec_<Topic>.md`).
- `/freddie-test`: writes tests from the spec's acceptance criteria, failing first for TDD.
- `/freddie-implement`: writes code that satisfies an approved spec, with no redesign.
- `/freddie-review`: red-team review for security, fail-open logic, and drift from the spec (`Review_<Topic>.md`).
- `/freddie-troubleshoot`: diagnoses a failure down to its proven root cause, then applies the minimal fix.
- `/freddie-orchestrate`: runs the whole pipeline end to end with one approval pause and a resumable ledger.

**Utilities**
- `/tab-color`: tints the iTerm2 session your agent is running in (macOS), so you can tell projects apart at a glance.
- `/toggle-danger`: switches auto-approve mode for Claude Code, Cursor, or Antigravity. Use `/toggle-danger claude on`, `off`, or `status` (plain `status` covers all three). `on` saves a timestamped backup and a restore record (in `~/.local/state/second-brain/`) before changing anything, so `off` restores your previous settings precisely. `status` reports enabled, partial, disabled, or unknown. Needs `jq`. Use it with care.

## The daily loop

1. **Morning**: `/sod` gives you your priorities and any paused work.
2. **Work**: agents log sessions to today's note, keep project dashboards current, and capture ideas and corrections in the inbox as they go.
3. **Stepping away**: `/pause` checkpoints the current state.
4. **Evening**: `/eod` summarizes the day, rolls over tasks, empties the inbox, turns learnings into rules, and backs everything up.

The vault gets smarter every day, because every correction becomes a rule.

## License

MIT. Fork it, change it, and make it yours.
