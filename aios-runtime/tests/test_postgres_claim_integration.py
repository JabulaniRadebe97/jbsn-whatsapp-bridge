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
                    updated_at DOUBLE PRECISION NOT NULL
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

    def connect_in_schema(self):
        conn = self.psycopg.connect(DSN, row_factory=self.dict_row)
        conn.execute(f'SET search_path TO "{self.schema}"')
        conn.commit()
        return conn

    def test_locked_queued_task_is_skipped_by_second_postgres_worker(self):
        from unittest.mock import patch

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
            try:
                first.execute("BEGIN")
                first_claim = self.runtime.claim_queued_task(self.runtime.PgConnection(first))
                self.assertEqual(first_claim, {"id": "one-task", "attempt": 1})

                second.execute("BEGIN")
                second_claim = self.runtime.claim_queued_task(self.runtime.PgConnection(second))
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

            self.assertEqual(row[0], "running")
            self.assertEqual(row[1], 1)
            self.assertEqual(events[0], 1)


if __name__ == "__main__":
    unittest.main()
