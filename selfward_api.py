"""Selfward local API (FastAPI). Run: python3 selfward_api.py  ->  http://localhost:8100/"""
import base64, gzip, hashlib, json, os, secrets, time
import httpx, uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sf import awake, db, llm, chat, graph, insights, memory, mood, narrative, openrouter, personas, remote, safety, stt, tailscale, tts
from sf.prompts import ALL_MODALITIES, MODALITY_DESCRIPTIONS, COMPANION_PERSONALITY_LABELS, COMPANION_GENDER_LABELS, SPIRITUAL_TRADITION_LABELS

app = FastAPI(title="Selfward")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8100", "http://127.0.0.1:8100", "tauri://localhost", "http://tauri.localhost"],
                   allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def front_door(request: Request, call_next):
    """Phones come through Tailscale Serve; they sign in first (sf/remote.py). Local use is unchanged."""
    refusal = remote.decide(request.method, request.url.path, request.headers, request.cookies.get(remote.COOKIE))
    if refusal:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": refusal[1], "remote_auth": refusal[0] == 401}, status_code=refusal[0], headers={"Cache-Control": "no-store"})
    resp = await call_next(request)
    if remote.is_remote(request.headers) and request.url.path.startswith("/api/"): resp.headers["Cache-Control"] = "no-store"      # nothing from the journal is cached on a phone
    return resp

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
        if k in LOCKED or k.startswith("remote_") or k not in db.DEFAULTS: continue
        if k == "api_key" and v is True: continue          # the UI only ever sees "set / not set"
        if k == "default_persona" and v not in personas.KINDS: bad("Unknown persona.")
        if k == "default_modality" and v not in ALL_MODALITIES: bad("Unknown approach.")
        if k.startswith("tts_") or k.startswith("voice_"):
            try: tts.validate_setting(k, v, body.get("values"))
            except ValueError as e: bad(str(e))
        if k == "context_tokens":
            try: v = int(v)
            except (TypeError, ValueError): bad("The window must be a number of tokens.")
            if not 2048 <= v <= 262144: bad("Use between 2,048 and 262,144 tokens.")
        db.set_setting(k, v)
    return db.all_settings()

@app.get("/api/models")
def models():
    pre = preflight(); return {"ollama": pre["models"], "current": db.get_setting("model"), "embed": db.get_setting("embed_model"), "ollama_up": pre["ollama"]}

@app.get("/api/openrouter/models")
def openrouter_models(refresh: bool = False):
    """The models OpenRouter lets you use for free. The list is public: this is the one request Selfward makes to openrouter.ai before you choose one."""
    try: return {"models": openrouter.free_models(force=refresh)}
    except Exception as e: bad("Couldn’t reach OpenRouter to get the list (" + type(e).__name__ + "). Check your connection and try again.", 502)

@app.post("/api/models/test")
def models_test(body: dict = None):
    """One tiny request to a model (the chosen one, or the one named), so a wrong key or a rate limit shows up here and not in the middle of a session."""
    model = (body or {}).get("model") or db.get_setting("model")
    try: llm.text([{"role": "user", "content": "Reply with the single word: ok"}], model=model, timeout=90)
    except Exception as e: bad(llm.friendly_error(e), 502)
    return {"ok": True, "model": model}

# ---------- voice: read aloud, and speech input for hands-free ----------
@app.get("/api/tts/status")
def tts_status(): return tts.status()

@app.post("/api/tts")
def tts_speak(body: dict):
    persona = body.get("persona")
    voice = body.get("voice") or (db.get_setting("voice_" + persona) if persona in personas.KINDS else "") or db.get_setting("tts_voice")
    speed = body.get("speed") if body.get("speed") is not None else (db.get_setting("voice_rate") or 1.0)
    try: audio = tts.synth(str(body.get("text", "")), voice, float(speed))
    except (ValueError, TypeError) as e: bad(str(e))
    except httpx.HTTPError: bad("The speech server isn't running yet. It starts by itself when it is installed; try again in a few seconds.", 502)
    except RuntimeError as e: bad(str(e), 502)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})

@app.get("/api/voice/status")
def voice_status(): return stt.status()

@app.post("/api/voice/start")
def voice_start():
    try: stt.start()
    except RuntimeError as e: bad(str(e), 409)
    return stt.status()

@app.post("/api/voice/stop")
def voice_stop(): stt.stop(); return stt.status()

@app.post("/api/voice/pause")
def voice_pause(): return {"ok": stt.send("pause")}

@app.post("/api/voice/resume")
def voice_resume(): return {"ok": stt.send("resume")}

@app.get("/api/voice/poll")
def voice_poll(after: int = 0): return stt.poll(after)

@app.on_event("shutdown")
def _close_microphone(): stt.stop(); stt.stop_worker(); awake.release()

@app.on_event("startup")
def _start(): awake.sync()

@app.post("/api/voice/transcribe")
async def voice_transcribe(request: Request):
    """A phone's recording (the body is the audio file) -> text, with the speech model on this laptop. Nothing is stored."""
    import tempfile
    from starlette.concurrency import run_in_threadpool
    body = await request.body()
    if not body: bad("No audio received.")
    if len(body) > stt.MAX_AUDIO_BYTES: bad("That recording is too long. Say a shorter sentence.", 413)
    kind = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    ext = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/webm": ".webm", "audio/mp4": ".mp4", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/aac": ".aac"}.get(kind)
    if not ext: bad("Unsupported audio type.", 415)
    def work():
        with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as f:
            f.write(body); f.flush(); return stt.transcribe(f.name)
    try: return {"text": await run_in_threadpool(work)}
    except RuntimeError as e: bad(str(e), 503)

# ---------- remote (phone) access ----------
@app.post("/api/remote/login")
def remote_login(body: dict, request: Request, response: Response):
    wait = remote.locked_for()
    if wait > 0: bad(f"Too many wrong tries. Wait {int(wait // 60) + 1} minutes.", 429)
    time.sleep(0.5)
    stored = db.get_setting("remote_hash")
    if not stored or not remote.check_pass(str(body.get("passphrase", "")), stored):
        remote.record_failure(); remote.log("wrong passphrase", request.headers.get("tailscale-user-login", "")); bad("Wrong passphrase.", 403)
    remote.clear_failures(); token = remote.new_session(request.headers.get("user-agent", "")); remote.log("signed in", request.headers.get("user-agent", "")[:80])
    response.set_cookie(remote.COOKIE, token, max_age=remote.SESSION_SECONDS, httponly=True, secure=True, samesite="strict", path="/")
    return {"ok": True}

@app.get("/api/remote/session")
def remote_session(request: Request):
    return {"enabled": remote.enabled(), "signed_in": bool(remote.valid_session(request.cookies.get(remote.COOKIE)))}

@app.post("/api/remote/logout")
def remote_logout(request: Request, response: Response):
    sid = remote.valid_session(request.cookies.get(remote.COOKIE))
    if sid: remote.revoke(sid)
    response.delete_cookie(remote.COOKIE, path="/"); return {"ok": True}

# Managing remote access is only possible from this computer (see LAPTOP_ONLY in sf/remote.py).
@app.get("/api/remote/status")
def remote_status():
    return {"enabled": remote.enabled(), "login": db.get_setting("remote_login") or "", "host": db.get_setting("remote_host") or "", "has_passphrase": bool(db.get_setting("remote_hash")),
            "keep_awake": db.get_setting("remote_keep_awake") is not False, "awake_held": awake.running(), "sessions": remote.list_sessions(), "log": (db.get_setting("remote_log") or [])[-20:]}

@app.put("/api/remote/config")
def remote_config(body: dict):
    if body.get("passphrase"):
        if len(str(body["passphrase"])) < 8: bad("Use at least 8 characters for the remote passphrase.")
        db.set_setting("remote_hash", remote.hash_pass(str(body["passphrase"]))); remote.revoke("all")      # a new passphrase signs every phone out
    if "login" in body: db.set_setting("remote_login", str(body["login"]).strip().lower())
    if "host" in body: db.set_setting("remote_host", str(body["host"]).strip().lower())
    if "keep_awake" in body: db.set_setting("remote_keep_awake", bool(body["keep_awake"]))
    if "enabled" in body:
        if body["enabled"] and not (db.get_setting("remote_hash") and db.get_setting("remote_login")): bad("Set a passphrase and your Tailscale login before turning remote access on.")
        db.set_setting("remote_enabled", bool(body["enabled"])); remote.log("turned on" if body["enabled"] else "turned off")
        if not body["enabled"]: remote.revoke("all")
    awake.sync()
    return remote_status()

@app.post("/api/remote/revoke")
def remote_revoke(body: dict): remote.revoke(str(body.get("id", "all"))); return remote_status()

@app.get("/api/remote/tailscale")
def remote_tailscale(): return tailscale.info()

# ---------- sessions & chat ----------
import re
MODEL_RE = re.compile(r"^[A-Za-z0-9_\-./:@+]{1,200}$")
def _check_model(m):
    """A model id such as ollama_chat/llama3.2:3b or openrouter/openrouter/free; empty means 'follow the default in Settings'."""
    if m in (None, ""): return ""
    if not isinstance(m, str) or not MODEL_RE.match(m): bad("That doesn't look like a model id (for example ollama_chat/llama3.2:3b).")
    return m

def _session_row(s):
    p = personas.resolve(s["persona"]); eff = s.get("model") or db.get_setting("model")
    last = db.q("SELECT content FROM messages WHERE session_id=? AND role='assistant' AND content!='' ORDER BY id DESC LIMIT 1", (s["id"],), one=True)
    return {**s, "persona_name": p["display"], "preview": (last["content"] if last else "")[:120], "model_effective": eff, "model_is_local": llm.is_local(eff)}

@app.get("/api/sessions")
def sessions(archived: bool = False):
    return [_session_row(s) for s in db.q("SELECT * FROM sessions WHERE archived=? ORDER BY updated DESC", (1 if archived else 0,))]

@app.post("/api/sessions")
def session_new(body: dict):
    sid = chat.new_session(body.get("persona"), body.get("modality"), body.get("title"))
    if body.get("model"): db.x("UPDATE sessions SET model=? WHERE id=?", (_check_model(body["model"]), sid))
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
        if k == "model": body[k] = _check_model(body[k])
        db.x(f"UPDATE sessions SET {k}=? WHERE id=?", (int(body[k]) if k == "archived" else body[k], sid))
    return {"ok": True}

@app.delete("/api/sessions/{sid}")
def session_del(sid: int):
    for t in ("messages", "memories", "safety_events"): db.x(f"DELETE FROM {t} WHERE session_id=?", (sid,))
    graph.delete_session(sid)
    db.x("DELETE FROM global_memories WHERE session_id=?", (sid,))
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

# ---------- mood check-ins ----------
@app.get("/api/mood")
def mood_view(days: int = 30): return mood.view(days)

@app.post("/api/mood")
def mood_log(body: dict):
    try: mid, crisis = mood.log(body.get("value"), body.get("note", ""))
    except ValueError as e: bad(str(e))
    return {"id": mid, "support": crisis}

@app.delete("/api/mood/{mid}")
def mood_del(mid: int): db.x("DELETE FROM moods WHERE id=?", (mid,)); return {"ok": True}

# ---------- the narrative ----------
@app.get("/api/narrative")
def narrative_get(): return narrative.view()

@app.post("/api/narrative/build")
def narrative_build(body: dict):
    try: material, withheld, more, room = narrative.plan(bool(body.get("local")))
    except Exception as e: bad(llm.friendly_error(e), 500)
    if not material:
        bad(f"The next {'item has' if withheld == 1 else 'items have'} wording that is never sent to a cloud model. Build on this computer to include it." if withheld else "Nothing new to add yet.")
    if not narrative.start(bool(body.get("local"))): bad("The narrative is already being written.", 409)
    return {"started": True, "items": len(material)}

@app.put("/api/narrative")
def narrative_put(body: dict):
    narrative.set_content(str(body.get("content", ""))); return {"ok": True}

@app.post("/api/narrative/restore")
def narrative_restore():
    try: narrative.restore_previous()
    except ValueError as e: bad(str(e))
    return {"ok": True}

@app.delete("/api/narrative")
def narrative_delete(): narrative.reset(); return {"ok": True}

@app.get("/api/narrative/export")
def narrative_export():
    return Response(narrative.view()["content"] or "", media_type="text/markdown", headers={"Content-Disposition": "attachment; filename=selfward-narrative.md"})

# ---------- what Selfward remembers ----------
@app.get("/api/global-memories")
def global_memories():
    titles = _session_titles()
    return [{k: v for k, v in r.items() if k != "vec"} | {"session_title": titles.get(r["session_id"], "")} for r in db.q("SELECT * FROM global_memories ORDER BY importance DESC, ts DESC")]

@app.post("/api/global-memories")
def global_memory_new(body: dict):
    try: return {"id": memory.add_manual(body.get("content"))}
    except ValueError as e: bad(str(e))

@app.delete("/api/global-memories/{mid}")
def global_memory_del(mid: int): db.x("DELETE FROM global_memories WHERE id=?", (mid,)); return {"ok": True}

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
TABLES = ["sessions", "messages", "memories", "safety_events", "graph_nodes", "graph_edges", "dreams", "notes", "global_memories", "narrative", "moods"]
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
    data = _dump(True); data["settings"] = {k: v for k, v in db.all_settings(hide=()).items() if k not in db.SECRET + ("lock_enabled",) and not k.startswith("remote_")}
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
            if k in db.DEFAULTS and k not in db.SECRET and not k.startswith("remote_"): c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
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
