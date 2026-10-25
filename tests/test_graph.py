import json, unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import graph

def talk(sid, text):
    with FakeModel("I hear you. "): client.post(f"/api/sessions/{sid}/send", json={"text": text}); wait_idle(sid)

def labels(v, t): return sorted(n["label"] for n in v["nodes"] if n["type"] == t)

class Extraction(unittest.TestCase):
    def test_what_a_message_brings_up(self):
        nodes, edges = graph.analyze("My mother called and I felt guilty and ashamed. I always mess things up before a deadline.")
        self.assertEqual(sorted(l for t, l in nodes if t == "emotion"), ["Guilt", "Shame"])
        self.assertIn(("person", "Mother"), nodes); self.assertIn(("event", "Deadline"), nodes)
        self.assertTrue(any(t == "belief" and l == "i always mess things up before a deadline" for t, l in nodes))
        self.assertIn(("Mother", "Guilt", "TRIGGERS"), edges); self.assertIn(("Guilt", "Shame", "ASSOCIATED_WITH"), edges)
        self.assertTrue(any(s == "Guilt" and ty == "CAUSES" for s, _, ty in edges))
    def test_quiet_messages_add_nothing(self):
        self.assertEqual(graph.analyze("I had a nice walk and a sandwich."), ([], []))
    def test_curly_apostrophes_and_extra_spaces(self):
        self.assertTrue(any(t == "belief" for t, _ in graph.analyze("I  can’t   do this")[0]))
    def test_a_word_inside_another_word_is_not_a_match(self):
        self.assertEqual(graph.analyze("a sadder day, a quitter's quest")[0], [])
        self.assertEqual([l for t, l in graph.analyze("so angry, such anger")[0]], ["Anger"])         # variants are one node

class Map(unittest.TestCase):
    def setUp(self): reset()
    def test_repeating_strengthens_up_to_a_cap(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        for _ in range(5): graph.extract(sid, "I felt anxious again")
        n = db.q("SELECT * FROM graph_nodes", one=True); self.assertEqual(n["strength"], graph.MAX_STRENGTH); self.assertEqual(db.q("SELECT COUNT(*) n FROM graph_nodes", one=True)["n"], 1)
    def test_a_feeling_connects_back_to_a_person_raised_earlier(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        graph.extract(sid, "My boss moved the meeting again"); graph.extract(sid, "I am so frustrated", ["My boss moved the meeting again"])
        v = graph.view(sid); self.assertTrue(any(e["source"] == "person:boss" and e["target"] == "emotion:frustration" and e["phrase"] == "brings up" for e in v["edges"]))
    def test_sessions_merge_into_one_map(self):
        a = client.post("/api/sessions", json={}).json()["id"]; b = client.post("/api/sessions", json={}).json()["id"]
        graph.extract(a, "I feel lonely"); graph.extract(b, "so lonely, my mom is far away")
        v = graph.view(); lonely = next(n for n in v["nodes"] if n["label"] == "Loneliness")
        self.assertEqual(lonely["sessions"], [a, b]); self.assertEqual(lonely["strength"], 2.0); self.assertEqual(len(graph.view(a)["nodes"]), 1)
        self.assertEqual(graph.view(a)["nodes"][0]["sessions"], [a])
    def test_strongest_links_read_as_sentences_and_repeats_rank_first(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        graph.extract(sid, "My boss was cruel and I felt hurt"); graph.extract(sid, "My boss again, hurt again"); graph.extract(sid, "My dad was kind but I felt sad")
        links = graph.view(sid)["links"]; self.assertEqual(links[0]["text"], "Boss brings up Hurt"); self.assertGreater(links[0]["weight"], links[-1]["weight"])
        self.assertNotIn("loops", graph.view(sid))
    def test_a_belief_is_one_clause_not_the_rest_of_the_paragraph(self):
        labels_ = [l for t, l in graph.analyze("I always fail when it matters. I feel calm now, though.")[0] if t == "belief"]
        self.assertEqual(labels_, ["i always fail when it matters"])
        self.assertTrue(all(len(l) <= 70 for t, l in graph.analyze("I think that " + "very " * 40 + "long")[0]))
    def test_type_filter_drops_edges_to_hidden_nodes(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; graph.extract(sid, "My dad yelled and I felt hurt")
        v = graph.view(sid, ["emotion"]); self.assertEqual(labels(v, "person"), []); self.assertEqual(v["edges"], [])

class MapThroughChat(unittest.TestCase):
    def setUp(self): reset()
    def test_a_turn_grows_the_map_from_the_users_words_only(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        with FakeModel("It sounds like your sister makes you feel sad. "): client.post(f"/api/sessions/{sid}/send", json={"text": "I went for a walk"}); wait_idle(sid)
        self.assertEqual(client.get("/api/graph").json()["nodes"], [])            # the reply's "sister" and "sad" don't count
        talk(sid, "My sister called and I felt hurt")
        v = client.get(f"/api/graph?session_id={sid}").json(); self.assertEqual(labels(v, "person"), ["Sister"]); self.assertEqual(labels(v, "emotion"), ["Hurt"])
    def test_crisis_messages_stay_out_of_the_map(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        client.post(f"/api/sessions/{sid}/send", json={"text": "I feel hopeless and I want to die"})
        self.assertEqual(client.get("/api/graph").json()["nodes"], [])
    def test_rebuild_from_existing_sessions_skips_crisis_turns(self):
        sid = client.post("/api/sessions", json={}).json()["id"]
        talk(sid, "My mom and I had an argument and I felt angry")
        client.post(f"/api/sessions/{sid}/send", json={"text": "I feel hopeless and I want to die"})
        db.x("DELETE FROM graph_nodes"); db.x("DELETE FROM graph_edges")
        self.assertEqual(client.post("/api/graph/rebuild").json()["messages"], 1)
        self.assertEqual(labels(client.get("/api/graph").json(), "emotion"), ["Anger"])
    def test_deleting_a_session_removes_its_part_of_the_map(self):
        a = client.post("/api/sessions", json={}).json()["id"]; b = client.post("/api/sessions", json={}).json()["id"]
        talk(a, "I felt jealous"); talk(b, "I felt jealous again")
        client.delete(f"/api/sessions/{a}"); n = client.get("/api/graph").json()["nodes"]; self.assertEqual(n[0]["sessions"], [b])
    def test_node_detail_and_exports(self):
        sid = client.post("/api/sessions", json={"title": "T"}).json()["id"]; talk(sid, "My boss was cruel and I felt hurt")
        d = client.get("/api/graph/node", params={"type": "person", "label": "Boss"}).json()
        self.assertEqual(d["links"][0]["label"], "Hurt"); self.assertEqual(d["links"][0]["relation"], "brings up"); self.assertEqual(d["sessions"][0]["id"], sid)
        self.assertEqual(client.get("/api/graph/node", params={"type": "person", "label": "Nobody"}).status_code, 404)
        self.assertIn("<node", client.get("/api/graph/export/graphml").text); self.assertEqual(len(json.loads(client.get("/api/graph/export/cytoscape").text)["elements"]["nodes"]), 2)
    def test_map_survives_backup_and_old_backups_rebuild_it(self):
        sid = client.post("/api/sessions", json={}).json()["id"]; talk(sid, "My dad left and I felt empty")
        blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/graph").json()["nodes"], [])
        client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(len(client.get("/api/graph").json()["nodes"]), 2)

if __name__ == "__main__": unittest.main()
