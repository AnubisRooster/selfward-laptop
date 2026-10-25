import json, unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import insights, llm

def talk(sid, text, reply="I hear you. "):
    with FakeModel(reply) as m: client.post(f"/api/sessions/{sid}/send", json={"text": text}); wait_idle(sid)
    return m

def new(): return client.post("/api/sessions", json={}).json()["id"]
def last(sid): return client.get(f"/api/sessions/{sid}").json()["messages"][-1]

class Dreams(unittest.TestCase):
    def setUp(self): reset()
    def test_a_dream_is_recognised_with_its_feelings_and_symbols(self):
        f, s = insights.detect_dream("Last night I dreamt I was falling from a bridge into dark water and felt terrified and lonely.")
        self.assertEqual(s, ["water", "falling", "bridge"]); self.assertEqual(f, ["fear", "loneliness"])
    def test_ordinary_talk_is_not_a_dream(self):
        self.assertIsNone(insights.detect_dream("I dream of a quieter job someday")); self.assertIsNone(insights.detect_dream("My day was fine."))
    def test_symbols_are_whole_words(self):
        f, s = insights.detect_dream("I had a dream about a carpenter and a firefly"); self.assertEqual(s, [])
    def test_a_dream_in_chat_is_saved_and_badged(self):
        sid = new(); talk(sid, "I had a dream where a snake followed me through the forest and I felt afraid of it")
        d = client.get("/api/dreams").json(); self.assertEqual(len(d), 1); self.assertEqual(d[0]["symbols"], ["forest", "snake"]); self.assertEqual(d[0]["session_id"], sid)
        self.assertEqual(last(sid)["meta"]["captured"]["dream"], d[0]["id"])
    def test_the_same_dream_is_not_saved_twice_and_crisis_turns_save_nothing(self):
        sid = new(); text = "I had a nightmare and I want to die"
        client.post(f"/api/sessions/{sid}/send", json={"text": text}); self.assertEqual(client.get("/api/dreams").json(), [])
        talk(sid, "I had a nightmare about the ocean"); self.assertEqual(len(client.get("/api/dreams").json()), 1)
    def test_plural_symbols_match_but_look_alikes_do_not(self):
        self.assertEqual(insights.detect_dream("I had a dream with snakes and doors and a carpenter")[1], ["snake", "door"])
    def test_manual_dream_and_delete(self):
        i = client.post("/api/dreams", json={"narrative": "A house with endless doors"}).json()["id"]
        d = client.get("/api/dreams").json()[0]; self.assertEqual((d["id"], d["symbols"], d["session_id"]), (i, ["house", "door"], None))
        self.assertEqual(client.post("/api/dreams", json={"narrative": "  "}).status_code, 400)
        client.delete(f"/api/dreams/{i}"); self.assertEqual(client.get("/api/dreams").json(), [])
    def test_interpretation_is_tentative_labelled_and_boundary_checked(self):
        i = client.post("/api/dreams", json={"narrative": "A snake in a garden"}).json()["id"]
        old = llm.text; seen = {}
        def fake(messages, **k): seen["p"] = messages[0]["content"]; return "One reading is that the snake stands for change."
        llm.text = fake
        try: r = client.post(f"/api/dreams/{i}/interpret").json()
        finally: llm.text = old
        self.assertIn("one way of looking", seen["p"]); self.assertIn("snake, garden", seen["p"]); self.assertEqual(client.get("/api/dreams").json()[0]["analysis"], r["analysis"])
        llm.text = lambda *a, **k: "Your diagnosis is a dissociative disorder."
        try: r = client.post(f"/api/dreams/{i}/interpret").json()
        finally: llm.text = old
        self.assertNotIn("diagnosis", r["analysis"])
    def test_a_dream_with_crisis_wording_is_never_sent_to_the_model(self):
        i = client.post("/api/dreams", json={"narrative": "I dreamed I would kill myself"}).json()["id"]
        old = llm.text; llm.text = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the model must not be asked"))
        try: r = client.post(f"/api/dreams/{i}/interpret").json()
        finally: llm.text = old
        self.assertIn("988", r["analysis"])
    def test_interpret_model_failure_is_explained(self):
        i = client.post("/api/dreams", json={"narrative": "A bird"}).json()["id"]; old = llm.text
        llm.text = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("Connection refused"))
        try: r = client.post(f"/api/dreams/{i}/interpret")
        finally: llm.text = old
        self.assertEqual(r.status_code, 502); self.assertIn("ollama", r.json()["detail"].lower())

class Notes(unittest.TestCase):
    def setUp(self): reset()
    def test_summary_note_appears_on_the_second_message_and_is_updated_not_duplicated(self):
        sid = new(); talk(sid, "My mother called and I felt guilty"); self.assertEqual(client.get("/api/notes").json(), [])
        talk(sid, "I always feel guilty about her"); notes = client.get("/api/notes").json()
        self.assertEqual(len(notes), 1); self.assertTrue(notes[0]["title"].startswith("Session Summary")); self.assertIn("Messages exchanged: 2", notes[0]["content"]); self.assertIn("Guilt", notes[0]["content"])
        self.assertEqual(last(sid)["meta"]["captured"]["note"], notes[0]["id"])
        talk(sid, "and my boss makes me anxious"); notes = client.get("/api/notes").json()
        self.assertEqual(len(notes), 1); self.assertIn("Messages exchanged: 3", notes[0]["content"]); self.assertIn("Boss", notes[0]["content"]); self.assertNotIn("note", last(sid)["meta"].get("captured", {}))
    def test_an_edited_summary_is_left_alone(self):
        sid = new(); talk(sid, "I felt sad"); talk(sid, "still sad"); n = client.get("/api/notes").json()[0]
        client.patch(f"/api/notes/{n['id']}", json={"content": "My own words"}); talk(sid, "and angry now")
        notes = client.get("/api/notes").json(); self.assertEqual(len(notes), 1); self.assertEqual(notes[0]["content"], "My own words")
    def test_manual_notes(self):
        i = client.post("/api/notes", json={"title": "Thought", "content": "Remember to rest"}).json()["id"]
        client.patch(f"/api/notes/{i}", json={"content": "Rest more"}); n = client.get("/api/notes").json()[0]; self.assertEqual((n["title"], n["content"], n["auto"]), ("Thought", "Rest more", 0))
        self.assertEqual(client.post("/api/notes", json={"title": " ", "content": ""}).status_code, 400); self.assertEqual(client.post("/api/notes", json={"title": "x", "session_id": 999}).status_code, 404)
        client.delete(f"/api/notes/{i}"); self.assertEqual(client.get("/api/notes").json(), [])
    def test_capture_still_happens_when_the_model_is_down(self):
        sid = new(); old = llm.stream
        def boom(*a, **k): raise ConnectionError("Connection refused"); yield
        llm.stream = boom
        try: client.post(f"/api/sessions/{sid}/send", json={"text": "I had a dream about a train"}); wait_idle(sid)
        finally: llm.stream = old
        self.assertEqual(len(client.get("/api/dreams").json()), 1); self.assertTrue(last(sid)["meta"]["error"]); self.assertIn("dream", last(sid)["meta"]["captured"])

class Insights(unittest.TestCase):
    def setUp(self): reset()
    def test_highlights_read_out_loud_and_fall_back_to_feelings(self):
        sid = new(); self.assertEqual(client.get("/api/insights").json()["highlights"], [])
        talk(sid, "I felt sad"); self.assertEqual(client.get("/api/insights").json()["highlights"], ["Feelings that have come up: Sadness."])
        talk(sid, "My boss was cruel and I felt hurt"); h = client.get(f"/api/insights?session_id={sid}").json()["highlights"]
        self.assertIn("You often feel hurt when Boss comes up.", h)
    def test_rebuild_adds_what_older_sessions_missed_without_duplicating(self):
        sid = new(); talk(sid, "I had a dream about a mountain"); talk(sid, "it was lonely")
        db.x("DELETE FROM dreams"); db.x("DELETE FROM notes")
        self.assertEqual(client.post("/api/insights/rebuild").json()["dreams_found"], 1); self.assertEqual(len(client.get("/api/notes").json()), 1)
        self.assertEqual(client.post("/api/insights/rebuild").json()["dreams_found"], 0); self.assertEqual(len(client.get("/api/notes").json()), 1)
    def test_deleting_a_session_takes_its_dreams_and_notes_and_backup_keeps_them(self):
        a = new(); b = new(); talk(a, "I had a dream about fire"); talk(b, "I had a dream about birds")
        blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        client.delete(f"/api/sessions/{a}"); self.assertEqual([d["session_id"] for d in client.get("/api/dreams").json()], [b])
        client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/dreams").json(), [])
        client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(len(client.get("/api/dreams").json()), 2)

if __name__ == "__main__": unittest.main()
