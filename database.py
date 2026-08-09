# -*- coding: utf-8 -*-
"""
database.py — ذخیره‌سازی دائمی با SQLite
====================================================================
چه چیزی ذخیره می‌شود:
    • نشست‌های چت و تک‌تک پیام‌ها
    • دستورات اجراشده و نتیجه‌شان
    • زنجیره‌های تعمیر و خروجی کامل
    • رویدادهای برنامه (لاگ)

چرا SQLite؟
    بدون سرور، تک‌فایل، در پایتون تعبیه شده. برای این حجم داده
    (چند هزار پیام) کاملاً کافی است.

نکته درباره همزمانی:
    سرور چندنخی است، پس هر عملیات اتصال خودش را می‌سازد
    (sqlite3 اتصال را بین نخ‌ها به اشتراک نمی‌گذارد).
    حالت WAL برای خواندن و نوشتن همزمان فعال است.
"""

import os
import re
import json
import time
import sqlite3
import threading

_WRITE_LOCK = threading.Lock()
_DB_PATH = None


def _default_dir():
    if os.name == 'nt':
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
                or os.environ.get("ProgramData") or os.getcwd())
    else:
        base = os.path.join(os.path.expanduser("~"), ".pcrepairtoolbox")
    d = os.path.join(base, "PCRepairToolbox")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.getcwd()
    return d


def db_path():
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.path.join(_default_dir(), "pc_toolbox.db")
    return _DB_PATH


def _conn():
    c = sqlite3.connect(db_path(), timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'گفتگوی جدید',
    persona     TEXT DEFAULT 'doctor',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    archived    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    persona     TEXT,
    model       TEXT,
    info_used   TEXT,
    created_at  REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    risk        TEXT,
    approved_by TEXT,
    job_id      TEXT,
    session_id  TEXT,
    exit_code   INTEGER,
    output      TEXT,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cmd_time ON commands(created_at DESC);

CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    kind        TEXT,
    steps       TEXT,
    status      TEXT,
    output      TEXT,
    session_id  TEXT,
    started_at  REAL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       TEXT DEFAULT 'info',
    message     TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt_time ON events(created_at DESC);
"""


def init_db():
    try:
        with _WRITE_LOCK, _conn() as c:
            c.executescript(SCHEMA)
        return {"success": True, "path": db_path()}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# نشست‌ها و پیام‌ها
# ---------------------------------------------------------------------------
def upsert_session(session_id, title=None, persona=None):
    now = time.time()
    try:
        with _WRITE_LOCK, _conn() as c:
            row = c.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row:
                sets, vals = ["updated_at=?"], [now]
                if title:
                    sets.append("title=?"); vals.append(title)
                if persona:
                    sets.append("persona=?"); vals.append(persona)
                vals.append(session_id)
                c.execute(f"UPDATE sessions SET {','.join(sets)} WHERE id=?", vals)
            else:
                c.execute("INSERT INTO sessions (id,title,persona,created_at,updated_at) "
                          "VALUES (?,?,?,?,?)",
                          (session_id, title or 'گفتگوی جدید', persona or 'doctor', now, now))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def add_message(session_id, role, content, persona=None, model=None, info_used=None):
    now = time.time()
    try:
        with _WRITE_LOCK, _conn() as c:
            c.execute("INSERT OR IGNORE INTO sessions (id,title,persona,created_at,updated_at) "
                      "VALUES (?,?,?,?,?)",
                      (session_id, 'گفتگوی جدید', persona or 'doctor', now, now))
            c.execute("INSERT INTO messages (session_id,role,content,persona,model,info_used,created_at) "
                      "VALUES (?,?,?,?,?,?,?)",
                      (session_id, role, content, persona, model,
                       json.dumps(info_used, ensure_ascii=False) if info_used else None, now))
            # عنوان خودکار از اولین پیام کاربر
            if role == "user":
                row = c.execute("SELECT title FROM sessions WHERE id=?", (session_id,)).fetchone()
                if row and row["title"] == 'گفتگوی جدید':
                    t = re.sub(r'\s+', ' ', content).strip()[:40]
                    c.execute("UPDATE sessions SET title=? WHERE id=?", (t or 'گفتگو', session_id))
            c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_sessions(limit=60, include_archived=False):
    try:
        with _conn() as c:
            q = ("SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS msg_count "
                 "FROM sessions s ")
            if not include_archived:
                q += "WHERE s.archived=0 "
            q += "ORDER BY s.updated_at DESC LIMIT ?"
            rows = c.execute(q, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_messages(session_id, limit=500):
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT role,content,persona,model,info_used,created_at FROM messages "
                "WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_session(session_id):
    try:
        with _WRITE_LOCK, _conn() as c:
            c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_messages(query, limit=60):
    """جست‌وجو در تمام گفتگوها."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT m.session_id, s.title, m.role, m.content, m.created_at "
                "FROM messages m JOIN sessions s ON s.id=m.session_id "
                "WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
                (f"%{query}%", limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# دستورات و jobها
# ---------------------------------------------------------------------------
def log_command(command, risk=None, approved_by=None, job_id=None,
                session_id=None, exit_code=None, output=None):
    try:
        with _WRITE_LOCK, _conn() as c:
            c.execute("INSERT INTO commands (command,risk,approved_by,job_id,session_id,"
                      "exit_code,output,created_at) VALUES (?,?,?,?,?,?,?,?)",
                      (command, risk, approved_by, job_id, session_id,
                       exit_code, (output or "")[:20000], time.time()))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_job(job_id, kind=None, steps=None, status=None, output=None,
             session_id=None, finished=False):
    now = time.time()
    try:
        with _WRITE_LOCK, _conn() as c:
            row = c.execute("SELECT job_id FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row:
                sets, vals = [], []
                if status:
                    sets.append("status=?"); vals.append(status)
                if output is not None:
                    sets.append("output=?"); vals.append(output[:200000])
                if finished:
                    sets.append("finished_at=?"); vals.append(now)
                if sets:
                    vals.append(job_id)
                    c.execute(f"UPDATE jobs SET {','.join(sets)} WHERE job_id=?", vals)
            else:
                c.execute("INSERT INTO jobs (job_id,kind,steps,status,output,session_id,started_at) "
                          "VALUES (?,?,?,?,?,?,?)",
                          (job_id, kind, json.dumps(steps, ensure_ascii=False) if steps else None,
                           status or "running", output, session_id, now))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_commands(limit=100):
    try:
        with _conn() as c:
            rows = c.execute("SELECT * FROM commands ORDER BY created_at DESC LIMIT ?",
                             (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def list_jobs(limit=50):
    try:
        with _conn() as c:
            rows = c.execute("SELECT job_id,kind,steps,status,started_at,finished_at "
                             "FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# رویدادها
# ---------------------------------------------------------------------------
def log_event_db(message, level="info"):
    try:
        with _WRITE_LOCK, _conn() as c:
            c.execute("INSERT INTO events (level,message,created_at) VALUES (?,?,?)",
                      (level, message[:2000], time.time()))
    except Exception:
        pass


def list_events(limit=200):
    try:
        with _conn() as c:
            rows = c.execute("SELECT level,message,created_at FROM events "
                             "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# آمار و نگهداری
# ---------------------------------------------------------------------------
def get_stats():
    try:
        with _conn() as c:
            g = lambda q: c.execute(q).fetchone()[0]
            size = os.path.getsize(db_path()) if os.path.exists(db_path()) else 0
            return {
                "success": True,
                "path": db_path(),
                "size_kb": round(size / 1024, 1),
                "sessions": g("SELECT COUNT(*) FROM sessions"),
                "messages": g("SELECT COUNT(*) FROM messages"),
                "commands": g("SELECT COUNT(*) FROM commands"),
                "jobs": g("SELECT COUNT(*) FROM jobs"),
                "events": g("SELECT COUNT(*) FROM events"),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def export_json(out_path=None):
    """پشتیبان کامل به‌صورت JSON."""
    out_path = out_path or os.path.join(_default_dir(),
                                        f"backup_{time.strftime('%Y%m%d_%H%M%S')}.json")
    try:
        data = {"exported": time.strftime("%Y-%m-%d %H:%M:%S"), "sessions": []}
        for s in list_sessions(limit=1000, include_archived=True):
            s["messages"] = get_messages(s["id"], limit=5000)
            data["sessions"].append(s)
        data["commands"] = list_commands(limit=2000)
        data["jobs"] = list_jobs(limit=500)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return {"success": True, "path": out_path,
                "size_kb": round(os.path.getsize(out_path) / 1024, 1)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup(days=90):
    """حذف داده‌های قدیمی‌تر از N روز."""
    cutoff = time.time() - days * 86400
    try:
        with _WRITE_LOCK, _conn() as c:
            n1 = c.execute("DELETE FROM events WHERE created_at<?", (cutoff,)).rowcount
            n2 = c.execute("DELETE FROM commands WHERE created_at<?", (cutoff,)).rowcount
            old = [r[0] for r in c.execute(
                "SELECT id FROM sessions WHERE updated_at<?", (cutoff,)).fetchall()]
            for sid in old:
                c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
            c.execute("DELETE FROM sessions WHERE updated_at<?", (cutoff,))
        with _conn() as c:
            c.execute("VACUUM")
        return {"success": True, "events": n1, "commands": n2, "sessions": len(old)}
    except Exception as e:
        return {"success": False, "error": str(e)}


init_db()


if __name__ == "__main__":
    print("مسیر دیتابیس:", db_path())
    upsert_session("t1", "تست")
    add_message("t1", "user", "سیستمم کند است")
    add_message("t1", "assistant", "بررسی می‌کنم...", persona="doctor")
    log_command("sfc /scannow", risk="safe", exit_code=0)
    print(json.dumps(get_stats(), ensure_ascii=False, indent=2))
