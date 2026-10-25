import unittest
from unittest import mock
from tests.helpers import client, reset, db, llm, FakeModel, wait_idle
from sf import openrouter

CATALOG = {"data": [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B", "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["tools"], "architecture": {"output_modalities": ["text"]}},
    {"id": "openrouter/free", "name": "Free Models Router", "context_length": 200000, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text"]}},
    {"id": "google/gemma-3-4b-it:free", "name": "Gemma 3 4B", "context_length": 32768, "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000, "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
    {"id": "openrouter/auto", "name": "Auto", "context_length": 2000000, "pricing": {"prompt": "-1", "completion": "-1"}},
    {"id": "google/lyria-preview", "name": "Music", "context_length": 9, "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text", "audio"]}},
    {"id": "nvidia/x-content-safety:free", "name": "Safety", "context_length": 9, "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "missing/pricing", "name": "None"},
]}

class Catalog(unittest.TestCase):
    def setUp(self): reset(); openrouter.reset()
    def test_only_free_text_chat_models_with_the_automatic_one_first(self):
        rows = openrouter.parse(CATALOG)
        self.assertEqual([r["id"] for r in rows], ["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-4b-it:free"])
        self.assertTrue(rows[0]["recommended"]); self.assertEqual(rows[0]["model"], "openrouter/openrouter/free"); self.assertIn("Automatic", rows[0]["name"]); self.assertFalse(rows[1]["recommended"])
    def test_the_endpoint_lists_them_caches_and_needs_no_key(self):
        with mock.patch("sf.openrouter.httpx.get") as get:
            get.return_value = mock.Mock(json=lambda: CATALOG, raise_for_status=lambda: None)
            self.assertEqual(len(client.get("/api/openrouter/models").json()["models"]), 3); client.get("/api/openrouter/models"); self.assertEqual(get.call_count, 1)
            client.get("/api/openrouter/models", params={"refresh": True}); self.assertEqual(get.call_count, 2)
            self.assertNotIn("Authorization", str(get.call_args))          # the list is public: the key is not sent to get it
    def test_a_network_failure_is_a_plain_502(self):
        with mock.patch("sf.openrouter.httpx.get", side_effect=OSError("down")):
            r = client.get("/api/openrouter/models"); self.assertEqual(r.status_code, 502); self.assertIn("OpenRouter", r.json()["detail"])

class Use(unittest.TestCase):
    def setUp(self): reset(); db.set_setting("model", "openrouter/openrouter/free"); db.set_setting("api_key", "sk-or-test")
    def test_the_key_goes_to_openrouter_and_nowhere_near_ollama(self):
        kw = llm._kwargs("openrouter/openrouter/free"); self.assertEqual((kw["model"], kw["api_key"]), ("openrouter/openrouter/free", "sk-or-test")); self.assertNotIn("num_ctx", kw); self.assertNotIn("api_base", kw)
        self.assertNotIn("api_key", llm._kwargs("ollama_chat/x"))
    def test_a_session_uses_the_chosen_model_and_the_test_can_name_another(self):
        seen = []
        old = llm.text; llm.text = lambda messages, model=None, **k: seen.append(model) or "ok"
        try:
            self.assertEqual(client.post("/api/models/test", json={"model": "openrouter/poolside/laguna-s-2.1:free"}).json()["model"], "openrouter/poolside/laguna-s-2.1:free")
            self.assertEqual(client.post("/api/models/test", json={}).json()["model"], "openrouter/openrouter/free")
        finally: llm.text = old
        self.assertEqual(seen, ["openrouter/poolside/laguna-s-2.1:free", "openrouter/openrouter/free"])
        sid = client.post("/api/sessions", json={}).json()["id"]; used = []; olds = llm.stream
        llm.stream = lambda messages, model=None, **k: used.append(model) or iter(["hi "])
        try: client.post(f"/api/sessions/{sid}/send", json={"text": "hello there"}); wait_idle(sid)
        finally: llm.stream = olds
        self.assertEqual(used, ["openrouter/openrouter/free"])
    def test_provider_failures_are_explained_and_never_show_the_key(self):
        cases = [("OpenrouterException - {\"error\":{\"message\":\"No endpoints found matching your data policy (Free model training)\",\"code\":404}}", "openrouter.ai/settings/privacy"),
                 ("OpenrouterException - {\"error\":{\"message\":\"Provider returned error\",\"code\":429}} rate limit", "rate-limiting"),
                 ("401 No auth credentials found sk-or-test", "API key"),
                 ("litellm.NotFoundError: OpenrouterException - {\"error\":{\"message\":\"Provider returned error\",\"code\":404,\"metadata\":{\"raw\":\"Function not found for account 'x'\"}}}", "isn't available to your account"),
                 ("{\"error\":{\"message\":\"thinkingmachines/inkling-small:free is only available on agentic harnesses.\",\"code\":403}}", "coding agents"),
                 ("APIError - {\"error\":{\"message\":\"Something odd happened upstream\",\"code\":500}}", "Something odd happened upstream"), ("402 This model requires more credits", "credits")]
        for raw, want in cases:
            msg = llm.friendly_error(Exception(raw)); self.assertIn(want, msg); self.assertNotIn("sk-or-test", msg)
        def boom(*a, **k): raise Exception("401 invalid key sk-or-test"); yield
        sid = client.post("/api/sessions", json={}).json()["id"]; old = llm.stream; llm.stream = boom
        try: client.post(f"/api/sessions/{sid}/send", json={"text": "hello there"}); wait_idle(sid)
        finally: llm.stream = old
        last = client.get(f"/api/sessions/{sid}").json()["messages"][-1]; self.assertIn("API key", last["content"]); self.assertNotIn("sk-or-test", last["content"])

if __name__ == "__main__": unittest.main()
