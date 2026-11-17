#!/usr/bin/env python3
"""Launch, doctor, drive, and clean up a procurement-copilot verification run.

Verification scaffolding. It does not change the calculator.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

APP = "procurement-copilot"
SKILL_DIR = Path(__file__).resolve().parents[1]
SERVE_PY = Path(__file__).resolve().parent / "serve.py"
BROWSER_MJS = Path(__file__).resolve().parent / "browser.mjs"
TMP_ROOT = Path("/tmp/procurement-copilot-verify")

RENDERED_TABS = ("quote", "price", "score", "inventory", "landed")
RENDERED_LABELS = ("报价比价", "价格分析", "供应商评分", "库存补货", "进口到岸成本")


def repo_root():
    start = Path.cwd()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists() and (candidate / "index.html").exists():
            return candidate
    raise SystemExit("repo root not found (need .git and index.html). Run from the checkout.")


def evidence_root(root):
    return root / ".cursor" / "skills" / "verify-procurement-copilot" / "evidence"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_id_new():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "pcv-%s-%s" % (stamp, os.urandom(3).hex())


def git_output(root, args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def git_head(root):
    return git_output(root, ["rev-parse", "HEAD"]).decode().strip()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def blob_at_head(root, rel):
    return git_output(root, ["show", "HEAD:%s" % rel])


def require_product_clean(root):
    problems = []
    for rel in ("index.html", "抖音码.png"):
        disk = (root / rel).read_bytes()
        committed = blob_at_head(root, rel)
        if disk != committed:
            problems.append("%s differs from HEAD" % rel)
    if problems:
        raise SystemExit("refusing to verify a modified app:\n- " + "\n- ".join(problems))


def is_elf(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def find_chrome():
    override = os.environ.get("VERIFY_CHROME")
    if override:
        path = Path(override)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise SystemExit("VERIFY_CHROME is not an executable file: %s" % override)
        return str(path)
    candidates = [
        Path("/opt/google/chrome/chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/google-chrome"),
    ]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK) and is_elf(path):
            return str(path)
    raise SystemExit(
        "no Chrome/Chromium ELF binary found. Set VERIFY_CHROME to the real browser binary. "
        "Do not use /usr/local/bin/google-chrome: that wrapper pins a shared profile and debugging port."
    )


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def state_path(run_id):
    return TMP_ROOT / run_id / "state.json"


def load_state(run_id):
    path = state_path(run_id)
    if not path.is_file():
        raise SystemExit("no live state for VERIFY_RUN_ID=%s at %s" % (run_id, path))
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state):
    path = Path(state["state_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def require_run_id():
    run_id = os.environ.get("VERIFY_RUN_ID", "").strip()
    if not run_id:
        raise SystemExit("VERIFY_RUN_ID is not set. Export the id printed by launch.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise SystemExit("VERIFY_RUN_ID has unexpected characters")
    return run_id


def append_jsonl(evidence, record):
    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / "commands.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def cmdline(pid):
    raw = Path("/proc/%s/cmdline" % pid).read_bytes()
    return raw.split(b"\0")


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return Path("/proc/%s" % pid).exists()


def listen_inodes(port):
    found = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        path = Path(table)
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            local, status, inode = parts[1], parts[3], parts[9]
            ip_hex, port_hex = local.split(":")
            if int(port_hex, 16) != port or status != "0A":
                continue
            if ip_hex not in ("0100007F", "0000000000000000000000000100007F"):
                continue
            found.add(inode)
    return found


def pid_inodes(pid):
    found = set()
    fd_dir = Path("/proc/%s/fd" % pid)
    if not fd_dir.is_dir():
        return found
    for entry in fd_dir.iterdir():
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        if target.startswith("socket:[") and target.endswith("]"):
            found.add(target[len("socket:[") : -1])
    return found


def http_get(url, timeout=3):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def dump_dom(chrome, profile, url):
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--user-data-dir=%s" % profile,
        "--virtual-time-budget=8000",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=25)
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    return proc.returncode, proc.stdout, proc.stderr


def assert_rendered(dom):
    text = dom.decode("utf-8", errors="replace")
    nav = re.search(r'<nav class="tabs" id="tabs">(.*?)</nav>', text, re.S)
    app = re.search(r'<main id="app">(.*?)</main>', text, re.S)
    problems = []
    if not nav:
        problems.append("rendered DOM has no #tabs")
    else:
        body = nav.group(1)
        if 'class="tab on"' not in body or 'data-tab="quote"' not in body:
            problems.append("报价比价 tab is not the active rendered tab")
        for key, label in zip(RENDERED_TABS, RENDERED_LABELS):
            needle = 'data-tab="%s">%s' % (key, label)
            if needle not in body:
                problems.append("missing rendered tab %s" % label)
    if not app:
        problems.append("rendered DOM has no #app")
    else:
        body = app.group(1)
        if 'data-act="run">开始计算' not in body:
            problems.append("#app is missing 开始计算")
        if "多份报价横向比价" not in body:
            problems.append("#app is missing the quote heading")
        if "点「载入示例」" not in body:
            problems.append("#app is missing the empty-result hint")
    return problems


def diagnose(state, chrome, write_dom_to=None):
    """Read-only checks. Returns a list of problems. Empty means the instance is drivable."""
    problems = []
    pid = state.get("server_pid")
    if not pid_alive(pid):
        return ["server pid %s is not running" % pid]
    try:
        parts = cmdline(pid)
    except OSError as exc:
        return ["cannot read server cmdline: %s" % exc]
    if b"serve.py" not in b" ".join(parts) or state["run_id"].encode() not in b" ".join(parts):
        return ["pid %s is not this run's serve.py" % pid]
    inodes = listen_inodes(state["port"])
    if not inodes:
        problems.append("nothing is listening on 127.0.0.1:%s" % state["port"])
    elif not (inodes & pid_inodes(pid)):
        problems.append("port %s is not owned by pid %s" % (state["port"], pid))
    url = state["url"]
    try:
        status, headers, body = http_get(url)
    except Exception as exc:
        return problems + ["GET %s failed: %s" % (url, exc)]
    if status != 200:
        problems.append("GET / returned %s" % status)
    header_map = {k.lower(): v for k, v in headers.items()}
    if header_map.get("x-verify-run") != state["run_id"]:
        problems.append("X-Verify-Run is %r" % header_map.get("x-verify-run"))
    if header_map.get("x-verify-commit") != state["commit"]:
        problems.append("X-Verify-Commit is %r, state has %s" % (header_map.get("x-verify-commit"), state["commit"]))
    if header_map.get("x-verify-app") != APP:
        problems.append("X-Verify-App is %r" % header_map.get("x-verify-app"))
    if b"<main id=\"app\"></main>" not in body:
        problems.append("served source is not the empty-shell index.html")
    if "采购决策助手 · 网页版" not in body.decode("utf-8", "replace"):
        problems.append("served page title is missing")
    disk = Path(state["repo_root"], "index.html").read_bytes()
    if body != disk:
        problems.append("served index.html bytes differ from the working tree")
    if sha256(disk) != state["index_sha256"]:
        problems.append("index.html hash changed since launch")
    head = git_head(Path(state["repo_root"]))
    if head != state["commit"]:
        problems.append("HEAD is %s but this server was stamped %s" % (head, state["commit"]))
    png_url = urllib.request.Request(url + urllib.parse.quote("抖音码.png"))
    try:
        with urllib.request.urlopen(png_url, timeout=3) as resp:
            png = resp.read()
            png_headers = {k.lower(): v for k, v in resp.headers.items()}
            png_status = resp.status
    except Exception as exc:
        problems.append("GET 抖音码.png failed: %s" % exc)
        png = b""
        png_headers = {}
        png_status = 0
    if png_status and png_status != 200:
        problems.append("抖音码.png returned %s" % png_status)
    if png and png_headers.get("x-verify-run") != state["run_id"]:
        problems.append("抖音码.png is missing this run header")
    if png and sha256(png) != state["png_sha256"]:
        problems.append("served png hash does not match launch")
    try:
        code, dom, err = dump_dom(chrome, Path(state["tmp_dir"]) / "doctor-profile", url)
    except subprocess.TimeoutExpired:
        problems.append("rendered DOM check timed out")
        return problems
    if code != 0:
        problems.append("chrome dump-dom exited %s: %s" % (code, err.decode("utf-8", "replace")[-400:]))
        return problems
    problems.extend(assert_rendered(dom))
    if write_dom_to is not None:
        write_dom_to.write_bytes(dom)
    return problems


def kill_owned(pid, predicate, label):
    if not pid or not pid_alive(pid):
        return "already-stopped"
    try:
        parts = cmdline(pid)
    except OSError as exc:
        raise SystemExit("cleanup refused: cannot read %s pid %s (%s)" % (label, pid, exc))
    if not predicate(parts):
        text = b" ".join(parts).decode("utf-8", "replace")
        raise SystemExit("cleanup refused: %s pid %s cmdline does not belong to this run: %s" % (label, pid, text[:300]))
    pgid = os.getpgid(pid)
    if pgid == pid:
        os.killpg(pgid, signal.SIGTERM)
    else:
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 3
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.1)
    if pid_alive(pid):
        if pgid == pid:
            os.killpg(pgid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)
    if pid_alive(pid):
        raise SystemExit("cleanup failed: %s pid %s is still alive" % (label, pid))
    return "stopped"


def copy_tail(src, dest, lines=200):
    if not src.is_file():
        return
    data = src.read_text(encoding="utf-8", errors="replace").splitlines()
    dest.write_text("\n".join(data[-lines:]) + ("\n" if data else ""), encoding="utf-8")


def cmd_launch():
    root = repo_root()
    require_product_clean(root)
    chrome = find_chrome()
    run_id = os.environ.get("VERIFY_RUN_ID", "").strip() or run_id_new()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise SystemExit("VERIFY_RUN_ID has unexpected characters")
    evidence = evidence_root(root) / run_id
    if evidence.exists():
        raise SystemExit("evidence already exists at %s; pick a new VERIFY_RUN_ID" % evidence)
    if state_path(run_id).exists():
        raise SystemExit("state already exists for %s; cleanup that run first" % run_id)
    port = int(os.environ["VERIFY_PORT"]) if os.environ.get("VERIFY_PORT") else free_port()
    commit = git_head(root)
    index_bytes = (root / "index.html").read_bytes()
    png_bytes = (root / "抖音码.png").read_bytes()
    tmp_dir = TMP_ROOT / run_id
    tmp_dir.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True)
    state = {
        "app": APP,
        "run_id": run_id,
        "commit": commit,
        "index_sha256": sha256(index_bytes),
        "png_sha256": sha256(png_bytes),
        "repo_root": str(root),
        "url": "http://127.0.0.1:%s/" % port,
        "port": port,
        "server_pid": None,
        "browser_pid": None,
        "cdp_port": None,
        "chrome": chrome,
        "evidence_dir": str(evidence),
        "tmp_dir": str(tmp_dir),
        "state_path": str(state_path(run_id)),
        "started_at": now(),
    }
    save_state(state)
    (evidence / "run.json").write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    access_log = evidence / "access.log"
    serve_log = open(evidence / "serve.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            str(SERVE_PY),
            "--root",
            str(root),
            "--port",
            str(port),
            "--run-id",
            run_id,
            "--commit",
            commit,
            "--access-log",
            str(access_log),
        ],
        cwd=str(root),
        stdout=serve_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    state["server_pid"] = server.pid
    save_state(state)
    deadline = time.time() + 10
    last_error = "not started"
    while time.time() < deadline:
        if server.poll() is not None:
            last_error = "server exited %s" % server.returncode
            break
        try:
            status, headers, body = http_get(state["url"])
            headers = {k.lower(): v for k, v in headers.items()}
            if status == 200 and headers.get("x-verify-run") == run_id and b"<main id=\"app\"></main>" in body:
                last_error = ""
                break
            last_error = "status %s" % status
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.15)
    if last_error:
        append_jsonl(evidence, {"ts": now(), "cmd": "launch", "exit": 1, "error": last_error})
        try:
            cmd_cleanup(run_id)
        except SystemExit:
            pass
        raise SystemExit("launch failed: %s" % last_error)
    try:
        code, dom, err = dump_dom(chrome, tmp_dir / "ready-profile", state["url"])
    except subprocess.TimeoutExpired:
        append_jsonl(evidence, {"ts": now(), "cmd": "launch", "exit": 1, "error": "dump-dom timeout"})
        cmd_cleanup(run_id)
        raise SystemExit("launch failed: chrome dump-dom timed out")
    (evidence / "ready.dom.html").write_bytes(dom)
    (evidence / "ready.dom.stderr.txt").write_bytes(err)
    rendered_problems = [] if code == 0 else ["dump-dom exit %s" % code]
    rendered_problems.extend(assert_rendered(dom) if code == 0 else [])
    if rendered_problems:
        append_jsonl(evidence, {"ts": now(), "cmd": "launch", "exit": 1, "error": rendered_problems})
        cmd_cleanup(run_id)
        raise SystemExit("launch failed rendered check:\n- " + "\n- ".join(rendered_problems))
    (evidence / "launch.txt").write_text(
        "\n".join([
            "exit=0",
            "VERIFY_RUN_ID=%s" % run_id,
            "VERIFY_URL=%s" % state["url"],
            "VERIFY_COMMIT=%s" % commit,
            "chrome=%s" % chrome,
            "server_pid=%s" % server.pid,
            "ready=#tabs has five tabs and #app has 开始计算",
            "started_at=%s" % state["started_at"],
        ]) + "\n",
        encoding="utf-8",
    )
    append_jsonl(evidence, {"ts": now(), "cmd": "launch", "exit": 0, "url": state["url"], "commit": commit, "pid": server.pid})
    print("VERIFY_RUN_ID=%s" % run_id)
    print("VERIFY_URL=%s" % state["url"])
    print("VERIFY_COMMIT=%s" % commit)
    print("READY tabs=5 button=开始计算")


def cmd_doctor(run_id):
    root = repo_root()
    evidence = evidence_root(root) / run_id
    if not state_path(run_id).is_file():
        text = "DOCTOR_FAIL run=%s\n- no live state at %s\n" % (run_id, state_path(run_id))
        if evidence.is_dir():
            (evidence / "doctor-after-cleanup.txt").write_text(text, encoding="utf-8")
            append_jsonl(evidence, {"ts": now(), "cmd": "doctor", "exit": 1, "problems": ["no live state"]})
        sys.stderr.write(text)
        raise SystemExit(1)
    state = load_state(run_id)
    evidence = Path(state["evidence_dir"])
    chrome = state.get("chrome") or find_chrome()
    dom_path = evidence / "doctor.dom.html"
    problems = diagnose(state, chrome, write_dom_to=dom_path)
    text = "DOCTOR_OK url=%s commit=%s pid=%s run=%s\n" % (
        state["url"], state["commit"], state["server_pid"], state["run_id"]
    )
    if problems:
        text = "DOCTOR_FAIL run=%s\n- %s\n" % (run_id, "\n- ".join(problems))
        (evidence / "doctor.txt").write_text(text, encoding="utf-8")
        append_jsonl(evidence, {"ts": now(), "cmd": "doctor", "exit": 1, "problems": problems})
        sys.stderr.write(text)
        raise SystemExit(1)
    (evidence / "doctor.txt").write_text(text, encoding="utf-8")
    append_jsonl(evidence, {"ts": now(), "cmd": "doctor", "exit": 0, "url": state["url"], "pid": state["server_pid"]})
    sys.stdout.write(text)


def cmd_browser(run_id, args):
    if not BROWSER_MJS.is_file():
        raise SystemExit("missing %s" % BROWSER_MJS)
    if not (SKILL_DIR / "node_modules" / "playwright-core").is_dir():
        raise SystemExit(
            "playwright-core is not installed. From the repo root run:\n"
            "npm install --prefix .cursor/skills/verify-procurement-copilot"
        )
    state = load_state(run_id)
    evidence = Path(state["evidence_dir"])
    proc = subprocess.run(
        ["node", str(BROWSER_MJS), *args],
        cwd=state["repo_root"],
        text=True,
        capture_output=True,
        env={**os.environ, "VERIFY_RUN_ID": run_id},
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    append_jsonl(evidence, {
        "ts": now(),
        "cmd": "browser " + " ".join(args),
        "exit": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    })
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def cmd_cleanup(run_id):
    path = state_path(run_id)
    root = repo_root()
    evidence = evidence_root(root) / run_id
    if not path.is_file():
        message = "cleanup: no live state for %s\n" % run_id
        if evidence.is_dir():
            (evidence / "cleanup.txt").write_text("exit=0\n" + message + "evidence kept at %s\n" % evidence, encoding="utf-8")
            append_jsonl(evidence, {"ts": now(), "cmd": "cleanup", "exit": 0, "note": "already stopped"})
        sys.stdout.write(message)
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    evidence = Path(state["evidence_dir"])
    notes = []

    def browser_ok(parts):
        text = b" ".join(parts).decode("utf-8", "replace")
        return state["run_id"] in text and "drive-profile" in text

    def server_ok(parts):
        text = b" ".join(parts).decode("utf-8", "replace")
        return "serve.py" in text and state["run_id"] in text

    if state.get("browser_pid"):
        notes.append("browser %s %s" % (state["browser_pid"], kill_owned(state["browser_pid"], browser_ok, "browser")))
    if state.get("server_pid"):
        notes.append("server %s %s" % (state["server_pid"], kill_owned(state["server_pid"], server_ok, "server")))
    tail_src = Path(state["tmp_dir"]) / "chrome-drive.log"
    if tail_src.is_file():
        copy_tail(tail_src, evidence / "chrome-drive.tail.log")
    tmp_dir = Path(state["tmp_dir"])
    if tmp_dir.is_dir():
        shutil.rmtree(tmp_dir)
    if path.exists():
        shutil.rmtree(path.parent, ignore_errors=True)
    text = "exit=0\n" + "\n".join(notes) + "\nevidence kept at %s\n" % evidence
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "cleanup.txt").write_text(text, encoding="utf-8")
    append_jsonl(evidence, {"ts": now(), "cmd": "cleanup", "exit": 0, "notes": notes})
    sys.stdout.write(text)


def main():
    parser = argparse.ArgumentParser(prog="verify.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("launch")
    sub.add_parser("doctor")
    sub.add_parser("cleanup")
    browser = sub.add_parser("browser")
    browser.add_argument("browser_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.cmd == "launch":
        cmd_launch()
        return
    run_id = require_run_id()
    if args.cmd == "doctor":
        cmd_doctor(run_id)
    elif args.cmd == "cleanup":
        cmd_cleanup(run_id)
    elif args.cmd == "browser":
        forwarded = args.browser_args
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]
        if not forwarded:
            raise SystemExit("browser command missing. Example: verify.py browser goto")
        cmd_browser(run_id, forwarded)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as exc:
        raise SystemExit("timed out: %s" % exc)
