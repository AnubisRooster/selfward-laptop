"""Shared setup: a temp journal, no model, no network, no background threads that outlive a test."""
import io, json, os, sys, tempfile, threading, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import DATA      # noqa: E402  (importing the package already pointed Selfward at a temp folder)

import selfward_api as api            # noqa: E402
from sf import db, llm, chat          # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

llm.embed = lambda texts: None
client = TestClient(api.app)

if os.path.realpath(db.DB_PATH) != os.path.realpath(os.path.join(DATA, "selfward.db")):
    raise RuntimeError(f"Refusing to run: the tests would use {db.DB_PATH}, not their own temporary journal.")

def reset():
    assert os.path.realpath(db.DB_PATH).startswith(os.path.realpath(tempfile.gettempdir())), "not a temporary journal"
    with db.tx() as c:
        for t in api.TABLES + ["settings"]: c.execute(f"DELETE FROM {t}")
    chat._running.clear(); chat._cancelled.clear()

class FakeModel:
    """Replaces the model: records what it was sent and streams a fixed reply."""
    def __init__(self, reply="That sounds hard. What was it like?"):
        self.reply = reply; self.calls = []
    def __enter__(self):
        self._old = llm.stream
        def fake(messages, model=None, temperature=0.6):
            self.calls.append(messages)
            for w in self.reply.split(" "): yield w + " "
        llm.stream = fake; return self
    def __exit__(self, *a): llm.stream = self._old

def wait_idle(sid, seconds=10):
    import time
    end = time.time() + seconds
    while time.time() < end:
        if sid not in chat._running: chat.join_background(); return
        time.sleep(0.02)
    raise AssertionError("the turn never finished")


def tiny_wav(frames=240):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class FakeSpeechServer:
    """Plays the part of the Kokoro server: /health, /v1/voices and /v1/audio/speech."""

    def __init__(self):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _send(self, status, body, kind="application/json"):
                self.send_response(status); self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health": self._send(200, b"{}")
                elif self.path == "/v1/voices": self._send(200, json.dumps({"voices": ["bf_emma", "af_heart", "am_michael"]}).encode())
                else: self._send(404, b"{}")

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                outer.requests.append(body); self._send(200, tiny_wav(), "audio/wav")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown(); self.server.server_close()
