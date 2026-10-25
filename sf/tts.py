"""Natural read-aloud voice: a thin proxy to a text-to-speech server on this machine.

The server speaks the OpenAI /v1/audio/speech API (Kokoro: tts/server.py, or Kokoro-FastAPI). Only loopback addresses are allowed, so what
the guide says never leaves this computer.

Selfward does not carry its own copy of the voice models (about 1 GB). It uses SmartWard's (tts/ and stt/ in its folder) when that is installed:
`voice_home()` finds the folder, and `ensure_started()` starts the server from there if nothing is listening. The folder is not a setting on
purpose: a setting that names a program to run is something a web page could try to change.
"""
import os, re, subprocess, threading, time
from pathlib import Path
from urllib.parse import urlparse
import httpx
from . import db

DEFAULT_URL = "http://127.0.0.1:8880"
VOICE_RE = re.compile(r"^[a-z]{2}_[a-z0-9_]{1,36}$")
SPEED = (0.5, 2.0)
MAX_TEXT = 3000
MAX_PROFILES = 24

def voice_home():
    """The folder that holds tts/ and stt/ (SELFWARD_VOICE_HOME, else SmartWard's, else this one), or None."""
    here = Path(__file__).resolve().parent.parent
    for c in (os.environ.get("SELFWARD_VOICE_HOME"), os.path.expanduser("~/SmartWardApp"), str(here)):
        if c and (Path(c) / "tts" / "start.sh").is_file(): return Path(c)
    return None

_started = {"at": 0.0}
def ensure_started():
    """Starts the speech server if it is installed but not running. start.sh does nothing when it is already up; tried at most every 30 s."""
    home = voice_home()
    if not home or not (home / "tts" / ".venv" / "bin" / "python").exists() or time.time() - _started["at"] < 30: return False
    _started["at"] = time.time()
    try: subprocess.Popen([str(home / "tts" / "start.sh")], cwd=str(home), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError: return False
    return True

def is_loopback(url: str) -> bool:
    try: host = (urlparse(url).hostname or "").lower()
    except Exception: return False
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")

def base() -> str:
    url = (db.get_setting("tts_url") or DEFAULT_URL).rstrip("/")
    if not is_loopback(url): raise ValueError("The speech server must be on this computer (127.0.0.1 or localhost).")
    return url

def voices() -> list:
    for path in ("/v1/voices", "/v1/audio/voices"):
        try:
            r = httpx.get(base() + path, timeout=3)
            if r.status_code == 200: return sorted(r.json().get("voices", []))
        except Exception: pass
    return []

def status() -> dict:
    home = voice_home(); installed = bool(home and (home / "tts" / ".venv" / "bin" / "python").exists())
    try: url = base()
    except ValueError as e: return {"up": False, "voices": [], "url": db.get_setting("tts_url"), "error": str(e), "installed": installed}
    try:
        up = httpx.get(url + "/health", timeout=2).status_code == 200
    except Exception:
        up = False
    if not up and installed: ensure_started()
    return {"up": up, "voices": voices() if up else [], "url": url, "installed": installed, "home": str(home) if home else ""}

def synth(text: str, voice: str, speed: float) -> bytes:
    text = (text or "").strip()
    if not text: raise ValueError("Nothing to read.")
    if len(text) > MAX_TEXT: raise ValueError(f"Text is too long ({len(text)} characters; the limit is {MAX_TEXT}).")
    if not VOICE_RE.match(voice or ""): raise ValueError("That isn't a voice name like af_heart.")
    if not (SPEED[0] <= speed <= SPEED[1]): raise ValueError("Speed must be between 0.5 and 2.")
    r = httpx.post(base() + "/v1/audio/speech", json={"model": "kokoro", "input": text, "voice": voice, "speed": speed, "response_format": "wav"}, timeout=180)
    if r.status_code != 200: raise RuntimeError(f"The speech server answered {r.status_code}: {r.text[:200]}")
    return r.content

GUIDE_VOICES = ("voice_therapist", "voice_companion", "voice_spiritual")

def validate_setting(key: str, value, incoming: dict | None = None):
    """Raises ValueError for a speech setting that shouldn't be saved."""
    if key == "tts_url":
        if not isinstance(value, str) or not is_loopback(value): raise ValueError("The speech server must be on this computer (127.0.0.1 or localhost).")
    elif key == "tts_engine":
        if value not in ("auto", "kokoro", "browser"): raise ValueError("Engine must be auto, kokoro or browser.")
    elif key == "tts_voice" or key in GUIDE_VOICES:
        if value != "" or key == "tts_voice":
            if not isinstance(value, str) or not VOICE_RE.match(value): raise ValueError("That isn't a voice name like af_heart.")
    elif key == "voice_rate":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not (SPEED[0] <= value <= SPEED[1]): raise ValueError("Speed must be between 0.5 and 2.")
