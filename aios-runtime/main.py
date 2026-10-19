"""JBSN AI OS Core Runtime bootstrap. Safe, plan-only worker; no arbitrary code execution."""
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("JBSN_DB_PATH", str(ROOT / "data" / "jbsn_aios.db")))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL) and os.environ.get("JBSN_DATABASE_BACKEND", "").lower() != "sqlite"
TOKEN = os.environ.get("JBSN_API_TOKEN", "")
VERSION = "0.2.0"


class PgCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        self._cursor.execute(sql.replace("?", "%s"), params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class PgConnection:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
        return False

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            sql = "BEGIN"
        cur.execute(sql.replace("?", "%s"), params)
        return PgCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


@contextmanager
def db():
    if USE_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL configured but psycopg dependency is not installed") from exc
        conn = psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row)
        wrapped = PgConnection(conn)
        try:
            yield wrapped
            # The db() context manager owns the transaction; commit successful
            # operations (including init_db DDL) before closing the connection.
            wrapped.commit()
        except Exception:
            wrapped.rollback()
            raise
        finally:
            conn.close()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    if USE_POSTGRES:
        statements = [
            """CREATE TABLE IF NOT EXISTS tasks(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, task_type TEXT NOT NULL,
                payload TEXT NOT NULL, status TEXT NOT NULL, risk TEXT NOT NULL,
                result TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL)""",
            "CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at)",
            """CREATE TABLE IF NOT EXISTS events(
                id BIGSERIAL PRIMARY KEY, task_id TEXT, event_type TEXT NOT NULL,
                detail TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS approvals(
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL,
                decision_by TEXT, reason TEXT, created_at DOUBLE PRECISION NOT NULL,
                decided_at DOUBLE PRECISION)""",
        ]
        with db() as c:
            for statement in statements:
                c.execute(statement)
    else:
        with db() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,task_type TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,risk TEXT NOT NULL,result TEXT,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status,created_at);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT NOT NULL,detail TEXT NOT NULL,created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,status TEXT NOT NULL,decision_by TEXT,reason TEXT,created_at REAL NOT NULL,decided_at REAL);""")


def event(c, task_id, kind, detail):
    c.execute("INSERT INTO events(task_id,event_type,detail,created_at) VALUES(?,?,?,?)", (task_id, kind, json.dumps(detail), time.time()))


def serial(row):
    if row is None:
        return None
    d = dict(row)
    for k in ("payload", "result"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


def plan(payload):
    objective = str(payload.get("objective", "")).strip()
    if not objective:
        raise ValueError("payload.objective is required")
    return {
        "mode": "plan_only",
        "objective": objective,
        "steps": ["define acceptance criteria", "inspect source and dependencies",
                  "create isolated implementation branch", "implement code and tests",
                  "run security and regression checks", "stage deployment",
                  "verify deployment and record evidence"],
        "notice": "This bootstrap does not generate or deploy code autonomously yet."
    }


class API(BaseHTTPRequestHandler):
    server_version = "JBSN-AIOS-Core/0.2"

    def send_json(self, status, obj):
        b = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def auth(self):
        if not TOKEN:
            self.send_json(503, {"error": "JBSN_API_TOKEN not configured; API fails closed"})
            return False
        got = self.headers.get("Authorization", "")
        if got.startswith("Bearer "):
            got = got[7:]
        if not secrets.compare_digest(got, TOKEN):
            self.send_json(401, {"error": "unauthorized"})
            return False
        return True

    def body(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n > 1000000:
            raise ValueError("request body too large")
        x = json.loads(self.rfile.read(n) if n else b"{}")
        if not isinstance(x, dict):
            raise ValueError("body must be a JSON object")
        return x

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            try:
                with db() as c:
                    c.execute("SELECT 1")
            except Exception:
                return self.send_json(503, {"service": "jbsn-aios-core", "version": VERSION,
                                            "status": "degraded", "database": "unavailable"})
            return self.send_json(200, {"service": "jbsn-aios-core", "version": VERSION,
                                        "status": "healthy", "mode": "safe-bootstrap",
                                        "database": "postgresql" if USE_POSTGRES else "sqlite",
                                        "persistent_storage_configured": USE_POSTGRES or bool(os.environ.get("JBSN_DB_PATH"))})
        if not self.auth():
            return
        if path == "/v1/tasks":
            with db() as c:
                rows = c.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 200").fetchall()
            return self.send_json(200, {"tasks": [serial(r) for r in rows]})
        if path.startswith("/v1/tasks/"):
            bits = path.strip("/").split("/")
            tid = bits[2]
            with db() as c:
                if len(bits) == 4 and bits[3] == "events":
                    rows = c.execute("SELECT * FROM events WHERE task_id=? ORDER BY id", (tid,)).fetchall()
                    return self.send_json(200, {"events": [dict(r) for r in rows]})
                row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
            return self.send_json(200 if row else 404, serial(row) or {"error": "task not found"})
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self.auth():
            return
        try:
            p = self.path.split("?", 1)[0]
            b = self.body()
            if p == "/v1/tasks":
                title = str(b.get("title", "")).strip()
                typ = str(b.get("task_type", ""))
                payload = b.get("payload", {})
                risk = str(b.get("risk", "green"))
                if not title:
                    raise ValueError("title is required")
                if typ != "plan":
                    raise ValueError("unregistered task_type; only plan is enabled in bootstrap")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                if risk not in ("green", "amber", "red"):
                    raise ValueError("risk must be green, amber, or red")
                tid = str(uuid.uuid4())
                now = time.time()
                status = "queued" if risk == "green" else "awaiting_approval"
                with db() as c:
                    c.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                              (tid, title, typ, json.dumps(payload), status, risk, None, None, 0, now, now))
                    event(c, tid, "task.created", {"risk": risk, "status": status})
                    if status == "awaiting_approval":
                        c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",
                                  (str(uuid.uuid4()), tid, "pending", None, None, now, None))
                        event(c, tid, "approval.requested", {"risk": risk})
                    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
                return self.send_json(201, serial(row))
            if p == "/v1/worker/run-one":
                with db() as c:
                    c.execute("BEGIN IMMEDIATE")
                    row = c.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
                    if row is None:
                        c.commit()
                        return self.send_json(200, {"task": None})
                    tid = row["id"]
                    c.execute("UPDATE tasks SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",
                              (time.time(), tid))
                    event(c, tid, "task.started", {"attempt": row["attempts"] + 1})
                    c.commit()
                task = self.get_task(tid)
                try:
                    result = plan(task["payload"])
                except Exception as e:
                    with db() as c:
                        c.execute("UPDATE tasks SET status='failed',error=?,updated_at=? WHERE id=?",
                                  (f"{type(e).__name__}: {e}"[:500], time.time(), tid))
                        event(c, tid, "task.failed", {"error_type": type(e).__name__})
                else:
                    with db() as c:
                        c.execute("UPDATE tasks SET status='succeeded',result=?,error=NULL,updated_at=? WHERE id=?",
                                  (json.dumps(result), time.time(), tid))
                        event(c, tid, "task.succeeded", {"mode": "plan_only"})
                return self.send_json(200, {"task": self.get_task(tid)})
            if p.startswith("/v1/tasks/") and p.endswith("/approval"):
                tid = p.strip("/").split("/")[2]
                decision = str(b.get("decision", ""))
                if decision not in ("approved", "rejected"):
                    raise ValueError("decision must be approved or rejected")
                with db() as c:
                    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
                    if not row:
                        return self.send_json(404, {"error": "task not found"})
                    if row["status"] != "awaiting_approval":
                        raise ValueError("task is not awaiting approval")
                    status = "queued" if decision == "approved" else "cancelled"
                    now = time.time()
                    c.execute("UPDATE approvals SET status=?,decision_by=?,reason=?,decided_at=? WHERE task_id=? AND status='pending'",
                              (decision, str(b.get("decision_by", "founder")), str(b.get("reason", "")), now, tid))
                    c.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (status, now, tid))
                    event(c, tid, "approval.decided",
                          {"decision": decision, "decision_by": str(b.get("decision_by", "founder"))})
                    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
                return self.send_json(200, serial(row))
            return self.send_json(404, {"error": "not found"})
        except (ValueError, json.JSONDecodeError) as e:
            return self.send_json(400, {"error": str(e)})
        except Exception as e:
            print(f"[JBSN-AIOS] internal request failure: {type(e).__name__}")
            return self.send_json(500, {"error": "internal error", "type": type(e).__name__})

    def get_task(self, tid):
        with db() as c:
            row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return serial(row)

    def log_message(self, fmt, *args):
        print("[JBSN-AIOS] " + (fmt % args))


if __name__ == "__main__":
    if USE_POSTGRES:
        print("PostgreSQL persistence enabled")
    else:
        print("WARNING: DATABASE_URL is absent or SQLite was explicitly selected; local SQLite is not durable on ephemeral hosting")
    init_db()
    host = os.environ.get("JBSN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    if not TOKEN:
        print("WARNING: API token missing; authenticated endpoints fail closed")
    print(f"JBSN AI OS Core Runtime {VERSION} listening on {host}:{port}")
    ThreadingHTTPServer((host, port), API).serve_forever()
