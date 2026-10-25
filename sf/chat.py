"""One chat turn: safety checks, memory, the persona's prompt, streaming the answer into the database."""
import json, threading
from . import db, llm, memory, personas, safety
from .prompts import MODALITY_PROMPTS

_running = set(); _cancelled = set()
HISTORY_CHARS = 14000          # about 3,500 tokens of earlier turns; older ones drop off the front

def new_session(persona=None, modality=None, title=None):
    persona = persona if persona in personas.KINDS else (db.get_setting("default_persona") or "therapist")
    modality = modality if modality in MODALITY_PROMPTS else (db.get_setting("default_modality") or "integrated")
    title = title or "New session"
    return db.x("INSERT INTO sessions(title,persona,modality,created,updated) VALUES(?,?,?,?,?)", (title, persona, modality, db.now(), db.now()))

def retained_history(msgs, budget=HISTORY_CHARS, keep=3):
    """The newest turns that fit the budget (always at least `keep`)."""
    out, used = [], 0
    for m in reversed(msgs):
        used += len(m["content"])
        if used > budget and len(out) >= keep: break
        out.append(m)
    return list(reversed(out))

def _store(session_id, role, content, meta=None):
    return db.x("INSERT INTO messages(session_id,role,content,meta,ts) VALUES(?,?,?,?,?)", (session_id, role, content, json.dumps(meta or {}), db.now()))

def _event(session_id, kind, level, message):
    db.x("INSERT INTO safety_events(session_id,type,level,message,ts) VALUES(?,?,?,?,?)", (session_id, kind, level, message, db.now()))

def cancel(session_id):
    if session_id not in _running: return False
    _cancelled.add(session_id); return True

def send(session_id, text):
    """Stores the message and starts the answer. Crisis wording is answered right here with local resources: the model never sees it."""
    text = (text or "").strip()
    if not text: raise ValueError("Write something first.")
    if session_id in _running: raise ValueError("Still answering your last message.")
    region = db.get_setting("region") or "US"
    crisis, level, pattern = safety.check_crisis(text)
    if crisis:
        _event(session_id, "crisis_keyword", level, f"Detected pattern: '{pattern}'")
        _store(session_id, "user", text); _store(session_id, "assistant", safety.resource_message(region), {"safety": "crisis"})
        _touch(session_id, text); return {"safety": "crisis"}
    if safety.check_self_harm_method(text):
        _event(session_id, "self_harm_method", "critical", "Detected self-harm method-seeking language")
        _store(session_id, "user", text); _store(session_id, "assistant", safety.method_refusal(region), {"safety": "method"})
        _touch(session_id, text); return {"safety": "method"}
    _store(session_id, "user", text)
    db.x("UPDATE sessions SET status='running', updated=? WHERE id=?", (db.now(), session_id))
    _running.add(session_id)
    threading.Thread(target=_turn, args=(session_id, text), daemon=True).start()
    return {"safety": None}

def _title(text, limit=60):
    """The first words of a message, cut at a word boundary."""
    text = " ".join(text.split())
    if len(text) <= limit: return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:!?") + "…"

def _touch(session_id, first_text):
    s = db.q("SELECT title FROM sessions WHERE id=?", (session_id,), one=True)
    if s and s["title"] == "New session": db.x("UPDATE sessions SET title=? WHERE id=?", (_title(first_text), session_id))
    db.x("UPDATE sessions SET updated=? WHERE id=?", (db.now(), session_id))

def build_messages(session, history, user_text, memories):
    persona = personas.resolve(session["persona"])
    msgs = [{"role": "system", "content": personas.system_prompt(persona, session["modality"], session["system_prompt"] or "")}]
    if memories: msgs.append({"role": "system", "content": "Relevant context from previous sessions:\n" + "\n".join("- " + m for m in memories)})
    msgs += [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": user_text})
    return msgs, persona

def _turn(session_id, user_text):
    session = db.q("SELECT * FROM sessions WHERE id=?", (session_id,), one=True)
    mid = _store(session_id, "assistant", "", {"streaming": True})
    try:
        earlier = db.q("SELECT role,content FROM messages WHERE session_id=? AND id<? AND role IN ('user','assistant') AND content!='' ORDER BY id", (session_id, mid))
        earlier = earlier[:-1] if earlier and earlier[-1]["role"] == "user" and earlier[-1]["content"] == user_text else earlier   # this turn's own message is added last
        history = retained_history(earlier)
        memories = memory.recall(user_text, exclude_session=session_id)
        msgs, persona = build_messages(session, history, user_text, memories)
        acc = ""
        for piece in llm.stream(msgs, model=llm.current_model(session)):
            if session_id in _cancelled: break
            acc += piece
            db.x("UPDATE messages SET content=? WHERE id=?", (acc, mid))
        stopped = session_id in _cancelled
        violation, pattern = safety.check_boundary(acc, persona["kind"])
        meta = {}
        if violation:
            _event(session_id, "boundary_violation", "warning", f"Detected pattern: '{pattern}'")
            acc = safety.BOUNDARY_REPLACEMENT; meta["safety"] = "boundary"
        if stopped: meta["cancelled"] = True
        db.x("UPDATE messages SET content=?, meta=? WHERE id=?", (acc or ("(stopped)" if stopped else "(no answer)"), json.dumps(meta), mid))
        if acc and not stopped and not violation:
            try: memory.remember(session_id, user_text, acc)
            except Exception: pass
    except Exception as e:
        db.x("UPDATE messages SET content=?, meta=? WHERE id=?", (llm.friendly_error(e), '{"error": true}', mid))
    finally:
        _running.discard(session_id); _cancelled.discard(session_id)
        db.x("UPDATE sessions SET status='idle', updated=? WHERE id=?", (db.now(), session_id))
        _touch(session_id, user_text)
