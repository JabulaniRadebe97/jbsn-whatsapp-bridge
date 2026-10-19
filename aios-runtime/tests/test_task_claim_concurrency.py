"""Regression tests for atomic task claiming in the JBSN AI OS runtime."""
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aios-runtime"))
import main as runtime  # noqa: E402


class FakeCursor:
    def __init__(self, row=None, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.sql = []
        self.row = {
            "id": "task-1",
            "attempts": 0,
            "status": "queued",
            "created_at": 1.0,
        }

    def execute(self, sql, params=()):
        self.sql.append(sql)
        if sql.lstrip().upper().startswith("SELECT"):
            return FakeCursor(self.row)
        return FakeCursor(rowcount=1)


class TaskClaimConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.backend_patch = patch.object(runtime, "USE_POSTGRES", False)
        self.backend_patch.start()
        self.addCleanup(self.backend_patch.stop)

    def make_sqlite_db(self, path):
        conn = sqlite3.connect(path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                lease_expires_at REAL,
                claim_token TEXT
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            INSERT INTO tasks(id,status,attempts,created_at,updated_at)
            VALUES ('only-task','queued',0,1,1);
        """)
        conn.commit()
        return conn

    def test_postgres_claim_uses_skip_locked(self):
        fake = FakeConnection()
        with patch.object(runtime, "USE_POSTGRES", True), patch.object(runtime, "database_epoch", return_value=1000.0):
            claim = runtime.claim_queued_task(fake)
        select_sql = next(s for s in fake.sql if s.lstrip().upper().startswith("SELECT"))
        self.assertIn("FOR UPDATE SKIP LOCKED", select_sql.upper())
        self.assertEqual(claim["id"], "task-1")
        self.assertEqual(claim["attempt"], 1)
        self.assertTrue(claim["claim_token"])
        self.assertTrue(any("UPDATE tasks SET status='running'" in s for s in fake.sql))
        self.assertTrue(any("INSERT INTO events" in s for s in fake.sql))

    def test_two_concurrent_sqlite_claimers_claim_task_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "claims.sqlite3")
            setup = self.make_sqlite_db(path)
            setup.close()
            barrier = threading.Barrier(2)
            claims = []
            errors = []

            def worker():
                conn = sqlite3.connect(path, timeout=5)
                conn.row_factory = sqlite3.Row
                try:
                    barrier.wait(timeout=3)
                    conn.execute("BEGIN IMMEDIATE")
                    claim = runtime.claim_queued_task(conn)
                    conn.commit()
                    claims.append(claim)
                except Exception as exc:  # surfaced in the test thread
                    conn.rollback()
                    errors.append(exc)
                finally:
                    conn.close()

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=8)

            self.assertFalse(any(thread.is_alive() for thread in threads), "claim threads timed out")
            self.assertEqual(errors, [])
            self.assertEqual(sum(claim is not None for claim in claims), 1)
            check = sqlite3.connect(path)
            row = check.execute("SELECT status, attempts FROM tasks WHERE id='only-task'").fetchone()
            event_count = check.execute(
                "SELECT COUNT(*) FROM events WHERE task_id='only-task' AND event_type='task.started'"
            ).fetchone()[0]
            check.close()
            self.assertEqual(row, ("running", 1))
            self.assertEqual(event_count, 1)

    def test_empty_queue_returns_none(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, status TEXT, attempts INTEGER,
                created_at REAL, updated_at REAL
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
                event_type TEXT, detail TEXT, created_at REAL
            );
        """)
        conn.execute("BEGIN IMMEDIATE")
        self.assertIsNone(runtime.claim_queued_task(conn))
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    unittest.main()
