import os, tempfile, unittest
from tests.helpers import client as c, reset
from sf import awake, tailscale

FAKE_TS = '''#!/bin/sh
case "$1" in
  status) echo '{"BackendState":"Running","Self":{"DNSName":"laptop.tail1234.ts.net.","UserID":42},"User":{"42":{"LoginName":"me@example.com"}}}' ;;
  serve) printf "%s\\n" "$SERVE_TEXT" ;;
esac
'''
ON = {"login": "me@example.com", "passphrase": "correct horse battery", "enabled": True}

class Awake(unittest.TestCase):
    def setUp(self): reset(); awake.release(); os.environ["SELFWARD_INHIBIT_CMD"] = "sleep 300"
    def tearDown(self): awake.release(); os.environ["SELFWARD_INHIBIT_CMD"] = "true"
    def test_held_only_while_remote_is_on(self):
        self.assertFalse(awake.sync()); c.put("/api/remote/config", json=ON); self.assertTrue(awake.running()); self.assertTrue(c.get("/api/remote/status").json()["awake_held"])
        c.put("/api/remote/config", json={"enabled": False}); self.assertFalse(awake.running())
    def test_can_be_switched_off_on_its_own(self):
        c.put("/api/remote/config", json=ON); c.put("/api/remote/config", json={"keep_awake": False}); self.assertFalse(awake.running()); self.assertFalse(c.get("/api/remote/status").json()["keep_awake"])
        c.put("/api/remote/config", json={"keep_awake": True}); self.assertTrue(awake.running())
    def test_a_missing_inhibitor_is_not_an_error(self):
        os.environ["SELFWARD_INHIBIT_CMD"] = "/nonexistent/inhibit"; self.assertFalse(awake.hold())

class Tailscale(unittest.TestCase):
    def setUp(self): reset()
    def tearDown(self): os.environ["SELFWARD_TAILSCALE_CMD"] = "/nonexistent/tailscale"; os.environ.pop("SERVE_TEXT", None)
    def _fake(self, serve_text):
        f = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False); f.write(FAKE_TS); f.close(); os.chmod(f.name, 0o755)
        os.environ["SELFWARD_TAILSCALE_CMD"] = f.name; os.environ["SERVE_TEXT"] = serve_text; self.addCleanup(os.unlink, f.name)
    def test_not_installed(self):
        self.assertEqual(c.get("/api/remote/tailscale").json(), {"installed": False})
    def test_it_uses_its_own_port_so_smartward_keeps_443(self):
        self.assertIn("--https=8443", tailscale.SERVE_COMMAND); self.assertIn("127.0.0.1:8100", tailscale.SERVE_COMMAND)
    def test_reads_the_address_login_and_whether_it_is_published(self):
        self._fake("https://laptop.tail1234.ts.net:8443 (tailnet only)\n|-- / proxy http://127.0.0.1:8100")
        d = c.get("/api/remote/tailscale").json()
        self.assertEqual((d["installed"], d["state"], d["dns_name"], d["login"], d["https_url"], d["published"]), (True, "Running", "laptop.tail1234.ts.net", "me@example.com", "https://laptop.tail1234.ts.net:8443", True))
    def test_smartwards_publication_does_not_count_as_ours(self):
        self._fake("https://laptop.tail1234.ts.net (tailnet only)\n|-- / proxy http://127.0.0.1:8000")
        self.assertFalse(c.get("/api/remote/tailscale").json()["published"])

if __name__ == "__main__": unittest.main()
