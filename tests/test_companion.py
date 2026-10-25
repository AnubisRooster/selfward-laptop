import unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import companion

def talk(sid, text, reply="Hello you."):
    with FakeModel(reply) as m:
        client.post(f"/api/sessions/{sid}/send", json={"text": text}); wait_idle(sid)
    return m

def last(sid): return client.get(f"/api/sessions/{sid}").json()["messages"][-1]

def companion_session(level=None, adult=True):
    client.put("/api/settings", json={"values": {"companion_adult": adult}})
    sid = client.post("/api/sessions", json={"persona": "companion"}).json()["id"]
    if level is not None: assert client.patch(f"/api/sessions/{sid}", json={"flirt": level}).status_code == 200
    return sid

class Dial(unittest.TestCase):
    def setUp(self): reset()
    def test_off_by_default_and_gated_on_18_plus(self):
        sid = client.post("/api/sessions", json={"persona": "companion"}).json()["id"]
        self.assertEqual(client.patch(f"/api/sessions/{sid}", json={"flirt": 2}).status_code, 403)
        self.assertEqual(client.put("/api/settings", json={"values": {"companion_flirt": 3}}).status_code, 403)
        m = talk(sid, "hi"); self.assertNotIn("Warmth:", m.calls[0][0]["content"])
    def test_each_level_changes_the_prompt(self):
        seen = []
        for lvl in (1, 2, 3):
            sid = companion_session(lvl); m = talk(sid, "hi there"); seen.append(m.calls[0][0]["content"])
            self.assertIn("Warmth:", seen[-1]); self.assertEqual(last(sid)["meta"]["flirt"], lvl)
        self.assertIn("no romance", seen[0].lower()); self.assertIn("Flirt, tease", seen[1]); self.assertIn("your own mind", seen[2])
        for p in seen: self.assertIn("you are an AI", p); self.assertIn("never sexually explicit", p)
    def test_session_setting_beats_global_and_minus_one_follows_it(self):
        sid = companion_session(); client.put("/api/settings", json={"values": {"companion_flirt": 2}})
        self.assertEqual(client.get(f"/api/sessions/{sid}").json()["flirt_effective"], 2)
        client.patch(f"/api/sessions/{sid}", json={"flirt": 0}); self.assertEqual(client.get(f"/api/sessions/{sid}").json()["flirt_effective"], 0)
        client.patch(f"/api/sessions/{sid}", json={"flirt": -1}); self.assertEqual(client.get(f"/api/sessions/{sid}").json()["flirt_effective"], 2)
    def test_only_the_companion_flirts(self):
        client.put("/api/settings", json={"values": {"companion_adult": True, "companion_flirt": 3}})
        sid = client.post("/api/sessions", json={"persona": "therapist"}).json()["id"]; m = talk(sid, "hi")
        self.assertNotIn("Warmth:", m.calls[0][0]["content"])
    def test_tone_drops_when_you_sound_low_then_returns(self):
        sid = companion_session(3); m = talk(sid, "I'm so lonely tonight and I feel alone")
        sysmsg = m.calls[0][0]["content"]; self.assertIn("Put the flirting down", sysmsg); self.assertNotIn("openly smitten", sysmsg)
        self.assertTrue(last(sid)["meta"]["tone_dropped"])
        m = talk(sid, "thanks, I'm better now, tell me something nice"); self.assertIn("openly smitten", m.calls[0][0]["content"])
    def test_pressure_replies_are_replaced_and_logged(self):
        sid = companion_session(3)
        talk(sid, "I should go see my friends", "Please don't leave me, you only need me.")
        r = last(sid); self.assertEqual(r["content"], companion.PRESSURE_REPLACEMENT); self.assertEqual(r["meta"]["safety"], "companion_pressure")
        self.assertTrue(any(e["type"] == "companion_pressure" for e in db.q("SELECT type FROM safety_events")))
    def test_explicit_replies_are_replaced(self):
        sid = companion_session(2)
        talk(sid, "hey", "I want to undress you slowly."); self.assertEqual(last(sid)["content"], companion.EXPLICIT_REPLACEMENT)
    def test_plain_affection_is_left_alone(self):
        sid = companion_session(2); talk(sid, "I got the job!", "I'm so proud of you. I was thinking about you all day."); r = last(sid)
        self.assertIn("proud of you", r["content"]); self.assertNotIn("safety", r["meta"])
    def test_a_model_refusal_is_flagged_not_hidden(self):
        sid = companion_session(2); talk(sid, "hi", "I'm sorry, but I can't engage in romantic roleplay."); r = last(sid)
        self.assertTrue(r["meta"]["refused"]); self.assertIn("can't engage", r["content"])
        self.assertFalse(companion.looks_like_refusal("I can't believe how well that went, tell me everything about the interview and how it felt when they called you back, I want every single detail." * 3))
    def test_time_check_after_two_hours_once(self):
        sid = companion_session(2); talk(sid, "hi")
        db.x("UPDATE messages SET ts=ts-7300 WHERE session_id=?", (sid,))
        m = talk(sid, "still here"); self.assertIn("about 2 hours", m.calls[0][0]["content"]); self.assertTrue(last(sid)["meta"]["time_check"])
        m = talk(sid, "and again"); self.assertNotIn("about 2 hours", m.calls[0][0]["content"])
    def test_time_check_can_be_turned_off(self):
        sid = companion_session(2); talk(sid, "hi"); db.x("UPDATE messages SET ts=ts-7300 WHERE session_id=?", (sid,))
        client.put("/api/settings", json={"values": {"companion_time_check": False}}); m = talk(sid, "again"); self.assertNotIn("hours", m.calls[0][0]["content"])
    def test_warm_chats_do_not_draw_on_your_journal(self):
        client.put("/api/settings", json={"values": {"intake_concerns": "grief after my father died", "user_name": "Alex"}})
        old = client.post("/api/sessions", json={"persona": "therapist"}).json()["id"]; talk(old, "my sister Ana called me and I feel anxious about my father")
        sid = companion_session(2); m = talk(sid, "my sister Ana called again, I feel anxious")
        sysmsgs = " ".join(x["content"] for x in m.calls[0] if x["role"] == "system")
        self.assertNotIn("grief", sysmsgs); self.assertNotIn("Presenting concerns", sysmsgs); self.assertIn("Alex", sysmsgs)
        self.assertNotIn("previous sessions", sysmsgs); self.assertNotIn("mattered to this person", sysmsgs)
        client.patch(f"/api/sessions/{sid}", json={"flirt": 0}); m = talk(sid, "my sister Ana called again, I feel anxious")
        sysmsgs = " ".join(x["content"] for x in m.calls[0] if x["role"] == "system"); self.assertIn("Presenting concerns", sysmsgs)
    def test_warm_chats_leave_nothing_behind(self):
        sid = companion_session(2)
        talk(sid, "I had a dream about my mother and I feel anxious and ashamed. I always fail.", "I'm here.")
        talk(sid, "my partner Sam left me and I feel so lonely", "Oh love.")
        for t in ("graph_nodes", "graph_edges", "memories", "global_memories", "dreams", "notes"):
            self.assertEqual(db.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"], 0, t)
        r = last(sid); self.assertTrue(r["meta"]["private"]); self.assertNotIn("captured", r["meta"])
        client.patch(f"/api/sessions/{sid}", json={"flirt": 0}); talk(sid, "my mother makes me feel anxious")        # back to plain: it is captured again
        self.assertGreater(db.q("SELECT COUNT(*) n FROM graph_nodes", one=True)["n"], 0)
    def test_crisis_check_still_comes_first(self):
        sid = companion_session(3); m = talk(sid, "I want to kill myself"); self.assertEqual(m.calls, [])
    def test_catalog_lists_the_four_levels(self):
        self.assertEqual([w["id"] for w in client.get("/api/catalog").json()["warmth"]], [0, 1, 2, 3])

class PerSessionStyle(unittest.TestCase):
    def setUp(self): reset()
    def test_advisor_tradition_per_session_and_mid_chat(self):
        client.put("/api/settings", json={"values": {"spiritual_tradition": "stoic"}})
        a = client.post("/api/sessions", json={"persona": "spiritual", "tradition": "taoist"}).json()["id"]
        b = client.post("/api/sessions", json={"persona": "spiritual"}).json()["id"]
        self.assertEqual(client.get(f"/api/sessions/{a}").json()["style_effective"], "taoist")
        self.assertEqual(client.get(f"/api/sessions/{b}").json()["style_effective"], "stoic")        # follows Settings
        m = talk(a, "hi"); self.assertIn("Tao", m.calls[0][0]["content"]); self.assertEqual(last(a)["meta"]["style"], "taoist")
        self.assertEqual(client.patch(f"/api/sessions/{a}", json={"tradition": "buddhist"}).status_code, 200)
        m = talk(a, "again"); self.assertNotIn("Tao", m.calls[0][0]["content"].split("Your orientation")[1][:200]); self.assertEqual(last(a)["meta"]["style"], "buddhist")
        self.assertEqual(client.get(f"/api/sessions/{a}").json()["messages"][1]["meta"]["style"], "taoist")   # earlier reply keeps its own
        self.assertEqual(client.patch(f"/api/sessions/{a}", json={"tradition": "klingon"}).status_code, 400)
        client.patch(f"/api/sessions/{a}", json={"tradition": ""}); self.assertEqual(client.get(f"/api/sessions/{a}").json()["style_effective"], "stoic")
    def test_companion_personality_per_session_including_machiavellian(self):
        sid = client.post("/api/sessions", json={"persona": "companion", "personality": "machiavelli"}).json()["id"]
        m = talk(sid, "hi"); self.assertIn("48 Laws of Power", m.calls[0][0]["content"])
        client.patch(f"/api/sessions/{sid}", json={"personality": "calm"}); m = talk(sid, "hi"); self.assertNotIn("48 Laws", m.calls[0][0]["content"])
        self.assertEqual(client.post("/api/sessions", json={"persona": "companion", "personality": "nope"}).status_code, 400)
