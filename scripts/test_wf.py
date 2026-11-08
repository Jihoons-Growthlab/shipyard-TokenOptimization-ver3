"""Self-test for wf.py on a temp fixture root. Run: python3 scripts/test_wf.py"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL = HERE.parent


class WF(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for d in ("config", "state", "reports"):
            (self.tmp / d).mkdir()
        for f in ("config/workflow.json", "config/token-policy.json", "state/tasks.json", "state/PROGRESS.md"):
            shutil.copy(REAL / f, self.tmp / f)
        conf = json.loads((self.tmp / "config/workflow.json").read_text())
        py = sys.executable
        conf["verify"]["backend"] = {"cwd": ".", "cmd": [py, "-c", "print('3 passed in 0.1s')"], "parser": "pytest"}
        conf["verify"]["frontend"] = {"cwd": ".", "cmd": [py, "-c",
            "import sys; print(' FAIL  src/a.test.js > x\\nAssertionError: expected 1\\n Tests  1 failed | 2 passed'); sys.exit(1)"], "parser": "vitest"}
        conf["env_checks"] = {"python": [py, "--version"]}
        conf["srcmap"]["openapi_cmd"]["cwd"] = "no-backend"
        (self.tmp / "config/workflow.json").write_text(json.dumps(conf))
        os.environ["WF_ROOT"] = str(self.tmp)
        os.environ["WF_CLAUDE_PROJECTS"] = str(self.tmp / "projects")
        sys.path.insert(0, str(HERE))
        import wf
        self.wf = __import__("importlib").reload(wf)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cmd(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.wf.COMMANDS[argv[0]](list(argv[1:]))
        return rc or 0, buf.getvalue()

    def finish_phase(self, sid, phase):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == phase:
                self.assertEqual(self.run_cmd("done-task", tid)[0], 0)
        time.sleep(1.1)
        (self.tmp / "state/PROGRESS.md").write_text("# 인계\n- 완료: P1\n")
        return self.run_cmd("handoff-phase")

    def test_session_flow_and_duplicate_refusal(self):
        rc, out = self.run_cmd("next")
        self.assertEqual(rc, 0)
        self.assertIn("PHASE P1", out)
        rc, out = self.run_cmd("claim", "${CLAUDE_SESSION_ID}")
        self.assertEqual(rc, 2)  # unsubstituted id
        rc, out = self.run_cmd("claim", "s1")
        self.assertEqual(rc, 0)
        self.assertIn("[claim]", out)
        self.assertIn("env: python=", out)
        self.assertIn("--- state/PROGRESS.md", out)
        rc, out = self.run_cmd("claim", "s1")
        self.assertIn("[resume]", out)
        # task cannot be done before its verification passes after the claim
        rc, out = self.run_cmd("done-task", "T01")
        self.assertEqual(rc, 1)
        self.assertIn("NOT DONE", out)
        self.assertEqual(self.run_cmd("verify", "backend", "tests/test_x.py")[0], 0)
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 1)
        self.assertIn("미완료 작업", out)
        # targeted run does not satisfy the full checkpoint
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == "P1":
                self.run_cmd("done-task", tid)
        (self.tmp / "state/PROGRESS.md").write_text("x\n")
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("전체 검증 backend", out)
        self.run_cmd("verify", "backend")
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 0, out)
        self.assertIn("PHASE P1 DONE", out)
        # done task is not redone
        rc, out = self.run_cmd("done-task", "T01")
        self.assertIn("already done", out)
        # same session may not start the next phase (Ver2 S5/S6 reuse)
        rc, out = self.run_cmd("claim", "s1")
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED", out)
        rc, out = self.run_cmd("claim", "s2")
        self.assertEqual(rc, 0)
        self.assertIn("PHASE P2", out)
        self.assertIn("reference/ui/login.png", out)
        self.assertIn("--- state/SOURCEMAP.md", out)

    def test_takeover_and_progress_limit(self):
        self.run_cmd("claim", "a")
        rc, out = self.run_cmd("claim", "b")
        self.assertIn("[takeover]", out)
        self.run_cmd("verify", "backend")
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == "P1":
                self.run_cmd("done-task", tid)
        (self.tmp / "state/PROGRESS.md").write_text("line\n" * 41)
        rc, out = self.run_cmd("handoff-phase")
        self.assertEqual(rc, 1)
        self.assertIn("41줄", out)

    def test_shots_gate_and_accept(self):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid, t in st["tasks"].items():
            if t["phase"] == "P1":
                st["status"][tid] = {"state": "done", "at": "2026-01-01T00:00:00+09:00"}
        (self.tmp / "state/tasks.json").write_text(json.dumps(st))
        self.wf.log_event("old", "phase-done", "P1")
        self.run_cmd("claim", "u1")
        conf = json.loads((self.tmp / "config/workflow.json").read_text())
        conf["verify"]["frontend"]["cmd"] = [sys.executable, "-c", "print(' Tests  4 passed (4)')"]
        conf["verify"]["build"] = {"cwd": ".", "cmd": [sys.executable, "-c", "print('built')"], "parser": "generic"}
        (self.tmp / "config/workflow.json").write_text(json.dumps(conf))
        self.run_cmd("verify", "frontend")
        self.run_cmd("verify", "build")
        for tid, t in st["tasks"].items():
            if t["phase"] == "P2":
                self.assertEqual(self.run_cmd("done-task", tid)[0], 0)
        time.sleep(1.1)
        (self.tmp / "state/PROGRESS.md").write_text("ok\n")
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("shots 체크포인트 없음", out)
        res = {"ts": "2999-01-01T00:00:00.000+00:00", "ok": False, "phases": ["P2"],
               "results": [{"name": "hull-list", "status": "over"}]}
        (self.tmp / "state/shots-result.json").write_text(json.dumps(res))
        rc, out = self.run_cmd("handoff-phase")
        self.assertIn("hull-list", out)
        rc, out = self.run_cmd("handoff-phase", "--accept-shots", "시드 날짜 차이")
        self.assertEqual(rc, 0, out)
        self.assertIn("시드 날짜 차이", (self.tmp / "state/accepted-shots.log").read_text())

    def test_verify_summary_and_dry_run(self):
        self.run_cmd("claim", "v")
        rc, out = self.run_cmd("verify", "frontend")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        self.assertIn("AssertionError: expected 1", out)
        self.assertIn("Tests  1 failed", out)
        log = json.loads((self.tmp / "state/verify.json").read_text())["frontend"]["log"]
        self.assertTrue((self.tmp / log).exists())
        rc, out = self.run_cmd("verify", "all", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("DRY-RUN"), 3)

    def test_block_and_all_done(self):
        st = json.loads((self.tmp / "state/tasks.json").read_text())
        for tid in st["tasks"]:
            st["status"][tid] = {"state": "done", "at": "x"}
        st["status"]["T20"] = {"state": "blocked", "reason": "Unity 라이선스"}
        (self.tmp / "state/tasks.json").write_text(json.dumps(st))
        for p in ("P1", "P2", "P3", "P4"):
            self.wf.log_event("x", "phase-done", p)
        rc, out = self.run_cmd("next")
        self.assertEqual(rc, 3)
        self.assertIn("차단(미실행): T20", out)
        self.assertEqual(self.run_cmd("claim", "z")[0], 3)
        self.assertEqual(self.run_cmd("launch", "--dry-run")[0], 3)

    def test_launch_guard(self):
        self.run_cmd("claim", "live")
        proj = self.wf.claude_project_dir()
        proj.mkdir(parents=True)
        (proj / "live.jsonl").write_text("{}\n")
        rc, out = self.run_cmd("launch", "--dry-run")
        self.assertEqual(rc, 2)
        rc, out = self.run_cmd("launch", "--dry-run", "--force")
        self.assertEqual(rc, 0)
        self.assertIn("/build", out)

    def test_srcmap(self):
        vue = self.tmp / "frontend/src/components/Panel.vue"
        vue.parent.mkdir(parents=True)
        vue.write_text("<script setup>\nconst p = defineProps({ hull: { type: Object, required: true }, mode: String })\n"
                       "const e = defineEmits(['saved', 'update:open'])\n</script>\n<style scoped>\n.panel .row:hover { color: red }\n"
                       "@media (max-width: 900px) { .panel-wide { width: 1px } }\n</style>\n")
        (self.tmp / "frontend/src/api").mkdir()
        (self.tmp / "frontend/src/api/client.js").write_text("export async function api(path) {}\nexport class ApiError {}\n")
        (self.tmp / "frontend/src/styles.css").write_text(".btn, .btn-primary > .ic { a: b }\n/* .nope */\n")
        py = self.tmp / "backend/app/routers/hulls.py"
        py.parent.mkdir(parents=True)
        py.write_text("@router.get('/hulls')\ndef list_hulls():\n    pass\ndef _private():\n    pass\n")
        (self.tmp / "backend/tests").mkdir()
        (self.tmp / "backend/tests/test_h.py").write_text("def test_a():\n    pass\ndef test_b():\n    pass\n")
        rc, out = self.run_cmd("srcmap")
        text = (self.tmp / "state/SOURCEMAP.md").read_text()
        self.assertIn("props[hull,mode] emits[saved,update:open] css[panel panel-wide row]", text)
        self.assertIn("client.js: api, ApiError", text)
        self.assertIn("styles.css: btn btn-primary ic", text)
        self.assertIn("list_hulls routes: GET /hulls", text)
        self.assertNotIn("_private", text)
        self.assertIn("test_h.py (2)", text)
        rc, out = self.run_cmd("srcmap", "--if-stale")
        self.assertIn("fresh", out)

    def test_usage_dedup(self):
        self.wf.log_event("sid1", "claim", "P1")
        proj = self.wf.claude_project_dir()
        (proj / "sid1" / "subagents").mkdir(parents=True)
        u = lambda i, o: {"input_tokens": 1, "output_tokens": o, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 100}
        rows = [{"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u(1, 5)}},
                {"type": "assistant", "message": {"id": "m1", "model": "x", "usage": u(1, 900)}},
                {"type": "assistant", "message": {"id": "m2", "model": "<synthetic>", "usage": u(1, 9)}}]
        (proj / "sid1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
        (proj / "sid1/subagents/a.jsonl").write_text(json.dumps({"type": "assistant", "message": {"id": "m3", "model": "x", "usage": u(1, 100)}}))
        rc, out = self.run_cmd("usage")
        rep = json.loads((self.tmp / "reports/usage.json").read_text())
        t = rep["total"]
        self.assertEqual(t["api_calls"], 2)
        self.assertEqual(t["output_tokens"], 1000)
        self.assertEqual(t["total"], 2 * 111 + 1000)
        self.assertEqual(t["short_calls"], 1)
        self.assertIsNone(rep["cost_usd"])


class Shots(unittest.TestCase):
    def test_totp_rfc6238_and_dry_run(self):
        # RFC 6238 SHA1 vector: secret "12345678901234567890", T=59 → 94287082 (8 digits)
        code = subprocess.run(["node", "--input-type=module", "-e",
            f"import {{totp}} from '{HERE / 'shots.mjs'}'; console.log(totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 59000, 30, 8))"],
            capture_output=True, text=True)
        self.assertEqual(code.stdout.strip(), "94287082", code.stderr)
        r = subprocess.run(["node", str(HERE / "shots.mjs"), "--dry-run"], capture_output=True, text=True,
                           env={**os.environ, "WF_ROOT": str(REAL)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("flows=0", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
