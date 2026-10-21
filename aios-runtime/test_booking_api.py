"""Schema tests for the internal appointment booking API."""
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import main


class BookingSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {"JBSN_DB_PATH": str(Path(self.tmp.name)/"db.sqlite"),
            "DATABASE_URL": "", "JBSN_DATABASE_BACKEND": "sqlite", "JBSN_API_TOKEN": "test-token"}, clear=False)
        self.patch.start()
        main.DB_PATH = Path(self.tmp.name)/"db.sqlite"
        main.DATABASE_URL = ""
        main.USE_POSTGRES = False
        main.TOKEN = "test-token"
        main.init_db()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_appointments_table_exists(self):
        with main.db() as c:
            row = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'").fetchone()
        self.assertIsNotNone(row)

    def test_slot_and_idempotency_are_unique(self):
        with main.db() as c:
            sql = "INSERT INTO appointments(id,start_at,duration_minutes,service,name,email,contact_consent,timezone,status,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)"
            values = ("a1","2030-01-02T08:00:00+00:00",30,"discovery","Test","test@example.com",1,"Africa/Johannesburg","confirmed","request-0001",1.0)
            c.execute(sql, values)
            with self.assertRaises(Exception):
                c.execute(sql, ("a2", values[1],30,"discovery","Test2","t2@example.com",1,"Africa/Johannesburg","confirmed","request-0002",2.0))
            with self.assertRaises(Exception):
                c.execute(sql, ("a3","2030-01-02T08:30:00+00:00",30,"discovery","Test3","t3@example.com",1,"Africa/Johannesburg","confirmed","request-0001",3.0))


if __name__ == "__main__":
    unittest.main()
