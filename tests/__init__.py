"""Point Selfward at a throwaway data folder BEFORE anything can import `sf.db`.

`sf.db` opens the journal the moment it is imported, using SELFWARD_DATA. Importing `tests` runs this
file first, whatever order test modules import things in, so a test can never touch your real journal.
"""
import atexit, os, shutil, tempfile

DATA = tempfile.mkdtemp(prefix="selfward-test-")
os.environ["SELFWARD_DATA"] = DATA
os.environ["OLLAMA_API_BASE"] = "http://127.0.0.1:9"
atexit.register(shutil.rmtree, DATA, ignore_errors=True)

# Remote access holds a "don't sleep" lock and asks Tailscale about itself; tests must never touch the real ones.
os.environ["SELFWARD_INHIBIT_CMD"] = "true"
os.environ["SELFWARD_TAILSCALE_CMD"] = "/nonexistent/tailscale"
