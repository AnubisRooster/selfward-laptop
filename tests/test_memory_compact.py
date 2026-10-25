import unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import chat, compact, llm, memory

def new(): return client.post("/api/sessions", json={}).json()["id"]
def talk(sid, text, reply="I hear you. "):
    with FakeModel(reply) as m: client.post(f"/api/sessions/{sid}/send", json={"text": text}); wait_idle(sid)
    return m
def system_text(m, call=0): return "\n".join(x["content"] for x in m.calls[call] if x["role"] == "system")

class GlobalMemory(unittest.TestCase):
    def setUp(self): reset()
    def test_weight_tiers(self):
        w = memory.weight
        self.assertEqual(w("I went through trauma growing up")[1], "insight"); self.assertGreaterEqual(w("I went through trauma growing up")[0], 0.9)
        self.assertEqual(w("My mother and I, I realized something")[1], "semantic")
        self.assertEqual(w("My mother is far away and I feel lonely and numb")[0], 0.55)
        self.assertEqual(w("anxious, lonely and stuck again")[1], "episodic")
        self.assertIsNone(w("I had a nice day at the park")); self.assertIsNone(w("my mother called"))        # one mild-to-moderate signal is not enough
    def test_words_are_whole_and_only_the_clients_words_count(self):
        self.assertIsNone(memory.weight("I enjoy painting and reshaping clay and hurting no one-ish"))
        self.assertIsNone(memory.weight("fine day", ))
        sid = new(); talk(sid, "I went for a walk", reply="That sounds like trauma, abuse and suicide are on your mind")
        self.assertEqual(client.get("/api/global-memories").json(), [])
    def test_a_weighty_exchange_is_kept_for_good_and_listed(self):
        sid = new(); talk(sid, "Growing up my dad hit me and I have never told anyone")
        g = client.get("/api/global-memories").json(); self.assertEqual(len(g), 1); self.assertEqual(g[0]["kind"], "insight"); self.assertEqual(g[0]["session_id"], sid)
        self.assertIn("never told", g[0]["content"]); self.assertNotIn("vec", g[0]); self.assertEqual(g[0]["manual"], 0)
    def test_it_is_recalled_in_another_session_under_its_own_heading_and_not_twice(self):
        a = new(); talk(a, "Growing up my dad hit me and I have never told anyone about the childhood fear")
        b = new(); m = talk(b, "I keep thinking about my dad and the childhood fear again")
        s = system_text(m); self.assertIn("Things that have mattered to this person across sessions", s)
        self.assertEqual(s.count("never told anyone"), 1)
    def test_not_recalled_in_the_session_it_came_from(self):
        a = new(); talk(a, "Growing up my dad hit me and I have never told anyone about the childhood fear")
        m = talk(a, "the childhood fear and my dad again"); self.assertNotIn("across sessions", system_text(m))
    def test_unrelated_chat_does_not_get_old_memories(self):
        a = new(); talk(a, "Growing up my dad hit me and I have never told anyone about the childhood fear")
        b = new(); m = talk(b, "what should I cook for dinner tonight, maybe pasta"); self.assertNotIn("across sessions", system_text(m))
    def test_switching_it_off_stops_keeping_and_recalling_but_keeps_what_exists(self):
        a = new(); talk(a, "Growing up my dad hit me and I have never told anyone about the childhood fear")
        client.put("/api/settings", json={"values": {"remember_across_sessions": False}})
        b = new(); m = talk(b, "my dad and the childhood fear, and trauma too"); self.assertNotIn("across sessions", system_text(m)); self.assertEqual(len(client.get("/api/global-memories").json()), 1)
        client.put("/api/settings", json={"values": {"remember_across_sessions": True}}); c = new(); m = talk(c, "my dad and the childhood fear"); self.assertIn("across sessions", system_text(m))
    def test_add_by_hand_delete_and_session_delete(self):
        i = client.post("/api/global-memories", json={"content": "  My sister Ana is my anchor  "}).json()["id"]
        g = client.get("/api/global-memories").json()[0]; self.assertEqual((g["content"], g["manual"], g["session_id"]), ("My sister Ana is my anchor", 1, None))
        self.assertEqual(client.post("/api/global-memories", json={"content": " "}).status_code, 400)
        a = new(); talk(a, "Growing up my dad hit me and I have never told anyone"); client.delete(f"/api/sessions/{a}")
        self.assertEqual([x["id"] for x in client.get("/api/global-memories").json()], [i])           # the session's memory went with it, yours stayed
        client.delete(f"/api/global-memories/{i}"); self.assertEqual(client.get("/api/global-memories").json(), [])
    def test_backup_and_erase_cover_it(self):
        client.post("/api/global-memories", json={"content": "Remember the lake house"}); blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/global-memories").json(), [])
        client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(client.get("/api/global-memories").json()[0]["content"], "Remember the lake house")

class Window(unittest.TestCase):
    def setUp(self): reset()
    def test_budget_leaves_room_and_never_collapses(self):
        self.assertEqual(compact.history_budget(8192, "s" * 4000, "", "hello"), int(8192 * 0.6))
        self.assertLess(compact.history_budget(2048, "s" * 4000, "m" * 800, "u" * 400), 1000); self.assertEqual(compact.history_budget(2048, "s" * 20000, "", ""), 256)
    def test_the_window_setting_reaches_ollama_and_is_validated(self):
        self.assertEqual(llm._kwargs("ollama_chat/x")["num_ctx"], 8192); self.assertNotIn("num_ctx", llm._kwargs("openrouter/x"))
        self.assertEqual(client.put("/api/settings", json={"values": {"context_tokens": 100}}).status_code, 400)
        self.assertEqual(client.put("/api/settings", json={"values": {"context_tokens": "lots"}}).status_code, 400)
        client.put("/api/settings", json={"values": {"context_tokens": 4096}}); self.assertEqual(llm._kwargs("ollama_chat/x")["num_ctx"], 4096)

    def _long_chat(self, n=14, size=1200):
        sid = new()
        for i in range(n):
            db.x("INSERT INTO messages(session_id,role,content,ts) VALUES(?,?,?,?)", (sid, "user", f"U{i} " + ("my sister named Ana lives far away " if i == 0 else "") + "reflection " * (size // 11), db.now()))
            db.x("INSERT INTO messages(session_id,role,content,ts) VALUES(?,?,?,?)", (sid, "assistant", f"A{i} " + "reflection " * (size // 11), db.now()))
        return sid
    def test_a_long_chat_is_trimmed_at_once_then_recapped_after_the_answer_and_the_recap_is_used_next(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}})
        sid = self._long_chat(); old = compact.summarize; calls = []
        def fake(block, model=None):
            calls.append(block); self.assertNotEqual(client.get(f"/api/sessions/{sid}").json()["messages"][-1]["content"], "")      # the answer is already there
            return "Client reflection recap: the guide heard reflection after reflection, and a sister named Ana."
        compact.summarize = fake
        try:
            m = talk(sid, "one more thing")
            sent = m.calls[0]; self.assertLess(sum(compact.tokens(x["content"]) for x in sent), 2048 * 0.85); self.assertNotIn("recap", system_text(m))
            self.assertEqual(sent[0]["role"], "system"); self.assertEqual(sent[-1]["content"], "one more thing"); self.assertEqual(len(calls), 1)
            row = db.q("SELECT summary, summary_covered FROM sessions WHERE id=?", (sid,), one=True); self.assertIn("Ana", row["summary"]); self.assertGreater(row["summary_covered"], 10)
            m = talk(sid, "and another")
            self.assertIn("Ongoing conversation recap", system_text(m)); self.assertIn("sister named Ana", system_text(m)); self.assertLess(sum(compact.tokens(x["content"]) for x in m.calls[0]), 2048 * 0.85)
            kept = [x["content"][:3] for x in m.calls[0] if x["role"] != "system"]; self.assertNotIn("U0 ", kept); self.assertEqual(kept[-2], "I h")      # newest turns word for word
        finally: compact.summarize = old
    def test_the_recap_is_reused_and_only_new_material_is_folded_in(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); sid = self._long_chat(); old = compact.summarize; blocks = []
        compact.summarize = lambda block, model=None: blocks.append(block) or "Recap one: the client shared reflection after reflection with the guide."
        try:
            talk(sid, "first"); talk(sid, "second")            # the second turn finds too little new to bother the model again
            self.assertEqual(len(blocks), 1)
            for i in range(8): db.x("INSERT INTO messages(session_id,role,content,ts) VALUES(?,?,?,?)", (sid, "user" if i % 2 == 0 else "assistant", f"N{i} " + "reflection " * 110, db.now()))
            talk(sid, "third")
        finally: compact.summarize = old
        self.assertEqual(len(blocks), 2); self.assertTrue(blocks[1].startswith("Earlier summary:\nRecap one:")); self.assertNotIn("U0 ", blocks[1])
    def test_if_the_summariser_fails_the_chat_still_answers_within_the_window(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); sid = self._long_chat(); old = compact.summarize
        def boom(*a, **k): raise ConnectionError("down")
        compact.summarize = boom
        try: m = talk(sid, "still there?")
        finally: compact.summarize = old
        self.assertLess(sum(compact.tokens(x["content"]) for x in m.calls[0]), 2048 * 0.85); self.assertNotIn("recap", system_text(m)); self.assertEqual(last_content(sid), "I hear you.")
    def test_a_recap_that_is_not_about_the_chat_is_not_kept(self):
        block = "Client: my sister Ana moved to Lisbon and I miss her\nGuide: that sounds hard, what do you miss most about her"
        self.assertTrue(compact.plausible("The client misses their sister Ana, who moved to Lisbon, and the guide asked what they miss about her.", block))
        self.assertFalse(compact.plausible("It seems like there's been a misunderstanding. The conversation doesn't make sense.", block))
        self.assertFalse(compact.plausible("I'm happy to help you explore pottery classes and what you hope to get out of them.", block))
        self.assertFalse(compact.plausible("Short.", block))
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); sid = self._long_chat(); old = compact.summarize
        compact.summarize = lambda *a, **k: "It seems like there's been a misunderstanding about the conversation provided to me here."
        try: m = talk(sid, "go on")
        finally: compact.summarize = old
        self.assertNotIn("recap", system_text(m)); self.assertEqual(db.q("SELECT summary FROM sessions WHERE id=?", (sid,), one=True)["summary"], "")
    def test_exchanges_that_fell_out_of_the_window_are_brought_back_when_they_bear_on_the_message(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); sid = self._long_chat()
        first = db.q("SELECT ts FROM messages WHERE session_id=? ORDER BY id LIMIT 1", (sid,), one=True)["ts"]
        db.x("INSERT INTO memories(session_id,kind,content,ts) VALUES(?,?,?,?)", (sid, "exchange", "The client said: my sister named Ana lives far away in Lisbon\nYou replied: That sounds lonely.", first))
        last = db.q("SELECT ts FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 1", (sid,), one=True)["ts"]
        db.x("INSERT INTO memories(session_id,kind,content,ts) VALUES(?,?,?,?)", (sid, "exchange", "The client said: my sister named Ana lives far away, recent\nYou replied: ok", last))
        old = compact.summarize; compact.summarize = lambda *a, **k: "nothing useful"
        try: m = talk(sid, "where does my sister named Ana live far away")
        finally: compact.summarize = old
        s = system_text(m); self.assertIn("Earlier in this same conversation", s); self.assertIn("Lisbon", s); self.assertNotIn("recent\nYou replied", s)      # only exchanges older than what is still shown
        self.assertLess(sum(compact.tokens(x["content"]) for x in m.calls[0]), 2048 * 0.85)
    def test_a_short_chat_does_not_repeat_itself_from_memory(self):
        sid = new(); talk(sid, "my sister named Ana lives far away in Lisbon"); m = talk(sid, "tell me about my sister named Ana far away")
        self.assertNotIn("Earlier in this same conversation", system_text(m))
    def test_short_chats_are_untouched(self):
        sid = new(); talk(sid, "hi"); old = compact.summarize; compact.summarize = lambda *a, **k: self.fail("no summary needed")
        try: m = talk(sid, "hello again")
        finally: compact.summarize = old
        self.assertNotIn("recap", system_text(m))
    def test_a_huge_single_message_still_fits_by_shedding_memories_and_history(self):
        client.put("/api/settings", json={"values": {"context_tokens": 2048}}); sid = self._long_chat(4, 800)
        old = compact.summarize; compact.summarize = lambda *a, **k: "Recap: the client shared reflection after reflection with the guide."
        try: m = talk(sid, "w " * 3000)                               # about 1,500 tokens on its own
        finally: compact.summarize = old
        self.assertEqual(m.calls[0][0]["role"], "system"); self.assertEqual(len([x for x in m.calls[0] if x["role"] != "system"]), 1)

def last_content(sid): return client.get(f"/api/sessions/{sid}").json()["messages"][-1]["content"].strip()

if __name__ == "__main__": unittest.main()
