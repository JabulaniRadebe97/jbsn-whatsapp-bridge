"""Real PostgreSQL integration coverage for task claiming.

Enabled in CI with JBSN_TEST_POSTGRES_DSN. Local unit runs skip this test unless
that environment variable points to an isolated test database.
"""
import os
import unittest
import uuid
from unittest.mock import patch

DSN = os.environ.get("JBSN_TEST_POSTGRES_DSN", "").strip()


@unittest.skipUnless(DSN, "set JBSN_TEST_POSTGRES_DSN to run real PostgreSQL integration test")
class PostgresTaskClaimIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg.rows import dict_row
        import main as runtime

        cls.psycopg = psycopg
        cls.dict_row = dict_row
        cls.runtime = runtime
        cls.schema = "claim_test_" + uuid.uuid4().hex[:16]
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{cls.schema}"')
            conn.execute(f'SET search_path TO "{cls.schema}"')
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at DOUBLE PRECISION NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    lease_expires_at DOUBLE PRECISION,
                    claim_token TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE events (
                    id BIGSERIAL PRIMARY KEY,
                    task_id TEXT,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                )
            """)

    @classmethod
    def tearDownClass(cls):
        with cls.psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{cls.schema}" CASCADE')

    def setUp(self):
        # Tests share one isolated schema; clear rows so ordering cannot leak
        # state from the PostgreSQL recovery test into the claim-lock test.
        conn = self.connect_in_schema()
        try:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM tasks")
            conn.commit()
        finally:
            conn.close()

    def connect_in_schema(self):
        conn = self.psycopg.connect(DSN, row_factory=type(self).dict_row)
        conn.execute(f'SET search_path TO "{self.schema}"')
        conn.commit()
        return conn

    def test_locked_queued_task_is_skipped_by_second_postgres_worker(self):
        with patch.object(self.runtime, "USE_POSTGRES", True):
            setup = self.connect_in_schema()
            try:
                setup.execute(
                    "INSERT INTO tasks(id,status,attempts,created_at,updated_at) "
                    "VALUES (%s,'queued',0,1,1)",
                    ("one-task",),
                )
                setup.commit()
            finally:
                setup.close()

            first = self.connect_in_schema()
            second = self.connect_in_schema()
            first_runtime = self.runtime.PgConnection(first)
            second_runtime = self.runtime.PgConnection(second)
            try:
                # Exercise the same transaction command used by the production
                # worker; PgConnection translates BEGIN IMMEDIATE to BEGIN for PostgreSQL.
                first_runtime.execute("BEGIN IMMEDIATE")
                first_claim = self.runtime.claim_queued_task(first_runtime)
                self.assertEqual(first_claim["id"], "one-task")
                self.assertEqual(first_claim["attempt"], 1)
                self.assertTrue(first_claim["claim_token"])

                second_runtime.execute("BEGIN IMMEDIATE")
                second_claim = self.runtime.claim_queued_task(second_runtime)
                self.assertIsNone(second_claim, "second worker must skip the row locked by the first worker")
                second.commit()
                first.commit()
            finally:
                first.close()
                second.close()

            check = self.connect_in_schema()
            try:
                row = check.execute(
                    "SELECT status, attempts FROM tasks WHERE id=%s", ("one-task",)
                ).fetchone()
                events = check.execute(
                    "SELECT COUNT(*) AS count FROM events "
                    "WHERE task_id=%s AND event_type='task.started'", ("one-task",)
                ).fetchone()
            finally:
                check.close()

            self.assertEqual(row["status"], "running")
            self.assertEqual(row["attempts"], 1)
            self.assertEqual(events["count"], 1)


    def test_expired_postgres_lease_is_requeued_with_audit_event(self):
        with patch.object(self.runtime, "USE_POSTGRES", True):
            setup = self.connect_in_schema()
            try:
                setup.execute(
                    "INSERT INTO tasks(id,status,attempts,created_at,updated_at,lease_expires_at,claim_token) "
                    "VALUES (%s,'running',1,1,1,%s,%s)",
                    ("expired-recovery", 10, "expired-token"),
                )
                setup.execute(
                    "INSERT INTO tasks(id,status,attempts,created_at,updated_at,lease_expires_at,claim_token) "
                    "VALUES (%s,'running',1,1,1,%s,%s)",
                    ("live-lease", 100, "live-token"),
                )
                setup.execute(
                    "INSERT INTO tasks(id,status,attempts,created_at,updated_at) "
                    "VALUES (%s,'running',1,1,1)",
                    ("legacy-unleased",),
                )
                setup.commit()
            finally:
                setup.close()

            conn = self.connect_in_schema()
            wrapped = self.runtime.PgConnection(conn)
            try:
                wrapped.execute("BEGIN IMMEDIATE")
                recovered = self.runtime.recover_expired_tasks(wrapped, now=20)
                conn.commit()
            finally:
                conn.close()

            check = self.connect_in_schema()
            try:
                rows = check.execute(
                    "SELECT id,status,claim_token,lease_expires_at FROM tasks ORDER BY id"
                ).fetchall()
                events = check.execute(
                    "SELECT event_type,detail FROM events WHERE task_id=%s ORDER BY id",
                    ("expired-recovery",),
                ).fetchall()
            finally:
                check.close()

            by_id = {row["id"]: row for row in rows}
            self.assertEqual(recovered, 1)
            self.assertEqual(by_id["expired-recovery"]["status"], "queued")
            self.assertIsNone(by_id["expired-recovery"]["claim_token"])
            self.assertIsNone(by_id["expired-recovery"]["lease_expires_at"])
            self.assertEqual(by_id["live-lease"]["status"], "running")
            self.assertEqual(by_id["legacy-unleased"]["status"], "running")
            self.assertEqual([event["event_type"] for event in events], ["task.recovered"])


    def test_init_db_migrates_legacy_postgres_tasks_without_losing_rows(self):
        # Replace only this isolated test schema's task table with the pre-lease
        # schema, then run the real PostgreSQL init_db migration against it.
        with patch.object(self.runtime, "USE_POSTGRES", True):
            setup = self.connect_in_schema()
            try:
                setup.execute("DROP TABLE tasks")
                setup.execute("""
                    CREATE TABLE tasks (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, task_type TEXT NOT NULL,
                        payload TEXT NOT NULL, status TEXT NOT NULL, risk TEXT NOT NULL,
                        result TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                        created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
                setup.execute(
                    "INSERT INTO tasks(id,title,task_type,payload,status,risk,attempts,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    ("legacy-row", "Legacy task", "plan", '{"objective":"keep me"}',
                     "running", "green", 1, 1, 1),
                )
                setup.commit()
            finally:
                setup.close()

            from contextlib import contextmanager

            @contextmanager
            def isolated_db():
                conn = self.connect_in_schema()
                wrapped = self.runtime.PgConnection(conn)
                try:
                    yield wrapped
                    wrapped.commit()
                except Exception:
                    wrapped.rollback()
                    raise
                finally:
                    conn.close()

            with patch.object(self.runtime, "db", isolated_db):
                self.runtime.init_db()

            check = self.connect_in_schema()
            try:
                columns = {row["column_name"] for row in check.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name='tasks'", (self.schema,)
                ).fetchall()}
                row = check.execute(
                    "SELECT id,title,status,attempts,lease_expires_at,claim_token FROM tasks WHERE id=%s",
                    ("legacy-row",),
                ).fetchone()
                approval_table = check.execute(
                    "SELECT to_regclass(%s) AS name", (self.schema + ".approvals",)
                ).fetchone()
            finally:
                check.close()

            self.assertIn("lease_expires_at", columns)
            self.assertIn("claim_token", columns)
            self.assertEqual(row["id"], "legacy-row")
            self.assertEqual(row["title"], "Legacy task")
            self.assertEqual(row["status"], "running")
            self.assertEqual(row["attempts"], 1)
            self.assertIsNone(row["lease_expires_at"])
            self.assertIsNone(row["claim_token"])
            self.assertIsNotNone(approval_table["name"])


if __name__ == "__main__":
    unittest.main()
