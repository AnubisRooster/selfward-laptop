"""Memory shared by all personas: each exchange is stored with an embedding and recalled by similarity."""
import re
from . import db, llm

RECALL_LIMIT = 3
MIN_SCORE = 0.3

def remember(session_id, user_text, reply):
    content = f"The client said: {user_text.strip()[:600]}\nYou replied: {reply.strip()[:600]}"
    vecs = llm.embed([content])
    db.x("INSERT INTO memories(session_id,kind,content,vec,ts) VALUES(?,?,?,?,?)",
         (session_id, "exchange", content, llm.pack(vecs[0]) if vecs else None, db.now()))

def _words(t): return {w for w in re.findall(r"[a-z']{4,}", t.lower())}

def recall(query, exclude_session=None, limit=RECALL_LIMIT):
    """Memories from earlier conversations that bear on `query`. Memories of the current chat are already in its history."""
    rows = db.q("SELECT id,session_id,content,vec FROM memories WHERE session_id IS NOT ? ORDER BY id DESC LIMIT 500", (exclude_session,))
    if not rows: return []
    qv = llm.embed([query]); scored = []
    if qv:
        import numpy as np
        q = np.array(qv[0], dtype="float32")
        for r in rows:
            if not r["vec"]: continue
            s = float(np.dot(q, np.frombuffer(r["vec"], dtype="float32")))
            if s >= MIN_SCORE: scored.append((s, r["content"]))
    else:                                                    # no embedding model: overlap of longer words
        qw = _words(query)
        for r in rows:
            o = len(qw & _words(r["content"]))
            if o >= 2: scored.append((o / (len(qw) + 1), r["content"]))
    scored.sort(key=lambda t: -t[0])
    return [c for _, c in scored[:limit]]
