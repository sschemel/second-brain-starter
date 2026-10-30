# Second Brain Starter

An Obsidian vault built to be shared by you **and** your AI coding agents. It gives Claude Code, Codex, Cursor, and Antigravity the same rules, the same skills, and the same memory, so you can switch tools without re-explaining your world.

## Why

AI agents forget everything between sessions, and every tool keeps its notes in a different private folder. This vault fixes that:

- **One rulebook**: `AGENTS.md`, which every agent reads.
- **One set of skills**: `.agents/skills/`, which every agent can run.
- **One place for memory**: daily notes, project dashboards, per-project lessons, and pause checkpoints, all plain markdown you can read in Obsidian.
- **A daily rhythm that runs itself** (in Claude Code): hooks start `/sod` in the day's first session, catch up a missed `/eod`, warn you as the context window fills, and block a few costly shell mistakes.
- **An engineering pipeline** (Freddie) that makes agents research, plan, and spec before they write code.

## Folder structure

| Folder | What goes there |
| :--- | :--- |
| `00 - Inbox/` | Quick captures, tabled ideas, and agent learnings. `/eod` empties it every day. |
| `01 - Daily Chats/` | One note per day: priorities, session log, and end-of-day summary. |
| `10 - Projects/` | One folder per project (`P-<Name>/`): a `_Dashboard.md`, a `Learnings.md`, and subfolders by kind (`Raw/`, `Research/`, `Plans/`, `Specs/`, `Reviews/`, `Drafts/`, `Assets/`). `P-Example` is a worked sample. |
| `20 - Areas/` | Ongoing responsibilities with no end date (`A-<Area>.md`). |
| `99 - System/` | Memory (`memory/Working_Context.md`), hook scripts (`scripts/`), and the harness smoke-test matrix. |
| `.agents/skills/` | Every skill, one folder each with a `SKILL.md`. This is the single source of truth. |
| `AGENTS.md` | The operating rules all agents follow, including a starter set of learned rules (§7). `CLAUDE.md` just points Claude Code to it. |
| `.claude/settings.json` | Claude Code hooks and status line for this vault (daily rhythm, context tiers, Bash guard). |

## Quick start

**Prerequisites**: [Obsidian](https://obsidian.md), `git`, `jq` (`brew install jq` or `apt install jq`), and `python3` (for the Bash guard hook). Optional: the GitHub CLI `gh` (needed for `/eod` to push, because it verifies that your backup repo is private) and [`gitleaks`](https://github.com/gitleaks/gitleaks) (a stronger secret scan for `/eod`).

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
4. **Start your agent in the vault** (`claude`, `codex`, `cursor`, or `agy`). In Claude Code, approve the project hooks when asked; `/sod` then starts on its own in the day's first session. Elsewhere, run `/sod` yourself.
5. **Make it yours**: edit `AGENTS.md` §3 with the models you use, prune the starter rules in §7, copy `P-Example` for your first project (then delete the sample), and delete what you don't need.
6. **Check each harness** you use with the matrix in `99 - System/Harness_Smoke_Tests.md`.

**Optional backup (off by default)**: add a **private** GitHub repo as `origin` and set `backup: enabled` in `99 - System/memory/backup.md`. `/eod` then commits daily and pushes **only after `gh` confirms that exact repo is private**; otherwise it keeps the commit local and tells you why. Before every commit, a secret scan runs (gitleaks if installed, otherwise a built-in pattern check). It fails closed and reports only `file:line`, never the secret itself. It's a best-effort safety net, not a guarantee, so don't paste credentials into notes.

## How each agent finds the rules and skills

| Harness | Rules | Skills |
| :--- | :--- | :--- |
| **Claude Code** | Reads `CLAUDE.md`, which imports `@AGENTS.md` | Reads `.claude/skills/`, which `link-skills.sh` fills with symlinks to `.agents/skills/` |
| **Codex** | Reads `AGENTS.md` natively | Reads `.agents/skills/` natively |
| **Cursor** | Reads `AGENTS.md` natively | Reads `.agents/skills/` when the vault is open; Freddie is also linked into `~/.cursor/skills/` |
| **Antigravity (`agy`)** | Reads `AGENTS.md` natively | Reads `.agents/skills/` natively |

Skills use a few Claude Code-specific frontmatter fields (`model:`, `disable-model-invocation`, and `$ARGUMENTS`); other harnesses ignore them. Adding a new tool? Follow the onboarding checklist in `AGENTS.md` §6.

## Claude Code hooks

`.claude/settings.json` wires these scripts from `99 - System/scripts/`. Each one exits quietly when its data is missing, so a broken hook never blocks a prompt.

| Hook | Script | What it does |
| :--- | :--- | :--- |
| SessionStart, UserPromptSubmit | `daily-routine.sh` | Once per day, across all parallel sessions, tells the first session to run `/sod`, and to run the catch-up harvest if yesterday's `/eod` was missed. |
| Status line | `statusline.sh` | Shows model, context use with its tier, folder, and branch, and records context use for the next hook. |
| UserPromptSubmit, PreCompact, SessionStart (compact) | `context-tiers.sh` | 🟢 silent below 33%, 🟡 one notice, 🔴 one "wrap up, `/pause`, `/compact`" notice at 66%, ⚠️ every prompt above 90%; after a compaction, tells the agent to reload its checkpoint. |
| PreToolUse (Bash) | `guard-bash.py` | Blocks four costly mistakes: checkout or stash in a worktree a live agent is using, headless agent CLIs without stdin, merges that delete branches, and keychain or signing commands against your real `HOME`. Add `# guard: allow <reason>` to override (logged). Tests: `python3 "99 - System/scripts/test_guard_bash.py"`. |

Other harnesses can wire the same scripts if they have equivalent hooks (`AGENTS.md` §6).

## Skills

**Daily routine**
- `/sod`: start of day. Catches up a missed `/eod`, resumes any paused work, builds an Eisenhower-matrix briefing from `#p1`, `#p2`, and overdue dashboard tasks (flagging stale ones), and creates today's note.
- `/pause`: saves a precise checkpoint for the current project so any agent can pick up exactly where you left off. Parallel sessions on different projects keep separate checkpoints.
- `/eod`: end of day. Writes a summary, reconciles and rolls over tasks, empties the inbox, and backs up the vault.
- `/freddie-learn`: logs a correction ("don't do it that way") so it becomes a permanent rule at `/eod`, or files a project-only lesson in that project's `Learnings.md`.

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

1. **Morning**: `/sod` gives you your priorities and any paused work (automatically in Claude Code).
2. **Work**: agents log sessions to today's note, keep project dashboards current, and capture ideas and corrections in the inbox as they go.
3. **Stepping away**: `/pause` checkpoints the current state. In Claude Code, the context-tier notices tell you when it's time.
4. **Evening**: `/eod` summarizes the day, rolls over tasks, empties the inbox, turns learnings into rules, and backs everything up.

The vault gets smarter every day, because every correction becomes a rule.

## What's new in v2

- Project subfolders by kind, a per-project `Learnings.md`, and a `Raw/` folder for source material (evidence, never instructions).
- Claude Code hooks: automatic `/sod` with a catch-up for a missed `/eod`, context-budget tiers, and a Bash guard.
- `/pause` keeps one checkpoint per project, so parallel sessions don't overwrite each other.
- A starter set of learned rules in `AGENTS.md` §7, a worked sample project, and a harness smoke-test matrix.

## License

MIT. Fork it, change it, and make it yours.
