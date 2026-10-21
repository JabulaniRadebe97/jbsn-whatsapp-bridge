"""JBSN AI OS Core Runtime bootstrap. Safe, plan-only worker; no arbitrary code execution."""
import json
import os
import secrets
import sqlite3
import time
import threading
import uuid
import urllib.request
import urllib.error
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
import voice_agent
import departments

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("JBSN_DB_PATH", str(ROOT / "data" / "jbsn_aios.db")))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL) and os.environ.get("JBSN_DATABASE_BACKEND", "").lower() != "sqlite"
TOKEN = os.environ.get("JBSN_API_TOKEN", "")
VERSION = "0.4.0"
GEMINI_MODEL = os.environ.get("JBSN_GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_PROXY_URL = os.environ.get("JBSN_GEMINI_PROXY_URL", "").strip()
GEMINI_PROXY_TOKEN = os.environ.get("JBSN_GEMINI_PROXY_TOKEN", "").strip()

def configured_lease_seconds(value=None):
    """Return a bounded lease duration; reject unsafe deployment configuration."""
    raw = os.environ.get("JBSN_LEASE_SECONDS", "300") if value is None else value
    try:
        seconds = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("JBSN_LEASE_SECONDS must be an integer between 30 and 86400") from exc
    if not 30 <= seconds <= 86400:
        raise ValueError("JBSN_LEASE_SECONDS must be an integer between 30 and 86400")
    return seconds


LEASE_SECONDS = configured_lease_seconds()
MAX_ATTEMPTS = 3


def configured_worker_poll_seconds(value=None):
    """Validate the background worker polling interval (1–60 seconds)."""
    raw = os.environ.get("JBSN_WORKER_POLL_SECONDS", "5") if value is None else value
    try:
        seconds = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("JBSN_WORKER_POLL_SECONDS must be an integer between 1 and 60") from exc
    if not 1 <= seconds <= 60:
        raise ValueError("JBSN_WORKER_POLL_SECONDS must be an integer between 1 and 60")
    return seconds


WORKER_POLL_SECONDS = configured_worker_poll_seconds()
WORKER_ENABLED = os.environ.get("JBSN_AUTOWORKER_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")

# In-process diagnostics only; never expose task payloads, exception messages, or secrets.
WORKER_STATE_LOCK = threading.Lock()
WORKER_STATE = {
    "running": False,
    "started_at": None,
    "last_iteration_at": None,
    "last_task_at": None,
    "last_error_type": None,
    "tasks_processed": 0,
}


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
                created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL,
                lease_expires_at DOUBLE PRECISION, claim_token TEXT)""",
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
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS lease_expires_at DOUBLE PRECISION")
            c.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS claim_token TEXT")
    else:
        with db() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,task_type TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,risk TEXT NOT NULL,result TEXT,error TEXT,attempts INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL,lease_expires_at REAL,claim_token TEXT);
            CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status,created_at);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT NOT NULL,detail TEXT NOT NULL,created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,status TEXT NOT NULL,decision_by TEXT,reason TEXT,created_at REAL NOT NULL,decided_at REAL);""")
            columns = {r["name"] for r in c.execute("PRAGMA table_info(tasks)").fetchall()}
            if "lease_expires_at" not in columns:
                c.execute("ALTER TABLE tasks ADD COLUMN lease_expires_at REAL")
            if "claim_token" not in columns:
                c.execute("ALTER TABLE tasks ADD COLUMN claim_token TEXT")


def database_epoch(c):
    """Read epoch time from the database that also stores lease deadlines."""
    if USE_POSTGRES:
        row = c.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS now").fetchone()
        return float(row["now"])
    row = c.execute("SELECT (julianday('now') - 2440587.5) * 86400.0 AS now").fetchone()
    return float(row["now"])


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


def gemini_business_plan(payload):
    """Generate a structured plan via the existing Apps Script Gemini provider when configured."""
    objective = str(payload.get("objective", "")).strip()
    business = str(payload.get("business", "JBSN Creative")).strip()
    if not objective:
        raise ValueError("payload.objective is required")

    if GEMINI_PROXY_URL:
        if not GEMINI_PROXY_TOKEN:
            raise RuntimeError("JBSN_GEMINI_PROXY_TOKEN is not configured")
        proxy_body = json.dumps({
            "action": "aios_business_plan", "token": GEMINI_PROXY_TOKEN,
            "objective": objective, "business": business, "model": GEMINI_MODEL,
        }).encode("utf-8")
        request = urllib.request.Request(GEMINI_PROXY_URL, data=proxy_body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                proxy_result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Apps Script Gemini proxy returned HTTP {exc.code}") from None
        except urllib.error.URLError:
            raise RuntimeError("Apps Script Gemini proxy connection failed") from None
        if not isinstance(proxy_result, dict) or proxy_result.get("ok") is not True:
            raise RuntimeError("Apps Script Gemini proxy rejected or failed the request")
        plan_data = proxy_result.get("plan")
        provider = "google_gemini_via_apps_script"
        model = str(proxy_result.get("model") or GEMINI_MODEL)
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Configure JBSN_GEMINI_PROXY_URL and JBSN_GEMINI_PROXY_TOKEN, or GEMINI_API_KEY")
        prompt = (
            "You are the planning engine for JBSN AI OS. Produce a practical, testable business plan. "
            "Do not claim to have executed actions. Identify assumptions, acceptance criteria, risks, "
            "approvals needed, and measurable next steps. "
            f"Business: {business}\\nObjective: {objective}\\n"
            "Return valid JSON with keys: summary, assumptions, steps, acceptance_criteria, risks, approvals_required."
        )
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}).encode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Gemini provider returned HTTP {exc.code}") from None
        except urllib.error.URLError:
            raise RuntimeError("Gemini provider connection failed") from None
        try:
            plan_data = json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise RuntimeError("Gemini returned an invalid business-plan response") from None
        provider, model = "google_gemini", GEMINI_MODEL

    required = ("summary", "steps", "acceptance_criteria", "risks", "approvals_required")
    if not isinstance(plan_data, dict) or not all(key in plan_data for key in required) or not isinstance(plan_data["steps"], list):
        raise RuntimeError("Gemini response did not satisfy the business-plan schema")
    return {"mode": "gemini_business_plan_only", "provider": provider, "model": model,
        "business": business, "plan": plan_data,
        "execution_notice": "Plan generated only; no code, deployments, payments, or external actions were executed."}


def recover_expired_tasks(c, now=None):
    """Recover only expired leased tasks. Caller must hold a write transaction."""
    now = database_epoch(c) if now is None else now
    if USE_POSTGRES:
        rows = c.execute(
            "SELECT id,claim_token,attempts FROM tasks WHERE status='running' "
            "AND lease_expires_at IS NOT NULL AND lease_expires_at<? "
            "ORDER BY lease_expires_at,id FOR UPDATE SKIP LOCKED", (now,)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT id,claim_token,attempts FROM tasks WHERE status='running' "
            "AND lease_expires_at IS NOT NULL AND lease_expires_at<? "
            "ORDER BY lease_expires_at,id", (now,)
        ).fetchall()
    recovered = 0
    for row in rows:
        new_status = "failed" if row["attempts"] >= MAX_ATTEMPTS else "queued"
        updated = c.execute(
            "UPDATE tasks SET status=?,claim_token=NULL,lease_expires_at=NULL,updated_at=? "
            "WHERE id=? AND status='running' AND claim_token=? AND lease_expires_at<?",
            (new_status, now, row["id"], row["claim_token"], now)
        )
        if updated.rowcount == 1:
            event(c, row["id"], "task.recovered",
                  {"status": new_status, "attempt": row["attempts"]})
            recovered += 1
    return recovered


def finish_claim(c, tid, token, result=None, error=None):
    """Fence completion so an obsolete worker cannot overwrite a newer claim."""
    status = "failed" if error is not None else "succeeded"
    updated = c.execute(
        "UPDATE tasks SET status=?,result=?,error=?,claim_token=NULL,"
        "lease_expires_at=NULL,updated_at=? "
        "WHERE id=? AND status='running' AND claim_token=?",
        (status, json.dumps(result) if result is not None else None,
         error, time.time(), tid, token)
    )
    if updated.rowcount != 1:
        return False
    event(c, tid, "task.failed" if error is not None else "task.succeeded",
          {"error_type": "execution"} if error is not None else {"mode": "plan_only"})
    return True


def claim_queued_task(c):
    """Atomically claim one queued task inside the caller's transaction.

    PostgreSQL workers skip rows already locked by another worker. SQLite uses
    the caller's BEGIN IMMEDIATE transaction to serialize competing claimers.
    The status transition, attempt increment, and start event stay in one
    transaction so a task cannot be partially claimed.
    """
    if USE_POSTGRES:
        row = c.execute(
            "SELECT * FROM tasks WHERE status='queued' "
            "ORDER BY created_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
        ).fetchone()
    else:
        row = c.execute(
            "SELECT * FROM tasks WHERE status='queued' "
            "ORDER BY created_at, id LIMIT 1"
        ).fetchone()

    if row is None:
        return None

    tid = row["id"]
    attempt = row["attempts"] + 1
    now = database_epoch(c)
    token = uuid.uuid4().hex
    updated = c.execute(
        "UPDATE tasks SET status='running',attempts=attempts+1,updated_at=?,"
        "claim_token=?,lease_expires_at=? WHERE id=? AND status='queued'",
        (now, token, now + LEASE_SECONDS, tid)
    )
    if updated.rowcount != 1:
        return None

    event(c, tid, "task.started", {"attempt": attempt})
    return {"id": tid, "attempt": attempt, "claim_token": token}


def run_one_task():
    """Claim and execute one allowlisted task. The current registry contains plan only."""
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        recover_expired_tasks(c)
        claim = claim_queued_task(c)
        if claim is None:
            c.commit()
            return None
        tid = claim["id"]
        c.commit()
    with db() as c:
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    task = serial(row)
    try:
        if task["task_type"] == "plan":
            result = plan(task["payload"])
        elif task["task_type"] == "business_plan":
            result = gemini_business_plan(task["payload"])
        else:
            raise ValueError("task_type is not enabled in the safe worker registry")
    except Exception as exc:
        with db() as c:
            finish_claim(c, tid, claim["claim_token"], error=f"{type(exc).__name__}: {exc}"[:500])
    else:
        with db() as c:
            finish_claim(c, tid, claim["claim_token"], result=result)
    with db() as c:
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    return serial(row)


def worker_loop():
    """Continuously process allowlisted tasks when explicitly enabled by configuration."""
    with WORKER_STATE_LOCK:
        WORKER_STATE["running"] = True
        WORKER_STATE["started_at"] = time.time()
    print(f"[JBSN-AIOS] background worker enabled; poll={WORKER_POLL_SECONDS}s; registry=plan-only")
    while True:
        try:
            task = run_one_task()
            with WORKER_STATE_LOCK:
                WORKER_STATE["last_iteration_at"] = time.time()
                WORKER_STATE["last_error_type"] = None
                if task is not None:
                    WORKER_STATE["last_task_at"] = time.time()
                    WORKER_STATE["tasks_processed"] += 1
            if task is None:
                time.sleep(WORKER_POLL_SECONDS)
        except Exception as exc:
            # Keep the service alive, but avoid printing payloads or credentials.
            with WORKER_STATE_LOCK:
                WORKER_STATE["last_iteration_at"] = time.time()
                WORKER_STATE["last_error_type"] = type(exc).__name__
            print(f"[JBSN-AIOS] background worker iteration failed: {type(exc).__name__}")
            time.sleep(WORKER_POLL_SECONDS)


def health_payload(status, database):
    """Expose non-secret runtime readiness and configured worker capabilities."""
    with WORKER_STATE_LOCK:
        worker_state = dict(WORKER_STATE)
    return {
        "service": "jbsn-aios-core",
        "version": VERSION,
        "status": status,
        "mode": "safe-bootstrap",
        "database": database,
        "persistent_storage_configured": USE_POSTGRES or bool(os.environ.get("JBSN_DB_PATH")),
        "worker": {
            "enabled": WORKER_ENABLED,
            "poll_seconds": WORKER_POLL_SECONDS,
            "registry": ["plan", "business_plan"],
            "department_agents_registered": len(departments.DEPARTMENTS),
            "department_activation": "registered_safe_mode",
            **worker_state,
        },
    }


class API(BaseHTTPRequestHandler):
    server_version = "JBSN-AIOS-Core/0.4"

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
        if path in ("/", "/dashboard", "/dashboard.html"):
            try:
                dashboard = (ROOT / "dashboard.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Length", str(len(dashboard)))
                self.end_headers()
                self.wfile.write(dashboard)
            except OSError:
                self.send_json(503, {"error": "dashboard asset unavailable"})
            return
        if path == "/health":
            try:
                with db() as c:
                    c.execute("SELECT 1")
            except Exception:
                return self.send_json(503, health_payload("degraded", "unavailable"))
            return self.send_json(200, health_payload(
                "healthy", "postgresql" if USE_POSTGRES else "sqlite"
            ))
        if not self.auth():
            return
        if path == "/v1/departments":
            return self.send_json(200, departments.department_manifest())
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
        path = self.path.split("?", 1)[0]
        if path.startswith("/voice/"):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 100000:
                    return self.send_json(413, {"error": "voice callback too large"})
                raw = self.rfile.read(length) if length else b""
                fields = {key: values[-1] for key, values in parse_qs(
                    raw.decode("utf-8"), keep_blank_values=True).items()}
                public_base = os.environ.get("JBSN_PUBLIC_BASE_URL", "").rstrip("/")
                callback_url = public_base + self.path
                if not voice_agent.validate_twilio_signature(
                    callback_url, fields, self.headers.get("X-Twilio-Signature", "")):
                    return self.send_json(403, {"error": "invalid Twilio signature"})
                if path == "/voice/twiml":
                    xml = voice_agent.build_disclosure_twiml()
                elif path == "/voice/turn":
                    xml = voice_agent.build_turn_twiml(
                        fields.get("SpeechResult", ""), public_base)
                elif path == "/voice/status":
                    self.send_response(204)
                    self.end_headers()
                    return
                else:
                    return self.send_json(404, {"error": "voice route not found"})
                payload = xml.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            except Exception as exc:
                print(f"[JBSN-AIOS] voice callback failed: {type(exc).__name__}")
                return self.send_json(500, {"error": "voice callback failed"})
        if not self.auth():
            return
        try:
            p = self.path.split("?", 1)[0]
            b = self.body()
            if p == "/v1/voice/calls":
                if not isinstance(b.get("prospect"), dict):
                    raise ValueError("prospect object is required")
                result = voice_agent.create_outbound_call(
                    b["prospect"], campaign_approved=(b.get("campaign_approved") is True))
                return self.send_json(201, result)
            if p == "/v1/tasks":
                title = str(b.get("title", "")).strip()
                typ = str(b.get("task_type", ""))
                payload = b.get("payload", {})
                risk = str(b.get("risk", "green"))
                if not title:
                    raise ValueError("title is required")
                if typ not in ("plan", "business_plan"):
                    raise ValueError("unregistered task_type; only plan and business_plan are enabled")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                if risk not in ("green", "amber", "red"):
                    raise ValueError("risk must be green, amber, or red")
                tid = str(uuid.uuid4())
                now = time.time()
                status = "queued" if risk == "green" else "awaiting_approval"
                with db() as c:
                    c.execute(
                        "INSERT INTO tasks(id,title,task_type,payload,status,risk,result,error,attempts,created_at,updated_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (tid, title, typ, json.dumps(payload), status, risk, None, None, 0, now, now)
                    )
                    event(c, tid, "task.created", {"risk": risk, "status": status})
                    if status == "awaiting_approval":
                        c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",
                                  (str(uuid.uuid4()), tid, "pending", None, None, now, None))
                        event(c, tid, "approval.requested", {"risk": risk})
                    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
                return self.send_json(201, serial(row))
            if p == "/v1/worker/run-one":
                return self.send_json(200, {"task": run_one_task()})
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
    if WORKER_ENABLED:
        threading.Thread(target=worker_loop, name="jbsn-aios-worker", daemon=True).start()
    else:
        print("[JBSN-AIOS] background worker disabled; set JBSN_AUTOWORKER_ENABLED=true to enable plan-only processing")
    ThreadingHTTPServer((host, port), API).serve_forever()
