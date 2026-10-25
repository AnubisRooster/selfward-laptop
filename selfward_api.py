"""Selfward local API (FastAPI). Run: python3 selfward_api.py  ->  http://localhost:8100/"""
import base64, gzip, hashlib, json, os, secrets, time
import httpx, uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sf import db, llm, chat, graph, insights, personas, safety
from sf.prompts import ALL_MODALITIES, MODALITY_DESCRIPTIONS, COMPANION_PERSONALITY_LABELS, COMPANION_GENDER_LABELS, SPIRITUAL_TRADITION_LABELS

app = FastAPI(title="Selfward")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8100", "http://127.0.0.1:8100", "tauri://localhost", "http://tauri.localhost"],
                   allow_methods=["*"], allow_headers=["*"])

def bad(msg, code=400): raise HTTPException(code, msg)

# ---------- status / settings ----------
@app.get("/api/status")
def status():
    return {"model": db.get_setting("model"), "preflight": preflight(), "onboarding_completed": bool(db.get_setting("onboarding_completed")),
            "disclaimer_accepted": bool(db.get_setting("disclaimer_accepted")), "lock_enabled": bool(db.get_setting("lock_enabled")), "ui_build": ui_build(),
            "region": db.get_setting("region"), "resources": [{"name": n, "contact": c} for n, c in safety.resources(db.get_setting("region"))]}

def ui_build():
    """Changes whenever the interface is rebuilt, so an open window can offer to reload."""
    try: return int(os.path.getmtime(os.path.join(_UI, "index.html")))
    except OSError: return 0

def preflight():
    out = {"ollama": False, "chat_model": False, "embed_model": False, "models": []}
    try:
        r = httpx.get(db.get_setting("ollama_base").rstrip("/") + "/api/tags", timeout=3); names = [m["name"] for m in r.json().get("models", [])]
        out.update(ollama=True, models=names)
        model = db.get_setting("model"); cm = model.split("/")[-1]; em = db.get_setting("embed_model")
        out["chat_model"] = (not model.startswith("ollama")) or cm in names or any(n.startswith(cm.split(":")[0]) for n in names)
        out["embed_model"] = any(n.split(":")[0] == em.split(":")[0] for n in names)
    except Exception: pass
    return out

@app.get("/api/catalog")
def catalog():
    """What the pickers offer: personas, the 15 approaches, companion and advisor options."""
    return {"personas": [{"id": k, "label": v["label"], "blurb": v["blurb"], "default_name": v["default_name"]} for k, v in personas.KINDS.items()],
            "modalities": [{"id": m, "description": MODALITY_DESCRIPTIONS.get(m, "")} for m in ALL_MODALITIES],
            "personalities": [{"id": k, "label": v} for k, v in COMPANION_PERSONALITY_LABELS.items()],
            "genders": [{"id": k, "label": v} for k, v in COMPANION_GENDER_LABELS.items()],
            "traditions": [{"id": k, "label": v} for k, v in SPIRITUAL_TRADITION_LABELS.items()],
            "regions": sorted(safety.RESOURCES) }

@app.get("/api/settings")
def get_settings(): return db.all_settings()

LOCKED = ("lock_hash", "lock_enabled")
@app.put("/api/settings")
def put_settings(body: dict):
    for k, v in (body.get("values") or {}).items():
        if k in LOCKED or k not in db.DEFAULTS: continue
        if k == "api_key" and v is True: continue          # the UI only ever sees "set / not set"
        if k == "default_persona" and v not in personas.KINDS: bad("Unknown persona.")
        if k == "default_modality" and v not in ALL_MODALITIES: bad("Unknown approach.")
        db.set_setting(k, v)
    return db.all_settings()

@app.get("/api/models")
def models():
    pre = preflight(); return {"ollama": pre["models"], "current": db.get_setting("model"), "embed": db.get_setting("embed_model"), "ollama_up": pre["ollama"]}

@app.post("/api/models/test")
def models_test():
    try: llm.text([{"role": "user", "content": "Reply with the single word: ok"}], timeout=60)
    except Exception as e: bad(llm.friendly_error(e), 502)
    return {"ok": True, "model": db.get_setting("model")}

# ---------- sessions & chat ----------
def _session_row(s):
    p = personas.resolve(s["persona"])
    last = db.q("SELECT content FROM messages WHERE session_id=? AND role='assistant' AND content!='' ORDER BY id DESC LIMIT 1", (s["id"],), one=True)
    return {**s, "persona_name": p["display"], "preview": (last["content"] if last else "")[:120]}

@app.get("/api/sessions")
def sessions(archived: bool = False):
    return [_session_row(s) for s in db.q("SELECT * FROM sessions WHERE archived=? ORDER BY updated DESC", (1 if archived else 0,))]

@app.post("/api/sessions")
def session_new(body: dict):
    sid = chat.new_session(body.get("persona"), body.get("modality"), body.get("title"))
    if body.get("model"): db.x("UPDATE sessions SET model=? WHERE id=?", (str(body["model"]), sid))
    return {"id": sid, "preflight": preflight()}

@app.get("/api/sessions/{sid}")
def session_get(sid: int):
    s = db.q("SELECT * FROM sessions WHERE id=?", (sid,), one=True)
    if not s: bad("No such session", 404)
    msgs = db.q("SELECT * FROM messages WHERE session_id=? ORDER BY id", (sid,))
    for m in msgs: m["meta"] = json.loads(m["meta"] or "{}")
    return {**_session_row(s), "messages": msgs, "system_prompt": s["system_prompt"]}

@app.patch("/api/sessions/{sid}")
def session_patch(sid: int, body: dict):
    for k in ("title", "persona", "modality", "system_prompt", "model", "archived"):
        if k not in body: continue
        if k == "persona" and body[k] not in personas.KINDS: bad("Unknown persona.")
        if k == "modality" and body[k] not in ALL_MODALITIES: bad("Unknown approach.")
        db.x(f"UPDATE sessions SET {k}=? WHERE id=?", (int(body[k]) if k == "archived" else body[k], sid))
    return {"ok": True}

@app.delete("/api/sessions/{sid}")
def session_del(sid: int):
    for t in ("messages", "memories", "safety_events"): db.x(f"DELETE FROM {t} WHERE session_id=?", (sid,))
    graph.delete_session(sid)
    for t in ("dreams", "notes"): db.x(f"DELETE FROM {t} WHERE session_id=?", (sid,))
    db.x("DELETE FROM sessions WHERE id=?", (sid,)); return {"ok": True}

@app.post("/api/sessions/{sid}/send")
def session_send(sid: int, body: dict):
    if not db.q("SELECT id FROM sessions WHERE id=?", (sid,), one=True): bad("No such session", 404)
    try: return chat.send(sid, body.get("text", ""))
    except ValueError as e: bad(str(e), 409)

@app.post("/api/sessions/{sid}/cancel")
def session_cancel(sid: int): return {"ok": chat.cancel(sid)}

@app.get("/api/safety/events")
def safety_events(): return db.q("SELECT * FROM safety_events ORDER BY ts DESC LIMIT 200")

# ---------- window errors ----------
@app.post("/api/client-log")
def client_log(body: dict):
    """The window reports what went wrong on screen, so a blank page leaves a note in the log (never message text)."""
    print(f"[window {str(body.get('kind'))[:20]}] {str(body.get('url'))[:200]}\n{str(body.get('text'))[:4000]}", flush=True)
    return {"ok": True}

# ---------- inner map ----------
def _types(t): return [x for x in (t or "").split(",") if x] or None

@app.get("/api/graph")
def graph_view(session_id: int = None, types: str = ""): return graph.view(session_id, _types(types))

@app.get("/api/graph/node")
def graph_node(type: str, label: str, session_id: int = None):
    d = graph.node_detail(type, label, session_id)
    if not d: bad("That isn't on the map (any more).", 404)
    return d

@app.post("/api/graph/rebuild")
def graph_rebuild(): return {"messages": graph.rebuild()}

@app.get("/api/graph/export/graphml")
def graph_graphml(session_id: int = None):
    return Response(graph.graphml(session_id), media_type="application/xml", headers={"Content-Disposition": "attachment; filename=selfward-map.graphml"})

@app.get("/api/graph/export/cytoscape")
def graph_cytoscape(session_id: int = None):
    return Response(json.dumps(graph.cytoscape(session_id), indent=1), media_type="application/json", headers={"Content-Disposition": "attachment; filename=selfward-map.json"})

# ---------- dreams, notes, insights ----------
def _session_titles(): return {x["id"]: x["title"] for x in db.q("SELECT id,title FROM sessions")}

@app.get("/api/dreams")
def dreams(session_id: int = None):
    titles = _session_titles()
    rows = db.q("SELECT * FROM dreams" + (" WHERE session_id=?" if session_id else "") + " ORDER BY ts DESC", (session_id,) if session_id else ())
    return [{**insights.dream_row(r), "session_title": titles.get(r["session_id"], "")} for r in rows]

@app.post("/api/dreams")
def dream_new(body: dict):
    text = (body.get("narrative") or "").strip()
    if not text: bad("Write the dream first.")
    sid = body.get("session_id")
    if sid is not None and not db.q("SELECT id FROM sessions WHERE id=?", (sid,), one=True): bad("No such session.", 404)
    low = insights._norm(text)
    feelings = [CANON_LABEL(w) for w in insights.DREAM_FEELINGS if insights._has(low, w)]
    return {"id": insights.add_dream(sid, text, list(dict.fromkeys(feelings)), [w for w in insights.SYMBOLS if insights._has(low, w, True)])}

def CANON_LABEL(w): return insights.CANON.get(w, w).lower()

@app.post("/api/dreams/{did}/interpret")
def dream_interpret(did: int):
    try: return {"analysis": insights.interpret(did)}
    except KeyError: bad("No such dream.", 404)
    except Exception as e: bad(llm.friendly_error(e), 502)

@app.delete("/api/dreams/{did}")
def dream_del(did: int): db.x("DELETE FROM dreams WHERE id=?", (did,)); return {"ok": True}

@app.get("/api/notes")
def notes(session_id: int = None):
    titles = _session_titles()
    rows = db.q("SELECT * FROM notes" + (" WHERE session_id=?" if session_id else "") + " ORDER BY ts DESC", (session_id,) if session_id else ())
    return [{**r, "session_title": titles.get(r["session_id"], "")} for r in rows]

@app.post("/api/notes")
def note_new(body: dict):
    title, content = (body.get("title") or "").strip(), (body.get("content") or "").strip()
    if not title and not content: bad("Write something first.")
    sid = body.get("session_id")
    if sid is not None and not db.q("SELECT id FROM sessions WHERE id=?", (sid,), one=True): bad("No such session.", 404)
    return {"id": db.x("INSERT INTO notes(session_id,type,title,content,auto,ts,updated) VALUES(?,?,?,?,0,?,?)", (sid, "journal", title or "Untitled note", content, db.now(), db.now()))}

@app.patch("/api/notes/{nid}")
def note_patch(nid: int, body: dict):
    n = db.q("SELECT * FROM notes WHERE id=?", (nid,), one=True)
    if not n: bad("No such note.", 404)
    db.x("UPDATE notes SET title=?, content=?, auto=?, updated=? WHERE id=?", (body.get("title", n["title"]), body.get("content", n["content"]), 2 if n["auto"] else 0, db.now(), nid))
    return {"ok": True}                                   # an automatic note you edit stays yours: it is no longer rewritten

@app.delete("/api/notes/{nid}")
def note_del(nid: int): db.x("DELETE FROM notes WHERE id=?", (nid,)); return {"ok": True}

@app.get("/api/insights")
def insights_view(session_id: int = None):
    n = lambda t: db.q(f"SELECT COUNT(*) n FROM {t}" + (" WHERE session_id=?" if session_id else ""), (session_id,) if session_id else (), one=True)["n"]
    return {"highlights": insights.highlights(session_id), "dreams": n("dreams"), "notes": n("notes")}

@app.post("/api/insights/rebuild")
def insights_rebuild(): return {"dreams_found": insights.rebuild()}

# ---------- lock ----------
def _hash(pin, salt): return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()
def _verify(pin, stored):
    try: salt, h = stored.split(":"); return secrets.compare_digest(_hash(pin, bytes.fromhex(salt)), h)
    except Exception: return False

@app.post("/api/lock/set")
def lock_set(body: dict):
    cur = db.get_setting("lock_hash")
    if cur and not _verify(body.get("current", ""), cur): bad("Current PIN is wrong.", 403)
    if not body.get("pin"):
        db.set_setting("lock_hash", ""); db.set_setting("lock_enabled", False); return {"enabled": False}
    pin = str(body["pin"])
    if len(pin) < 4 or not pin.isdigit(): bad("Use at least 4 digits.")
    salt = secrets.token_bytes(16); db.set_setting("lock_hash", salt.hex() + ":" + _hash(pin, salt)); db.set_setting("lock_enabled", True)
    return {"enabled": True}

_fails = {"n": 0, "until": 0.0}
@app.post("/api/lock/verify")
def lock_verify(body: dict):
    st = db.get_setting("lock_hash")
    if not st: return {"ok": True}
    if time.time() < _fails["until"]: return {"ok": False, "wait": int(_fails["until"] - time.time()) + 1}
    time.sleep(0.4)
    ok = _verify(str(body.get("pin", "")), st)
    if ok: _fails["n"] = 0
    else:
        _fails["n"] += 1
        if _fails["n"] >= 5: _fails["until"] = time.time() + min(300, 30 * (_fails["n"] - 4))     # a pause after repeated misses
    return {"ok": ok}

# ---------- onboarding ----------
@app.post("/api/onboarding/complete")
def onboarding_complete(body: dict):
    for k in ("user_name", "user_pronouns", "user_age", "intake_concerns", "intake_history", "intake_goals", "region",
              "default_persona", "default_modality", "companion_name", "spiritual_name", "therapist_name"):
        if k in body and k in db.DEFAULTS: db.set_setting(k, body[k])
    if not body.get("accept_disclaimer"): bad("Please read and accept the notice first.")
    db.set_setting("disclaimer_accepted", True); db.set_setting("onboarding_completed", True)
    return {"ok": True}

# ---------- export / backup / erase ----------
TABLES = ["sessions", "messages", "memories", "safety_events", "graph_nodes", "graph_edges", "dreams", "notes"]
def _dump(with_blobs=False):
    out = {"version": 1, "exported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tables": {}}
    for t in TABLES:
        rows = db.q(f"SELECT * FROM {t} ORDER BY id")
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, (bytes, bytearray)): r[k] = base64.b64encode(v).decode() if with_blobs else None
        out["tables"][t] = rows
    return out

@app.get("/api/export/json")
def export_json():
    return Response(json.dumps(_dump(), indent=1, sort_keys=True), media_type="application/json", headers={"Content-Disposition": "attachment; filename=selfward-journal.json"})

@app.get("/api/export/markdown")
def export_md():
    out = []
    for s in db.q("SELECT * FROM sessions ORDER BY created"):
        out += [f"# {s['title']}", f"_{personas.resolve(s['persona'])['display']} · {s['modality']} · {time.strftime('%Y-%m-%d', time.localtime(s['created']))}_", ""]
        for m in db.q("SELECT role,content FROM messages WHERE session_id=? AND content!='' ORDER BY id", (s["id"],)):
            out.append(f"**{'You' if m['role'] == 'user' else personas.resolve(s['persona'])['display']}:** {m['content']}\n")
        out.append("\n---\n")
    return Response("\n".join(out), media_type="text/markdown", headers={"Content-Disposition": "attachment; filename=selfward-journal.md"})

def _key(pw, salt):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(pw.encode())

@app.post("/api/backup")
def backup(body: dict):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pw = body.get("passphrase", "")
    if len(pw) < 8: bad("Use a passphrase of at least 8 characters.")
    data = _dump(True); data["settings"] = {k: v for k, v in db.all_settings(hide=()).items() if k not in db.SECRET + ("lock_enabled",)}
    raw = gzip.compress(json.dumps(data).encode()); salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    blob = b"SFBK1" + salt + nonce + AESGCM(_key(pw, salt)).encrypt(nonce, raw, b"SFBK1")
    return Response(blob, media_type="application/octet-stream", headers={"Content-Disposition": "attachment; filename=selfward-backup.sfbk"})

@app.post("/api/restore")
async def restore(request: Request):
    """Raw .sfbk body + X-Passphrase header. A wrong passphrase or damaged file never changes anything."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    blob = await request.body(); pw = request.headers.get("x-passphrase", "")
    if not blob.startswith(b"SFBK1") or len(blob) < 40: bad("That doesn't look like a Selfward backup.")
    try: data = json.loads(gzip.decompress(AESGCM(_key(pw, blob[5:21])).decrypt(blob[21:33], blob[33:], b"SFBK1")))
    except Exception: bad("Wrong passphrase, or the file is damaged. Nothing was changed.", 403)
    with db.tx() as c:
        for t in TABLES: c.execute(f"DELETE FROM {t}")
        for t, rows in data["tables"].items():
            if t not in TABLES: continue
            for r in rows:
                if isinstance(r.get("vec"), str): r["vec"] = base64.b64decode(r["vec"])
                c.execute(f"INSERT INTO {t}({','.join(r.keys())}) VALUES({','.join('?' * len(r))})", list(r.values()))
        for k, v in data.get("settings", {}).items():
            if k in db.DEFAULTS and k not in db.SECRET: c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
    if "graph_nodes" not in data["tables"]: graph.rebuild()          # a backup from before the map existed
    if "dreams" not in data["tables"]: insights.rebuild()            # ... or before dreams and notes
    return {"restored": {t: len(r) for t, r in data["tables"].items()}}

@app.post("/api/danger/erase")
def erase(body: dict):
    if body.get("confirm") != "erase": bad("Type erase to confirm.")
    with db.tx() as c:
        for t in TABLES: c.execute(f"DELETE FROM {t}")
    return {"ok": True}

_UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
if os.path.isdir(_UI): app.mount("/", StaticFiles(directory=_UI, html=True), name="ui")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("SELFWARD_PORT", "8100")), access_log=False)
