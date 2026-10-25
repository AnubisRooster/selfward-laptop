import unittest
from tests.helpers import client, reset, db, chat, FakeModel, wait_idle
from sf import personas, memory
from sf.prompts import MODALITY_PROMPTS, ALL_MODALITIES

def talk(sid, text, reply="Tell me more."):
    with FakeModel(reply) as m:
        client.post(f"/api/sessions/{sid}/send", json={"text": text}); wait_idle(sid)
    return m

class Chat(unittest.TestCase):
    def setUp(self): reset()
    def test_a_turn_streams_into_the_database(self):
        sid = client.post("/api/sessions", json={"persona": "therapist", "modality": "cbt"}).json()["id"]
        m = talk(sid, "I keep thinking I will fail", "What evidence do you have? ")
        s = client.get(f"/api/sessions/{sid}").json()
        self.assertEqual([x["role"] for x in s["messages"]], ["user", "assistant"])
        self.assertEqual(s["messages"][1]["content"].strip(), "What evidence do you have?"); self.assertEqual(s["status"], "idle")
        self.assertEqual(s["title"], "I keep thinking I will fail")
        self.assertIn("CBT-informed", m.calls[0][0]["content"])                      # the approach shapes the system prompt
        self.assertEqual(m.calls[0][-1], {"role": "user", "content": "I keep thinking I will fail"})
    def test_history_is_sent_once_and_in_order(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        talk(sid, "first"); m = talk(sid, "second")
        sent = [(x["role"], x["content"].strip()) for x in m.calls[0][1:]]
        self.assertEqual(sent, [("user", "first"), ("assistant", "Tell me more."), ("user", "second")])
    def test_every_approach_has_a_prompt(self):
        self.assertEqual(len(ALL_MODALITIES), 15); self.assertEqual(set(ALL_MODALITIES), set(MODALITY_PROMPTS))
        for m in ALL_MODALITIES: self.assertIn("Response style", MODALITY_PROMPTS[m]) if m != "active_imagination" else None
    def test_personas_use_their_own_prompts_and_names(self):
        client.put("/api/settings", json={"values": {"companion_name": "Robin", "companion_personality": "calm", "companion_gender": "nonbinary", "user_name": "Alex"}})
        sid = client.post("/api/sessions", json={"persona": "companion"}).json()["id"]; m = talk(sid, "hi")
        sysmsg = m.calls[0][0]["content"]
        self.assertIn("You are Robin, an AI companion", sysmsg); self.assertIn("calm and grounded", sysmsg); self.assertIn("they/them", sysmsg); self.assertIn("The client's name is Alex", sysmsg)
        sid = client.post("/api/sessions", json={"persona": "spiritual"}).json()["id"]; m = talk(sid, "hi")
        self.assertIn("You are Sage, a thoughtful spiritual companion", m.calls[0][0]["content"]); self.assertIn("Stoic", client.get("/api/catalog").json()["traditions"][1]["label"])
    def test_unnamed_therapist_has_no_name_line(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; m = talk(sid, "hi")
        self.assertNotIn("Your name is", m.calls[0][0]["content"])
        client.put("/api/settings", json={"values": {"therapist_name": "Dr. Ash"}}); m = talk(sid, "again")
        self.assertIn("Your name is Dr. Ash", m.calls[0][0]["content"])
    def test_one_answer_at_a_time(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; chat._running.add(sid)
        self.assertEqual(client.post(f"/api/sessions/{sid}/send", json={"text": "hi"}).status_code, 409)
    def test_empty_message_is_refused(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        self.assertEqual(client.post(f"/api/sessions/{sid}/send", json={"text": "  "}).status_code, 409)
    def test_model_failure_is_explained_not_hidden(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        from sf import llm
        old = llm.stream
        def boom(*a, **k): raise ConnectionError("Connection refused"); yield
        llm.stream = boom
        try: client.post(f"/api/sessions/{sid}/send", json={"text": "hi"}); wait_idle(sid)
        finally: llm.stream = old
        last = client.get(f"/api/sessions/{sid}").json()["messages"][-1]
        self.assertTrue(last["meta"].get("error")); self.assertIn("ollama", last["content"].lower())
    def test_title_is_cut_at_a_word(self):
        self.assertEqual(chat._title("I have been feeling anxious about work lately and cannot switch off in the evenings"), "I have been feeling anxious about work lately and cannot…")
        self.assertEqual(chat._title("Short one"), "Short one")
    def test_history_budget_keeps_the_newest(self):
        msgs = [{"role": "user", "content": "x" * 5000} for _ in range(6)] + [{"role": "user", "content": "newest"}]
        kept = chat.retained_history(msgs, budget=12000)
        self.assertEqual(kept[-1]["content"], "newest"); self.assertLess(len(kept), len(msgs)); self.assertGreaterEqual(len(kept), 3)

class Memory(unittest.TestCase):
    def setUp(self): reset()
    def test_other_sessions_are_recalled_by_shared_words(self):
        a = client.post("/api/sessions", json={}).json()["id"]; talk(a, "My sister Marlene and I argued about the inheritance house")
        b = client.post("/api/sessions", json={}).json()["id"]; m = talk(b, "I keep replaying the inheritance argument with Marlene")
        joined = " ".join(x["content"] for x in m.calls[0] if x["role"] == "system")
        self.assertIn("Relevant context from previous sessions", joined); self.assertIn("Marlene", joined)
    def test_the_current_session_is_not_recalled_twice(self):
        a = client.post("/api/sessions", json={}).json()["id"]; talk(a, "My sister Marlene and I argued about the inheritance house")
        m = talk(a, "the inheritance argument with Marlene again")
        self.assertFalse(any("Relevant context" in x["content"] for x in m.calls[0] if x["role"] == "system"))

class Sessions(unittest.TestCase):
    def setUp(self): reset()
    def test_delete_removes_everything_about_the_session(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; talk(sid, "hello there my friend")
        client.delete(f"/api/sessions/{sid}")
        for t in ("sessions", "messages", "memories"): self.assertEqual(db.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"], 0)
    def test_unknown_persona_and_approach_are_refused(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        self.assertEqual(client.patch(f"/api/sessions/{sid}", json={"persona": "wizard"}).status_code, 400)
        self.assertEqual(client.patch(f"/api/sessions/{sid}", json={"modality": "astrology"}).status_code, 400)
    def test_archive_hides_from_the_main_list(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; client.patch(f"/api/sessions/{sid}", json={"archived": True})
        self.assertEqual(client.get("/api/sessions").json(), []); self.assertEqual(len(client.get("/api/sessions?archived=true").json()), 1)

if __name__ == "__main__": unittest.main()
