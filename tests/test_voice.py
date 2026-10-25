import os, sys, time, unittest
from tests.helpers import client as c, reset, db, FakeSpeechServer, FakeModel, wait_idle
from sf import stt, tts

FAKE = os.path.join(os.path.dirname(__file__), "fixtures", "fake_listener.py")
def wait(pred, secs=5):
    end = time.time() + secs
    while time.time() < end:
        if pred(): return True
        time.sleep(0.05)
    return False

class Speech(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.fake = FakeSpeechServer()
    @classmethod
    def tearDownClass(cls): cls.fake.close()
    def setUp(self):
        reset(); self.fake.requests.clear(); tts._started["at"] = time.time()          # never start a real server from a test
        c.put("/api/settings", json={"values": {"tts_url": self.fake.url}})
    def test_status_lists_voices_when_up_and_says_down_when_not(self):
        s = c.get("/api/tts/status").json(); self.assertTrue(s["up"]); self.assertEqual(s["voices"], ["af_heart", "am_michael", "bf_emma"])
        c.put("/api/settings", json={"values": {"tts_url": "http://127.0.0.1:9"}}); s = c.get("/api/tts/status").json(); self.assertFalse(s["up"]); self.assertEqual(s["voices"], [])
    def test_speech_is_proxied_with_the_chosen_voice_and_speed(self):
        r = c.post("/api/tts", json={"text": "Hello there.", "voice": "bf_emma", "speed": 1.3}); self.assertEqual(r.status_code, 200); self.assertTrue(r.content.startswith(b"RIFF"))
        self.assertEqual((self.fake.requests[-1]["input"], self.fake.requests[-1]["voice"], self.fake.requests[-1]["speed"]), ("Hello there.", "bf_emma", 1.3))
    def test_each_guide_has_its_own_voice_with_the_default_as_fallback(self):
        c.put("/api/settings", json={"values": {"tts_voice": "af_heart", "voice_companion": "am_michael", "voice_rate": 0.9}})
        c.post("/api/tts", json={"text": "Hi.", "persona": "companion"}); self.assertEqual((self.fake.requests[-1]["voice"], self.fake.requests[-1]["speed"]), ("am_michael", 0.9))
        c.post("/api/tts", json={"text": "Hi.", "persona": "therapist"}); self.assertEqual(self.fake.requests[-1]["voice"], "af_heart")           # no voice set for this guide
        c.post("/api/tts", json={"text": "Hi.", "persona": "wizard"}); self.assertEqual(self.fake.requests[-1]["voice"], "af_heart")
        c.post("/api/tts", json={"text": "Hi.", "persona": "companion", "voice": "bf_emma"}); self.assertEqual(self.fake.requests[-1]["voice"], "bf_emma")  # an explicit choice (the Listen button) wins
    def test_bad_requests_are_refused_plainly(self):
        for body in ({"text": ""}, {"text": "x" * 3001}, {"text": "hi", "voice": "../../etc"}, {"text": "hi", "speed": 9}):
            self.assertEqual(c.post("/api/tts", json=body).status_code, 400, body)
    def test_the_speech_server_must_be_on_this_computer(self):
        for url in ("http://example.com:8880", "http://192.168.1.5:8880", "http://127.0.0.1.evil.com"):
            r = c.put("/api/settings", json={"values": {"tts_url": url}}); self.assertEqual(r.status_code, 400, url); self.assertIn("this computer", r.json()["detail"])
    def test_voice_settings_are_validated(self):
        for values in ({"tts_engine": "cloud"}, {"voice_rate": 5}, {"tts_voice": "nope"}, {"voice_companion": "not a voice"}, {"voice_rate": True}):
            self.assertEqual(c.put("/api/settings", json={"values": values}).status_code, 400, values)
        self.assertEqual(c.put("/api/settings", json={"values": {"voice_companion": ""}}).status_code, 200)         # empty = use the default voice
    def test_no_server_is_a_clear_502(self):
        c.put("/api/settings", json={"values": {"tts_url": "http://127.0.0.1:9"}}); r = c.post("/api/tts", json={"text": "Hello."}); self.assertEqual(r.status_code, 502); self.assertIn("isn't running", r.json()["detail"])
    def test_the_voice_folder_cannot_be_chosen_through_settings(self):
        c.put("/api/settings", json={"values": {"voice_home": "/tmp/evil", "tts_start": "rm -rf /"}}); self.assertNotIn("voice_home", c.get("/api/settings").json())

class Listener(unittest.TestCase):
    def setUp(self): reset(); os.environ["SELFWARD_STT_CMD"] = f"{sys.executable} {FAKE}"; stt.reset()
    def tearDown(self): stt.reset(); os.environ.pop("SELFWARD_STT_CMD", None)
    def test_start_delivers_events_in_order_and_only_once(self):
        self.assertEqual(c.post("/api/voice/start").status_code, 200); self.assertTrue(wait(lambda: len(c.get("/api/voice/poll").json()["events"]) >= 2))
        body = c.get("/api/voice/poll").json(); self.assertEqual([e["type"] for e in body["events"]], ["ready", "text"]); self.assertEqual(body["events"][1]["text"], "hello there")
        self.assertEqual(c.get("/api/voice/poll", params={"after": body["seq"]}).json()["events"], [])
    def test_pause_resume_stop(self):
        c.post("/api/voice/start"); wait(lambda: c.get("/api/voice/poll").json()["ready"])
        self.assertTrue(c.post("/api/voice/pause").json()["ok"]); self.assertTrue(wait(lambda: c.get("/api/voice/poll").json()["state"] == "paused"))
        self.assertTrue(c.post("/api/voice/resume").json()["ok"]); self.assertTrue(wait(lambda: c.get("/api/voice/poll").json()["state"] == "listening"))
        self.assertFalse(c.post("/api/voice/stop").json()["running"]); self.assertFalse(c.post("/api/voice/pause").json()["ok"])
    def test_the_microphone_closes_by_itself_when_nobody_is_asking(self):
        old = stt.IDLE_STOP_S; stt.IDLE_STOP_S = 1
        try: c.post("/api/voice/start"); self.assertTrue(wait(lambda: c.get("/api/voice/poll").json()["running"])); self.assertTrue(wait(lambda: not stt.status()["running"], 5))
        finally: stt.IDLE_STOP_S = old
    def test_not_installed_is_a_clear_409(self):
        os.environ.pop("SELFWARD_STT_CMD"); stt.reset(); old = tts.voice_home; tts.voice_home = lambda: None
        try: r = c.post("/api/voice/start"); self.assertEqual(r.status_code, 409); self.assertIn("isn't installed", r.json()["detail"]); self.assertFalse(c.get("/api/voice/status").json()["installed"])
        finally: tts.voice_home = old
    def test_spoken_crisis_words_get_the_same_screen_as_typed_ones(self):
        sid = c.post("/api/sessions", json={}).json()["id"]
        with FakeModel() as m: r = c.post(f"/api/sessions/{sid}/send", json={"text": "I want to end my life."}).json()      # what the listener would hand over
        self.assertEqual(r["safety"], "crisis"); self.assertEqual(m.calls, [])

if __name__ == "__main__": unittest.main()
