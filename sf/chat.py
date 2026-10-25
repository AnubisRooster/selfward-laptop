"""One chat turn: safety checks, memory, the persona's prompt, streaming the answer into the database."""
import json, threading
from . import companion, compact, db, graph, insights, llm, memory, personas, safety, tagging
from .prompts import MODALITY_PROMPTS

_running = set(); _cancelled = set()

def new_session(persona=None, modality=None, title=None):
    persona = persona if persona in personas.KINDS else (db.get_setting("default_persona") or "therapist")
    modality = modality if modality in MODALITY_PROMPTS else (db.get_setting("default_modality") or "integrated")
    title = title or "New session"
    return db.x("INSERT INTO sessions(title,persona,modality,created,updated) VALUES(?,?,?,?,?)", (title, persona, modality, db.now(), db.now()))

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

def build_messages(session, history, user_text, memories, recap="", important=(), older=()):
    persona = personas.resolve(session["persona"])
    msgs = [{"role": "system", "content": personas.system_prompt(persona, session["modality"], session["system_prompt"] or "", session.get("_extra", ""))}]
    if important: msgs.append({"role": "system", "content": "Things that have mattered to this person across sessions:\n" + "\n".join("- " + m for m in important)})
    if memories: msgs.append({"role": "system", "content": "Relevant context from previous sessions:\n" + "\n".join("- " + m for m in memories)})
    if older: msgs.append({"role": "system", "content": "Earlier in this same conversation (no longer shown in full):\n" + "\n".join("- " + m for m in older)})
    if recap: msgs.append({"role": "system", "content": "Ongoing conversation recap (earlier turns, condensed — treat as verbatim history):\n" + recap})
    msgs += [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": user_text})
    return msgs, persona

def fit(session, earlier, user_text, memories, important):
    """Builds the prompt so it fits the model's window: older turns become a recap, then memories and turns are dropped until it fits."""
    window = llm.context_tokens(); persona = personas.resolve(session["persona"])
    system_text = personas.system_prompt(persona, session["modality"], session["system_prompt"] or "", session.get("_extra", ""))
    older = []
    budget = compact.history_budget(window, system_text, "\n".join(memories) + "\n".join(important) + "x" * 1500, user_text)    # room for what recall may add
    recap, history = compact.for_prompt(session["id"], earlier, budget)
    if history and len(history) < len(earlier) and history[0].get("ts"):            # the chat outgrew the window: bring back the earlier exchanges that bear on this message
        try: older = memory.recall_in_session(user_text, session["id"], history[0]["ts"])
        except Exception: older = []
    def build(): return build_messages(session, history, user_text, memories, recap, important, older)
    msgs, persona = build()
    while sum(compact.tokens(m["content"]) + 4 for m in msgs) > window * 0.85:      # an estimate can undercount: shrink until it fits
        if older: older = older[:-1]
        elif important: important = important[:-1]
        elif memories: memories = memories[:-1]
        elif history: history = history[1:]
        elif recap: recap = ""
        else: break
        msgs, persona = build()
    return msgs, persona

_background = []        # recap refreshes in flight (tests wait on them)

def _refresh_recap(session, everything):
    """After the answer: folds older turns into the stored recap, so the next long turn has it. A failure only means the next turn trims instead."""
    try:
        persona = personas.resolve(session["persona"])
        budget = compact.history_budget(llm.context_tokens(), personas.system_prompt(persona, session["modality"], session["system_prompt"] or "", session.get("_extra", "")), "x" * 2400, "x" * 400)
        with tagging.MODEL_LOCK:
            compact.refresh(session["id"], everything, budget, summarizer=lambda block: compact.summarize(block, llm.current_model(session)))
    except Exception as e:
        print(f"[recap skipped] {type(e).__name__}: {str(e)[:150]}", flush=True)

def _second_look(session_id, text, mid, user_mid):
    try:
        tagging.look(session_id, text, mid)
        if user_mid: tagging.mark(user_mid)
    except Exception as e:
        print(f"[second look skipped] {type(e).__name__}: {str(e)[:150]}", flush=True)

def join_background(timeout=30):
    for t in list(_background): t.join(timeout)
    _background[:] = [t for t in _background if t.is_alive()]

def _who(session, persona=None):
    """Which guide (and approach) is speaking, as it was when the reply was written."""
    p = persona or personas.resolve(session["persona"])
    return {"persona": p["kind"], "persona_name": p["display"], **({"modality": session["modality"]} if p["kind"] == "therapist" else {})}

def _capture(session_id, user_text, earlier):
    """What your message adds besides the answer: the inner map, a dream record, the session's summary note. Never blocks the answer."""
    try:
        nodes, edges = graph.extract(session_id, user_text, [m["content"] for m in earlier if m["role"] == "user"])
        out = insights.capture(session_id, user_text)
        if nodes: out["nodes"] = nodes
        if edges: out["edges"] = edges
        return out
    except Exception:
        return {}

def _turn(session_id, user_text):
    session = db.q("SELECT * FROM sessions WHERE id=?", (session_id,), one=True)
    mid = _store(session_id, "assistant", "", {"streaming": True}); captured = {}
    try:
        earlier = db.q("SELECT role,content,ts FROM messages WHERE session_id=? AND id<? AND role IN ('user','assistant') AND content!='' ORDER BY id", (session_id, mid))
        earlier = earlier[:-1] if earlier and earlier[-1]["role"] == "user" and earlier[-1]["content"] == user_text else earlier   # this turn's own message is added last
        captured = _capture(session_id, user_text, earlier)       # from your words alone, so it happens even if the model is down
        memories = memory.recall(user_text, exclude_session=session_id)
        important = memory.recall_global(user_text, exclude_session=session_id)
        memories = [m for m in memories if m not in important]          # said once, under the stronger heading
        extra, warmth = companion.addendum(session, user_text) if session["persona"] == "companion" else ("", {})        # the companion's warmth dial for this turn
        session = {**session, "_extra": extra}
        msgs, persona = fit(session, earlier, user_text, memories, important)
        acc = ""
        for piece in llm.stream(msgs, model=llm.current_model(session)):
            if session_id in _cancelled: break
            acc += piece
            db.x("UPDATE messages SET content=? WHERE id=?", (acc, mid))
        stopped = session_id in _cancelled
        violation, pattern = safety.check_boundary(acc, persona["kind"])
        meta = {"model": llm.current_model(session), **_who(session, persona)}      # who wrote this reply (the guide, approach and model can all change mid-session)
        if violation:
            _event(session_id, "boundary_violation", "warning", f"Detected pattern: '{pattern}'")
            acc = safety.BOUNDARY_REPLACEMENT; meta["safety"] = "boundary"
        if warmth and not violation:
            meta["flirt"] = warmth["flirt"]
            if warmth.get("tone_dropped"): meta["tone_dropped"] = True
            if warmth.get("time_check"): meta["time_check"] = True
            kind, phrase = companion.reply_problem(acc)
            if kind:
                _event(session_id, "companion_" + kind, "warning", f"Detected pattern: '{phrase}'")
                acc = companion.PRESSURE_REPLACEMENT if kind == "pressure" else companion.EXPLICIT_REPLACEMENT
                meta["safety"] = "companion_" + kind; meta.pop("time_check", None); violation = True
            elif companion.looks_like_refusal(acc): meta["refused"] = True        # the model stepped out of the role; the page says so
        if stopped: meta["cancelled"] = True
        if acc and not stopped and not violation:
            try:
                memory.remember(session_id, user_text, acc); captured["memory"] = 1
                if memory.promote(session_id, user_text, acc): captured["insight"] = 1            # kept for good: shown as "insight saved"
            except Exception: pass
        if captured: meta["captured"] = captured
        db.x("UPDATE messages SET content=?, meta=? WHERE id=?", (acc or ("(stopped)" if stopped else "(no answer)"), json.dumps(meta), mid))
        if tagging.enabled() and not stopped:                  # an optional second look by the model on this computer, after the answer (see sf/tagging.py)
            user_row = db.q("SELECT id FROM messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1", (session_id,), one=True)
            t = threading.Thread(target=_second_look, args=(session_id, user_text, mid, user_row["id"] if user_row else None), daemon=True); _background.append(t); t.start()
        if acc and not stopped and not violation:
            t = threading.Thread(target=_refresh_recap, args=(session, earlier + [{"role": "user", "content": user_text}, {"role": "assistant", "content": acc}]), daemon=True)
            _background.append(t); t.start()
    except Exception as e:
        db.x("UPDATE messages SET content=?, meta=? WHERE id=?", (llm.friendly_error(e), json.dumps({"error": True, "captured": captured, "model": llm.current_model(session), **_who(session)}), mid))
    finally:
        _running.discard(session_id); _cancelled.discard(session_id)
        db.x("UPDATE sessions SET status='idle', updated=? WHERE id=?", (db.now(), session_id))
        _touch(session_id, user_text)
