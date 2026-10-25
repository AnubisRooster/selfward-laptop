"""SQLite storage for Selfward (sessions, messages, memories, safety events, settings)."""
import json, os, sqlite3, threading, time
from contextlib import contextmanager

DATA_DIR = os.environ.get("SELFWARD_DATA", os.path.expanduser("~/.local/share/selfward"))
os.makedirs(DATA_DIR, exist_ok=True)
os.chmod(DATA_DIR, 0o700)          # a journal: only this user reads it
DB_PATH = os.path.join(DATA_DIR, "selfward.db")
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, title TEXT, persona TEXT DEFAULT 'therapist', modality TEXT DEFAULT 'integrated',
  system_prompt TEXT DEFAULT '', model TEXT DEFAULT '', status TEXT DEFAULT 'idle', archived INTEGER DEFAULT 0, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT, content TEXT, meta TEXT DEFAULT '{}', ts REAL);
CREATE INDEX IF NOT EXISTS ix_msg_session ON messages(session_id);
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, session_id INTEGER, kind TEXT DEFAULT 'exchange', content TEXT, vec BLOB, ts REAL);
CREATE TABLE IF NOT EXISTS graph_nodes(id INTEGER PRIMARY KEY, session_id INTEGER, type TEXT, label TEXT, strength REAL DEFAULT 1.0, props TEXT DEFAULT '{}', ts REAL);
CREATE INDEX IF NOT EXISTS ix_gn_session ON graph_nodes(session_id);
CREATE TABLE IF NOT EXISTS graph_edges(id INTEGER PRIMARY KEY, session_id INTEGER, source INTEGER, target INTEGER, type TEXT, weight REAL DEFAULT 1.0, ts REAL);
CREATE INDEX IF NOT EXISTS ix_ge_session ON graph_edges(session_id);
CREATE TABLE IF NOT EXISTS dreams(id INTEGER PRIMARY KEY, session_id INTEGER, narrative TEXT, feelings TEXT DEFAULT '[]', symbols TEXT DEFAULT '[]', analysis TEXT DEFAULT '', ts REAL);
CREATE INDEX IF NOT EXISTS ix_dream_session ON dreams(session_id);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, session_id INTEGER, type TEXT DEFAULT 'journal', title TEXT, content TEXT, auto INTEGER DEFAULT 0, ts REAL, updated REAL);
CREATE INDEX IF NOT EXISTS ix_note_session ON notes(session_id);
CREATE TABLE IF NOT EXISTS global_memories(id INTEGER PRIMARY KEY, session_id INTEGER, kind TEXT DEFAULT 'semantic', content TEXT, keywords TEXT DEFAULT '', importance REAL DEFAULT 0.5, vec BLOB, manual INTEGER DEFAULT 0, ts REAL);
CREATE TABLE IF NOT EXISTS narrative(id INTEGER PRIMARY KEY, content TEXT DEFAULT '', previous TEXT DEFAULT '', watermark REAL DEFAULT 0, session_count INTEGER DEFAULT 0, updated REAL);
CREATE TABLE IF NOT EXISTS moods(id INTEGER PRIMARY KEY, value INTEGER, note TEXT DEFAULT '', ts REAL);
CREATE INDEX IF NOT EXISTS ix_mood_ts ON moods(ts);
CREATE TABLE IF NOT EXISTS safety_events(id INTEGER PRIMARY KEY, session_id INTEGER, type TEXT, level TEXT, message TEXT, ts REAL);
"""

def _connect():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=OFF")
    return c

_conn = _connect()
with _lock:
    _conn.executescript(SCHEMA); _conn.commit()
def _add_column(table, column, decl):
    """Journals made by an earlier version get the new column; a fresh one already has it."""
    with _lock:
        if column not in [r["name"] for r in _conn.execute(f"PRAGMA table_info({table})")]:
            _conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}"); _conn.commit()

_add_column("sessions", "summary", "TEXT DEFAULT ''")
_add_column("sessions", "summary_covered", "INTEGER DEFAULT 0")
for _f in (DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm"):
    try: os.chmod(_f, 0o600)
    except OSError: pass

def q(sql, args=(), one=False):
    with _lock:
        cur = _conn.execute(sql, args); rows = cur.fetchall()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows

def x(sql, args=()):
    """Execute a write; returns lastrowid."""
    with _lock:
        cur = _conn.execute(sql, args); _conn.commit(); return cur.lastrowid

@contextmanager
def tx():
    with _lock:
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback(); raise

DEFAULTS = {
    "model": os.environ.get("SELFWARD_MODEL", "ollama_chat/llama3.2:3b"),
    "embed_model": "nomic-embed-text",
    "ollama_base": os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
    "api_key": "", "onboarding_completed": False, "disclaimer_accepted": False,
    "lock_enabled": False, "lock_after": 60, "lock_idle": 15, "lock_hash": "",
    "default_persona": "therapist", "default_modality": "integrated", "region": "US",
    "therapist_name": "", "companion_name": "Kai", "spiritual_name": "Sage",
    "companion_personality": "warm", "companion_gender": "unspecified", "spiritual_tradition": "interfaith",
    "tts_engine": "auto", "tts_url": "http://127.0.0.1:8880", "tts_voice": "af_heart", "voice_rate": 1.0, "voice_pause_ms": 800, "voice_therapist": "", "voice_companion": "", "voice_spiritual": "", "voice_name": "",
    "remote_enabled": False, "remote_keep_awake": True, "remote_login": "", "remote_host": "", "remote_hash": "", "remote_sessions": {}, "remote_log": [],
    "tag_with_model": False, "tagging_model": "", "context_tokens": 8192, "remember_across_sessions": True,
    "user_name": "", "user_pronouns": "", "user_age": "", "intake_concerns": "", "intake_history": "", "intake_goals": "",
}
SECRET = ("lock_hash", "api_key", "remote_hash")

def get_setting(key):
    r = q("SELECT value FROM settings WHERE key=?", (key,), one=True)
    if r is None: return DEFAULTS.get(key)
    try: return json.loads(r["value"])
    except Exception: return r["value"]

def set_setting(key, value):
    x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

def all_settings(hide=SECRET):
    out = dict(DEFAULTS)
    for r in q("SELECT key,value FROM settings"):
        try: out[r["key"]] = json.loads(r["value"])
        except Exception: out[r["key"]] = r["value"]
    for h in hide:
        if h in out: out[h] = bool(out[h])
    for k in ("remote_sessions", "remote_log"): out.pop(k, None)             # who is signed in is not for the settings page to hand out
    return out

def now(): return time.time()
