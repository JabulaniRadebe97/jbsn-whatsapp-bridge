"""Executable SQLite regression tests for leased task recovery and fencing."""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as runtime  # noqa: E402


class TaskRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.backend = patch.object(runtime, "USE_POSTGRES", False)
        self.backend.start()
        self.addCleanup(self.backend.stop)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE tasks(
                id TEXT PRIMARY KEY,title TEXT NOT NULL,task_type TEXT NOT NULL,
                payload TEXT NOT NULL,status TEXT NOT NULL,risk TEXT NOT NULL,
                result TEXT,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,updated_at REAL NOT NULL,
                lease_expires_at REAL,claim_token TEXT
            );
            CREATE TABLE events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,
                event_type TEXT NOT NULL,detail TEXT NOT NULL,created_at REAL NOT NULL
            );
            CREATE TABLE approvals(
                id TEXT PRIMARY KEY,task_id TEXT NOT NULL,status TEXT NOT NULL,
                decision_by TEXT,reason TEXT,created_at REAL NOT NULL,decided_at REAL
            );
        """)

    def tearDown(self):
        self.conn.close()

    def add_task(self, task_id, status, attempts=1, lease=None, token=None, risk="green"):
        self.conn.execute(
            "INSERT INTO tasks(id,title,task_type,payload,status,risk,result,error,attempts,"
            "created_at,updated_at,lease_expires_at,claim_token) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_id, task_id, "plan", json.dumps({"objective": "test"}), status, risk,
             None, None, attempts, 1, 1, lease, token),
        )
        self.conn.commit()

    def test_lease_duration_configuration_accepts_bounded_integer(self):
        self.assertEqual(runtime.configured_lease_seconds("30"), 30)
        self.assertEqual(runtime.configured_lease_seconds("300"), 300)
        self.assertEqual(runtime.configured_lease_seconds("86400"), 86400)

    def test_lease_duration_configuration_rejects_invalid_values(self):
        for value in ("", "abc", "29", "86401", "-1", "30.5"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    runtime.configured_lease_seconds(value)

    def test_expired_lease_requeues_and_records_event(self):
        self.add_task("expired", "running", lease=10, token="old")
        recovered = runtime.recover_expired_tasks(self.conn, now=20)
        row = self.conn.execute("SELECT status,claim_token,lease_expires_at FROM tasks WHERE id='expired'").fetchone()
        events = self.conn.execute("SELECT event_type FROM events WHERE task_id='expired'").fetchall()
        self.assertEqual(recovered, 1)
        self.assertEqual(tuple(row), ("queued", None, None))
        self.assertEqual([r["event_type"] for r in events], ["task.recovered"])

    def test_live_and_legacy_unleased_tasks_are_not_recovered(self):
        self.add_task("live", "running", lease=30, token="live-token")
        self.add_task("legacy", "running", lease=None, token=None)
        self.assertEqual(runtime.recover_expired_tasks(self.conn, now=20), 0)
        statuses = self.conn.execute("SELECT id,status FROM tasks ORDER BY id").fetchall()
        self.assertEqual([(r["id"], r["status"]) for r in statuses],
                         [("legacy", "running"), ("live", "running")])

    def test_max_attempts_exhaustion_marks_failed(self):
        self.add_task("exhausted", "running", attempts=runtime.MAX_ATTEMPTS, lease=10, token="x")
        self.assertEqual(runtime.recover_expired_tasks(self.conn, now=20), 1)
        row = self.conn.execute("SELECT status FROM tasks WHERE id='exhausted'").fetchone()
        self.assertEqual(row["status"], "failed")

    def test_stale_claim_cannot_complete_after_recovery_and_reclaim(self):
        self.add_task("fenced", "running", lease=10, token="old-token")
        runtime.recover_expired_tasks(self.conn, now=20)
        claim = runtime.claim_queued_task(self.conn)
        self.assertIsNotNone(claim)
        self.assertNotEqual(claim["claim_token"], "old-token")
        self.assertFalse(runtime.finish_claim(self.conn, "fenced", "old-token",
                                              result={"mode": "stale"}))
        row = self.conn.execute("SELECT status,claim_token,result FROM tasks WHERE id='fenced'").fetchone()
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["claim_token"], claim["claim_token"])
        self.assertIsNone(row["result"])

    def test_approval_and_cancelled_tasks_are_not_recovered(self):
        self.add_task("approval", "awaiting_approval", lease=1, token=None, risk="amber")
        self.add_task("cancelled", "cancelled", lease=1, token=None, risk="red")
        self.assertEqual(runtime.recover_expired_tasks(self.conn, now=100), 0)

    def test_successful_completion_clears_lease_and_token(self):
        self.add_task("done", "running", lease=100, token="current")
        result = {"mode": "plan_only", "objective": "test"}
        self.assertTrue(runtime.finish_claim(self.conn, "done", "current", result=result))
        row = self.conn.execute(
            "SELECT status,result,claim_token,lease_expires_at FROM tasks WHERE id='done'"
        ).fetchone()
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(json.loads(row["result"]), result)
        self.assertIsNone(row["claim_token"])
        self.assertIsNone(row["lease_expires_at"])

    def test_sqlite_init_migrates_existing_task_table_without_losing_records(self):
        with patch.object(runtime, "DB_PATH", Path(self._temp_db_path())):
            old_conn = sqlite3.connect(runtime.DB_PATH)
            old_conn.executescript("""
                CREATE TABLE tasks(
                    id TEXT PRIMARY KEY,title TEXT NOT NULL,task_type TEXT NOT NULL,
                    payload TEXT NOT NULL,status TEXT NOT NULL,risk TEXT NOT NULL,
                    result TEXT,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,updated_at REAL NOT NULL
                );
                INSERT INTO tasks VALUES(
                    'legacy','Legacy','plan','{"objective":"keep"}','running',
                    'green',NULL,NULL,1,1,1
                );
            """)
            old_conn.commit()
            old_conn.close()
            runtime.init_db()
            with sqlite3.connect(runtime.DB_PATH) as migrated:
                cols = {row[1] for row in migrated.execute("PRAGMA table_info(tasks)")}
                legacy = migrated.execute(
                    "SELECT id,status,payload FROM tasks WHERE id='legacy'"
                ).fetchone()
            self.assertIn("lease_expires_at", cols)
            self.assertIn("claim_token", cols)
            self.assertEqual(legacy, ("legacy", "running", '{"objective":"keep"}'))

    def _temp_db_path(self):
        import tempfile
        handle = tempfile.NamedTemporaryFile(prefix="jbsn-recovery-", suffix=".sqlite", delete=False)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name


if __name__ == "__main__":
    unittest.main()
