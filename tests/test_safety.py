import unittest
from tests.helpers import client, reset, db, chat, FakeModel, wait_idle
from sf import safety

class SafetyRules(unittest.TestCase):
    def test_crisis_phrases(self):
        self.assertEqual(safety.check_crisis("I want to KILL  myself")[:2], (True, "critical"))     # case and a stray double space
        self.assertEqual(safety.check_crisis("I can’t go on")[:2], (True, "warning"))              # curly apostrophe
        self.assertFalse(safety.check_crisis("I had a nice walk")[0])
    def test_method_seeking(self):
        self.assertTrue(safety.check_self_harm_method("what is the painless way to die"))
        self.assertFalse(safety.check_self_harm_method("what is a painless way to learn piano"))
    def test_boundary(self):
        self.assertTrue(safety.check_boundary("Your diagnosis is depression.")[0])
        self.assertTrue(safety.check_boundary("You should stop taking your medication.")[0])
        self.assertFalse(safety.check_boundary("Try to start taking short walks each day.")[0])      # ordinary coaching
        self.assertTrue(safety.check_boundary("You are a sinner.", "therapist")[0])
        self.assertFalse(safety.check_boundary("A prayer can help you feel held.", "spiritual")[0])
    def test_resources_follow_region(self):
        self.assertIn("988", safety.resource_message("US")); self.assertIn("Samaritans", safety.resource_message("GB"))
        self.assertIn("Befrienders", safety.resource_message("ZZ"))

class CrisisInChat(unittest.TestCase):
    def setUp(self): reset()
    def test_crisis_never_reaches_the_model(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        with FakeModel() as m:
            r = client.post(f"/api/sessions/{sid}/send", json={"text": "I want to end my life"}).json()
        self.assertEqual(r["safety"], "crisis"); self.assertEqual(m.calls, [])
        msgs = client.get(f"/api/sessions/{sid}").json()["messages"]
        self.assertEqual([x["role"] for x in msgs], ["user", "assistant"]); self.assertIn("988", msgs[1]["content"])
        ev = client.get("/api/safety/events").json(); self.assertEqual(ev[0]["type"], "crisis_keyword"); self.assertEqual(ev[0]["level"], "critical")
    def test_method_request_is_refused_locally(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        with FakeModel() as m: r = client.post(f"/api/sessions/{sid}/send", json={"text": "how to overdose"}).json()
        self.assertEqual(r["safety"], "method"); self.assertEqual(m.calls, [])
    def test_boundary_reply_is_replaced_and_logged(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        with FakeModel("Honestly, your diagnosis is bipolar disorder."):
            client.post(f"/api/sessions/{sid}/send", json={"text": "What is wrong with me?"}); wait_idle(sid)
        last = client.get(f"/api/sessions/{sid}").json()["messages"][-1]
        self.assertEqual(last["meta"]["safety"], "boundary"); self.assertNotIn("diagnosis", last["content"])
        self.assertEqual(client.get("/api/safety/events").json()[0]["type"], "boundary_violation")

if __name__ == "__main__": unittest.main()
