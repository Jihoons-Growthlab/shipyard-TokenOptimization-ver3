#!/usr/bin/env python3
"""Ver3 workflow state, verification, dev services, source map and usage. Stdlib only.

Exit codes: 0 ok, 1 check failed, 2 refused (session/state), 3 nothing to do (all tasks done).
"""
import datetime as dt
import glob
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("WF_ROOT") or Path(__file__).resolve().parent.parent)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def after(a, b):
    """a >= b for ISO timestamps with any offset."""
    return dt.datetime.fromisoformat(a) >= dt.datetime.fromisoformat(b)


def load(rel):
    return json.loads((ROOT / rel).read_text())


def save(rel, data):
    p = ROOT / rel
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(p)


def cfg():
    return load("config/workflow.json")


def policy():
    return load("config/token-policy.json")


# ---------------------------------------------------------------- sessions / tasks

LOG = "state/sessions.log"


def log_event(sid, event, phase="-"):
    with open(ROOT / LOG, "a") as f:
        f.write(f"{now()} {sid} {event} {phase}\n")


def events():
    p = ROOT / LOG
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        parts = line.split()
        if len(parts) == 4:
            rows.append(dict(ts=parts[0], sid=parts[1], event=parts[2], phase=parts[3]))
    return rows


def tasks_state():
    return load("state/tasks.json")


def is_done(st, tid):
    return st["status"].get(tid, {}).get("state") == "done"


def is_blocked(st, tid):
    return st["status"].get(tid, {}).get("state") == "blocked"


def next_phase(st):
    for ph in st["phases"]:
        pending = [t for t, v in st["tasks"].items() if v["phase"] == ph["id"] and not is_done(st, t) and not is_blocked(st, t)]
        if pending or not any(e["event"] == "phase-done" and e["phase"] == ph["id"] for e in events()):
            return ph, pending
    return None, []


def phase_claim(phase_id):
    """Latest claim of the phase that has no phase-done after it."""
    claim = None
    for e in events():
        if e["phase"] != phase_id:
            continue
        if e["event"] in ("claim", "resume", "takeover"):
            claim = claim if (claim and e["event"] == "resume" and claim["sid"] == e["sid"]) else e
        elif e["event"] == "phase-done":
            claim = None
    return claim


def current_claim():
    st = tasks_state()
    ph, _ = next_phase(st)
    return (ph, phase_claim(ph["id"])) if ph else (None, None)


def brief(st, ph, pending):
    pol = policy()["phase_budget"]
    out = [f"PHASE {ph['id']} {ph['title']}",
           f"budget(실험값): ~{pol['api_calls']} calls, context soft cap {pol['context_soft_cap'] // 1000}k",
           f"notes: {ph.get('notes', '')}",
           "pending:"]
    for tid in pending:
        t = st["tasks"][tid]
        imgs = " ".join(f"reference/ui/{i}.png" for i in t["images"]) or "-"
        out.append(f"  {tid} step{t['step']} {t['title']} | specs: {' '.join(t['specs'])} | images: {imgs} | verify: {','.join(t['verify'])}")
    done = [t for t, v in st["tasks"].items() if v["phase"] == ph["id"] and is_done(st, t)]
    if done:
        out.append(f"done in phase (do not redo): {' '.join(done)}")
    for t, v in st["status"].items():
        if v.get("state") == "blocked":
            out.append(f"BLOCKED {t}: {v.get('reason')} (사용자 조치 후 wf.py reopen {t} <이유>)")
    out.append(f"checkpoint: verify {','.join(ph['checkpoint'])}" + (" + shots" if ph["shots"] else ""))
    return "\n".join(out)


def cmd_next(args):
    st = tasks_state()
    ph, pending = next_phase(st)
    if not ph:
        blocked = [t for t, v in st["status"].items() if v.get("state") == "blocked"]
        print("ALL_DONE: 모든 작업이 완료됐다. Claude를 실행하지 않는다." + (f" 차단(미실행): {' '.join(blocked)}" if blocked else ""))
        cmd_usage([])
        return 3
    print(brief(st, ph, pending))
    c = phase_claim(ph["id"])
    if c:
        print(f"open claim: {c['sid']} since {c['ts']}")
    return 0


def transcript(sid):
    return claude_project_dir() / f"{sid}.jsonl"


def cmd_launch(args):
    force = "--force" in args
    st = tasks_state()
    ph, _ = next_phase(st)
    if not ph:
        return cmd_next([])
    c = phase_claim(ph["id"])
    if c and not force:
        tp = transcript(c["sid"])
        mins = cfg()["launch"]["active_minutes"]
        if tp.exists() and time.time() - tp.stat().st_mtime < mins * 60:
            print(f"REFUSED: 세션 {c['sid']}가 {ph['id']}를 진행 중이며 {mins}분 안에 기록이 있다. "
                  "그 세션을 저장·종료한 뒤 다시 실행하거나 --force를 붙인다.")
            return 2
    cmd_next([])
    lc = cfg()["launch"]
    env = {**os.environ, **lc["env"]}
    os.chdir(ROOT)
    argv = lc["command"] + [lc["prompt"]]
    if "--dry-run" in args:
        print("DRY-RUN:", " ".join(argv))
        return 0
    os.execvpe(argv[0], argv, env)


def cmd_claim(args):
    if not args or not args[0] or "$" in args[0]:
        print("REFUSED: 세션 ID가 없다. /build 안에서 ${CLAUDE_SESSION_ID}로 호출한다.")
        return 2
    sid = args[0]
    st = tasks_state()
    ph, pending = next_phase(st)
    if not ph:
        print("ALL_DONE: 모든 작업이 완료됐다. 검증 상태를 state/PROGRESS.md에서 보고하고 멈춘다.")
        return 3
    finished = [e["phase"] for e in events() if e["sid"] == sid and e["event"] == "phase-done"]
    if finished:
        log_event(sid, "refused", ph["id"])
        print(f"REFUSED: 이 세션({sid[:8]})은 이미 {','.join(finished)}을 끝냈다. "
              "컨텍스트를 이어 쓰지 않도록 /exit 후 `scripts/start.sh --launch`로 새 세션을 연다.")
        return 2
    c = phase_claim(ph["id"])
    event = "claim" if not c else ("resume" if c["sid"] == sid else "takeover")
    log_event(sid, event, ph["id"])
    print(f"[{event}] session {sid[:8]}" + (f" (이전 세션 {c['sid'][:8]}의 미완료 phase를 이어받음: PROGRESS.md 기준으로 재개)" if event == "takeover" else ""))
    print(brief(st, ph, pending))
    env = ensure_env()
    print("env: " + " ".join(f"{k}={v}" for k, v in env.items()))
    prog = ROOT / cfg()["progress"]["file"]
    print(f"--- {prog.relative_to(ROOT)}\n{prog.read_text().strip()}")
    if ph["id"] != "P1":
        build_srcmap(if_stale=True, quiet=True)
        sm = ROOT / cfg()["srcmap"]["out"]
        if sm.exists():
            print(f"--- {sm.relative_to(ROOT)}\n{sm.read_text().strip()}")
    return 0


def claim_ts(ph_id):
    c = phase_claim(ph_id)
    return c["ts"] if c else None


def cmd_done_task(args):
    if not args:
        print("usage: handoff.sh task <TID>")
        return 1
    tid = args[0]
    st = tasks_state()
    if tid not in st["tasks"]:
        print(f"unknown task {tid}")
        return 1
    t = st["tasks"][tid]
    if is_done(st, tid):
        print(f"{tid} already done ({st['status'][tid]['at']}); 재작업은 `wf.py reopen {tid} <이유>`로만 한다.")
        return 0
    since = claim_ts(t["phase"])
    if not since:
        print(f"REFUSED: {t['phase']} claim이 없다. /build로 시작한다.")
        return 2
    ver = load_verify()
    bad = [v for v in expand(t["verify"]) if not (ver.get(v, {}).get("ok") and after(ver[v]["ts"], since))]
    if bad:
        print(f"NOT DONE {tid}: 이번 claim 이후 통과 기록이 없는 검증 {','.join(bad)} → scripts/verify.sh {' '.join(bad)}")
        return 1
    sid = phase_claim(t["phase"])["sid"]
    st["status"][tid] = {"state": "done", "at": now(), "session": sid}
    save("state/tasks.json", st)
    log_event(sid, f"task-done:{tid}", t["phase"])
    left = [x for x, v in st["tasks"].items() if v["phase"] == t["phase"] and not is_done(st, x)]
    print(f"DONE {tid}. phase {t['phase']} 남은 작업: {' '.join(left) or '없음 → 체크포인트 후 handoff.sh phase'}")
    return 0


def cmd_block(args):
    if len(args) < 2:
        print("usage: handoff.sh block <TID> <사용자만 할 수 있는 조치>")
        return 1
    st = tasks_state()
    t = st["tasks"][args[0]]
    c = phase_claim(t["phase"])
    st["status"][args[0]] = {"state": "blocked", "at": now(), "reason": " ".join(args[1:]), "session": c and c["sid"]}
    save("state/tasks.json", st)
    log_event(c["sid"] if c else "user", f"blocked:{args[0]}", t["phase"])
    print(f"BLOCKED {args[0]}: 최종 보고에 미실행으로 남는다.")
    return 0


def cmd_reopen(args):
    if len(args) < 2:
        print("usage: wf.py reopen <TID> <reason>")
        return 1
    st = tasks_state()
    st["status"].pop(args[0], None)
    save("state/tasks.json", st)
    log_event("user", f"reopen:{args[0]}", st["tasks"][args[0]]["phase"])
    with open(ROOT / "state/reopen.log", "a") as f:
        f.write(f"{now()} {args[0]} {' '.join(args[1:])}\n")
    print(f"reopened {args[0]}")
    return 0


def cmd_handoff_phase(args):
    accept = None
    if "--accept-shots" in args:
        i = args.index("--accept-shots")
        accept = " ".join(args[i + 1:]).strip()
        if not accept:
            print("--accept-shots 뒤에 이유를 적는다.")
            return 1
    st = tasks_state()
    ph, pending = next_phase(st)
    if not ph:
        print("ALL_DONE")
        return 3
    since = claim_ts(ph["id"])
    if not since:
        print("REFUSED: claim이 없다.")
        return 2
    problems = []
    if pending:
        problems.append(f"미완료 작업 {' '.join(pending)}")
    ver = load_verify()
    for v in expand(ph["checkpoint"]):
        r = ver.get(v)
        if not (r and r["ok"] and not r["args"] and after(r["ts"], since)):
            problems.append(f"전체 검증 {v} 통과 기록 없음(인자 없이 scripts/verify.sh {v})")
    if ph["shots"]:
        sp = ROOT / "state/shots-result.json"
        res = json.loads(sp.read_text()) if sp.exists() else None
        if not res or not after(res["ts"], since) or ph["id"] not in res.get("phases", []):
            problems.append(f"shots 체크포인트 없음(node scripts/shots.mjs --phase {ph['id']})")
        elif not res["ok"] and not accept:
            over = [r["name"] for r in res["results"] if r["status"] not in ("ok", "pass")]
            problems.append(f"shots 기준 초과·오류 {' '.join(over)} → 수정하거나 --accept-shots <이유>")
    pc = cfg()["progress"]
    prog = ROOT / pc["file"]
    lines = len(prog.read_text().splitlines())
    if lines > pc["max_lines"]:
        problems.append(f"PROGRESS.md {lines}줄 > {pc['max_lines']}")
    if not after(dt.datetime.fromtimestamp(prog.stat().st_mtime).astimezone().isoformat(), since):
        problems.append("PROGRESS.md가 이번 claim 이후 갱신되지 않음")
    if problems:
        print("HANDOFF REFUSED:\n  " + "\n  ".join(problems))
        return 1
    sid = phase_claim(ph["id"])["sid"]
    if accept:
        with open(ROOT / "state/accepted-shots.log", "a") as f:
            f.write(f"{now()} {ph['id']} {accept}\n")
    build_srcmap(if_stale=True, quiet=True)
    log_event(sid, "phase-done", ph["id"])
    if (ROOT / ".git").exists():
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=False)
    nxt, _ = next_phase(tasks_state())
    print(f"PHASE {ph['id']} DONE. 다음: {nxt['id'] if nxt else '없음(전체 완료)'}")
    cmd_usage(["--quiet"])
    print("다음: /exit 후 scripts/start.sh --launch" if nxt else "전체 완료: scripts/start.sh 로 최종 사용량 확인")
    return 0


def cmd_status(args):
    st = tasks_state()
    for ph in st["phases"]:
        ids = [t for t, v in st["tasks"].items() if v["phase"] == ph["id"]]
        marks = " ".join(f"{t}{'✓' if is_done(st, t) else '·'}" for t in ids)
        done = any(e["event"] == "phase-done" and e["phase"] == ph["id"] for e in events())
        print(f"{ph['id']} {'DONE' if done else '    '} {marks}")
    return 0


# ---------------------------------------------------------------- env

def ensure_env():
    p = ROOT / "state/env.json"
    if p.exists():
        return json.loads(p.read_text())
    res = {}
    for k, argv in cfg()["env_checks"].items():
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            res[k] = (r.stdout.strip().splitlines() or ["ok"])[0] if r.returncode == 0 else "MISSING"
        except (OSError, subprocess.TimeoutExpired):
            res[k] = "MISSING"
    p.write_text(json.dumps(res, ensure_ascii=False) + "\n")
    return res


# ---------------------------------------------------------------- verify

def load_verify():
    p = ROOT / "state/verify.json"
    return json.loads(p.read_text()) if p.exists() else {}


def expand(targets):
    v = cfg()["verify"]
    out = []
    for t in targets:
        out += v[t] if isinstance(v.get(t), list) else [t]
    return out


def summarize(parser, text, ok):
    lines = [ANSI.sub("", l).rstrip() for l in text.splitlines()]
    if parser == "pytest":
        head = [l for l in lines if re.search(r"\d+ (passed|failed|errors?)\b", l)][-1:]
        detail = [l for l in lines if l.startswith(("FAILED ", "ERROR "))][:20]
        detail += [l for l in lines if l.startswith("E  ")][:15]
    elif parser == "vitest":
        head = [l.strip() for l in lines if re.match(r"\s*(Test Files|Tests)\s", l)]
        detail = [l for l in lines if re.search(r"FAIL |×|✗|AssertionError|Error:", l)][:25]
    elif parser == "unity":
        head = [l for l in lines if re.search(r"Build (Finished|succeeded|failed)|Exiting batchmode", l)][-2:]
        detail = [l for l in lines if re.search(r"error CS\d+|BuildFailedException|Aborting batchmode|Scripts have compiler errors", l)][:20]
    else:
        head, detail = [], []
    if not ok and not detail:
        detail = [l for l in lines if re.search(r"error|Error|ERR!", l)][-15:] or [l for l in lines if l.strip()][-15:]
    return head, detail


def cmd_verify(args):
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if not args:
        print("usage: verify.sh <backend|frontend|build|unity|all> [extra args]")
        return 1
    target, extra = args[0], args[1:]
    conf = cfg()["verify"]
    if target not in conf:
        print(f"unknown target {target}")
        return 1
    if isinstance(conf[target], list):
        rc = 0
        for t in conf[target]:
            rc = max(rc, cmd_verify([t] + (["--dry-run"] if dry else [])))
        return rc
    c = conf[target]
    argv = c["cmd"] + extra
    cwd = ROOT / c["cwd"]
    if dry:
        print(f"DRY-RUN {target}: (cd {c['cwd']} && {' '.join(argv)})")
        return 0
    logdir = ROOT / "reports/logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{target}.log"
    t0 = time.time()
    if not cwd.is_dir():
        ok, text = False, f"{c['cwd']}/ 없음"
    else:
        env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "CI": "1"}
        try:
            r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=c.get("timeout", 900))
            ok, text = r.returncode == 0, r.stdout + r.stderr
        except subprocess.TimeoutExpired as e:
            ok, text = False, f"TIMEOUT {c.get('timeout')}s\n{e.stdout or ''}"
        except OSError as e:
            ok, text = False, str(e)
    log.write_text(text)
    head, detail = summarize(c["parser"], text, ok)
    ver = load_verify()
    ver[target] = {"ok": ok, "ts": now(), "args": extra, "summary": " | ".join(head), "log": str(log.relative_to(ROOT))}
    save("state/verify.json", ver)
    print(f"[verify] {target} {'PASS' if ok else 'FAIL'} {' | '.join(head)} ({time.time() - t0:.0f}s) log={log.relative_to(ROOT)}")
    if not ok:
        print("\n".join("  " + l for l in detail))
    return 0 if ok else 1


# ---------------------------------------------------------------- dev services

RUN = ROOT / "state/run"


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def pid_alive(name):
    p = RUN / f"{name}.pid"
    if not p.exists():
        return None
    pid = int(p.read_text())
    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        p.unlink()
        return None


def stop(name):
    pid = pid_alive(name)
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                break
        (RUN / f"{name}.pid").unlink(missing_ok=True)
        return True
    return False


def healthy(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def cmd_dev(args):
    action = args[0] if args else "status"
    fresh = "--fresh" in args
    d = cfg()["dev"]
    RUN.mkdir(parents=True, exist_ok=True)
    svcs = d["services"]
    if action == "status":
        for n, s in svcs.items():
            print(f"{n}: pid={pid_alive(n) or '-'} port={'open' if port_open(s['port']) else 'closed'} health={'ok' if healthy(s['health']) else 'fail'}")
        return 0
    if action == "down":
        for n in svcs:
            print(f"{n}: {'stopped' if stop(n) else 'not running'}")
        return 0
    if action != "up":
        print("usage: dev.sh up [--fresh] | down | status")
        return 1
    env = dict(os.environ)
    mode = "fresh" if fresh else "default"
    if fresh:
        for k, v in d["fresh_env"].items():
            env[k] = str(ROOT / v)
        db = Path(env["SHIPYARD_DB_PATH"])
        for f in glob.glob(str(db) + "*"):
            os.remove(f)
        Path(env["SHIPYARD_FILE_DIR"]).mkdir(parents=True, exist_ok=True)
    mode_file = RUN / "mode"
    prev = mode_file.read_text() if mode_file.exists() else None
    if fresh or prev != mode:
        stop("backend")
    seed = d["seed"]
    if fresh or not pid_alive("backend"):
        r = subprocess.run(seed["cmd"], cwd=ROOT / seed["cwd"], env=env, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"seed FAIL: {(r.stdout + r.stderr).strip()[-800:]}")
            return 1
    for n, s in svcs.items():
        if pid_alive(n):
            continue
        if port_open(s["port"]):
            print(f"{n}: port {s['port']}를 다른 프로세스가 쓰고 있다. 종료 후 다시 실행한다.")
            return 1
        cwd = ROOT / s["cwd"]
        if not cwd.is_dir():
            print(f"{n}: {s['cwd']}/ 없음")
            return 1
        (ROOT / "reports/logs").mkdir(parents=True, exist_ok=True)
        logf = open(ROOT / "reports/logs" / f"dev-{n}.log", "w")
        p = subprocess.Popen(s["cmd"], cwd=cwd, env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        (RUN / f"{n}.pid").write_text(str(p.pid))
    mode_file.write_text(mode)
    deadline = time.time() + d["health_timeout"]
    pending = dict(svcs)
    while pending and time.time() < deadline:
        for n in list(pending):
            if healthy(pending[n]["health"]):
                pending.pop(n)
        time.sleep(0.5)
    if pending:
        print(f"health FAIL: {' '.join(pending)} (reports/logs/dev-*.log)")
        return 1
    print(f"dev up ({mode}): " + " ".join(f"{n}={s['health']}" for n, s in svcs.items()))
    return 0


# ---------------------------------------------------------------- source map

def scan_files():
    sc = cfg()["srcmap"]
    files = []
    for r in sc["roots"]:
        base = ROOT / r
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(ROOT).as_posix()
            if p.is_file() and p.suffix in (".py", ".vue", ".js", ".css", ".cs", ".jslib") and not re.search(
                    r"(node_modules|__pycache__|/Library/|/Temp/|\.venv|/dist/)", rel):
                files.append(p)
    return files


def files_hash(files):
    h = hashlib.sha1()
    for p in files:
        s = p.stat()
        h.update(f"{p.relative_to(ROOT)}:{s.st_mtime_ns}:{s.st_size}\n".encode())
    return h.hexdigest()[:12]


def css_classes(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    preludes = [p for p in re.findall(r"([^{};]+)\{", css) if not p.strip().startswith("@")]  # selectors only
    return sorted(set(re.findall(r"\.([A-Za-z_][\w-]*)", " ".join(preludes))))


def balanced(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] in "([{":
            depth += 1
        elif text[i] in ")]}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return text[start + 1:]


def vue_api(src):
    props, emits = [], []
    m = re.search(r"defineProps\s*(<[^>]*>)?\s*\(", src)
    if m:
        body = m.group(1) or balanced(src, m.end() - 1)
        inner = body.strip()
        if inner.startswith("["):
            props = re.findall(r"['\"](\w+)['\"]", inner)
        else:
            inner = inner.strip("{}<> ")
            depth, key, out = 0, "", []
            for ch in inner:  # collect top-level keys only
                if ch in "{[(":
                    depth += 1
                elif ch in "}])":
                    depth -= 1
                if depth == 0:
                    key += ch
            props = re.findall(r"(?:^|[,;\n])\s*['\"]?(\w+)['\"]?\??\s*:", key)
    m = re.search(r"defineEmits\s*(<[^>]*>)?\s*\(", src)
    if m:
        body = m.group(1) or balanced(src, m.end() - 1)
        emits = re.findall(r"['\"]([\w:-]+)['\"]", body)
    style = "".join(re.findall(r"<style[^>]*>(.*?)</style>", src, flags=re.S))
    return props, emits, css_classes(style)


def openapi_lines():
    oc = cfg()["srcmap"]["openapi_cmd"]
    if not (ROOT / oc["cwd"]).is_dir():
        return []
    try:
        r = subprocess.run(oc["cmd"], cwd=ROOT / oc["cwd"], capture_output=True, text=True, timeout=oc["timeout"])
        spec = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return []
    out = []
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            params = ",".join(p["name"] for p in op.get("parameters", []) if p.get("in") == "query")
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            ref = body.get("$ref", "").split("/")[-1] or ("multipart" if "multipart/form-data" in op.get("requestBody", {}).get("content", {}) else "")
            out.append(f"{method.upper()} {path}" + (f" ?{params}" if params else "") + (f" body={ref}" if ref else ""))
    return out


def build_srcmap(if_stale=False, quiet=False):
    sc = cfg()["srcmap"]
    out = ROOT / sc["out"]
    files = scan_files()
    h = files_hash(files)
    if if_stale and out.exists() and out.read_text().startswith(f"<!-- srcmap:{h} -->"):
        if not quiet:
            print(f"srcmap fresh ({h})")
        return 0
    lines = [f"<!-- srcmap:{h} -->", "# SOURCEMAP (scripts/wf.py srcmap가 생성. 직접 고치지 않는다)"]
    api = openapi_lines()
    if api:
        lines += ["## API (openapi)"] + api
    py, vue, js, css, cs, tests = [], [], [], [], [], []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        src = p.read_text(errors="ignore")
        if "/tests/" in rel or "__tests__" in rel or re.search(r"\.(test|spec)\.js$", rel):
            n = len(re.findall(r"^\s*def test_|\b(?:it|test)\(", src, flags=re.M))
            tests.append(f"{rel} ({n})")
        elif p.suffix == ".py":
            names = re.findall(r"^(?:async )?def (\w+)|^class (\w+)", src, flags=re.M)
            names = [a or b for a, b in names if not (a or b).startswith("_")]
            routes = re.findall(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)", src)
            r = (" routes: " + ", ".join(f"{m.upper()} {u}" for m, u in routes)) if routes and not api else ""
            if names or r:
                py.append(f"{rel}: {', '.join(names)}{r}")
        elif p.suffix == ".vue":
            props, emits, cls = vue_api(src)
            vue.append(f"{rel}: props[{','.join(props)}] emits[{','.join(emits)}]" + (f" css[{' '.join(cls[:40])}]" if cls else ""))
        elif p.suffix == ".js":
            names = re.findall(r"^export (?:default )?(?:async )?(?:function\*?|const|let|class) (\w+)", src, flags=re.M)
            if re.search(r"^export default", src, flags=re.M) and not names:
                names = ["default"]
            if names:
                js.append(f"{rel}: {', '.join(names)}")
        elif p.suffix == ".css":
            cls = css_classes(src)
            css.append(f"{rel}: {' '.join(cls[:150])}" + (f" …(+{len(cls) - 150})" if len(cls) > 150 else ""))
        elif p.suffix in (".cs", ".jslib"):
            names = re.findall(r"\bclass (\w+)|public [\w<>\[\], ]+? (\w+)\s*\(", src)
            cs.append(f"{rel}: {', '.join(a or b for a, b in names)}")
    for title, rows in (("Python", py), ("Vue (props/emits/scoped css)", vue), ("JS exports", js), ("CSS classes", css),
                        ("Unity", cs), ("Tests (count)", tests)):
        if rows:
            lines += [f"## {title}"] + rows
    text = "\n".join(lines) + "\n"
    out.write_text(text)
    if not quiet:
        print(f"srcmap written {sc['out']} {len(text.encode())}B" + (" (max_bytes 초과: 항목을 줄일 것)" if len(text.encode()) > sc["max_bytes"] else ""))
    return 0


def cmd_srcmap(args):
    return build_srcmap(if_stale="--if-stale" in args)


# ---------------------------------------------------------------- usage

def claude_project_dir():
    base = Path(os.environ.get("WF_CLAUDE_PROJECTS") or Path.home() / ".claude/projects")
    return base / re.sub(r"[^A-Za-z0-9]", "-", str(ROOT.resolve()))


FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def session_usage(sid, short_out):
    d = claude_project_dir()
    files = [d / f"{sid}.jsonl"] + [Path(p) for p in glob.glob(str(d / sid / "**/*.jsonl"), recursive=True)]
    msgs = {}
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(errors="ignore").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            m = o.get("message") or {}
            if o.get("type") == "assistant" and m.get("id") and m.get("model") != "<synthetic>":
                msgs[m["id"]] = m.get("usage") or {}  # last write wins (streamed partials)
    tot = {k: sum(u.get(k, 0) for u in msgs.values()) for k in FIELDS}
    ctx = [u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0) for u in msgs.values()]
    tot.update(api_calls=len(msgs), total=sum(tot[k] for k in FIELDS),
               first_ctx=ctx[0] if ctx else 0, max_ctx=max(ctx) if ctx else 0,
               short_calls=sum(1 for u in msgs.values() if u.get("output_tokens", 0) < short_out),
               subagent_files=len(files) - 1, found=bool(msgs))
    return tot


def cmd_usage(args):
    pol = policy()
    sids = []
    phase_of = {}
    for e in events():
        if e["event"] in ("claim", "resume", "takeover") and e["sid"] not in sids:
            sids.append(e["sid"])
        if e["event"] in ("claim", "resume", "takeover"):
            phase_of.setdefault(e["sid"], e["phase"])
    rows = {sid: session_usage(sid, pol["short_call_output_tokens"]) for sid in sids}
    grand = {k: sum(r[k] for r in rows.values()) for k in FIELDS + ("api_calls", "total", "short_calls")}
    rates = pol["pricing"]["usd_per_mtok"]
    cost = None
    if all(isinstance(rates[k], (int, float)) for k in ("input", "output", "cache_creation", "cache_read")):
        cost = round((grand["input_tokens"] * rates["input"] + grand["output_tokens"] * rates["output"]
                      + grand["cache_creation_input_tokens"] * rates["cache_creation"]
                      + grand["cache_read_input_tokens"] * rates["cache_read"]) / 1e6, 2)
    report = {"generated": now(), "project_dir": str(claude_project_dir()), "sessions": [
        {"sid": s, "phase": phase_of.get(s), **r} for s, r in rows.items()], "total": grand,
        "cost_usd": cost, "cost_note": None if cost is not None else "token-policy.json pricing 미설정: 비용 미산출",
        "budget": {"total_tokens_target": pol["total_tokens_target"], "phase_api_calls": pol["phase_budget"]["api_calls"]}}
    (ROOT / "reports").mkdir(exist_ok=True)
    save("reports/usage.json", report)
    print(f"usage (reports/usage.json): sessions={len(rows)} calls={grand['api_calls']} total={grand['total']:,} "
          f"target={pol['total_tokens_target']:,}" + (f" cost=${cost}" if cost is not None else ""))
    if "--quiet" not in args:
        for s, r in rows.items():
            flag = " OVER-CALLS" if r["api_calls"] > pol["phase_budget"]["api_calls"] else ""
            miss = "" if r["found"] else " (transcript 없음)"
            print(f"  {phase_of.get(s)} {s[:8]} calls={r['api_calls']} short={r['short_calls']} total={r['total']:,} "
                  f"first_ctx={r['first_ctx']:,} max_ctx={r['max_ctx']:,}{flag}{miss}")
    return 0


COMMANDS = {"next": cmd_next, "launch": cmd_launch, "claim": cmd_claim, "done-task": cmd_done_task,
            "reopen": cmd_reopen, "block": cmd_block, "handoff-phase": cmd_handoff_phase, "status": cmd_status, "verify": cmd_verify,
            "dev": cmd_dev, "srcmap": cmd_srcmap, "usage": cmd_usage}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("commands: " + " ".join(COMMANDS))
        sys.exit(1)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]) or 0)
