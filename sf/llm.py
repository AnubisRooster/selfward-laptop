"""LLM + embedding access (Ollama by default; any litellm model id in the `model` setting)."""
import json, math, re, struct
import httpx
from . import db

def is_local(model): return model.startswith("ollama")

def context_tokens():
    try: return max(2048, int(db.get_setting("context_tokens") or 8192))
    except (TypeError, ValueError): return 8192

def _kwargs(model):
    kw = {"model": model}
    # Ollama's own default window is small (often 4,096 tokens) and it silently cuts the START of a long prompt, which is where the persona and its rules are.
    if is_local(model): kw["api_base"] = db.get_setting("ollama_base"); kw["num_ctx"] = context_tokens()
    elif db.get_setting("api_key"): kw["api_key"] = db.get_setting("api_key")
    return kw

def current_model(session=None):
    return (session or {}).get("model") or db.get_setting("model")

def text(messages, model=None, temperature=0.3, timeout=300):
    from litellm import completion
    model = model or db.get_setting("model")
    resp = completion(messages=messages, temperature=temperature, timeout=timeout, **_kwargs(model))
    return (resp.choices[0].message.content or "").strip()

def stream(messages, model=None, temperature=0.6):
    from litellm import completion
    model = model or db.get_setting("model")
    for part in completion(messages=messages, stream=True, temperature=temperature, **_kwargs(model)):
        d = part.choices[0].delta
        if getattr(d, "content", None): yield d.content

def friendly_error(e):
    """A short, honest reason in plain words (never the whole traceback, never the API key)."""
    msg = str(e); key = db.get_setting("api_key")
    if key: msg = msg.replace(key, "•••")
    low = msg.lower()
    if "data policy" in low or "no endpoints found" in low:
        return "OpenRouter has no free provider that matches your privacy settings. In your OpenRouter account (openrouter.ai/settings/privacy) allow free models that may use your prompts, or pick a different model."
    if "agentic harness" in low:
        return "This free model only works inside coding agents, not in chat. Pick another one (the Automatic one is a safe choice)."
    if "notfounderror" in low or "not found for account" in low:
        return "OpenRouter says this model isn't available to your account right now. Pick another free model (the Automatic one is a safe choice)."
    if "credits" in low or "402" in low:
        return "OpenRouter says this model needs credits. Choose a free model (ending in :free) or add credits to your account."
    if "connection" in low or "connect" in low and "refused" in low:
        return "I couldn't reach the model. If you use Ollama, make sure it is running (`ollama serve`)."
    if "not found" in low and "model" in low:
        return "That model isn't installed. Pick another in Settings, or run `ollama pull` for it."
    if "api key" in low or "auth" in low or "401" in low:
        return "The provider didn't accept the API key. Check it in Settings."
    if "rate" in low and "limit" in low or "429" in low:
        return "The provider is rate-limiting requests. Try again in a moment."
    if "context" in low and ("length" in low or "window" in low):
        return "This conversation has grown too long for the model's context window. Start a new session or choose a model with a larger context."
    inner = re.search(r'"message":\s*"([^"]{4,200})"', msg)                    # the provider's own sentence, not a stack of wrappers
    last = inner.group(1) if inner else (msg.strip().splitlines()[-1] if msg.strip() else type(e).__name__)
    return "I couldn't get an answer just now. " + last[:200]

def json_from(txt):
    """Pull the first JSON object/array out of an LLM reply (models wrap it in prose/fences)."""
    if not txt: return None
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M)
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = txt.find(open_c), txt.rfind(close_c)
        if s != -1 and e > s:
            try: return json.loads(txt[s:e + 1])
            except Exception: continue
    return None

def embed(texts):
    """Unit-length vectors from the local embedding model, or None when it isn't available."""
    if not texts: return []
    try:
        r = httpx.post(db.get_setting("ollama_base").rstrip("/") + "/api/embed",
                       json={"model": db.get_setting("embed_model"), "input": [t[:2000] for t in texts]}, timeout=120)
        r.raise_for_status()
        out = []
        for v in r.json()["embeddings"]:
            n = math.sqrt(sum(a * a for a in v)) or 1.0
            out.append([a / n for a in v])
        return out
    except Exception:
        return None

def pack(v): return struct.pack(f"{len(v)}f", *v)
def unpack(b): return list(struct.unpack(f"{len(b)//4}f", b)) if b else None
