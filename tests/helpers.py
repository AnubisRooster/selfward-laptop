"""Shared setup: a temp journal, no model, no network, no background threads that outlive a test."""
import os, sys, tempfile, threading

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
