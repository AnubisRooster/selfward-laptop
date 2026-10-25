import os, time, unittest
from tests.helpers import client, reset, db
from sf import mood

os.environ["TZ"] = "UTC"; time.tzset()
DAY = 86400
T0 = 1_700_000_000 - (1_700_000_000 % DAY) + 12 * 3600          # noon UTC on a fixed day

class Mood(unittest.TestCase):
    def setUp(self): reset()
    def test_a_check_in_is_saved_with_its_note(self):
        r = client.post("/api/mood", json={"value": 4, "note": "  Good   walk today "}).json(); self.assertIsNone(r["support"])
        v = client.get("/api/mood").json(); e = v["entries"][0]; self.assertEqual((e["id"], e["value"], e["note"]), (r["id"], 4, "Good walk today")); self.assertEqual(v["last"]["value"], 4); self.assertEqual(v["labels"]["1"], "Very low")
    def test_only_whole_numbers_one_to_five(self):
        for bad in (0, 6, -1, 3.5, "4", None, True): self.assertEqual(client.post("/api/mood", json={"value": bad}).status_code, 400, bad)
        self.assertEqual(client.get("/api/mood").json()["entries"], [])
    def test_notes_are_trimmed_not_refused(self):
        client.post("/api/mood", json={"value": 3, "note": "x" * 900}); self.assertEqual(len(client.get("/api/mood").json()["entries"][0]["note"]), 500)
    def test_daily_averages_group_by_local_day_and_agree_with_the_numbers(self):
        for ts, v in ((T0, 2), (T0 + 3600, 4), (T0 + DAY, 5), (T0 + 3 * DAY, 1)): mood.log(v, "", ts)
        d = mood.daily_averages(db.q("SELECT value,ts FROM moods ORDER BY ts")); self.assertEqual([(x[0][5:], x[1], x[2]) for x in d][:2], [(time.strftime("%m-%d", time.gmtime(T0)), 3.0, 2), (time.strftime("%m-%d", time.gmtime(T0 + DAY)), 5.0, 1)])
        v = mood.view(30, now=T0 + 4 * DAY); self.assertEqual([x["average"] for x in v["daily"]], [3.0, 5.0, 1.0]); self.assertEqual(v["stats"]["count"], 4); self.assertEqual(v["stats"]["average"], 3.0)
        self.assertEqual((v["stats"]["best_day"], v["stats"]["lowest_day"]), (v["daily"][1]["day"], v["daily"][2]["day"])); self.assertEqual(v["stats"]["days_logged"], 3)
    def test_late_night_belongs_to_that_calendar_day(self):
        mood.log(2, "", T0 - 12 * 3600 + 60); mood.log(4, "", T0 - 12 * 3600 + 23 * 3600 + 3000)          # 00:01 and 23:50 the same day
        self.assertEqual(len(mood.view(30, now=T0)["daily"]), 1)
    def test_the_range_limits_what_is_shown_but_not_what_is_kept(self):
        mood.log(3, "old", T0 - 40 * DAY); mood.log(4, "new", T0)
        self.assertEqual([e["note"] for e in mood.view(30, now=T0)["entries"]], ["new"]); self.assertEqual({e["note"] for e in mood.view(90, now=T0)["entries"]}, {"old", "new"})
        self.assertEqual(mood.view(0, now=T0)["days"], 1); self.assertEqual(mood.view(9999, now=T0)["days"], 365)
    def test_empty_journal_has_no_averages_to_invent(self):
        v = client.get("/api/mood").json(); self.assertEqual((v["daily"], v["entries"], v["last"], v["stats"]["average"], v["stats"]["best_day"]), ([], [], None, None, None))
    def test_support_wording_in_a_note_gets_the_crisis_lines_and_is_logged_not_sent_anywhere(self):
        r = client.post("/api/mood", json={"value": 1, "note": "I want to end my life"}).json(); self.assertIn("988", r["support"])
        self.assertEqual(client.get("/api/safety/events").json()[0]["type"], "crisis_keyword"); self.assertEqual(client.get("/api/mood").json()["entries"][0]["value"], 1)       # still saved
        client.put("/api/settings", json={"values": {"region": "GB"}}); self.assertIn("Samaritans", client.post("/api/mood", json={"value": 1, "note": "kill myself"}).json()["support"])
        self.assertIsNone(client.post("/api/mood", json={"value": 1, "note": "A rough, tired day"}).json()["support"])                    # low alone is not an alarm
    def test_delete_backup_and_erase(self):
        a = client.post("/api/mood", json={"value": 2, "note": "keep"}).json()["id"]; b = client.post("/api/mood", json={"value": 5}).json()["id"]; client.delete(f"/api/mood/{b}")
        self.assertEqual([e["id"] for e in client.get("/api/mood").json()["entries"]], [a])
        blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content; client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/mood").json()["entries"], [])
        client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(client.get("/api/mood").json()["entries"][0]["note"], "keep")
        self.assertEqual(len(client.get("/api/export/json").json()["tables"]["moods"]), 1)
    def test_mood_stays_out_of_the_models_reach(self):
        from tests.helpers import FakeModel, wait_idle
        client.post("/api/mood", json={"value": 1, "note": "secret worry about the lake house"})
        sid = client.post("/api/sessions", json={}).json()["id"]
        with FakeModel() as m: client.post(f"/api/sessions/{sid}/send", json={"text": "tell me about the lake house"}); wait_idle(sid)
        self.assertNotIn("secret worry", str(m.calls))

if __name__ == "__main__": unittest.main()
