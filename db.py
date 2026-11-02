"""SQLite state: post queue + tiny key/value meta table."""
import sqlite3
from datetime import datetime, timezone

from config import DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  status TEXT NOT NULL,   -- draft | pending_review | ready | rejected | published | failed
  topic TEXT, image_prompt TEXT, caption TEXT, alt_text TEXT,
  image_path TEXT, image_url TEXT, qc_score REAL, qc_notes TEXT,
  attempts INTEGER DEFAULT 0, error TEXT, ig_media_id TEXT,
  created_at TEXT, published_at TEXT
);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn():
    c = sqlite3.connect(DATA / "agent.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def add_post(**f):
    f.setdefault("created_at", now_iso())
    cols = ", ".join(f)
    marks = ", ".join("?" for _ in f)
    with _conn() as c:
        return c.execute(f"INSERT INTO posts({cols}) VALUES({marks})", list(f.values())).lastrowid


def update(pid, **f):
    sets = ", ".join(f"{k}=?" for k in f)
    with _conn() as c:
        c.execute(f"UPDATE posts SET {sets} WHERE id=?", [*f.values(), pid])


def get(pid):
    with _conn() as c:
        return c.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()


def list_status(*statuses):
    q = ",".join("?" for _ in statuses)
    with _conn() as c:
        return c.execute(f"SELECT * FROM posts WHERE status IN ({q}) ORDER BY id", statuses).fetchall()


def count(status):
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM posts WHERE status=?", (status,)).fetchone()[0]


def next_ready():
    with _conn() as c:
        return c.execute("SELECT * FROM posts WHERE status='ready' ORDER BY id LIMIT 1").fetchone()


def recent(n=15):
    """Latest topics/captions, so the model avoids repeating itself."""
    with _conn() as c:
        rows = c.execute(
            "SELECT topic, caption FROM posts WHERE status!='rejected' ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [f"{r['topic']} | {(r['caption'] or '')[:80]}" for r in rows]


def last_published():
    with _conn() as c:
        r = c.execute("SELECT MAX(published_at) FROM posts WHERE status='published'").fetchone()[0]
    return datetime.fromisoformat(r) if r else None


def published_since(iso):
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM posts WHERE status='published' AND published_at>=?", (iso,)
        ).fetchone()[0]


def get_meta(k, default=None):
    with _conn() as c:
        r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def set_meta(k, v):
    with _conn() as c:
        c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
