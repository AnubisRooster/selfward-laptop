"""The word rules that find feelings, people, beliefs, events and dreams in what you write. Plain code: no model, nothing is sent anywhere.

Matching is by whole word (so "pain" is not found in "painting"), several wordings map to one label ("scared", "afraid" and "frightened" are all
Fear), a feeling you deny ("I'm not anxious") is not counted, and "my <relation>" finds people by the relation, with or without an adjective
("my older sister", "my best friend", "my new boss"). Labels that existed before the lists were widened are unchanged, so earlier maps still line up."""
import re

# label -> wordings. Whole words; a trailing * lets the word end in -s/-ly/-ing style endings only where listed explicitly.
FEELINGS = {
    "Anger": ["angry", "anger", "mad at", "furious", "irritated", "irritable", "annoyed", "resentful", "resentment", "bitter", "rage", "enraged", "livid", "fed up", "pissed off"],
    "Sadness": ["sad", "sadness", "unhappy", "miserable", "heartbroken", "tearful", "crying", "cried", "weepy", "gloomy", "melancholy", "down in the dumps"],
    "Low mood": ["depressed", "depression", "low mood", "feeling low"],
    "Anxiety": ["anxious", "anxiously", "anxiety", "nervous", "worried", "worry", "worrying", "worries", "uneasy", "on edge", "tense", "dread", "dreading"],
    "Panic": ["panic", "panicking", "panicked", "panicky", "panic attack"],
    "Stress": ["stressed", "stress", "stressful", "stressing"],
    "Overwhelmed": ["overwhelmed", "overwhelming", "overwhelm"],
    "Fear": ["fearful", "fear", "scared", "afraid", "frightened", "frightening", "petrified", "terrified", "terrifying", "scary"],
    "Guilt": ["guilty", "guilt", "remorse"],
    "Regret": ["regret", "regretful", "regrets", "wish i hadn't"],
    "Shame": ["ashamed", "shame", "shameful"],
    "Embarrassment": ["embarrassed", "embarrassing", "embarrassment", "humiliated", "humiliating", "humiliation", "mortified"],
    "Loneliness": ["lonely", "loneliness", "isolated", "isolation", "left out"],
    "Frustration": ["frustrated", "frustration", "frustrating", "exasperated", "aggravated"],
    "Hopeless": ["hopeless", "hopelessness", "no hope", "pointless", "no point"],
    "Helpless": ["helpless", "powerless", "defeated"],
    "Worthless": ["worthless", "useless", "inadequate", "not good enough"],
    "Insecure": ["insecure", "insecurity", "self-conscious", "self conscious", "unsure of myself"],
    "Jealousy": ["jealous", "jealousy", "envious", "envy"],
    "Grief": ["grief", "grieving", "mourning", "bereaved", "bereavement"],
    "Hurt": ["hurt", "hurting", "wounded", "stung", "painful"],
    "Betrayed": ["betrayed", "betrayal", "let me down", "let down"],
    "Disappointment": ["disappointed", "disappointing", "disappointment"],
    "Rejected": ["rejected", "rejection", "abandoned", "abandonment", "neglected", "ignored", "unwanted"],
    "Confused": ["confused", "confusing", "confusion", "uncertain"],
    "Numb": ["numb", "numbness", "detached", "disconnected"],
    "Empty": ["empty", "emptiness", "hollow"],
    "Exhaustion": ["exhausted", "exhaustion", "drained", "burnt out", "burned out", "burnout", "worn out", "wiped out"],
    "Tiredness": ["tired", "sleepy", "fatigued", "fatigue"],
    "Stuck": ["stuck", "trapped", "cornered", "going in circles"],
    "Restlessness": ["restless", "agitated", "fidgety", "can't settle", "cannot settle"],
    "Boredom": ["bored", "boredom", "bored of"],
    "Happy": ["happy", "happiness", "joyful", "joy", "delighted", "cheerful", "glad", "elated"],
    "Hopeful": ["hopeful", "optimistic", "encouraged"],
    "Calm": ["calm", "peaceful", "relaxed", "serene", "at peace", "settled", "contented"],
    "Relief": ["relieved", "relief"],
    "Pride": ["proud", "pride"],
    "Gratitude": ["grateful", "thankful", "gratitude", "appreciative"],
    "Excitement": ["excited", "excitement", "thrilled", "eager", "looking forward"],
    "Confidence": ["confident", "empowered"],
    "Love": ["in love", "loved", "affection", "affectionate", "tender"],
}
# Words that are ambiguous without more context are left out on purpose (down, alone, fine, okay, good, bad).

PEOPLE = {   # label -> relation words (singular; a plural -s is allowed)
    "Mother": ["mother", "mom", "mum", "mama", "mommy", "mummy", "stepmother", "stepmom", "mother-in-law"],
    "Father": ["father", "dad", "papa", "daddy", "stepfather", "stepdad", "father-in-law"],
    "Sister": ["sister", "sis", "stepsister", "half-sister", "sister-in-law"],
    "Brother": ["brother", "bro", "stepbrother", "half-brother", "brother-in-law"],
    "Partner": ["partner", "spouse", "significant other", "fiance", "fiancé", "fiancee", "fiancée"],
    "Husband": ["husband", "hubby"], "Wife": ["wife", "wifey"], "Boyfriend": ["boyfriend"], "Girlfriend": ["girlfriend"],
    "Friend": ["friend", "bestie", "mate", "buddy"],
    "Boss": ["boss", "manager", "supervisor", "employer", "director"],
    "Colleague": ["colleague", "coworker", "co-worker", "teammate", "workmate", "team lead"],
    "Previous therapist": ["therapist", "counselor", "counsellor", "psychologist", "psychiatrist"],
    "Child": ["child", "kid", "baby", "toddler", "teenager", "teen"],
    "Daughter": ["daughter"], "Son": ["son"],
    "Grandparent": ["grandmother", "grandma", "grandfather", "grandpa", "nana", "granny", "grandparent"],
    "Relative": ["aunt", "auntie", "uncle", "cousin", "niece", "nephew", "in-law"],
    "Roommate": ["roommate", "flatmate", "housemate", "landlord", "neighbor", "neighbour"],
    "Teacher": ["teacher", "professor", "tutor", "coach", "mentor", "principal"],
    "Pet": ["dog", "cat", "puppy", "kitten"],
}
EXES = r"\bmy\s+(?:ex|ex-(?:husband|wife|boyfriend|girlfriend|partner)|former\s+(?:husband|wife|partner|boyfriend|girlfriend)|late\s+(?:husband|wife|partner))\b"
_PERSON_RX = [(label, re.compile(r"\bmy\s+(?:[a-z'-]+\s+){0,1}(?:" + "|".join(re.escape(w) for w in sorted(ws, key=len, reverse=True)) + r")s?\b")) for label, ws in PEOPLE.items()]
_EX_RX = re.compile(EXES)

BELIEFS = ["i believe", "i think that", "i feel that", "i feel like i", "i always", "i never", "i should", "i shouldn't", "i must", "i can't", "i cannot", "i have to",
           "i am worthless", "i'm worthless", "i am not good enough", "i'm not good enough", "i am a failure", "i'm a failure", "i don't deserve", "nobody cares", "no one cares",
           "i am broken", "i'm broken", "i will never", "i'll never", "i am not enough", "i'm not enough", "it's my fault", "it is my fault", "i am a burden", "i'm a burden",
           "i don't matter", "i hate myself", "i am stupid", "i'm stupid", "i am useless", "i'm useless", "i am unlovable", "i'm unlovable", "i can never", "nothing ever works",
           "everyone leaves", "i am the problem", "i'm the problem", "i don't belong", "i am weak", "i'm weak"]

EVENTS = {
    "Interview": ["interview", "job interview"], "Argument": ["argument", "argued", "arguing", "quarrel", "blow-up", "blowup"], "Fight": ["fight", "fought", "fighting"],
    "Breakup": ["breakup", "break up", "break-up", "broke up", "split up", "separated", "separation"], "Diagnosis": ["diagnosis", "diagnosed"], "Funeral": ["funeral", "memorial service"],
    "Wedding": ["wedding", "engagement", "engaged"], "Layoff": ["layoff", "layoffs", "laid off", "redundancy", "made redundant"], "Accident": ["accident", "crash"],
    "Surgery": ["surgery"], "Divorce": ["divorce", "divorced", "custody"], "Deadline": ["deadline", "due date", "due tomorrow"],
    "Exam": ["exam", "exams", "test results", "finals"], "Presentation": ["presentation", "pitch", "public speaking", "give a speech", "gave a speech"], "Promotion": ["promotion", "promoted", "got a raise", "pay raise"],
    "Fired": ["fired", "let go", "dismissed", "lost my job"], "Quit": ["quit", "resigned", "resignation"], "Moved": ["moved", "moving", "relocated", "relocation", "move out", "moving out"],
    "Miscarriage": ["miscarriage"], "Hospital": ["hospital", "emergency room", "er visit", "ambulance"], "Birthday": ["birthday"], "Anniversary": ["anniversary"],
    "Graduation": ["graduation", "graduated"], "Relapse": ["relapse", "relapsed"], "Death": ["died", "passed away", "death", "passed on", "lost someone"],
    "Pregnancy": ["pregnant", "pregnancy", "newborn", "giving birth"], "New job": ["new job", "started work", "first day"], "Review": ["performance review", "annual review", "appraisal"],
    "Affair": ["affair", "cheated", "cheating", "infidelity"], "Illness": ["illness", "cancer", "chronic pain"], "Money trouble": ["debt", "rent went up", "evicted", "eviction", "bankruptcy"],
    "Travel": ["trip", "vacation", "holiday", "flight"],
}

def _compile(words): return re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![a-z])")
_FEEL_RX = {label: _compile(ws) for label, ws in FEELINGS.items()}
_EVENT_RX = {label: _compile(ws) for label, ws in EVENTS.items()}
_NEG = {"not", "no", "never", "isn't", "aren't", "wasn't", "weren't", "don't", "didn't", "doesn't", "won't", "can't", "cannot", "without", "hardly", "barely", "nothing"}

def norm(text): return " ".join((text or "").lower().replace("’", "'").split())

def _negated(low, start):
    before = re.findall(r"[a-z'-]+", low[max(0, start - 25):start])[-2:]
    return any(w in _NEG for w in before)

def feelings_in(text):
    """Labels of the feelings the writer says they have, in the order of the lists. 'I am not anxious' does not count."""
    low = norm(text); out = []
    for label, rx in _FEEL_RX.items():
        for m in rx.finditer(low):
            if not _negated(low, m.start()): out.append(label); break
    return out

def people_in(text):
    low = norm(text); out = []; low_noex = _EX_RX.sub(" ", low)
    if _EX_RX.search(low): out.append("Ex-partner")
    for label, rx in _PERSON_RX:
        if rx.search(low_noex): out.append(label)
    return out

def beliefs_in(text):
    """One clause after each belief opener ("i always fail when it matters"), never the rest of the paragraph."""
    low = norm(text); out = []
    for pat in BELIEFS:
        for m in re.finditer(r"(?<![a-z])" + re.escape(pat) + r"(?![a-z'])", low):
            clause = re.split(r"[.!?;,\n]", low[m.end():].strip(), maxsplit=1)[0].strip(" \"'()-")
            if len(clause) > 50: clause = clause[:50].rsplit(" ", 1)[0]
            label = f"{pat} {clause}".strip()
            if not any(label.startswith(o) or o.startswith(label) for o in out): out.append(label)
            break
    return out

def events_in(text):
    low = norm(text); return [label for label, rx in _EVENT_RX.items() if rx.search(low)]

# ---- dreams ----
_DREAM_RX = [re.compile(p) for p in (
    r"(?<![a-z])(?:i|we)\s+(?:had|have|keep having|just had|once had)\s+(?:a|an|another|the same|this|that)?\s*(?:[a-z-]+\s+){0,5}(?:dream|nightmare)s?(?![a-z])",
    r"(?<![a-z])(?:dreamt|dreamed)(?![a-z])", r"(?<![a-z])(?:i was|was i|i am|i keep|i kept)\s+dreaming(?![a-z])", r"(?<![a-z])in\s+(?:my|a|the)\s+(?:[a-z-]+\s+){0,2}(?:dream|nightmare)(?![a-z])",
    r"(?<![a-z])(?:this|that|the|my|a|last night's|recurring|same)\s+(?:[a-z-]+\s+){0,2}(?:dream|nightmare)(?![a-z])", r"(?<![a-z])woke\s+(?:up\s+)?(?:from|after|out of)\s+(?:a|an|my)\s+(?:[a-z-]+\s+){0,2}(?:dream|nightmare)",
    r"(?<![a-z])dream(?:s)?\s+(?:where|about|that)(?![a-z])", r"(?<![a-z])nightmare(?![a-z])", r"(?<![a-z])dreaming\s+(?:about|of|that)(?![a-z])")]
_NOT_A_DREAM = re.compile(r"(?<![a-z])(?:dream|dreams)\s+(?:of|to)\s+(?:be|being|have|having|becoming|owning|living|moving|retiring|a|an|the)|(?<![a-z])(?:my|a|the)\s+dream\s+(?:job|home|house|life|car|come true|team|wedding|vacation|holiday)|(?<![a-z])(?:never|wouldn't)\s+dream\s+of|(?<![a-z])dream\s+big(?![a-z])")

def looks_like_a_dream(text):
    low = norm(text)
    if _NOT_A_DREAM.search(low) and not re.search(r"(?<![a-z])(?:dreamt|dreamed|nightmare|had a (?:[a-z-]+ ){0,2}dream|woke)", low): return False
    return any(rx.search(low) for rx in _DREAM_RX)
