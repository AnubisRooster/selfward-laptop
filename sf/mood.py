"""Mood check-ins: a quick 1 to 5 now and then, with an optional note, and a trend over the days.

Ported from the iPhone app (MoodStore): the scale (1 very low ... 5 great), one entry per tap, and daily averages for the chart.
Days are your computer's local days. Nothing here is sent to a model: the check-ins and their notes stay in your journal."""
import time
from . import db, safety

LABELS = {1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Great"}
MAX_NOTE = 500

def log(value, note="", ts=None):
    """Saves one check-in. Returns (id, crisis_message_or_None): wording in the note that calls for support gets the same screen as in a session."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5: raise ValueError("Pick a number from 1 to 5.")
    note = " ".join((note or "").split())[:MAX_NOTE] if note else ""
    ts = ts or db.now()
    mid = db.x("INSERT INTO moods(value,note,ts) VALUES(?,?,?)", (value, note, ts))
    crisis = None
    if note and (safety.check_crisis(note)[0] or safety.check_self_harm_method(note)):
        db.x("INSERT INTO safety_events(session_id,type,level,message,ts) VALUES(NULL,'crisis_keyword','critical','Wording in a mood note that calls for support',?)", (ts,))
        crisis = safety.resource_message(db.get_setting("region") or "US")
    return mid, crisis

def day_of(ts): return time.strftime("%Y-%m-%d", time.localtime(ts))

def daily_averages(entries):
    """[(day, average, count)] by local calendar day, oldest first. The one rule the chart and the numbers both use."""
    by = {}
    for e in entries: by.setdefault(day_of(e["ts"]), []).append(e["value"])
    return [(d, sum(v) / len(v), len(v)) for d, v in sorted(by.items())]

def view(days=30, now=None):
    now = now or db.now(); days = max(1, min(int(days), 365))
    start = time.mktime(time.strptime(day_of(now - (days - 1) * 86400), "%Y-%m-%d"))          # the start of the first day in range
    entries = db.q("SELECT id,value,note,ts FROM moods WHERE ts>=? ORDER BY ts", (start,))
    daily = [{"day": d, "average": round(a, 2), "count": n} for d, a, n in daily_averages(entries)]
    stats = {"count": len(entries), "average": round(sum(e["value"] for e in entries) / len(entries), 2) if entries else None,
             "days_logged": len(daily), "best_day": max(daily, key=lambda x: x["average"])["day"] if daily else None,
             "lowest_day": min(daily, key=lambda x: x["average"])["day"] if daily else None}
    last = db.q("SELECT id,value,note,ts FROM moods ORDER BY ts DESC LIMIT 1", one=True)
    return {"days": days, "daily": daily, "entries": list(reversed(entries))[:200], "stats": stats, "last": last, "labels": {str(k): v for k, v in LABELS.items()}}
