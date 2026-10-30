#!/usr/bin/env python3
"""PreToolUse(Bash) guard: blocks four costly mistakes (G1-G4).

Contract: reads the hook JSON on stdin. Deny -> prints a hookSpecificOutput
JSON with permissionDecision "deny" and exits 0. Allow -> exit 0, no output.
Fail-open: any exception (or a parse that cannot finish) allows the command
and logs decision "error".

Env: GUARD_LOG (log path), FARM_HOME (default ~/farm), FARM_JOB_ID,
GUARD_AGENT_NAMES (comma list, extends the agent process names; tests).

Self-contained on purpose: it does not import the farm package. "farm" is an
optional headless-job runner (not included in this template); when it is absent,
FARM_HOME simply doesn't exist and G1 relies on the live-process scan alone.

Wire it as a Claude Code PreToolUse hook with matcher "Bash" (see the vault's
.claude/settings.json). Tests: python3 test_guard_bash.py
Python 3.9 compatible, stdlib only.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

PUNCT = set("();<>|&")
ESCAPE_RE = re.compile(r"#\s*guard:\s*allow\s+(\S.*)$", re.MULTILINE)
AGENT_NAMES = {"claude", "codex", "agy", "cursor-agent", "agent", "xcodebuild",
               "swift", "swift-build", "swift-test", "node"}
NODE_HINTS = ("claude", "codex", "playwright", "vitest")
SSH_VALUE_OPTS = {"-i", "-p", "-o", "-l", "-F", "-J", "-L", "-R", "-D", "-b",
                  "-c", "-E", "-S", "-W", "-w", "-B", "-I", "-m", "-O", "-Q"}
SECURITY_BAD = {"create-keychain", "unlock-keychain", "import", "delete-keychain",
                "set-key-partition-list", "default-keychain", "list-keychains"}


@dataclass
class Seg:
    words: List[str]
    stdin_redirected: bool = False
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    remote: bool = False
    under_farm: bool = False


class State:
    def __init__(self, cwd: Optional[str], env: Dict[str, str]) -> None:
        self.cwd = cwd
        self.env = env


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_path() -> str:
    return os.environ.get("GUARD_LOG") or os.path.expanduser("~/.claude/state/guard.log")


_VAL = r"""(?:"[^"]*"|'[^']*'|\S+)"""
_PW_FLAG_RE = re.compile(r"(?<!\S)(--passphrase|--password|--pass|-pass|-p|-P)(\s+|=)" + _VAL)
_PASS_COLON_RE = re.compile(r"\bpass:" + _VAL)
_SEC_ATTACHED_RE = re.compile(r"(?<!\S)-p(?!ass(?:\s|=|$))(?=[^\s=])" + _VAL)
_SECURITY_RE = re.compile(r"(?<![\w./-])security\b")
_SECRET_ASSIGN_RE = re.compile(r"(\b\w*(?:PASSWORD|TOKEN|SECRET)\w*=)" + _VAL, re.IGNORECASE)


def redact(text: str) -> str:
    try:
        text = _PW_FLAG_RE.sub(lambda m: m.group(1) + m.group(2) + "***", text)
        text = _PASS_COLON_RE.sub("pass:***", text)
        if _SECURITY_RE.search(text):
            text = _SEC_ATTACHED_RE.sub("-p***", text)
        return _SECRET_ASSIGN_RE.sub(lambda m: m.group(1) + "***", text)
    except Exception:
        return text


def write_log(rule: Optional[str], decision: str, cwd: Optional[str], cmd: str, reason: str) -> None:
    try:
        p = log_path()
        d = os.path.dirname(p)
        os.makedirs(d, mode=0o700, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except Exception:
            pass
        line = json.dumps({"ts": now_iso(), "rule": rule, "decision": decision,
                           "cwd": cwd, "cmd": redact(cmd)[:300], "reason": redact(reason)})
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            try:
                os.fchmod(fd, 0o600)
            except Exception:
                pass
            os.write(fd, (line + "\n").encode("utf-8", "replace"))
        finally:
            os.close(fd)
    except Exception:
        pass


def base(w: str) -> str:
    return os.path.basename(w)


# ---------------------------------------------------------------- parsing

def tokenize(line: str) -> List[str]:
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = "#"
    return list(lex)


def is_punct(tok: str) -> bool:
    return bool(tok) and all(c in PUNCT for c in tok)


def _trailing_backslashes_odd(line: str) -> bool:
    n = len(line) - len(line.rstrip("\\"))
    return n % 2 == 1


def logical_lines(cmd: str) -> List[Tuple[str, List[str]]]:
    """Return [(line, tokens)] with continuations/quotes joined and heredoc bodies skipped."""
    lines = cmd.split("\n")
    out: List[Tuple[str, List[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        toks: List[str] = []
        while True:
            if _trailing_backslashes_odd(line) and i < len(lines):
                line = line[:-1] + " " + lines[i]
                i += 1
                continue
            try:
                toks = tokenize(line)
            except ValueError:
                if i < len(lines):
                    line = line + "\n" + lines[i]
                    i += 1
                    continue
                raise
            break
        out.append((line, toks))
        # heredoc delimiters on this line
        delims: List[str] = []
        for k, t in enumerate(toks):
            if t == "<<" and k + 1 < len(toks) and not is_punct(toks[k + 1]):
                delims.append(toks[k + 1])
        for d in delims:
            want = d.lstrip("-")
            while i < len(lines):
                body = lines[i]
                i += 1
                if body.strip() == want or body.strip() == d:
                    break
    return out


def join_dir(cwd: Optional[str], p: str) -> Optional[str]:
    if "$" in p or "`" in p:
        return None
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return os.path.normpath(p)
    if cwd is None:
        return None
    return os.path.normpath(os.path.join(cwd, p))


def _strip_flags(words: List[str], i: int, value_opts: frozenset = frozenset(),
                 on_value=None) -> int:
    """Skip option words from i. Options in value_opts take the next word; --x=v is one word.
    on_value(opt, val) is called for every option value seen."""
    while i < len(words) and words[i].startswith("-") and len(words[i]) > 1:
        w = words[i]
        if w in value_opts:
            if on_value and i + 1 < len(words):
                on_value(w, words[i + 1])
            i += 2
        else:
            if on_value and w.startswith("--") and "=" in w:
                k, _, v = w.partition("=")
                on_value(k, v)
            i += 1
    return i


SUDO_VALUE = frozenset("-u -g -h -p -C -U -r -t -D --user --group --host --prompt "
                       "--close-from --role --type --chdir".split())
TIMEOUT_VALUE = frozenset(("-k", "-s", "--kill-after", "--signal"))
XARGS_VALUE = frozenset("-n -I -L -s -P -d -E".split())
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def strip_wrappers(words: List[str], local: Dict[str, str],
                   cwdbox: Optional[List[Optional[str]]] = None) -> List[str]:
    """Strip wrapper commands; VAR=val and env assignments land in `local` (this segment only).
    env -C / sudo -D change the segment cwd held in cwdbox[0]."""
    if cwdbox is None:
        cwdbox = [None]

    def chdir(_o: str, v: str) -> None:
        cwdbox[0] = join_dir(cwdbox[0], v)

    def sudo_dir(o: str, v: str) -> None:
        if o in ("-D", "--chdir"):
            chdir(o, v)

    while words:
        w = words[0]
        b = base(w)
        if ASSIGN_RE.match(w):
            k, _, v = w.partition("=")
            local[k] = v
            words = words[1:]
        elif b == "env":
            i = 1
            split_str = None
            while i < len(words):
                x = words[i]
                if ASSIGN_RE.match(x):
                    k, _, v = x.partition("=")
                    local[k] = v
                    i += 1
                elif x in ("-S", "--split-string") and i + 1 < len(words):
                    split_str = words[i + 1]
                    i += 2
                    break
                elif x.startswith("--split-string=") or (x.startswith("-S") and len(x) > 2):
                    split_str = x.split("=", 1)[1] if x.startswith("--") else x[2:]
                    i += 1
                    break
                elif x in ("-i", "--ignore-environment", "-"):
                    local.clear()
                    i += 1
                elif x in ("-u", "--unset") and i + 1 < len(words):
                    local.pop(words[i + 1], None)
                    i += 2
                elif x.startswith("--unset="):
                    local.pop(x.split("=", 1)[1], None)
                    i += 1
                elif x in ("-C", "--chdir") and i + 1 < len(words):
                    chdir(x, words[i + 1])
                    i += 2
                elif x.startswith("--chdir="):
                    chdir(x, x.split("=", 1)[1])
                    i += 1
                elif x.startswith("-") and len(x) > 1:
                    i += 1
                else:
                    break
            if split_str is not None:
                try:
                    pre = shlex.split(split_str)
                except ValueError:
                    pre = split_str.split()
                words = pre + words[i:]
            else:
                words = words[i:]
        elif b == "command":
            words = words[_strip_flags(words, 1, frozenset()):]
        elif b in ("nohup", "time", "exec"):
            words = words[1:]
        elif b == "nice":
            words = words[_strip_flags(words, 1, frozenset(("-n",))):]
        elif b == "caffeinate":
            words = words[_strip_flags(words, 1):]
        elif b == "sudo":
            words = words[_strip_flags(words, 1, SUDO_VALUE, sudo_dir):]
        elif b == "perl" and len(words) >= 3 and words[1] == "-e":
            words = words[3:]
            if words and words[0].isdigit():
                words = words[1:]
        elif b in ("timeout", "gtimeout"):
            i = _strip_flags(words, 1, TIMEOUT_VALUE)
            if i < len(words):
                i += 1  # duration
            words = words[i:]
        elif b == "xargs":
            words = words[_strip_flags(words, 1, XARGS_VALUE):]
        else:
            break
    return words


def handle_segment(words: List[str], stdin_red: bool, st: State, depth: int,
                   remote: bool, out: List[Seg]) -> None:
    local = dict(st.env)
    cwdbox: List[Optional[str]] = [st.cwd]
    words = strip_wrappers(list(words), local, cwdbox)
    if not words:
        return
    b = base(words[0])
    if b == "unset":
        for w in words[1:]:
            if not w.startswith("-"):
                st.env.pop(w, None)
        return
    if b in ("cd", "pushd"):
        args = [w for w in words[1:] if not (w.startswith("-") and w != "-")]
        if not args:
            st.cwd = os.path.expanduser("~")
        elif args[0] == "-":
            st.cwd = None
        else:
            st.cwd = join_dir(st.cwd, args[0])
        return
    if b == "export":
        for w in words[1:]:
            if "=" in w:
                k, _, v = w.partition("=")
                st.env[k] = v
        return
    seg = Seg(words=words, stdin_redirected=stdin_red, cwd=cwdbox[0],
              env=local, remote=remote, under_farm=(b == "farm"))
    if depth == 0:
        if b in ("sh", "bash", "zsh"):
            for k in range(1, len(words) - 1):
                w = words[k]
                if w.startswith("-") and not w.startswith("--") and "c" in w:
                    out.extend(parse(words[k + 1], cwdbox[0], 1, dict(local), remote, stdin_red))
                    return
        elif b == "ssh":
            i = 1
            ssh_n = False
            while i < len(words) and words[i].startswith("-") and len(words[i]) > 1:
                if words[i] in SSH_VALUE_OPTS:
                    i += 2
                    continue
                if "n" in words[i][1:]:
                    ssh_n = True
                i += 1
            rest = words[i + 1:]  # words[i] is the host
            if rest:
                out.extend(parse(" ".join(rest), None, 1, dict(local), True,
                                 stdin_red or ssh_n))
                return
    out.append(seg)


def parse(cmd: str, cwd: Optional[str], depth: int = 0,
          env: Optional[Dict[str, str]] = None, remote: bool = False,
          stdin: bool = False) -> List[Seg]:
    st = State(cwd, dict(env or {}))
    out: List[Seg] = []
    stack: List[Tuple[Optional[str], Dict[str, str]]] = []
    for _line, toks in logical_lines(cmd):
        words: List[str] = []
        red = stdin
        pipe_next = False
        skip = False

        def flush() -> None:
            nonlocal words, red, pipe_next
            handle_segment(words, red, st, depth, remote, out)
            words = []
            red = stdin or pipe_next
            pipe_next = False

        for t in toks:
            if skip:
                skip = False
                if not is_punct(t):
                    continue
            if is_punct(t):
                if ("(" in t or ")" in t) and "<" not in t and ">" not in t:
                    flush()
                    for ch in t:
                        if ch == "(":
                            stack.append((st.cwd, dict(st.env)))
                        elif ch == ")" and stack:
                            st.cwd, st.env = stack.pop()
                    continue
                if "<" in t or ">" in t:
                    if "<" in t:
                        red = True
                    skip = True
                    continue
                if "|" in t and "&&" not in t and "||" not in t:
                    pipe_next = True
                flush()
                continue
            words.append(t)
        flush()
    return out


# ------------------------------------------------------------------ rules

def run(argv: List[str], timeout: float) -> Optional[str]:
    try:
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=timeout)
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", "replace")
    except Exception:
        return None


def gitdir_target(j: Optional[str]) -> Optional[str]:
    """Work tree that a --git-dir names. A linked worktree's gitdir records its worktree's
    .git file in `<gitdir>/gitdir`; otherwise a /.git suffix names the parent.
    (`git --git-dir=X rev-parse --show-toplevel` just echoes the cwd, so it is not used.)"""
    if j is None:
        return None
    try:
        with open(os.path.join(j, "gitdir")) as f:
            rec = f.read().strip()
        if rec:
            t = join_dir(j, rec)
            if t is not None and os.path.basename(t) == ".git":
                return os.path.dirname(t)
    except Exception:
        pass
    if os.path.basename(j) == ".git":
        return os.path.dirname(j)
    return None


def git_parse(words: List[str], cwd: Optional[str]):
    i = 1
    d = cwd
    wt_dir: Optional[str] = None
    gd_dir: Optional[str] = None
    has_wt = has_gd = False

    def _gd(x: str) -> Optional[str]:
        return gitdir_target(join_dir(d, x))

    while i < len(words):
        w = words[i]
        if w == "--work-tree" and i + 1 < len(words):
            has_wt, wt_dir = True, join_dir(d, words[i + 1])
            i += 2
            continue
        if w.startswith("--work-tree="):
            has_wt, wt_dir = True, join_dir(d, w.split("=", 1)[1])
            i += 1
            continue
        if w == "--git-dir" and i + 1 < len(words):
            has_gd, gd_dir = True, _gd(words[i + 1])
            i += 2
            continue
        if w.startswith("--git-dir="):
            has_gd, gd_dir = True, _gd(w.split("=", 1)[1])
            i += 1
            continue
        if w == "-C":
            if i + 1 >= len(words):
                break
            d = join_dir(d, words[i + 1]) if d is not None or os.path.isabs(words[i + 1]) else None
            i += 2
            continue
        if w in ("-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
            continue
        if w.startswith("-"):
            i += 1
            continue
        break
    sub = words[i] if i < len(words) else None
    if has_wt:
        d = wt_dir
    elif has_gd:
        d = gd_dir if gd_dir is not None else d
    return sub, words[i + 1:], d


def git_destructive(seg: Seg):
    """Return (sub, target_dir) if the git segment is destructive, else None."""
    sub, args, d = git_parse(seg.words, seg.cwd)
    if sub is None:
        return None
    bad = False
    target = d
    if sub in ("checkout", "switch", "rebase", "pull"):
        bad = True
    elif sub == "restore":
        staged_only = ("--staged" in args or "-S" in args) and "--worktree" not in args and "-W" not in args
        bad = not staged_only
    elif sub == "stash":
        nxt = next((a for a in args if not a.startswith("-")), None)
        bad = nxt not in ("list", "show")
    elif sub == "reset":
        bad = "--hard" in args
    elif sub == "clean":
        bad = any(a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a)
                  for a in args)
    elif sub == "worktree":
        if args and args[0] == "remove":
            rest = [a for a in args[1:] if not a.startswith("-")]
            if rest:
                bad = True
                target = join_dir(d, rest[0])
    if not bad:
        return None
    return sub, target


def toplevel(d: str) -> Optional[str]:
    if not d or not os.path.isdir(d):
        return None
    out = run(["git", "-C", d, "rev-parse", "--show-toplevel"], 2)
    if not out or not out.strip():
        return None
    return os.path.realpath(out.strip())


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def registry_live(top: str, hook_cwd: Optional[str]) -> Optional[str]:
    home = os.path.expanduser(os.environ.get("FARM_HOME") or "~/farm")
    jobs_dir = os.path.join(home, "jobs")
    try:
        names = sorted(os.listdir(jobs_dir))
    except Exception:
        return None
    me = os.environ.get("FARM_JOB_ID")
    for n in names:
        try:
            with open(os.path.join(jobs_dir, n, "job.json")) as f:
                job = json.load(f)
            if job.get("state") not in ("queued", "running"):
                continue
            wt = job.get("worktree") or job.get("cwd")
            if not wt:
                continue
            wt = os.path.realpath(os.path.expanduser(wt))
            if not (inside(top, wt) or inside(wt, top)):
                continue
            if me and job.get("id") == me:
                continue
            return str(job.get("id") or n)
        except Exception:
            continue
    return None


def _mentions(cmd: str, top: str) -> bool:
    """True when a word of cmd (after realpath) equals top or lies under it (path boundary)."""
    for w in cmd.split():
        for c in (w, w.split("=", 1)[1]) if "=" in w else (w,):
            if c.startswith("/") and (inside(c, top) or inside(os.path.realpath(c), top)):
                return True
    return False


def process_live(top: str) -> Optional[str]:
    t0 = time.time()
    names = set(AGENT_NAMES)
    extra = os.environ.get("GUARD_AGENT_NAMES", "")
    names.update(x.strip() for x in extra.split(",") if x.strip())
    ps = run(["ps", "-A", "-o", "pid=,ppid=,command="], 3)
    if not ps:
        return None
    procs: Dict[int, Tuple[int, str]] = {}
    for line in ps.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", line)
        if m:
            procs[int(m.group(1))] = (int(m.group(2)), m.group(3))
    anc = set()
    p = os.getpid()
    while p and p not in anc:
        anc.add(p)
        p = procs.get(p, (0, ""))[0]

    def name_of(cmd: str) -> Optional[str]:
        parts = cmd.split(None, 1)
        if not parts:
            return None
        b = base(parts[0])
        if b == "node":
            return b if any(h in cmd for h in NODE_HINTS) else None
        return b if b in names else None

    for pid, (_pp, cmd) in procs.items():
        if pid in anc:
            continue
        nm = name_of(cmd)
        if nm and _mentions(cmd, top):
            return "%s pid %d" % (nm, pid)
    remaining = 3 - (time.time() - t0)
    if remaining > 0.3:
        lsof = shutil.which("lsof") or ("/usr/sbin/lsof" if os.path.exists("/usr/sbin/lsof") else None)
        out = run([lsof, "-nP", "-a", "-d", "cwd", "-Fpn"], remaining) if lsof else None
        if out:
            pid = None
            for line in out.splitlines():
                if line.startswith("p"):
                    try:
                        pid = int(line[1:])
                    except ValueError:
                        pid = None
                elif line.startswith("n") and pid is not None:
                    path = line[1:]
                    if inside(path, top) and pid not in anc and pid in procs:
                        nm = name_of(procs[pid][1])
                        if nm:
                            return "%s pid %d" % (nm, pid)
    return None


def rule_g1(segs: List[Seg], hook_cwd: Optional[str]):
    for s in segs:
        if s.remote or not s.words or base(s.words[0]) != "git":
            continue
        d = git_destructive(s)
        if not d:
            continue
        sub, target = d
        if target is None:
            continue
        top = toplevel(target)
        if not top:
            continue
        who = registry_live(top, hook_cwd) or process_live(top)
        if who:
            return ("G1", "guard G1: git %s in %s, where %s is live. Do instead: git show <rev>:<path>, "
                          "or git worktree add --detach <new path> <rev>. %s" % (sub, top, who, HINT))
    return None


HINT = 'If this is intended, append "# guard: allow <reason>" (logged).'


def rule_g2(segs: List[Seg]):
    for s in segs:
        w = s.words
        if s.stdin_redirected or s.under_farm or not w:
            continue
        if any(x in ("--help", "-h", "--version", "-V") for x in w):
            continue
        b = base(w[0])
        rest = w[1:]
        hit = False
        if b == "codex":
            sub = next((x for x in rest if not x.startswith("-")), None)
            hit = sub in ("exec", "e")
        elif b == "agy":
            hit = any(x == "-p" or x.startswith("-p=") or x == "--print" for x in rest)
        elif b in ("cursor-agent", "agent") or (b == "cursor" and rest[:1] == ["agent"]):
            hit = any(x in ("-p", "--print") for x in rest)
        elif b == "claude":
            hit = any(x in ("-p", "--print") for x in rest)
        if hit:
            return ("G2", "guard G2: headless agent run without stdin (%s hangs waiting on stdin). "
                          "Do instead: add < /dev/null (or < prompt-file), or launch it through a job runner that supplies stdin. %s"
                    % (b, HINT))
    return None


def _is_pr_merge(w: List[str]) -> bool:
    if not w or base(w[0]) != "gh":
        return False
    pos = [x for x in w[1:] if not x.startswith("-")]
    return pos[:2] == ["pr", "merge"]


def _deletes_branch(w: List[str]) -> bool:
    if not w:
        return False
    b = base(w[0])
    if b == "gh" and len(w) > 1 and w[1] == "api":
        m = any(w[i] in ("-X", "--method") and i + 1 < len(w) and w[i + 1].upper() == "DELETE"
                for i in range(len(w))) or any(x.upper() in ("-XDELETE", "--METHOD=DELETE") for x in w)
        return m and any("refs/heads/" in x for x in w)
    if b == "git":
        sub, args, _d = git_parse(w, None)
        if sub == "push":
            return "--delete" in args or any(x.startswith(":") and len(x) > 1 for x in args)
        if sub == "branch":
            return any(x in ("-D", "-d") for x in args)
    return False


def rule_g3(segs: List[Seg]):
    msg = ("guard G3: merging and deleting the branch in one command can strand the PR. "
           "Do instead: merge now; delete the branch in a separate command after "
           "gh pr view <N> --json state shows MERGED. %s" % HINT)
    merge_idx = None
    for i, s in enumerate(segs):
        if _is_pr_merge(s.words):
            if any(x in ("--delete-branch", "-d")
                   or (x.startswith("--delete-branch=")
                       and x.split("=", 1)[1].lower() not in ("false", "0", "f"))
                   for x in s.words):
                return ("G3", msg)
            if merge_idx is None:
                merge_idx = i
        elif merge_idx is not None and _deletes_branch(s.words):
            return ("G3", msg)
    return None


def real_home() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:
        return os.path.expanduser("~")


def _codesign_signs(rest: List[str]) -> bool:
    for x in rest:
        if x in ("--sign", "--force") or x.startswith("--sign=") or x.startswith("--force="):
            return True
        if re.match(r"^-[A-Za-z]+$", x):
            letters = set(x[1:])
            if letters <= set("vdRD"):
                continue
            if "s" in letters or "f" in letters:
                return True
    return False


def _g4_hit(w: List[str]) -> bool:
    if not w:
        return False
    b = base(w[0])
    rest = w[1:]
    if b == "security":
        sub = next((x for x in rest if not x.startswith("-")), None)
        if sub == "list-keychains":
            return "-s" in rest
        return sub in SECURITY_BAD
    if b == "codesign":
        return _codesign_signs(rest)
    if b in ("altool", "notarytool"):
        return True
    if b == "xcrun":
        return any(base(x) in ("altool", "notarytool") for x in rest)
    return False


def _is_temp_home(v: str, rh: str) -> bool:
    """True when HOME=v is a throwaway home (does not resolve to the real home)."""
    if "$(" in v or "`" in v or v.endswith("$"):
        return True
    real = os.path.realpath(rh)
    x = v.replace("${HOME}", rh).replace("$HOME", rh)
    home_rel = x != v or v == "~" or v.startswith("~/")
    if x == "~" or x.startswith("~/"):
        x = rh + x[1:]
    if "$" in x or "~" in x[:1]:
        return True
    r = os.path.realpath(x)
    if r == real:
        return False
    if home_rel and inside(r, real):
        return False
    return True


def rule_g4(segs: List[Seg]):
    rh = real_home().rstrip("/")
    proc_ok = (os.environ.get("GUARD_ON_BUILD_MACHINE") == "1"
               or os.environ.get("HOME", rh).rstrip("/") != rh)
    for s in segs:
        if not _g4_hit(s.words):
            continue
        home = s.env.get("HOME")
        if home is not None and _is_temp_home(home, rh):
            continue
        if s.env.get("GUARD_ON_BUILD_MACHINE") == "1" or proc_ok:
            continue
        return ("G4", "guard G4: touches the real keychain/signing identity. Do instead: run with "
                      "HOME=$(mktemp -d) and a throwaway keychain, or set GUARD_ON_BUILD_MACHINE=1 "
                      "on the build machine. %s" % HINT)
    return None


def check(segs: List[Seg], hook_cwd: Optional[str]) -> Optional[Tuple[str, str]]:
    for r in (lambda: rule_g1(segs, hook_cwd), lambda: rule_g2(segs),
              lambda: rule_g3(segs), lambda: rule_g4(segs)):
        res = r()
        if res:
            return res
    return None


# ------------------------------------------------------------------- main

def _alarm(_sig, _frm):
    raise TimeoutError("guard parse timed out")


def main() -> int:
    cmd = ""
    cwd: Optional[str] = None
    try:
        try:
            signal.signal(signal.SIGALRM, _alarm)
            signal.alarm(8)
        except Exception:
            pass
        data = json.loads(sys.stdin.read())
        if not isinstance(data, dict):
            raise ValueError("hook input is not an object")
        if data.get("tool_name") != "Bash":
            return 0
        ti = data.get("tool_input") or {}
        cmd = ti.get("command") or ""
        cwd = data.get("cwd") or os.getcwd()
        if not cmd.strip():
            return 0
        m = ESCAPE_RE.search(cmd)
        if m:
            write_log(None, "override", cwd, cmd, m.group(1).strip())
            return 0
        segs = parse(cmd, cwd)
        res = check(segs, cwd)
        if res:
            rule, msg = res
            write_log(rule, "deny", cwd, cmd, msg)
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": msg}}))
            sys.stdout.flush()
        return 0
    except BaseException as e:  # fail-open
        if isinstance(e, SystemExit):
            return 0
        write_log(None, "error", cwd, cmd, "%s: %s" % (type(e).__name__, e))
        return 0
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
