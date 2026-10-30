#!/usr/bin/env python3
"""Tests for guard-bash.py (AC32-AC40). Stdlib only, no pytest.

Every guard run is a subprocess with a temp GUARD_LOG and temp FARM_HOME, so
the real ~/.claude/state/guard.log and ~/farm are never touched.

Run: python3 "99 - System/scripts/test_guard_bash.py"
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
GUARD = HERE / "guard-bash.py"
CORPUS = HERE / "guard_corpus.jsonl"

failures = 0
TMPROOT = Path(os.path.realpath(tempfile.mkdtemp(prefix="guardtest-")))
procs: List[subprocess.Popen] = []


def check(desc: str, cond: bool, detail: str = "") -> None:
    global failures
    if cond:
        print("PASS: " + desc)
    else:
        failures += 1
        print("FAIL: " + desc + (" -- " + detail if detail else ""))


def git(*args: str, cwd: Optional[Path] = None) -> None:
    subprocess.run(["git"] + list(args), cwd=str(cwd) if cwd else None, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_repo(name: str) -> Path:
    p = TMPROOT / name
    p.mkdir()
    git("init", "-q", cwd=p)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-q", "-m", "i", cwd=p)
    return p


def base_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    for k in ("FARM_JOB_ID", "GUARD_ON_BUILD_MACHINE", "GUARD_AGENT_NAMES"):
        env.pop(k, None)
    env["GUARD_LOG"] = str(TMPROOT / "guard.log")
    env["FARM_HOME"] = str(TMPROOT / "farmhome")
    if extra:
        env.update(extra)
    return env


def run_guard(cmd: str, cwd: str, extra_env: Optional[Dict[str, str]] = None,
              raw_stdin: Optional[str] = None, py: Optional[str] = None) -> Tuple[int, str, str]:
    payload = raw_stdin if raw_stdin is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd})
    r = subprocess.run([py or sys.executable, str(GUARD)], input=payload.encode(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=base_env(extra_env), timeout=30)
    return r.returncode, r.stdout.decode(), r.stderr.decode()


def decision(cmd: str, cwd: str, extra_env: Optional[Dict[str, str]] = None) -> Tuple[str, Optional[str]]:
    rc, out, err = run_guard(cmd, cwd, extra_env)
    if rc != 0:
        return "rc%d" % rc, err
    if not out.strip():
        return "allow", None
    d = json.loads(out)["hookSpecificOutput"]
    msg = d["permissionDecisionReason"]
    rule = msg.split(":", 1)[0].replace("guard ", "")
    return "deny" if d["permissionDecision"] == "deny" else "?", rule


def read_log() -> List[dict]:
    p = TMPROOT / "guard.log"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def reset_log() -> None:
    p = TMPROOT / "guard.log"
    if p.exists():
        p.unlink()


# ---- fixtures -------------------------------------------------------------

WT = make_repo("wt")
IDLE = make_repo("idle")
JOB_ID = "live-20261011T0000-abcd"
(TMPROOT / "farmhome" / "jobs" / JOB_ID).mkdir(parents=True)
(TMPROOT / "farmhome" / "jobs" / JOB_ID / "job.json").write_text(json.dumps(
    {"id": JOB_ID, "state": "running", "worktree": str(WT), "cwd": str(WT)}))
# a finished job pointing at IDLE must not count as live
(TMPROOT / "farmhome" / "jobs" / "done-1").mkdir()
(TMPROOT / "farmhome" / "jobs" / "done-1" / "job.json").write_text(json.dumps(
    {"id": "done-1", "state": "done", "worktree": str(IDLE)}))
OTHER = str(TMPROOT)  # a neutral hook cwd outside the worktree


def sub(s: str) -> str:
    return s.replace("{WT}", str(WT)).replace("{IDLE}", str(IDLE)).replace("{TMP}", str(TMPROOT))


# ---- tests ----------------------------------------------------------------

def test_corpus() -> None:
    lines = [json.loads(x) for x in CORPUS.read_text().splitlines() if x.strip()]
    check("AC32 corpus has at least 40 lines", len(lines) >= 40, str(len(lines)))
    for row in lines:
        cmd, cwd = sub(row["cmd"]), sub(row["cwd"])
        got, rule = decision(cmd, cwd)
        want = row["expect"]
        ok = got == want and (want == "allow" or rule == row["rule"])
        check("AC32 corpus: %s [%s]" % (row["note"], want), ok,
              "got %s/%s for %r" % (got, rule, cmd[:120]))


def test_g1_registry() -> None:
    w = str(WT)
    cases = [
        ("git -C %s stash" % w, OTHER, None, "deny"),
        ("cd %s && git checkout main" % w, OTHER, None, "deny"),
        ("git worktree remove %s" % w, OTHER, None, "deny"),
        ("git -C %s diff" % w, OTHER, None, "allow"),
        ("git show HEAD:README", w, None, "allow"),
        ("git -C %s stash" % w, OTHER, {"FARM_JOB_ID": JOB_ID}, "allow"),
        # A10: hook_cwd inside the worktree no longer exempts; only FARM_JOB_ID does
        ("git -C %s checkout main" % w, w, None, "deny"),
        ("git -C %s stash" % w, w + "/sub", None, "deny"),
        ("git -C %s checkout main" % w, w, {"FARM_JOB_ID": JOB_ID}, "allow"),
        ("git -C %s checkout main" % w, w, {"FARM_JOB_ID": "other-job"}, "deny"),
    ]
    for cmd, cwd, env, want in cases:
        got, rule = decision(cmd, cwd, env)
        check("AC33 G1 registry %s: %s (cwd=%s env=%s)" % (want, cmd.replace(w, "<wt>"),
              cwd.replace(w, "<wt>").replace(OTHER, "<other>"), env), got == want and (want == "allow" or rule == "G1"),
              "got %s/%s" % (got, rule))


def test_g1_process() -> None:
    b = make_repo("procrepo")
    p = subprocess.Popen(["sleep", "30"], cwd=str(b))
    procs.append(p)
    try:
        time.sleep(0.3)
        env = {"GUARD_AGENT_NAMES": "sleep"}
        got, rule = decision("git -C %s reset --hard" % b, OTHER, env)
        check("AC34 G1 process: live agent-named process in repo -> deny", got == "deny" and rule == "G1", "%s/%s" % (got, rule))
        got, rule = decision("git -C %s reset --hard" % b, OTHER, None)
        check("AC34 G1 process: same process but name not an agent -> allow", got == "allow", "%s/%s" % (got, rule))
        got, rule = decision("git -C %s reset --soft HEAD" % b, OTHER, env)
        check("AC34 G1 process: non-destructive git -> allow", got == "allow", "%s/%s" % (got, rule))
    finally:
        p.kill()
        p.wait()
    got, rule = decision("git -C %s reset --hard" % b, OTHER, {"GUARD_AGENT_NAMES": "sleep"})
    check("AC34 G1 process: after the process exits -> allow", got == "allow", "%s/%s" % (got, rule))

    # An ancestor whose cwd is in the repo and whose name is an "agent" is never counted.
    c = make_repo("ancrepo")
    code = (
        "import json,os,subprocess,sys\n"
        "payload=json.dumps({'tool_name':'Bash','tool_input':{'command':'git -C %s reset --hard'},'cwd':%r})\n"
        "r=subprocess.run([sys.executable,%r],input=payload.encode(),stdout=subprocess.PIPE,env=os.environ)\n"
        "sys.stdout.write(r.stdout.decode())\n" % (c, OTHER, str(GUARD))
    )
    env = base_env({"GUARD_AGENT_NAMES": "python3,Python,python,python3.9,python3.11,python3.13"})
    r = subprocess.run([sys.executable, "-c", code], cwd=str(c), env=env,
                       stdout=subprocess.PIPE, timeout=30)
    check("AC34 G1 process: ancestor with agent name and cwd in repo is ignored",
          r.stdout.decode().strip() == "", r.stdout.decode()[:200])


def test_g1_process_boundary() -> None:
    """A17: process match is on path boundaries, not raw substrings."""
    keep = make_repo("repo")
    old = make_repo("repo-old")
    env = {"GUARD_AGENT_NAMES": "perl"}
    p = subprocess.Popen(["perl", "-e", "sleep 30", str(old)], cwd=OTHER)
    procs.append(p)
    try:
        time.sleep(0.3)
        got, rule = decision("git -C %s reset --hard" % keep, OTHER, env)
        check("AC49 A17 agent mentioning /repo-old is not counted for /repo", got == "allow", "%s/%s" % (got, rule))
        got, rule = decision("git -C %s reset --hard" % old, OTHER, env)
        check("AC49 A17 agent mentioning /repo-old is counted for /repo-old", got == "deny" and rule == "G1", "%s/%s" % (got, rule))
    finally:
        p.kill()
        p.wait()
    p = subprocess.Popen(["perl", "-e", "sleep 30", str(keep) + "/sub/file"], cwd=OTHER)
    procs.append(p)
    try:
        time.sleep(0.3)
        got, rule = decision("git -C %s reset --hard" % keep, OTHER, env)
        check("AC49 A17 agent with a path under /repo is counted", got == "deny" and rule == "G1", "%s/%s" % (got, rule))
    finally:
        p.kill()
        p.wait()


def test_a11_env_scope() -> None:
    cases = [
        ("HOME=/tmp/h security create-keychain -p x k; security unlock-keychain login.keychain", "deny"),
        ("env HOME=/tmp/h security create-keychain k; security unlock-keychain k", "deny"),
        ("HOME=/tmp/h security create-keychain k", "allow"),
        ("export HOME=/tmp/h; security create-keychain k; security import c.p12", "allow"),
        ("HOME=/tmp/h true && security unlock-keychain k", "deny"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC49 A11 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G4"), "%s/%s" % (got, rule))


def test_a12_wrappers() -> None:
    w = str(WT)
    cases = [
        ("sudo -u b git -C %s checkout main" % w, "deny", "G1"),
        ("sudo -g staff -u b git -C %s stash" % w, "deny", "G1"),
        ("command -p git -C %s stash" % w, "deny", "G1"),
        ("nice -n 5 git -C %s stash" % w, "deny", "G1"),
        ("timeout -k 1s 2s codex exec x", "deny", "G2"),
        ("timeout -s KILL 2s codex exec x", "deny", "G2"),
        ("env -u FOO codex exec x < /dev/null", "allow", None),
        ("env -u FOO codex exec x", "deny", "G2"),
        ('env -S "git -C %s stash"' % w, "deny", "G1"),
    ]
    for cmd, want, wr in cases:
        got, rule = decision(cmd, OTHER)
        check("AC49 A12 %s: %s" % (want, cmd.replace(w, "<wt>")), got == want and (want == "allow" or rule == wr), "%s/%s" % (got, rule))


def test_a13_git_targets() -> None:
    w = str(WT)
    cases = [
        "git --work-tree=%s --git-dir=%s/.git checkout main" % (w, w),
        "git --work-tree %s checkout main" % w,
        "git --git-dir %s/.git stash" % w,
        "git --git-dir=%s/.git reset --hard" % w,
    ]
    for cmd in cases:
        got, rule = decision(cmd, OTHER)
        check("AC49 A13 deny: %s" % cmd.replace(w, "<wt>"), got == "deny" and rule == "G1", "%s/%s" % (got, rule))
    got, rule = decision("git --work-tree=%s --git-dir=%s/.git status" % (w, w), OTHER)
    check("AC49 A13 read-only with --work-tree allowed", got == "allow")


def test_a14_g4_coverage() -> None:
    cases = [
        ('codesign -fs "Dev" a.app', "deny"),
        ("codesign -s X a.app", "deny"),
        ("codesign --sign X a.app", "deny"),
        ("codesign --sign=X a.app", "deny"),
        ("codesign --force a.app", "deny"),
        ("codesign -dvvv a.app", "allow"),
        ("codesign -vR a.app", "allow"),
        ("codesign --display a.app", "allow"),
        ("xcrun --sdk macosx notarytool submit a.zip", "deny"),
        ("xcrun -v altool --upload-app", "deny"),
        ("xcrun --sdk macosx clang x.c", "allow"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC49 A14 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G4"), "%s/%s" % (got, rule))


def test_a15_log_hygiene() -> None:
    logdir = TMPROOT / "newlogdir"
    logp = logdir / "guard.log"
    payload = json.dumps({"tool_name": "Bash", "cwd": OTHER, "tool_input": {
        "command": "security create-keychain -p secret123 k; MY_API_TOKEN=tok456 security unlock-keychain k"}})
    env = base_env({"GUARD_LOG": str(logp)})
    subprocess.run([sys.executable, str(GUARD)], input=payload.encode(), stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, env=env, timeout=30)
    check("AC49 A15 guard.log is mode 0600", logp.exists() and (os.stat(str(logp)).st_mode & 0o777) == 0o600,
          oct(os.stat(str(logp)).st_mode & 0o777) if logp.exists() else "missing")
    check("AC49 A15 new log dir is mode 0700", logdir.exists() and (os.stat(str(logdir)).st_mode & 0o777) == 0o700)
    text = logp.read_text() if logp.exists() else ""
    check("AC49 A15 logged -p secret shows ***", "***" in text and "secret123" not in text, text[:200])
    check("AC49 A15 TOKEN assignment redacted", "tok456" not in text and "MY_API_TOKEN=***" in text, text[:300])


def test_a16_delete_branch_false() -> None:
    cases = [
        ("gh pr merge 12 --squash --delete-branch=false", "allow"),
        ("gh pr merge 12 --squash --delete-branch=true", "deny"),
        ("gh pr merge 12 --squash -d", "deny"),
        ("gh pr merge 12 --squash --delete-branch", "deny"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC49 A16 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G3"), "%s/%s" % (got, rule))


def _check_cases(tag: str, cases, cwd: str = None) -> None:
    for cmd, want, wr in cases:
        got, rule = decision(cmd, cwd or OTHER)
        check("%s %s: %s" % (tag, want, cmd.replace(str(WT), "<wt>")),
              got == want and (want == "allow" or rule == wr), "%s/%s" % (got, rule))


def test_b9_env_semantics() -> None:
    link = TMPROOT / "homelink"
    os.symlink(os.path.realpath(os.path.expanduser("~")), str(link))
    _check_cases("AC56 B9", [
        ("( export HOME=/tmp/h ); security unlock-keychain x", "deny", "G4"),
        ("(export HOME=/tmp/h; security unlock-keychain x)", "allow", None),
        ("export GUARD_ON_BUILD_MACHINE=1; env -i security import c.p12", "deny", "G4"),
        ("export HOME=/tmp/h; env -u HOME security unlock-keychain x", "deny", "G4"),
        ("export HOME=/tmp/h; env --unset HOME security unlock-keychain x", "deny", "G4"),
        ("export HOME=/tmp/h; env --unset=HOME security unlock-keychain x", "deny", "G4"),
        ("export HOME=/tmp/h; unset HOME; security unlock-keychain x", "deny", "G4"),
        ("export HOME=${HOME}; security unlock-keychain x", "deny", "G4"),
        ("export HOME=~; security unlock-keychain x", "deny", "G4"),
        ("export HOME=%s; security unlock-keychain x" % link, "deny", "G4"),
        ("export HOME=$(mktemp -d); security import c.p12", "allow", None),
        ("export HOME=/tmp/h; security unlock-keychain x", "allow", None),
    ])


def test_b10_b11_wrappers() -> None:
    w = str(WT)
    _check_cases("AC56 B10/B11", [
        ("env -C %s git checkout main" % w, "deny", "G1"),
        ("env --chdir=%s git stash" % w, "deny", "G1"),
        ("env --chdir %s git stash" % w, "deny", "G1"),
        ("sudo -D %s git stash" % w, "deny", "G1"),
        ("sudo --chdir %s git stash" % w, "deny", "G1"),
        ("sudo --user nobody git -C %s checkout main" % w, "deny", "G1"),
        ("sudo --user=nobody --group staff git -C %s checkout main" % w, "deny", "G1"),
        ("sudo --prompt x --close-from 5 git -C %s stash" % w, "deny", "G1"),
        ("timeout --kill-after 1 2 codex exec hi", "deny", "G2"),
        ("timeout --signal KILL 2 codex exec hi", "deny", "G2"),
        ("timeout --signal=KILL --kill-after=1 2 codex exec hi", "deny", "G2"),
        ("xargs -n 1 git -C %s checkout main" % w, "deny", "G1"),
        ("xargs -I {} git -C %s stash" % w, "deny", "G1"),
        ("xargs -I{} git -C %s stash" % w, "deny", "G1"),
        ("env -C %s git status" % w, "allow", None),
    ])


def test_b12_log() -> None:
    logdir = TMPROOT / "oldlog"
    logdir.mkdir()
    os.chmod(str(logdir), 0o755)
    logp = logdir / "guard.log"
    logp.write_text("")
    os.chmod(str(logp), 0o644)
    cmds = ["security unlock-keychain --passphrase hunter2 x",
            "security import k -pPWattached1 -T x",
            "openssl enc -pass pass:pcolon3 -in a",
            "tool -pass pnext4 x"]
    for c in cmds:
        payload = json.dumps({"tool_name": "Bash", "cwd": OTHER, "tool_input": {"command": c + " # guard: allow t"}})
        subprocess.run([sys.executable, str(GUARD)], input=payload.encode(), stdout=subprocess.PIPE,
                       env=base_env({"GUARD_LOG": str(logp)}), timeout=30)
    check("AC56 B12 existing 0644 guard.log becomes 0600", (os.stat(str(logp)).st_mode & 0o777) == 0o600)
    check("AC56 B12 existing 0755 dir becomes 0700", (os.stat(str(logdir)).st_mode & 0o777) == 0o700)
    text = logp.read_text()
    for secret in ("hunter2", "PWattached1", "pcolon3", "pnext4"):
        check("AC56 B12 %s redacted" % secret, secret not in text, text[:400])
    check("AC56 B12 *** present", text.count("***") >= 4, text[:400])


def test_b13_delete_branch_values() -> None:
    _check_cases("AC56 B13", [
        ("gh pr merge 1 --delete-branch=True", "deny", "G3"),
        ("gh pr merge 1 --delete-branch=yes", "deny", "G3"),
        ("gh pr merge 1 --delete-branch=1", "deny", "G3"),
        ("gh pr merge 1 --delete-branch=0", "allow", None),
        ("gh pr merge 1 --delete-branch=FALSE", "allow", None),
        ("gh pr merge 1 --delete-branch=f", "allow", None),
    ])


def test_b14_b15_registry() -> None:
    r = make_repo("lrepo")
    wtree = TMPROOT / "lrepo-linked"
    git("worktree", "add", "-q", "--detach", str(wtree), cwd=r)
    name = os.listdir(str(r / ".git" / "worktrees"))[0]
    jd = TMPROOT / "farmhome" / "jobs"
    for jid, wt in (("b14-live", str(wtree)), ("b15-live", str(r / "sub"))):
        (jd / jid).mkdir()
        (jd / jid / "job.json").write_text(json.dumps({"id": jid, "state": "running", "worktree": wt}))
    try:
        gd = str(r / ".git" / "worktrees" / name)
        _check_cases("AC56 B14", [
            ("git --git-dir=%s checkout main" % gd, "deny", "G1"),
            ("git --git-dir %s stash" % gd, "deny", "G1"),
        ])
        _check_cases("AC56 B15", [("git -C %s stash" % r, "deny", "G1")])
    finally:
        for jid in ("b14-live", "b15-live"):
            shutil.rmtree(str(jd / jid), ignore_errors=True)
    _check_cases("AC56 B14/B15 after jobs end", [("git -C %s stash" % r, "allow", None)])


def test_g2() -> None:
    cases = [
        ('codex exec -m x "do it"', "deny"),
        ("codex exec -m x - < p.txt", "allow"),
        ("cat p | codex exec -", "allow"),
        ('agy --model "M" -p="hi" < /dev/null', "allow"),
        ("farm run --name a --class light --cwd . -- codex exec x", "allow"),
        ("ssh -n buildhost 'codex exec x'", "allow"),
        ("ssh buildhost 'codex exec x'", "deny"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC35 G2 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G2"), "%s/%s" % (got, rule))


def test_g3() -> None:
    cases = [
        ("gh pr merge 12 --squash --delete-branch", "deny"),
        ("gh pr merge 12 --squash && gh api -X DELETE repos/o/r/git/refs/heads/x", "deny"),
        ("gh pr merge 12 --squash", "allow"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC36 G3 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G3"), "%s/%s" % (got, rule))


def test_g4() -> None:
    cases = [
        ("security unlock-keychain login.keychain", "deny"),
        ("xcrun altool --upload-app -f a.ipa", "deny"),
        ("HOME=/tmp/h security create-keychain -p x k", "allow"),
        ("GUARD_ON_BUILD_MACHINE=1 codesign -s X a.app", "allow"),
        ("security find-identity -v", "allow"),
        ("codesign -dv a.app", "allow"),
        ("export HOME=$(mktemp -d); security import c.p12", "allow"),
    ]
    for cmd, want in cases:
        got, rule = decision(cmd, OTHER)
        check("AC37 G4 %s: %s" % (want, cmd), got == want and (want == "allow" or rule == "G4"), "%s/%s" % (got, rule))
    got, _ = decision("security unlock-keychain k", OTHER, {"GUARD_ON_BUILD_MACHINE": "1"})
    check("AC37 G4 allow when guard process env has GUARD_ON_BUILD_MACHINE=1", got == "allow")
    got, _ = decision("security unlock-keychain k", OTHER, {"HOME": str(TMPROOT)})
    check("AC37 G4 allow when guard process HOME is not the real home", got == "allow")


def test_escape_hatch() -> None:
    reset_log()
    got, _ = decision("git -C %s stash # guard: allow owner asked" % WT, OTHER)
    log = read_log()
    ov = [x for x in log if x["decision"] == "override"]
    check("AC38 escape hatch allows", got == "allow")
    check("AC38 override logged with reason", len(ov) == 1 and ov[0]["reason"] == "owner asked", str(log))
    reset_log()
    decision("git -C %s stash" % WT, OTHER)
    log = read_log()
    check("deny is logged with rule and cmd", len(log) == 1 and log[0]["decision"] == "deny"
          and log[0]["rule"] == "G1" and log[0]["cwd"] == OTHER, str(log))


def test_fail_open() -> None:
    reset_log()
    rc, out, _ = run_guard("", OTHER, raw_stdin="{not json")
    log = read_log()
    check("AC39 malformed stdin -> exit 0, no output", rc == 0 and out == "", "%s %r" % (rc, out))
    check("AC39 malformed stdin -> error logged", any(x["decision"] == "error" for x in log), str(log))
    reset_log()
    rc, out, _ = run_guard('codex exec "never closes', OTHER)
    log = read_log()
    check("AC39 unbalanced quote -> exit 0, no deny", rc == 0 and out == "", "%s %r" % (rc, out))
    check("AC39 unbalanced quote -> error logged", any(x["decision"] == "error" for x in log), str(log))
    reset_log()
    rc, out, _ = run_guard("", OTHER, raw_stdin=json.dumps({"tool_name": "Read", "tool_input": {}}))
    check("non-Bash tool -> silent allow", rc == 0 and out == "" and read_log() == [])
    rc, out, _ = run_guard("", OTHER, raw_stdin=json.dumps({"tool_name": "Bash", "tool_input": {"command": "  "}, "cwd": OTHER}))
    check("empty command -> silent allow", rc == 0 and out == "")


def test_latency() -> None:
    n = 20
    t0 = time.time()
    for _ in range(n):
        rc, out, _ = run_guard("ls -la", OTHER)
        if rc != 0 or out:
            break
    mean_ms = (time.time() - t0) / n * 1000
    print("INFO: mean latency for 'ls -la' over %d runs: %.1f ms (%s)" % (n, mean_ms, sys.version.split()[0]))
    check("AC40 non-git command allowed with mean latency under 150 ms", rc == 0 and out == "" and mean_ms < 150,
          "%.1f ms" % mean_ms)


def cleanup() -> None:
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass
    shutil.rmtree(str(TMPROOT), ignore_errors=True)


def main() -> int:
    global failures
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    try:
        for t in tests:
            try:
                t()
            except Exception as e:  # noqa: BLE001
                failures += 1
                print("FAIL: %s raised %s: %s" % (t.__name__, type(e).__name__, e))
    finally:
        cleanup()
    print()
    if failures:
        print("%d check(s) FAILED" % failures)
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
