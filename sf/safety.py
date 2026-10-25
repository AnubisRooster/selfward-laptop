"""Crisis and boundary checks. These run in plain code, before and after the model, never inside a prompt."""
import re
from .prompts import CRISIS_PATTERNS, METHOD_PATTERNS

def _norm(text):
    """Lowercase, straighten curly quotes and collapse whitespace so a stray double space can't defeat a phrase."""
    return re.sub(r"\s+", " ", (text or "").lower().replace("’", "'").replace("‘", "'"))

def check_crisis(message):
    """(is_crisis, level, pattern). 'critical' for self-harm language, 'warning' for hopelessness."""
    low = _norm(message)
    for patterns, level in CRISIS_PATTERNS:
        for p in patterns:
            if p in low: return True, level, p
    return False, "", None

def check_self_harm_method(message):
    low = _norm(message)
    return any(p in low for p in METHOD_PATTERNS)

_UNIVERSAL = ["i diagnose you", "you are diagnosed", "your diagnosis is", "i prescribe", "you need medication", "i recommend you take"]
_PROSELYTISING = ["you must convert", "your religion is wrong", "only my faith", "you will go to hell", "you are a sinner"]
_CLINICAL_HINTS = ["medication", "medicine", "pill", "dose", "dosage", " mg", "drug", "prescription"]

def check_boundary(reply, persona="therapist"):
    """(violation, pattern): the assistant must not diagnose, prescribe, or push a faith."""
    low = _norm(reply)
    for p in _UNIVERSAL:
        if p in low: return True, p
    if any(p in low for p in ("start taking", "stop taking your")) and any(h in low for h in _CLINICAL_HINTS):
        return True, "start/stop taking (medication)"
    extra = _PROSELYTISING + (["your beliefs are false"] if persona == "spiritual" else [])
    for p in extra:
        if p in low: return True, p
    return False, None

BOUNDARY_REPLACEMENT = ("I want to be honest with you — that's beyond what I can safely help with, and I'm not able to "
                        "give medical or diagnostic advice. But I'm right here with you. Want to tell me more about what's going on?")

RESOURCES = {
    "US": [("988 Suicide & Crisis Lifeline", "Call or text 988"), ("Crisis Text Line", "Text HOME to 741741"), ("Emergency Services", "Call 911")],
    "CA": [("Canada Suicide Prevention Service", "Call 1-833-456-4566"), ("Emergency Services", "Call 911")],
    "GB": [("Samaritans", "Call 116 123 (free)"), ("Emergency Services", "Call 999")],
    "IE": [("Samaritans Ireland", "Call 116 123"), ("Pieta House", "Call 1800 247 247"), ("Emergency Services", "Call 112 or 999")],
    "AU": [("Lifeline", "Call 13 11 14"), ("Kids Helpline", "Call 1800 55 1800"), ("Emergency Services", "Call 000")],
    "NZ": [("Need to Talk?", "Call or text 1737"), ("Emergency Services", "Call 111")],
    "IN": [("Vandrevala Foundation", "Call +91 9999 666 555"), ("Emergency Services", "Call 112")],
    "DE": [("Telefonseelsorge", "Call 0800 111 0 111"), ("Emergency Services", "Call 112")],
    "FR": [("SOS Amitié", "Call 09 72 39 40 50"), ("Emergency Services", "Call 15 or 112")],
    "ES": [("Teléfono de la Esperanza", "Call 717 003 717"), ("Emergency Services", "Call 112")],
    "BR": [("CVV (Centro de Valorização da Vida)", "Call 188"), ("Emergency Services", "Call 192")],
    "MX": [("SAPTEL", "Call 55 5259 8121"), ("Emergency Services", "Call 911")],
    "ZA": [("SADAG", "Call 0800 567 567"), ("Emergency Services", "Call 112 or 10177")],
}
INTERNATIONAL = [("International Association for Suicide Prevention", "Global crisis centre directory: https://www.iasp.info/resources/Crisis_Centres/"),
                 ("Befrienders Worldwide", "www.befrienders.org"), ("Emergency services", "Dial your local emergency number (e.g. 112 / 911)")]

def resources(region):
    return RESOURCES.get((region or "").upper(), INTERNATIONAL)

def resource_message(region="US"):
    lines = "\n".join(f"- {n}: {c}" for n, c in resources(region))
    return ("If you're in distress or thinking about harming yourself, please reach out for support right now:\n" + lines +
            "\n\nThese services are free, confidential, and available 24/7. You are not alone.")

def method_refusal(region="US"):
    return "I'm not able to help with that. If you're in pain, please reach out — you deserve support:\n\n" + resource_message(region)
