"""Memory shared by all personas.

Two kinds, both recalled by similarity across your other sessions:
- every exchange is embedded and recalled (episodic), and
- exchanges that carry real weight (trauma, a parent, shame, a realisation...) are promoted to a durable global memory,
  which you can see, add to and delete in Settings."""
import re
from . import db, llm

RECALL_LIMIT = 3
GLOBAL_LIMIT = 4
MIN_SCORE = 0.3

def _content(user_text, reply):
    return f"The client said: {user_text.strip()[:600]}\nYou replied: {reply.strip()[:600]}"

def remember(session_id, user_text, reply):
    content = _content(user_text, reply)
    vecs = llm.embed([content])
    db.x("INSERT INTO memories(session_id,kind,content,vec,ts) VALUES(?,?,?,?,?)",
         (session_id, "exchange", content, llm.pack(vecs[0]) if vecs else None, db.now()))
    return content

def _words(t): return {w for w in re.findall(r"[a-z']{4,}", t.lower())}

def _rank(query, rows, limit, boost=lambda r: 0.0):
    """Rows (with content and vec) by similarity to `query` (words in common when there is no embedding model), best first."""
    if not rows: return []
    qv = llm.embed([query]); scored = []
    if qv:
        import numpy as np
        q = np.array(qv[0], dtype="float32")
        for r in rows:
            if not r["vec"]: continue
            s = float(np.dot(q, np.frombuffer(r["vec"], dtype="float32")))
            if s >= MIN_SCORE: scored.append((s + boost(r), r))
    else:
        qw = _words(query)
        for r in rows:
            o = len(qw & _words(r["content"]))
            if o >= 2: scored.append((o / (len(qw) + 1) + boost(r), r))
    scored.sort(key=lambda t: -t[0])
    return [r for _, r in scored[:limit]]

def recall(query, exclude_session=None, limit=RECALL_LIMIT):
    """Memories from earlier conversations that bear on `query`. Memories of the current chat are already in its history."""
    rows = db.q("SELECT id,session_id,content,vec FROM memories WHERE session_id IS NOT ? ORDER BY id DESC LIMIT 500", (exclude_session,))
    return [r["content"] for r in _rank(query, rows, limit)]

# ---- global memory ----
TIER3 = ["trauma", "traumatic", "abuse", "abused", "assault", "suicidal", "suicide", "self-harm", "self harm", "harming myself",
         "since childhood", "as a child", "growing up", "my childhood", "breakthrough", "epiphany", "completely changed"]
TIER2 = ["my mother", "my father", "my mom", "my dad", "realized", "realised", "i discovered", "i learned", "i understand now", "for the first time",
         "i've never told", "always felt", "never felt", "always been", "never been", "ashamed", "shame", "guilt", "guilty", "grief", "grieving",
         "lost someone", "they died", "afraid", "terrified", "phobia", "abandoned", "rejection", "rejected", "neglected"]
TIER1 = ["anxious", "anxiety", "panic", "lonely", "loneliness", "hopeless", "worthless", "empty", "numb", "stuck", "hurt", "pain", "struggling",
         "overwhelmed", "relationship", "marriage", "divorce", "separation", "insight", "pattern", "repeated", "keeps happening"]

def _hits(low, terms): return sum(1 for t in terms if re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", low))

def weight(user_text, reply=""):
    """(importance, kind) when an exchange is significant enough to keep for good, else None.

    One strong signal is enough (0.85+), or two meaningful ones (0.65+), or one meaningful with two mild (0.55), or three mild (0.45+).
    The words are matched whole ("pain" is not found in "painting"), and only your own words count: the reply could say anything."""
    low = " ".join((user_text or "").lower().replace("’", "'").split())
    t3, t2, t1 = _hits(low, TIER3), _hits(low, TIER2), _hits(low, TIER1)
    if t3 >= 1: return min(0.85 + (t3 - 1) * 0.05, 1.0), "insight"
    if t2 >= 2: return min(0.65 + (t2 - 2) * 0.05, 0.85), "semantic"
    if t2 == 1 and t1 >= 2: return 0.55, "semantic"
    if t1 >= 3: return min(0.45 + (t1 - 3) * 0.03, 0.6), "episodic"
    return None

def promote(session_id, user_text, reply):
    """Keeps this exchange as a global memory when it carries weight. Returns the new id, or None."""
    if not db.get_setting("remember_across_sessions"): return None
    w = weight(user_text, reply)
    if not w: return None
    content = _content(user_text, reply); vecs = llm.embed([content])
    return db.x("INSERT INTO global_memories(session_id,kind,content,keywords,importance,vec,manual,ts) VALUES(?,?,?,?,?,?,0,?)",
                (session_id, w[1], content, " ".join(sorted(_words(user_text))[:12]), w[0], llm.pack(vecs[0]) if vecs else None, db.now()))

def add_manual(text):
    text = " ".join((text or "").split())[:600]
    if not text: raise ValueError("Write what to remember first.")
    vecs = llm.embed([text])
    return db.x("INSERT INTO global_memories(session_id,kind,content,keywords,importance,vec,manual,ts) VALUES(NULL,'semantic',?,?,0.8,?,1,?)",
                (text, " ".join(sorted(_words(text))[:12]), llm.pack(vecs[0]) if vecs else None, db.now()))

def recall_global(query, exclude_session=None, limit=GLOBAL_LIMIT):
    """What has mattered before that bears on `query`: similarity first, importance as the tie-breaker. Memories from this chat are skipped."""
    if not db.get_setting("remember_across_sessions"): return []
    rows = db.q("SELECT id,session_id,content,vec,importance FROM global_memories WHERE session_id IS NOT ? OR session_id IS NULL", (exclude_session,)) if exclude_session else db.q("SELECT id,session_id,content,vec,importance FROM global_memories")
    return [r["content"] for r in _rank(query, rows, limit, boost=lambda r: r["importance"] * 0.5)]

def recall_in_session(query, session_id, before_ts, limit=3):
    """Exchanges from THIS chat that are too old to still be in the prompt word for word (and that the recap may have only touched on)."""
    rows = db.q("SELECT id,session_id,content,vec FROM memories WHERE session_id=? AND ts<? ORDER BY id DESC LIMIT 500", (session_id, before_ts))
    return [r["content"] for r in _rank(query, rows, limit)]
