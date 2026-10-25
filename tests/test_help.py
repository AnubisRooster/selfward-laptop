import os, re, unittest
from tests.helpers import client as c, reset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class HelpGuide(unittest.TestCase):
    def setUp(self): reset()
    def test_the_guide_is_served_and_is_the_file_in_the_program_folder(self):
        r = c.get("/api/help"); self.assertEqual(r.status_code, 200); self.assertEqual(r.json()["markdown"], open(os.path.join(ROOT, "HELP.md"), encoding="utf-8").read())
    def test_it_covers_install_configuration_and_the_extras(self):
        md = c.get("/api/help").json()["markdown"]; heads = [l[3:] for l in md.splitlines() if l.startswith("## ")]
        for want in ("Install", "First run", "Choosing the model", "Voice", "Open it from your phone", "Updating", "Troubleshooting"): self.assertTrue(any(want in h for h in heads), want)
    def test_every_command_it_tells_you_to_run_points_at_something_real(self):
        md = c.get("/api/help").json()["markdown"]
        for script in set(re.findall(r"scripts/([a-z_]+\.sh)", md)): self.assertTrue(os.path.exists(os.path.join(ROOT, "scripts", script)), script)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "bin", "start_selfward.sh"))); self.assertTrue(os.path.exists(os.path.join(ROOT, "requirements.txt")))
        self.assertIn("tailscale serve --bg --https=8443 127.0.0.1:8100", md)
        from sf import tailscale; self.assertIn(tailscale.SERVE_COMMAND, md)                              # what Settings shows and what the guide says agree
    def test_what_it_says_about_settings_names_things_that_exist(self):
        md = c.get("/api/help").json()["markdown"]
        with open(os.path.join(ROOT, "frontend/src/views/Settings.tsx"), encoding="utf-8") as f: ui = f.read()
        with open(os.path.join(ROOT, "frontend/src/views/RemoteSettings.tsx"), encoding="utf-8") as f: ui += f.read()
        for label in ("Test it", "Show free models", "Remote access (phone)", "Your guides", "Privacy & lock", "Your data", "What Selfward remembers", "Allow my phone to connect", "Keep this laptop awake"):
            self.assertIn(label, ui, label)
    def test_a_signed_in_phone_can_read_it_and_a_stranger_cannot(self):
        from tests.test_remote import VIA, turn_on, sign_in
        VIA.pop("Cookie", None); turn_on(); self.assertEqual(c.get("/api/help", headers=VIA).status_code, 401); sign_in(); self.assertEqual(c.get("/api/help", headers=VIA).status_code, 200)

if __name__ == "__main__": unittest.main()
