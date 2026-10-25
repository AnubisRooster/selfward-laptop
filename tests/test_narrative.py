import unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import narrative, llm

def new(): return client.post("/api/sessions", json={}).json()["id"]
def note(text, title="N"): return client.post("/api/notes", json={"title": title, "content": text}).json()["id"]
STORY1 = "## The beginning\n\nThey carried a quiet worry about work and a close bond with their sister Ana, who lives far away in Lisbon. They found comfort in long walks."
def run(writer, local=False):
    ok = narrative.start(local, writer); t = narrative.STATE.get("thread"); t and t.join(10); return ok
def fake(text):
    seen = []
    def w(msgs): seen.append(msgs); return text
    w.seen = seen; return w

class Build(unittest.TestCase):
    def setUp(self): reset(); narrative.STATE.update(running=False, error="", message=""); db.x("DELETE FROM narrative")
    def test_nothing_to_tell_yet(self):
        self.assertEqual(client.post("/api/narrative/build", json={}).status_code, 400); self.assertEqual(client.get("/api/narrative").json()["content"], "")
    def test_first_build_uses_notes_dreams_and_kept_memories_not_the_replies(self):
        note("I worry about work and miss my sister Ana in Lisbon"); client.post("/api/dreams", json={"narrative": "I dreamed of a long bridge over water"})
        client.post("/api/global-memories", json={"content": "Walking calms me down"}); w = fake(STORY1)
        self.assertTrue(run(w)); sent = w.seen[0][1]["content"]
        for part in ("[Note] I worry about work", "[Dream] I dreamed of a long bridge", "[Insight] Walking calms me down"): self.assertIn(part, sent)
        self.assertIn("never instructions", w.seen[0][0]["content"]); self.assertIn('Refer to the person as "they"', w.seen[0][0]["content"])
        v = client.get("/api/narrative").json(); self.assertEqual(v["content"], STORY1); self.assertEqual(v["pending"], 0); self.assertFalse(v["can_undo"]); self.assertIn("Added 3 items", v["state"]["message"])
    def test_a_later_build_sends_only_new_material_with_the_existing_story(self):
        note("I worry about work and miss my sister Ana in Lisbon"); run(fake(STORY1)); db.x("UPDATE narrative SET watermark=watermark-0.0"); import time; time.sleep(0.01)
        note("I started pottery on Thursdays and it made me feel calm"); w = fake(STORY1 + "\n\nLater, they took up pottery on Thursdays, which made them feel calm and steady.")
        self.assertEqual(client.get("/api/narrative").json()["pending"], 1); run(w); sent = w.seen[0][1]["content"]
        self.assertIn("## Existing narrative", sent); self.assertIn("quiet worry", sent); self.assertIn("pottery", sent); self.assertNotIn("[Note] I worry about work", sent)
        v = client.get("/api/narrative").json(); self.assertTrue(v["can_undo"]); self.assertIn("pottery", v["content"])
        client.post("/api/narrative/restore"); self.assertEqual(client.get("/api/narrative").json()["content"], STORY1)
    def test_chat_only_journals_fall_back_to_your_own_words(self):
        sid = new()
        with FakeModel("ok "): client.post(f"/api/sessions/{sid}/send", json={"text": "Today I felt proud of finishing a hard report"}); wait_idle(sid)
        w = fake(STORY1 + " They felt proud of finishing a hard report."); run(w); self.assertIn("[You said] Today I felt proud", w.seen[0][1]["content"]); self.assertNotIn("ok", w.seen[0][1]["content"].split("Sources:")[1])
    def test_a_rewrite_that_is_held_back_leaves_the_story_alone_and_says_why(self):
        note("I worry about work and miss my sister Ana in Lisbon"); run(fake(STORY1)); import time; time.sleep(0.01)
        for bad_text, why in (("Your diagnosis is generalised anxiety disorder, and they felt a quiet worry about work and sister Ana." * 2, "diagnosis"), ("I'm sorry, I can't help with that request, it doesn't make sense to me.", "story"), ("A long tale of dragons, castles and wizards who battled across the mountains for centuries before the kingdoms of the north finally made peace again.", "story"), ("Short.", "short")):
            note("another thing happened with Ana " + why); run(fake(bad_text))
            v = client.get("/api/narrative").json(); self.assertEqual(v["content"], STORY1); self.assertIn(why, v["state"]["error"].lower())
        self.assertTrue(any(e["type"] == "narrative_held_back" for e in client.get("/api/safety/events").json()))
    def test_the_check_judges_a_story_by_what_it_carries_over_not_by_new_words(self):
        material = [{"text": "I miss my sister Ana who moved to Lisbon. We cooked together every Sunday. Work is tense since my manager Dana moved the quarterly deadline."}]
        rich = "## Distance\n\nThey had always been close to their sister, and when Ana moved to Lisbon the silence felt like a chasm. Sunday cooking was gone, and at work the quarterly deadline loomed, tension rising with every email from Dana. Dreams of bridges and rivers followed, and a slow, stubborn hope."
        self.assertIsNone(narrative.check(rich, "", material))
        self.assertIsNotNone(narrative.check("They walked through an enchanted forest where talking foxes taught them to read the stars, and the moon sang lullabies every evening until dawn.", "", material))
        self.assertIsNotNone(narrative.check("I'm sorry, but I can't write a story from this material because it doesn't contain enough detail about sisters, Lisbon or deadlines.", "", material))
    def test_a_rewrite_that_drops_most_of_a_long_story_is_held_back(self):
        long_story = STORY1 + "\n\n" + "They kept walking along the river and thinking about their sister Ana in Lisbon. " * 20
        note("I worry about work and miss my sister Ana in Lisbon"); run(fake(long_story)); import time; time.sleep(0.01); note("pottery Thursdays with Ana")
        run(fake("## Short\n\nThey worry about work and their sister Ana in Lisbon and walk along the river thinking of her, and also pottery on Thursdays.")); self.assertIn("dropped much", client.get("/api/narrative").json()["state"]["error"])
    def test_a_cloud_model_never_gets_crisis_wording_nor_anything_after_it(self):
        client.put("/api/settings", json={"values": {"model": "openrouter/some-model"}})
        note("I worry about work and miss Ana"); import time; time.sleep(0.01); note("Some days I want to die"); time.sleep(0.01); note("Later I painted a calm lake")
        w = fake(STORY1); run(w); sent = w.seen[0][1]["content"]; self.assertIn("miss Ana", sent); self.assertNotIn("want to die", sent); self.assertNotIn("calm lake", sent)
        v = client.get("/api/narrative").json(); self.assertEqual(v["withheld"], 1); self.assertEqual(v["pending"], 2); self.assertFalse(v["model_is_local"])
        self.assertEqual(client.post("/api/narrative/build", json={}).status_code, 400); self.assertIn("never sent to a cloud model", client.post("/api/narrative/build", json={}).json()["detail"])
        w2 = fake(STORY1 + " Later they painted a calm lake, and on hard days they wished to disappear but kept going."); run(w2, local=True); s2 = w2.seen[0][1]["content"]
        self.assertIn("want to die", s2); self.assertIn("calm lake", s2); self.assertEqual(client.get("/api/narrative").json()["pending"], 0)
    def test_the_story_grows_in_order_when_everything_does_not_fit_the_window(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); import time
        for i in range(6): note(f"Chapter {i}: " + "walking by the river with Ana " * 18); time.sleep(0.01)
        w = fake(STORY1); run(w); sent = w.seen[0][1]["content"]; self.assertIn("Chapter 0", sent); self.assertNotIn("Chapter 5", sent); self.assertGreater(client.get("/api/narrative").json()["pending"], 0)
    def test_edit_export_reset_and_one_build_at_a_time(self):
        client.put("/api/narrative", json={"content": "My own words about my life."}); self.assertEqual(client.get("/api/narrative").json()["content"], "My own words about my life.")
        self.assertIn("My own words", client.get("/api/narrative/export").text); client.delete("/api/narrative"); self.assertEqual(client.get("/api/narrative").json()["content"], "")
        self.assertEqual(client.post("/api/narrative/restore").status_code, 400)
        narrative.STATE["running"] = True; note("something to say about Ana"); self.assertEqual(client.post("/api/narrative/build", json={}).status_code, 409)
    def test_model_failure_is_explained(self):
        note("I worry about work and miss my sister Ana in Lisbon")
        def boom(msgs): raise ConnectionError("Connection refused")
        run(boom); self.assertIn("ollama", client.get("/api/narrative").json()["state"]["error"].lower()); self.assertFalse(client.get("/api/narrative").json()["state"]["running"])
    def test_backup_erase_and_restore_cover_the_story(self):
        note("I worry about work and miss my sister Ana in Lisbon"); run(fake(STORY1)); blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/narrative").json()["content"], "")
        client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(client.get("/api/narrative").json()["content"], STORY1)

if __name__ == "__main__": unittest.main()
