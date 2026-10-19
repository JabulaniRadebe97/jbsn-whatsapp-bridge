"""Tests for opt-in continuous, allowlisted background task processing."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as runtime  # noqa: E402


class AutoWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="jbsn-autoworker-")
        self.db_path = Path(self.tmp.name) / "runtime.sqlite"
        self.backend = patch.object(runtime, "USE_POSTGRES", False)
        self.backend.start()
        self.addCleanup(self.backend.stop)
        self.path_patch = patch.object(runtime, "DB_PATH", self.db_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        runtime.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def create_task(self, risk="green"):
        now = 1000.0
        with runtime.db() as c:
            c.execute(
                "INSERT INTO tasks(id,title,task_type,payload,status,risk,result,error,attempts,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("task-1", "Safe plan", "plan", json.dumps({"objective": "test auto worker"}),
                 "queued" if risk == "green" else "awaiting_approval", risk, None, None, 0, now, now),
            )
        return "task-1"

    def test_poll_interval_is_bounded(self):
        self.assertEqual(runtime.configured_worker_poll_seconds("1"), 1)
        self.assertEqual(runtime.configured_worker_poll_seconds("5"), 5)
        self.assertEqual(runtime.configured_worker_poll_seconds("60"), 60)
        for value in ("", "0", "61", "nope", "1.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.configured_worker_poll_seconds(value)

    def test_background_worker_tick_completes_allowlisted_plan(self):
        self.create_task()
        result = runtime.run_one_task()
        self.assertEqual(result["id"], "task-1")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["result"]["mode"], "plan_only")
        with runtime.db() as c:
            events = [r["event_type"] for r in c.execute(
                "SELECT event_type FROM events WHERE task_id=? ORDER BY id", ("task-1",)
            ).fetchall()]
        self.assertEqual(events, ["task.started", "task.succeeded"])

    def test_gemini_business_plan_requires_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Configure JBSN_GEMINI_PROXY_URL"):
                runtime.gemini_business_plan({"objective": "Build JBSN Creative"})

    def test_gemini_business_plan_parses_valid_json(self):
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps({
            "summary": "Test plan", "assumptions": [], "steps": ["step one"],
            "acceptance_criteria": ["criterion"], "risks": [], "approvals_required": []
        })}]}}]}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(response).encode("utf-8")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
             patch.object(runtime.urllib.request, "urlopen", return_value=FakeResponse()):
            result = runtime.gemini_business_plan({"objective": "Build JBSN Creative"})
        self.assertEqual(result["provider"], "google_gemini")
        self.assertEqual(result["mode"], "gemini_business_plan_only")
        self.assertIn("no code", result["execution_notice"])

    def test_gemini_business_plan_uses_apps_script_proxy_without_runtime_key(self):
        plan = {"summary": "Proxy plan", "assumptions": [], "steps": ["step"],
                "acceptance_criteria": ["pass"], "risks": [], "approvals_required": []}
        response = {"ok": True, "provider": "google_gemini", "model": "gemini-2.5-flash", "plan": plan}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(response).encode("utf-8")
        with patch.object(runtime, "GEMINI_PROXY_URL", "https://script.google.com/macros/s/example/exec"), \\
             patch.object(runtime, "GEMINI_PROXY_TOKEN", "test-proxy-token"), \\
             patch.object(runtime.urllib.request, "urlopen", return_value=FakeResponse()) as fetch, \\
             patch.dict(os.environ, {}, clear=True):
            result = runtime.gemini_business_plan({"objective": "Build JBSN Creative"})
        self.assertEqual(result["provider"], "google_gemini_via_apps_script")
        self.assertEqual(result["plan"]["summary"], "Proxy plan")
        sent = json.loads(fetch.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["action"], "aios_business_plan")
        self.assertEqual(sent["token"], "test-proxy-token")

    def test_worker_does_not_process_tasks_waiting_for_approval(self):
        self.create_task(risk="amber")
        self.assertIsNone(runtime.run_one_task())
        with runtime.db() as c:
            row = c.execute("SELECT status,attempts FROM tasks WHERE id=?", ("task-1",)).fetchone()
        self.assertEqual((row["status"], row["attempts"]), ("awaiting_approval", 0))

    def test_empty_queue_is_a_noop(self):
        self.assertIsNone(runtime.run_one_task())


if __name__ == "__main__":
    unittest.main()
