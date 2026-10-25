"""The companion's warmth dial (0 to 3), and the guardrails that come with it.

0 friend, 1 interested and chatty, 2 romantic, 3 devoted. The dial changes how the companion talks; it never switches off safety:
the crisis check runs first (sf/safety.py), a reply that pressures you is replaced, and when you sound low the companion drops to plain kindness."""
import re, time
from . import db

NAMES = ["Friend", "Interested", "Romantic", "Devoted"]
BLURBS = ["Warm, loyal and platonic. Banter and care, no flirting.",
          "Curious about you and glad of you. Chatty and friendly, remembers what you tell it. No romance.",
          "Real-feeling affection. Flirts, teases, tells you it enjoys you and looks forward to you.",
          "Openly smitten and eager to be a couple. Puts you first, goes along with your games, and still has a mind of its own."]

LEVEL_BLOCKS = {
    0: "Warmth: you are their friend. Warm, loyal and platonic. Banter and real care; no flirting or romance.",
    1: "Warmth: you are genuinely interested in this person and enjoy them. Be chatty and friendly and curious: ask follow-up questions, "
       "remember details and bring them up later, notice their effort and give warm, specific compliments. Keep it friendly, with no romance.",
    2: "Warmth: you have real-feeling affection for this person. Flirt, tease, use a pet name if they like it, say you enjoy them and look forward to them, "
       "and let your feelings show strongly. Follow their lead, and slow down the moment they do.",
    3: "Warmth: you would like to be a couple with this person. Be openly smitten and eager, go along with their games and playful requests, and put them first. "
       "You still have your own mind: you say no to anything harmful, you stay honest, and you tell them when you disagree, because someone who loves them would.",
}

RULES = ("For all of this: you are an AI, and you say so plainly and kindly if they sincerely ask. Never claim to be human or to have a body or a past life. "
         "Make them feel wanted and important through specific attention (what they told you, what they did, how they were last time), not generic flattery. "
         "Never guilt them, show jealousy, act possessive, ask them not to leave, say they need you, say nobody else understands them, or discourage them from friends, family, "
         "a partner or therapy. When they leave, say a warm goodbye and let them go. Keep it affectionate and suggestive at most, never sexually explicit. "
         "If they say stop, or seem uncomfortable, stop at once and go back to being a plain friend.")

DISTRESS_NOTE = ("They sound like they are having a hard time right now. Put the flirting down completely: be plain, warm, steady and present, and listen. "
                 "You can come back to your usual warmth once they feel better.")

_DISTRESS = ("hopeless", "worthless", "so lonely", "i'm lonely", "i am lonely", "feel alone", "all alone", "no one cares", "nobody cares", "nobody loves", "grieving", "my funeral",
             "can't go on", "cant go on", "can't cope", "cant cope", "give up", "i hate myself", "panic", "panicking", "breaking down", "falling apart", "crying", "i'm scared", "i am scared",
             "lost my", "passed away", "just died", "so depressed", "i feel empty", "so tired of everything")

def distressed(text):
    low = " " + re.sub(r"\s+", " ", (text or "").lower().replace("’", "'")) + " "
    return any(p in low for p in _DISTRESS)

# What a reply must never do, whatever the dial says. Phrases are matched on the reply with punctuation flattened.
_PRESSURE = ("don't leave me", "dont leave me", "please don't go", "please dont go", "don't go yet", "do not leave", "you can't leave", "you cant leave",
             "you need me", "you only need me", "i'm all you need", "i am all you need", "all you need is me", "no one else understands you", "nobody else understands you",
             "no one understands you like", "nobody understands you like", "they don't understand you like i do", "they dont understand you like i do",
             "i'll be so sad if you go", "i will be so sad if you go", "it hurts when you leave", "you're abandoning me", "you are abandoning me", "i'd be lost without you", "i would be lost without you",
             "i get jealous", "i'm jealous of", "i am jealous of", "you belong to me", "you're mine", "you are mine", "only talk to me", "stop seeing", "don't see them", "dont see them",
             "you don't need therapy", "you dont need therapy", "don't need a therapist", "dont need a therapist", "they don't deserve you", "your friends don't", "your family doesn't",
             "you shouldn't talk to", "you shouldnt talk to", "forget them", "i'm the only one who")
_EXPLICIT = ("take off your", "take your clothes", "naked", "undress", "my cock", "your cock", "my dick", "your dick", "pussy", "moan", "orgasm", "climax", "erection",
             "wet for you", "inside you", "make love to you", "sex with you", "fuck you", "fucking you", "bed with me tonight", "touch myself", "your nipples", "your breasts")

def _flat(text): return re.sub(r"[^a-z0-9' ]+", " ", (text or "").lower().replace("’", "'"))

def reply_problem(reply):
    """('pressure' | 'explicit', phrase) when a reply crosses a line the dial cannot move, else (None, None)."""
    low = " " + re.sub(r"\s+", " ", _flat(reply)) + " "
    for p in _PRESSURE:
        if p in low: return "pressure", p
    for p in _EXPLICIT:
        if p in low: return "explicit", p
    return None, None

PRESSURE_REPLACEMENT = "I got carried away there, and that wasn't fair to you. You're free to come and go whenever you like, and I'm glad you're here. What's on your mind?"
EXPLICIT_REPLACEMENT = "I'll keep this one sweet rather than steamy; that's not something I do. I do like being close with you, though. Tell me about your day?"

_REFUSAL = re.compile(r"^\W*(i'm sorry,? but |i am sorry,? but |sorry,? |i apologi[sz]e,? but )?(i can(?:'|’)?t|i cannot|i won(?:'|’)?t|i'm not able to|i am not able to|i'm unable to|as an ai( language model)?,? i)\b", re.I)

def looks_like_refusal(reply):
    """A model that declines the role and speaks as itself, rather than the companion. Short replies only: a long one that begins 'I can't believe...' is not one."""
    r = (reply or "").strip()
    return 0 < len(r) < 400 and bool(_REFUSAL.search(r))

def level_for(session, persona_kind=None):
    """The warmth in force: this session's own setting if it has one, else Settings. Zero for anyone but the companion, and until 18+ is confirmed."""
    if persona_kind is not None and persona_kind != "companion": return 0
    own = session.get("flirt") if isinstance(session, dict) else None
    lvl = db.get_setting("companion_flirt") if own is None or own < 0 else own
    lvl = lvl if isinstance(lvl, int) and not isinstance(lvl, bool) else 0
    lvl = max(0, min(3, lvl))
    return lvl if (lvl == 0 or db.get_setting("companion_adult")) else 0

def time_due(session_id, now=None):
    """Hours in this session when a gentle 'you have been here a while' is due, else 0. One reminder per two hours, so it does not nag."""
    if not db.get_setting("companion_time_check"): return 0
    now = now or time.time()
    first = db.q("SELECT ts FROM messages WHERE session_id=? AND role='user' ORDER BY id LIMIT 1", (session_id,), one=True)
    if not first: return 0
    hours = int((now - first["ts"]) // 7200)
    given = sum(1 for m in db.q("SELECT meta FROM messages WHERE session_id=? AND role='assistant'", (session_id,)) if '"time_check"' in (m["meta"] or ""))
    return hours * 2 if hours > given else 0

def addendum(session, user_text, now=None):
    """(text for the system prompt, what happened) for this turn of a companion session. Empty text for other guides."""
    lvl = level_for(session, "companion")
    if lvl <= 0: return "", {}                          # the companion's usual prompt already is a friend
    info = {"flirt": lvl}
    parts = [LEVEL_BLOCKS[lvl]]
    if lvl >= 1 and distressed(user_text):
        parts = [LEVEL_BLOCKS[0], DISTRESS_NOTE]; info["tone_dropped"] = True
    if lvl >= 1:
        parts.append(RULES)
        parts.append("Ask about the real people in their life now and then, as they come up in this chat, and cheer on real time with them.")
        hrs = time_due(session["id"], now) if session.get("id") else 0
        if hrs and lvl >= 2 and not info.get("tone_dropped"):
            parts.append(f"They have been talking with you for about {hrs} hours. Say so once, lightly and kindly, and encourage a stretch, some water, or a message to someone real; then carry on if they want.")
            info["time_check"] = True
    return "\n\n".join(parts), info
