"""The inner map: emotions, people, beliefs and events that come up in your sessions, and how they connect.

Ported from the iPhone app (GraphService, GraphExportService). Extraction is plain keyword rules, so it needs no model and
nothing is sent anywhere. Nodes belong to a session; the map across sessions merges nodes that share a type and label."""
import json, re
from . import db

EMOTIONS = ["angry", "anger", "sad", "sadness", "happy", "anxious", "anxiety", "fearful", "fear", "guilty", "guilt", "ashamed", "shame",
            "hopeful", "lonely", "loneliness", "frustrated", "frustration", "overwhelmed", "hopeless", "jealous", "jealousy", "grief", "hurt",
            "betrayed", "confused", "numb", "empty", "worthless", "helpless"]
# Variants of one feeling become one node ("angry" and "anger" are both Anger); the phone app kept them apart and also
# matched "guilt" inside "guilty", so one sentence put two nodes on the map.
CANON = {"angry": "Anger", "sad": "Sadness", "anxious": "Anxiety", "fearful": "Fear", "guilty": "Guilt", "ashamed": "Shame",
         "lonely": "Loneliness", "frustrated": "Frustration", "jealous": "Jealousy", "break up": "Breakup", "laid off": "Layoff", "moving": "Moved"}
PERSONS = [("my mother", "Mother"), ("my mom", "Mother"), ("my father", "Father"), ("my dad", "Father"), ("my sister", "Sister"),
           ("my brother", "Brother"), ("my partner", "Partner"), ("my husband", "Husband"), ("my wife", "Wife"), ("my friend", "Friend"),
           ("my boss", "Boss"), ("my therapist", "Previous therapist"), ("my child", "Child"), ("my daughter", "Daughter"),
           ("my son", "Son"), ("my colleague", "Colleague"), ("my ex", "Ex-partner")]
BELIEFS = ["i believe", "i think that", "i feel that", "i always", "i never", "i should", "i must", "i can't", "i have to", "i am worthless",
           "i am not good enough", "i am a failure", "i don't deserve", "nobody cares", "i am broken", "i will never"]
EVENTS = ["interview", "argument", "breakup", "break up", "diagnosis", "funeral", "wedding", "layoff", "laid off", "fight", "accident",
          "surgery", "divorce", "deadline", "exam", "presentation", "promotion", "fired", "quit", "moved", "moving", "miscarriage",
          "hospital", "birthday", "anniversary", "graduation", "relapse"]

COLORS = {"person": "#4A90D9", "event": "#F5A623", "emotion": "#D0021B", "belief": "#7ED321", "theme": "#9B59B6"}
TYPE_NAMES = {"emotion": "Emotions", "person": "People", "belief": "Beliefs", "event": "Events", "theme": "Themes"}
EDGE_PHRASE = {"CAUSES": "leads to", "TRIGGERS": "brings up", "SUPPRESSES": "pushes down", "COMPENSATES_FOR": "covers for", "ASSOCIATED_WITH": "goes with"}
RECENT_WINDOW = 6          # earlier messages still "in play" when wiring edges for the current one
MAX_STRENGTH = 2.0

def _dedupe(specs):
    seen, out = set(), []
    for s in specs:
        if s[1] not in seen: seen.add(s[1]); out.append(s)
    return out

def analyze(message):
    """(nodes, edges) a message implies: nodes are (type, label), edges are (source label, target label, type)."""
    low = " ".join((message or "").lower().replace("’", "'").split())
    has = lambda w: re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low) is not None
    emotions = _dedupe([("emotion", CANON.get(w, w.capitalize())) for w in EMOTIONS if has(w)])
    persons = _dedupe([("person", label) for pat, label in PERSONS if pat in low])
    beliefs = []
    for pat in BELIEFS:
        if pat in low:
            parts = low.split(pat)
            if len(parts) > 1:
                clause = re.split(r"[.!?;,\n]", parts[1].strip(), maxsplit=1)[0].strip(" \"'()-")        # one clause, not the rest of the paragraph
                if len(clause) > 50: clause = clause[:50].rsplit(" ", 1)[0]
                beliefs.append(("belief", f"{pat} {clause}" if clause else pat))
    beliefs = _dedupe(beliefs)
    events = _dedupe([("event", CANON.get(w, w.capitalize())) for w in EVENTS if has(w)])
    edges = []
    for src in persons + events:
        edges += [(src[1], e[1], "TRIGGERS") for e in emotions]
    for e in emotions:
        edges += [(e[1], b[1], "CAUSES") for b in beliefs]
    for b in beliefs:
        edges += [(b[1], e[1], "ASSOCIATED_WITH") for e in emotions]
    for i in range(len(emotions)):
        for j in range(i + 1, len(emotions)):
            edges.append((emotions[i][1], emotions[j][1], "ASSOCIATED_WITH"))
    return emotions + persons + beliefs + events, edges

def cross_edges(current, recent):
    """Edges between this message's entities and those of recent ones, in both time directions."""
    of = lambda specs, t: [s for s in specs if s[0] == t]
    out = []
    def link(a, b, t): out.extend((x[1], y[1], t) for x in a for y in b)
    for t in ("person", "event"):
        link(of(recent, t), of(current, "emotion"), "TRIGGERS"); link(of(current, t), of(recent, "emotion"), "TRIGGERS")
    link(of(recent, "emotion"), of(current, "belief"), "CAUSES"); link(of(current, "emotion"), of(recent, "belief"), "CAUSES")
    link(of(recent, "belief"), of(current, "emotion"), "ASSOCIATED_WITH"); link(of(current, "belief"), of(recent, "emotion"), "ASSOCIATED_WITH")
    return out

def _node(session_id, label):
    return db.q("SELECT * FROM graph_nodes WHERE session_id=? AND lower(label)=lower(?)", (session_id, label), one=True)

def _add_node(session_id, type_, label):
    n = _node(session_id, label)
    if n:
        db.x("UPDATE graph_nodes SET strength=? WHERE id=?", (min(n["strength"] + 0.5, MAX_STRENGTH), n["id"])); return n["id"]
    return db.x("INSERT INTO graph_nodes(session_id,type,label,strength,ts) VALUES(?,?,?,1.0,?)", (session_id, type_, label, db.now()))

def _add_edge(session_id, src_label, tgt_label, type_):
    a, b = _node(session_id, src_label), _node(session_id, tgt_label)
    if not a or not b or a["id"] == b["id"]: return
    e = db.q("SELECT * FROM graph_edges WHERE session_id=? AND source=? AND target=? AND type=?", (session_id, a["id"], b["id"], type_), one=True)
    if e: db.x("UPDATE graph_edges SET weight=? WHERE id=?", (min(e["weight"] + 0.5, MAX_STRENGTH), e["id"]))
    else: db.x("INSERT INTO graph_edges(session_id,source,target,type,weight,ts) VALUES(?,?,?,?,1.0,?)", (session_id, a["id"], b["id"], type_, db.now()))

def extract(session_id, message, recent_messages=()):
    """Adds what `message` brings up to this session's map. Returns how many nodes it touched."""
    nodes, edges = analyze(message)
    for t, label in nodes: _add_node(session_id, t, label)
    for s, t, ty in edges: _add_edge(session_id, s, t, ty)
    recent = [n for m in list(recent_messages)[-RECENT_WINDOW:] for n in analyze(m)[0]]
    for s, t, ty in cross_edges(nodes, recent): _add_edge(session_id, s, t, ty)
    return len(nodes)

def rebuild():
    """Clears the map and rebuilds it from every session's own messages (skipping ones answered by the crisis screen)."""
    with db.tx() as c:
        c.execute("DELETE FROM graph_nodes"); c.execute("DELETE FROM graph_edges")
    done = 0
    for s in db.q("SELECT id FROM sessions ORDER BY id"):
        msgs = db.q("SELECT id,role,content,meta FROM messages WHERE session_id=? ORDER BY id", (s["id"],))
        users = []
        for i, m in enumerate(msgs):
            if m["role"] != "user": continue
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            if nxt and json.loads(nxt["meta"] or "{}").get("safety") in ("crisis", "method"): continue
            extract(s["id"], m["content"], users); users.append(m["content"]); done += 1
    return done

def delete_session(session_id):
    db.x("DELETE FROM graph_nodes WHERE session_id=?", (session_id,)); db.x("DELETE FROM graph_edges WHERE session_id=?", (session_id,))

def view(session_id=None, types=None):
    """The map for one session, or merged across all of them. Nodes: id 'type:label'."""
    where, args = ("WHERE session_id=?", (session_id,)) if session_id else ("", ())
    rows = db.q(f"SELECT * FROM graph_nodes {where}", args)
    by_id, merged = {}, {}
    for r in rows:
        key = f"{r['type']}:{r['label'].lower()}"
        n = merged.setdefault(key, {"id": key, "type": r["type"], "label": r["label"], "strength": 0.0, "sessions": set(), "color": COLORS.get(r["type"], "#999999")})
        n["strength"] += r["strength"]; n["sessions"].add(r["session_id"]); by_id[r["id"]] = key
    edges = {}
    for e in db.q(f"SELECT * FROM graph_edges {where}", args):
        a, b = by_id.get(e["source"]), by_id.get(e["target"])
        if not a or not b or a == b: continue
        k = (a, b, e["type"]); x = edges.setdefault(k, {"source": a, "target": b, "type": e["type"], "phrase": EDGE_PHRASE.get(e["type"], e["type"].replace("_", " ").lower()), "weight": 0.0})
        x["weight"] += e["weight"]
    nodes = [{**n, "sessions": sorted(n["sessions"])} for n in merged.values() if not types or n["type"] in types]
    keep = {n["id"] for n in nodes}
    edges = [e for e in edges.values() if e["source"] in keep and e["target"] in keep]
    top = {t: sorted([n for n in nodes if n["type"] == t], key=lambda n: -n["strength"])[:5] for t in TYPE_NAMES}
    stats = {"nodes": len(nodes), "edges": len(edges), "sessions": len({s for n in nodes for s in n["sessions"]}),
             "top": {t: [{"label": n["label"], "strength": round(n["strength"], 1)} for n in v] for t, v in top.items() if v}}
    return {"nodes": nodes, "edges": edges, "stats": stats, "links": _top_links(nodes, edges), "types": [{"id": k, "label": v, "color": COLORS[k]} for k, v in TYPE_NAMES.items()]}

def _top_links(nodes, edges, limit=8):
    """The connections that came up most, as sentences ("Boss brings up Anxiety").

    The phone app also listed "cycles". Every feeling and belief from one message is linked both ways by construction,
    so those cycles were artefacts of the rules, not patterns in you; they are left out."""
    label = {n["id"]: n["label"] for n in nodes}
    top = sorted(edges, key=lambda e: -e["weight"])[:limit]
    return [{"text": f"{label[e['source']]} {e['phrase']} {label[e['target']]}", "weight": round(e["weight"], 1), "source": e["source"], "target": e["target"]} for e in top]

def node_detail(type_, label, session_id=None):
    v = view(session_id); key = f"{type_}:{label.lower()}"
    n = next((x for x in v["nodes"] if x["id"] == key), None)
    if not n: return None
    names = {x["id"]: x for x in v["nodes"]}
    out = [{"label": names[e["target"]]["label"], "type": names[e["target"]]["type"], "relation": e["phrase"], "direction": "out", "weight": e["weight"]} for e in v["edges"] if e["source"] == key]
    inc = [{"label": names[e["source"]]["label"], "type": names[e["source"]]["type"], "relation": e["phrase"], "direction": "in", "weight": e["weight"]} for e in v["edges"] if e["target"] == key]
    sess = db.q(f"SELECT id,title,updated FROM sessions WHERE id IN ({','.join('?' * len(n['sessions']))}) ORDER BY updated DESC", n["sessions"]) if n["sessions"] else []
    return {"node": n, "links": sorted(out + inc, key=lambda l: -l["weight"]), "sessions": sess}

def graphml(session_id=None):
    from xml.sax.saxutils import escape
    v = view(session_id)
    x = ['<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
         '<key id="label" for="node" attr.name="label" attr.type="string"/><key id="type" for="node" attr.name="type" attr.type="string"/>'
         '<key id="strength" for="node" attr.name="strength" attr.type="double"/><key id="rel" for="edge" attr.name="relation" attr.type="string"/>'
         '<key id="weight" for="edge" attr.name="weight" attr.type="double"/><graph edgedefault="directed">']
    for n in v["nodes"]: x.append(f'<node id="{escape(n["id"], {chr(34): "&quot;"})}"><data key="label">{escape(n["label"])}</data><data key="type">{n["type"]}</data><data key="strength">{n["strength"]}</data></node>')
    for e in v["edges"]: x.append(f'<edge source="{escape(e["source"], {chr(34): "&quot;"})}" target="{escape(e["target"], {chr(34): "&quot;"})}"><data key="rel">{e["type"]}</data><data key="weight">{e["weight"]}</data></edge>')
    x.append("</graph></graphml>"); return "".join(x)

def cytoscape(session_id=None):
    v = view(session_id)
    return {"elements": {"nodes": [{"data": {"id": n["id"], "label": n["label"], "type": n["type"], "strength": n["strength"], "color": n["color"]}} for n in v["nodes"]],
                         "edges": [{"data": {"source": e["source"], "target": e["target"], "relation": e["type"], "weight": e["weight"]}} for e in v["edges"]]}}
