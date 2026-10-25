import unittest
from tests.helpers import client as c, reset, db, FakeModel, wait_idle
from sf import remote

HOST = "laptop.tail1234.ts.net"
VIA = {"Host": HOST + ":8443", "X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https", "Tailscale-User-Login": "me@example.com"}

def turn_on(login="me@example.com", passphrase="correct horse battery"):
    r = c.put("/api/remote/config", json={"login": login, "passphrase": passphrase, "enabled": True}); assert r.status_code == 200, r.text

def sign_in(passphrase="correct horse battery", headers=None):
    """The test client talks http, so it would not send a Secure cookie back; carry the cookie by hand like a browser on https."""
    r = c.post("/api/remote/login", json={"passphrase": passphrase}, headers=headers or VIA)
    if r.status_code == 200 and headers is None: VIA["Cookie"] = "sf_remote=" + r.headers["set-cookie"].split("sf_remote=")[1].split(";")[0]
    return r

class Base(unittest.TestCase):
    def setUp(self): reset(); VIA.pop("Cookie", None)

class LocalUseIsUnchanged(Base):
    def test_the_local_window_needs_no_sign_in_even_with_remote_on(self):
        turn_on()
        for host in ("127.0.0.1:8100", "localhost:8100", "[::1]:8100"): self.assertEqual(c.get("/api/status", headers={"Host": host}).status_code, 200, host)
        self.assertEqual(c.get("/api/settings").status_code, 200)
    def test_a_web_page_cannot_reach_the_api_by_rebinding_its_own_name(self):
        self.assertEqual(c.get("/api/settings", headers={"Host": "evil.example.com:8100"}).status_code, 400)
    def test_remote_settings_never_come_back_or_get_written_through_settings(self):
        turn_on(); s = c.get("/api/settings").json()
        self.assertIs(s["remote_hash"], True); self.assertNotIn("remote_sessions", s); self.assertNotIn("remote_log", s)
        c.put("/api/settings", json={"values": {"remote_enabled": False, "remote_hash": "x", "remote_login": "evil@example.com", "remote_host": "evil.ts.net"}})
        self.assertTrue(remote.enabled()); self.assertEqual(db.get_setting("remote_login"), "me@example.com"); self.assertEqual(db.get_setting("remote_host"), "")
    def test_a_backup_neither_carries_nor_changes_remote_access(self):
        import gzip, json
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from tests.helpers import api
        turn_on(); blob = c.post("/api/backup", json={"passphrase": "correct horse"}).content
        data = json.loads(gzip.decompress(AESGCM(api._key("correct horse", blob[5:21])).decrypt(blob[21:33], blob[33:], b"SFBK1")))
        self.assertFalse([k for k in data["settings"] if k.startswith("remote_")])
        c.put("/api/remote/config", json={"login": "changed@example.com"}); c.post("/api/restore", content=blob, headers={"x-passphrase": "correct horse"})
        self.assertEqual(db.get_setting("remote_login"), "changed@example.com"); self.assertTrue(remote.enabled())

class TheFrontDoor(Base):
    def test_off_by_default_even_if_the_proxy_is_running(self):
        r = c.get("/api/status", headers=VIA); self.assertEqual(r.status_code, 403); self.assertIn("turned off", r.json()["detail"])
    def test_cannot_be_turned_on_without_a_passphrase_and_login(self):
        self.assertEqual(c.put("/api/remote/config", json={"enabled": True}).status_code, 400); self.assertEqual(c.put("/api/remote/config", json={"passphrase": "short"}).status_code, 400)
    def test_the_app_shell_loads_without_a_session_but_the_api_does_not(self):
        turn_on(); r = c.get("/api/status", headers=VIA); self.assertEqual(r.status_code, 401); self.assertTrue(r.json()["remote_auth"]); self.assertNotEqual(c.get("/", headers=VIA).status_code, 401)
    def test_wrong_passphrase_is_refused_then_the_right_one_signs_in(self):
        turn_on(); self.assertEqual(sign_in("nope nope nope").status_code, 403)
        r = sign_in(); self.assertEqual(r.status_code, 200); cookie = r.headers["set-cookie"].lower()
        for flag in ("httponly", "secure", "samesite=strict", "max-age=604800"): self.assertIn(flag, cookie)           # seven days
        self.assertEqual(c.get("/api/status", headers=VIA).status_code, 200); self.assertTrue(c.get("/api/remote/session", headers=VIA).json()["signed_in"])
    def test_five_wrong_tries_lock_sign_in_for_a_while(self):
        turn_on()
        for _ in range(5): sign_in("wrong wrong wrong")
        self.assertEqual(sign_in().status_code, 429); remote.clear_failures(); self.assertEqual(sign_in().status_code, 200)
    def test_only_the_allowed_tailscale_account_gets_in(self):
        turn_on(); other = {**VIA, "Tailscale-User-Login": "someone@else.com"}
        self.assertEqual(sign_in(headers=other).status_code, 403); self.assertEqual(c.get("/api/status", headers=other).status_code, 403)
        self.assertEqual(c.get("/api/status", headers={k: v for k, v in other.items() if k != "Tailscale-User-Login"}).status_code, 403)
    def test_only_the_tailscale_host_name_is_accepted(self):
        turn_on(); self.assertEqual(c.get("/api/status", headers={**VIA, "Host": "evil.example.com"}).status_code, 403)
        c.put("/api/remote/config", json={"host": HOST}); self.assertEqual(c.get("/api/status", headers={**VIA, "Host": "other.ts.net"}).status_code, 403)
    def test_cross_site_writes_are_refused_even_with_a_session(self):
        turn_on(); sign_in()
        self.assertEqual(c.post("/api/sessions", json={}, headers={**VIA, "Origin": "https://evil.example.com"}).status_code, 403)
        self.assertEqual(c.post("/api/sessions", json={}, headers={**VIA, "Origin": f"https://{HOST}:8443"}).status_code, 200)
    def test_sign_out_revoke_and_expiry_end_the_session(self):
        turn_on(); sign_in(); self.assertEqual(c.post("/api/remote/logout", headers=VIA).status_code, 200); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)
        VIA.pop("Cookie"); sign_in(); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 200)
        s = db.get_setting("remote_sessions")
        for v in s.values(): v["last"] -= remote.SESSION_SECONDS + 5
        db.set_setting("remote_sessions", s); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)
    def test_secrets_are_stored_hashed(self):
        turn_on(); sign_in(); self.assertNotIn("correct horse", str(db.get_setting("remote_hash"))); self.assertNotIn(VIA["Cookie"].split("=")[1], str(db.get_setting("remote_sessions")))
    def test_api_answers_to_a_phone_are_not_cached(self):
        turn_on(); sign_in(); self.assertEqual(c.get("/api/status", headers=VIA).headers["cache-control"], "no-store")
    def test_turning_it_off_or_changing_the_passphrase_signs_every_phone_out(self):
        turn_on(); sign_in(); c.put("/api/remote/config", json={"passphrase": "another long one"}); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 401)
        VIA.pop("Cookie"); sign_in("another long one"); self.assertEqual(c.get("/api/status", headers=VIA).status_code, 200)
        c.put("/api/remote/config", json={"enabled": False}); self.assertEqual(db.get_setting("remote_sessions"), {})

class WhatAPhoneCanDo(Base):
    """You chose that a signed-in phone can do everything in the app. The few exceptions are the ones that would let a stolen phone lock you out or listen to the room."""
    def test_a_signed_in_phone_uses_the_whole_app(self):
        turn_on(); sign_in()
        sid = c.post("/api/sessions", json={}, headers=VIA).json()["id"]
        with FakeModel("Hello from the laptop. ") as m:
            self.assertEqual(c.post(f"/api/sessions/{sid}/send", json={"text": "hi from my phone"}, headers=VIA).status_code, 200); wait_idle(sid)
        for path in ("/api/status", "/api/settings", "/api/sessions", f"/api/sessions/{sid}", "/api/graph", "/api/dreams", "/api/notes", "/api/insights", "/api/narrative", "/api/mood",
                     "/api/global-memories", "/api/safety/events", "/api/export/markdown", "/api/export/json", "/api/catalog", "/api/models", "/api/tts/status"):
            self.assertEqual(c.get(path, headers=VIA).status_code, 200, path)
        self.assertEqual(c.post("/api/mood", json={"value": 4}, headers=VIA).status_code, 200)
        self.assertEqual(c.put("/api/settings", json={"values": {"default_persona": "companion"}}, headers=VIA).status_code, 200)
        self.assertEqual(c.patch(f"/api/sessions/{sid}", json={"model": "openrouter/openrouter/free"}, headers=VIA).status_code, 200)
        self.assertEqual(c.post("/api/backup", json={"passphrase": "correct horse"}, headers=VIA).status_code, 200)
        self.assertEqual(c.delete(f"/api/sessions/{sid}", headers=VIA).status_code, 200)
        self.assertEqual(c.post("/api/danger/erase", json={"confirm": "erase"}, headers=VIA).status_code, 200)
    def test_managing_remote_access_and_the_laptops_microphone_stay_on_the_laptop(self):
        turn_on(); sign_in()
        for method, path in (("get", "/api/remote/status"), ("get", "/api/remote/tailscale"), ("put", "/api/remote/config"), ("post", "/api/remote/revoke"),
                             ("post", "/api/voice/start"), ("post", "/api/voice/stop"), ("post", "/api/voice/pause"), ("post", "/api/voice/resume"), ("get", "/api/voice/poll"), ("get", "/api/voice/status")):
            r = getattr(c, method)(path, headers=VIA, **({"json": {}} if method in ("put", "post") else {})); self.assertEqual(r.status_code, 403, f"{method} {path}"); self.assertIn("laptop", r.json()["detail"])
        self.assertTrue(remote.enabled())
    def test_a_phone_that_is_not_signed_in_can_do_nothing(self):
        turn_on()
        for method, path in (("get", "/api/sessions"), ("get", "/api/export/json"), ("post", "/api/danger/erase"), ("put", "/api/settings"), ("post", "/api/mood"), ("post", "/api/tts")):
            r = getattr(c, method)(path, headers=VIA, **({"json": {}} if method in ("put", "post") else {})); self.assertEqual(r.status_code, 401, path)
    def test_the_phone_gets_the_crisis_lines_like_anywhere_else(self):
        turn_on(); sign_in(); sid = c.post("/api/sessions", json={}, headers=VIA).json()["id"]
        with FakeModel() as m: r = c.post(f"/api/sessions/{sid}/send", json={"text": "I want to end my life"}, headers=VIA).json()
        self.assertEqual(r["safety"], "crisis"); self.assertEqual(m.calls, []); self.assertTrue(c.get("/api/status", headers=VIA).json()["resources"])

class Pieces(unittest.TestCase):
    def test_host_names(self):
        self.assertEqual(remote.host_of({"host": "Laptop.ts.net:8443"}), "laptop.ts.net"); self.assertEqual(remote.host_of({"host": "[::1]:8100"}), "::1"); self.assertEqual(remote.host_of({}), "")
    def test_passphrase_hash_round_trip(self):
        x = remote.hash_pass("a long passphrase"); self.assertTrue(remote.check_pass("a long passphrase", x)); self.assertFalse(remote.check_pass("another one", x)); self.assertFalse(remote.check_pass("x", "garbage"))

if __name__ == "__main__": unittest.main()
