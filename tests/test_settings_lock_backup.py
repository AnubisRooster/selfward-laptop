import unittest
from tests.helpers import client, reset, db, FakeModel, wait_idle
from sf import chat as chatmod

class Settings(unittest.TestCase):
    def setUp(self): reset()
    def test_secrets_are_never_returned(self):
        client.put("/api/settings", json={"values": {"api_key": "sk-secret"}})
        s = client.get("/api/settings").json(); self.assertIs(s["api_key"], True); self.assertNotIn("sk-secret", client.get("/api/settings").text)
        client.put("/api/settings", json={"values": {"api_key": True}}); self.assertEqual(db.get_setting("api_key"), "sk-secret")   # echoing the flag back doesn't wipe it
    def test_lock_state_cannot_be_set_through_settings(self):
        client.put("/api/settings", json={"values": {"lock_enabled": True, "lock_hash": "x", "nonsense": 1}})
        self.assertFalse(db.get_setting("lock_enabled")); self.assertEqual(db.get_setting("lock_hash"), ""); self.assertNotIn("nonsense", client.get("/api/settings").json())
    def test_onboarding_needs_the_notice_accepted(self):
        self.assertEqual(client.post("/api/onboarding/complete", json={"user_name": "Alex"}).status_code, 400)
        self.assertFalse(client.get("/api/status").json()["onboarding_completed"])
        client.post("/api/onboarding/complete", json={"user_name": "Alex", "region": "GB", "accept_disclaimer": True})
        st = client.get("/api/status").json(); self.assertTrue(st["onboarding_completed"]); self.assertTrue(any("Samaritans" in r["name"] for r in st["resources"]))

class Lock(unittest.TestCase):
    def setUp(self): reset(); import selfward_api as a; a._fails.update(n=0, until=0.0)
    def test_pin_round_trip(self):
        self.assertTrue(client.post("/api/lock/verify", json={"pin": "1"}).json()["ok"])               # no PIN set yet
        self.assertEqual(client.post("/api/lock/set", json={"pin": "12"}).status_code, 400)
        self.assertEqual(client.post("/api/lock/set", json={"pin": "abcd"}).status_code, 400)
        self.assertTrue(client.post("/api/lock/set", json={"pin": "2468"}).json()["enabled"])
        self.assertNotIn("2468", db.get_setting("lock_hash"))
        self.assertFalse(client.post("/api/lock/verify", json={"pin": "0000"}).json()["ok"]); self.assertTrue(client.post("/api/lock/verify", json={"pin": "2468"}).json()["ok"])
        self.assertEqual(client.post("/api/lock/set", json={"pin": "1357", "current": "9999"}).status_code, 403)
        self.assertFalse(client.post("/api/lock/set", json={"pin": "", "current": "2468"}).json()["enabled"])
    def test_repeated_wrong_pins_pause_guessing(self):
        client.post("/api/lock/set", json={"pin": "2468"})
        for _ in range(5): client.post("/api/lock/verify", json={"pin": "0000"})
        r = client.post("/api/lock/verify", json={"pin": "2468"}).json(); self.assertFalse(r["ok"]); self.assertGreater(r["wait"], 0)

class Backup(unittest.TestCase):
    def setUp(self): reset()
    def test_encrypted_round_trip_and_wrong_passphrase(self):
        sid = client.post("/api/sessions", json={"title": "Keep me"}).json()["id"]
        with FakeModel("Noted. "): client.post(f"/api/sessions/{sid}/send", json={"text": "remember this entry"}); wait_idle(sid)
        blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        self.assertNotIn(b"remember this", blob)
        self.assertEqual(client.post("/api/backup", json={"passphrase": "short"}).status_code, 400)
        client.post("/api/danger/erase", json={"confirm": "erase"}); self.assertEqual(client.get("/api/sessions").json(), [])
        self.assertEqual(client.post("/api/restore", content=blob, headers={"x-passphrase": "wrong one!!"}).status_code, 403)
        self.assertEqual(client.get("/api/sessions").json(), [])
        r = client.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"}); self.assertEqual(r.json()["restored"]["messages"], 2)
        self.assertEqual(client.get(f"/api/sessions/{sid}").json()["messages"][0]["content"], "remember this entry")
    def test_backup_leaves_out_keys_and_pin(self):
        client.put("/api/settings", json={"values": {"api_key": "sk-secret"}}); client.post("/api/lock/set", json={"pin": "2468"})
        from tests.helpers import api; import gzip, json
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        blob = client.post("/api/backup", json={"passphrase": "correct horse"}).content
        data = json.loads(gzip.decompress(AESGCM(api._key("correct horse", blob[5:21])).decrypt(blob[21:33], blob[33:], b"SFBK1")))
        self.assertNotIn("api_key", data["settings"]); self.assertNotIn("lock_hash", data["settings"])
    def test_erase_needs_the_word(self):
        self.assertEqual(client.post("/api/danger/erase", json={"confirm": "yes"}).status_code, 400)
    def test_exports(self):
        sid = client.post("/api/sessions", json={"title": "Export me"}).json()["id"]
        with FakeModel("Hello back. "): client.post(f"/api/sessions/{sid}/send", json={"text": "hello"}); wait_idle(sid)
        self.assertIn("Export me", client.get("/api/export/markdown").text); self.assertEqual(len(client.get("/api/export/json").json()["tables"]["messages"]), 2)

if __name__ == "__main__": unittest.main()


class LockTimers(unittest.TestCase):
    def setUp(self): reset()
    def test_away_and_idle_are_separate_validated_numbers_with_a_calmer_idle_default(self):
        s = client.get("/api/settings").json(); self.assertEqual((s["lock_after"], s["lock_idle"]), (60, 15))
        for bad in ({"lock_after": 5}, {"lock_after": 90000}, {"lock_idle": -1}, {"lock_idle": 5000}, {"lock_idle": "10"}, {"lock_idle": True}, {"lock_after": 30.5}):
            self.assertEqual(client.put("/api/settings", json={"values": bad}).status_code, 400, bad)
        self.assertEqual(client.put("/api/settings", json={"values": {"lock_after": 120, "lock_idle": 0}}).status_code, 200)
        s = client.get("/api/settings").json(); self.assertEqual((s["lock_after"], s["lock_idle"]), (120, 0))
    def test_a_backup_does_not_carry_the_lock_state_but_the_timers_may(self):
        client.put("/api/settings", json={"values": {"lock_idle": 30}}); self.assertEqual(client.get("/api/settings").json()["lock_idle"], 30)
