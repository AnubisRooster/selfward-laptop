"""Who is talking: the three personas, and the system prompt each one gets."""
from . import db
from .prompts import (MODALITY_PROMPTS, COMPANION_PROMPT, SPIRITUAL_PROMPT, COMPANION_PERSONALITY, COMPANION_GENDER, SPIRITUAL_TRADITION)

KINDS = {
    "therapist": {"label": "AI Reflection Guide", "default_name": "", "blurb": "A reflective guide that follows a therapeutic approach you choose."},
    "companion": {"label": "Companion", "default_name": "Kai", "blurb": "A warm, chatty friend who wants to know you, encourage you, and grow with you across sessions."},
    "spiritual": {"label": "Spiritual Advisor", "default_name": "Sage", "blurb": "A wise, non-denominational guide drawing on philosophy and wisdom traditions to help you find meaning and peace."},
}

def resolve(kind):
    kind = kind if kind in KINDS else "therapist"
    name = (db.get_setting(kind + "_name") or "").strip() or KINDS[kind]["default_name"]
    if kind == "companion":
        traits = "\n".join(x for x in (COMPANION_PERSONALITY.get(db.get_setting("companion_personality")) or COMPANION_PERSONALITY["warm"],
                                       COMPANION_GENDER.get(db.get_setting("companion_gender"), "")) if x)
    elif kind == "spiritual":
        traits = SPIRITUAL_TRADITION.get(db.get_setting("spiritual_tradition")) or SPIRITUAL_TRADITION["interfaith"]
    else: traits = ""
    return {"kind": kind, "name": name, "display": name or KINDS[kind]["label"], "traits": traits}

def profile_context():
    s = db.all_settings(); lines = []
    if s["user_name"]:
        line = f"The client's name is {s['user_name']}."
        if s["user_pronouns"]: line += f" Pronouns: {s['user_pronouns']}."
        if s["user_age"]: line += f" Age: {s['user_age']}."
        lines.append(line)
    if s["intake_concerns"]: lines.append(f"Presenting concerns: {s['intake_concerns']}")
    if s["intake_history"]: lines.append(f"Therapy background: {s['intake_history']}")
    if s["intake_goals"]: lines.append(f"Goals: {s['intake_goals']}")
    return ("Client context (from intake):\n" + "\n".join(lines)) if lines else ""

def system_prompt(persona, modality, custom=""):
    if persona["kind"] == "companion":
        prompt = COMPANION_PROMPT.replace("%NAME%", persona["name"] or "Kai").replace("%TRAITS%", persona["traits"])
    elif persona["kind"] == "spiritual":
        prompt = SPIRITUAL_PROMPT.replace("%NAME%", persona["name"] or "Sage").replace("%TRADITION%", persona["traits"])
    else:
        base = MODALITY_PROMPTS.get(modality) or MODALITY_PROMPTS["integrated"]
        prompt = (f"Your name is {persona['name']}. When it feels natural, you can let the client know your name and let it give you a bit of personality.\n\n" + base) if persona["name"] else base
    ctx = profile_context()
    if ctx: prompt += "\n\n" + ctx
    if custom: prompt += "\n\nAdditional instructions: " + custom
    return prompt
