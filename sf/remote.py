"""The front door for reaching Selfward from a phone (through Tailscale Serve).

Ported from SmartWard (sw/remote.py). The API itself still listens on 127.0.0.1 only. A request that came through the proxy carries
forwarded headers: it is "remote" and must pass every check below. A request without them is the local window and keeps working as it always did
(its Host must still be a loopback name, which stops a web page from reaching the API by rebinding its own DNS name).

What a signed-in phone may do differs from SmartWard on purpose: you chose that it can do everything in the app, including settings, backup,
export and erase. Two things stay on the laptop because they make no sense, or are dangerous, from a phone:
- managing remote access itself (turning it on or off, the passphrase, who is signed in): a stolen phone must not be able to keep itself signed in,
  change the passphrase and lock you out, or switch the door off and on again to look like a new device;
- the laptop's own microphone (a phone has its own, and a remote switch for the laptop's would be a way to listen to the room).
Sign-in lasts 7 days after the last use, because this is a private journal."""
import hashlib, hmac, re, secrets, threading, time
from urllib.parse import urlparse
from . import db

COOKIE = "sf_remote"
SESSION_SECONDS = 7 * 86400
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
FORWARDED = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "tailscale-user-login")
SAFE = ("GET", "HEAD", "OPTIONS")

_R = lambda m, p: (m, re.compile("^" + p + "$"))
# Refused to a phone even when signed in. Everything else under /api/ is allowed once signed in.
LAPTOP_ONLY = [
    _R("GET", r"/api/remote/(status|tailscale)"), _R("PUT", r"/api/remote/config"), _R("POST", r"/api/remote/revoke"),
    _R("GET", r"/api/voice/(status|poll)"), _R("POST", r"/api/voice/(start|stop|pause|resume)"),
]
PUBLIC = [_R("POST", r"/api/remote/login"), _R("GET", r"/api/remote/session")]

_lock = threading.Lock()
_fails = []          # times of recent wrong passphrases
_locked_until = [0.0]


def host_of(headers):
    """The Host header without its port: `laptop.ts.net:8443` -> `laptop.ts.net`, `[::1]:8100` -> `::1`."""
    h = (headers.get("host") or "").strip().lower()
    if h.startswith("[") and "]" in h: return h[1:h.index("]")]
    return h.split(":")[0] if h.count(":") == 1 else h

def is_remote(headers): return any(k in headers for k in FORWARDED)
def enabled(): return bool(db.get_setting("remote_enabled"))
def _matches(rules, method, path): return any(m == method and r.match(path) for m, r in rules)

def host_ok(host):
    want = (db.get_setting("remote_host") or "").strip().lower()
    return host == want if want else host.endswith(".ts.net")


# ---- passphrase and sessions ----
def hash_pass(p):
    salt = secrets.token_bytes(16)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt, 200_000).hex()

def check_pass(p, stored):
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex(), h)
    except Exception:
        return False

def _digest(token): return hashlib.sha256(token.encode()).hexdigest()
def _sessions(): return db.get_setting("remote_sessions") or {}

def new_session(user_agent=""):
    token = secrets.token_urlsafe(32)
    with _lock:
        now = time.time(); s = {k: v for k, v in _sessions().items() if now - v["last"] < SESSION_SECONDS}
        s[_digest(token)] = {"created": now, "last": now, "agent": (user_agent or "")[:120]}
        db.set_setting("remote_sessions", s)
    return token

def valid_session(token):
    """The session's id when the cookie is good (and slides its expiry), else None. Only a hash of the token is stored."""
    if not token: return None
    d = _digest(token)
    with _lock:
        s = _sessions(); v = s.get(d); now = time.time()
        if not v or now - v["last"] > SESSION_SECONDS: return None
        if now - v["last"] > 600: v["last"] = now; db.set_setting("remote_sessions", s)
    return d[:8]

def list_sessions():
    return [{"id": k[:8], "created": v["created"], "last": v["last"], "agent": v.get("agent", "")} for k, v in sorted(_sessions().items(), key=lambda kv: -kv[1]["last"])]

def revoke(which):
    with _lock:
        s = _sessions(); s = {} if which == "all" else {k: v for k, v in s.items() if k[:8] != which}
        db.set_setting("remote_sessions", s)

def log(event, detail=""):
    with _lock:
        entries = (db.get_setting("remote_log") or [])[-49:] + [{"ts": time.time(), "event": event, "detail": detail[:160]}]
        db.set_setting("remote_log", entries)


# ---- throttle: five wrong passphrases lock sign-in for five minutes ----
def locked_for(): return max(0.0, _locked_until[0] - time.time())

def record_failure():
    now = time.time()
    with _lock:
        _fails[:] = [t for t in _fails if now - t < 900] + [now]
        if len(_fails) >= 5: _locked_until[0] = now + 300; _fails.clear()

def clear_failures():
    with _lock: _fails.clear(); _locked_until[0] = 0.0


# ---- the decision ----
def decide(method, path, headers, cookie=None):
    """None to let the request through, or (status, message) to refuse it."""
    host = host_of(headers)
    if not is_remote(headers):
        return None if host in LOCAL_HOSTS else (400, "Unexpected host name.")
    if not enabled(): return (403, "Remote access is turned off on this computer.")
    if not host_ok(host): return (403, "Unexpected host name.")
    want = (db.get_setting("remote_login") or "").strip().lower()
    if want and (headers.get("tailscale-user-login") or "").strip().lower() != want: return (403, "This Tailscale account isn't allowed.")
    origin = headers.get("origin")
    if origin and method not in SAFE and (urlparse(origin).hostname or "").lower() != host: return (403, "Cross-site request refused.")
    if not path.startswith("/api/"): return None                      # the app itself (page, scripts, icons), so it can show the sign-in
    if _matches(PUBLIC, method, path): return None
    if not valid_session(cookie): return (401, "Sign in required.")
    if _matches(LAPTOP_ONLY, method, path): return (403, "That can only be done on the laptop itself.")
    return None
