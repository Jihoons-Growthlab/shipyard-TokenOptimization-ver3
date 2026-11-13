"""Small deterministic phase tracker. Run from the kit root."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state/progress.json"
PHASES = [f"P{i}" for i in range(1, 8)]

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("next")
    check = sub.add_parser("check")
    check.add_argument("name")
    check.add_argument("command", nargs=argparse.REMAINDER)
    finish = sub.add_parser("finish")
    finish.add_argument("phase", choices=PHASES)
    finish.add_argument("--evidence", required=True)
    args = parser.parse_args()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    current = next((p for p in PHASES if p not in state), None)
    if args.action == "next":
        print(f"Current phase: {current or 'Complete'}")
        if current:
            print((ROOT / f"phases/{current}.md").read_text())
            print((ROOT / "state/HANDOFF.md").read_text())
        return 0
    if args.action == "check":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command or not args.name.replace("-", "").replace("_", "").isalnum():
            parser.error("Provide a simple check name and command")
        logs = ROOT / "state/logs"
        logs.mkdir(exist_ok=True)
        path = logs / f"{args.name}.log"
        started = time.time()
        with path.open("w") as output:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=3600)
                code = result.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                output.write(str(error))
                code = 1
        record = {"phase": current, "command": command, "exit_code": code, "seconds": round(time.time()-started, 2), "log": str(path.relative_to(ROOT))}
        path.with_suffix(".json").write_text(json.dumps(record, indent=2))
        print(json.dumps(record))
        if code:
            print("\n".join(path.read_text(errors="replace").splitlines()[-30:]))
        return code
    if args.phase != current:
        parser.error("Finish the current phase first")
    evidence = ROOT / args.evidence
    record = json.loads(evidence.read_text())
    if record.get("phase") != current or record.get("exit_code") != 0:
        parser.error("Evidence must be a successful check of the current phase")
    state[current] = record
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2))
    temp.replace(STATE)
    print(f"Recorded {current}. Review acceptance evidence before starting a fresh session.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
