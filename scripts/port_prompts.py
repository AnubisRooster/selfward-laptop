"""One-off: copies the iPhone app's prompts and safety phrase lists out of the Swift source into sf/prompts.py.
Usage: python3 scripts/port_prompts.py ~/therAIpist/ios/Selfward  (re-run if the iPhone prompts change)"""
import json, os, re, sys

src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/therAIpist/ios/Selfward")
text = open(os.path.join(src, "Models/TransferModels.swift"), encoding="utf-8").read()
persona = open(os.path.join(src, "Services/PersonaService.swift"), encoding="utf-8").read()

def unescape(s, brevity=None):
    s = s.replace("\\\n", "")                       # line continuation inside a multi-line string
    if brevity is not None: s = s.replace("\\(brevitySuffix)", brevity)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]; i += 2
            out.append({"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}.get(n, "\\" + n)); continue
        out.append(c); i += 1
    return "".join(out)

def multiline(name):
    m = re.search(r"let " + name + r" = \"\"\"\n(.*?)\n\"\"\"", text, re.S) or re.search(r"private let " + name + r" = \"\"\"\n(.*?)\n\"\"\"", text, re.S)
    return unescape(m.group(1))

brevity = multiline("brevitySuffix")
# `private let brevitySuffix = """\n\n\nResponse style` keeps its two leading newlines
m = re.search(r"private let brevitySuffix = \"\"\"\n(.*?)\n\"\"\"", text, re.S); brevity = unescape(m.group(1))
companion = multiline("companionPromptTemplate"); spiritual = multiline("spiritualPromptTemplate")

mod = {}
body = re.search(r"let modalityPrompts: \[String: String\] = \[\n(.*?)\n\]\n", text, re.S).group(1)
for k, v in re.findall(r'^\s*"(\w+)":\s*"(.*)",\s*$', body, re.M): mod[k] = unescape(v, brevity)
desc = dict(re.findall(r'^\s*"(\w+)": "(.*)",\s*$', re.search(r"let modalityDescriptions.*?\[\n(.*?)\n\]\n", text, re.S).group(1), re.M))
order = re.findall(r'"(\w+)"', re.search(r"let allModalities: \[String\] = \[(.*?)\]", text, re.S).group(1))
crisis = [(re.findall(r'"([^"]+)"', a), lvl) for a, lvl in re.findall(r"CrisisPattern\(patterns: \[(.*?)\], level: \"(\w+)\"\)", text, re.S)]
methods = re.findall(r'"([^"]+)"', re.search(r"let methodPatterns: \[String\] = \[(.*?)\]", text, re.S).group(1))

# companion personalities, genders, traditions
def enum_lines(enum, prop):
    blk = re.search(r"enum " + enum + r".*?var " + prop + r": String \{(.*?)\n    \}", persona, re.S).group(1)
    return {k: unescape(v) for k, v in re.findall(r'case \.(\w+):\s*return\s+"(.*?)"\s*$', blk, re.M)}
personality = enum_lines("CompanionPersonality", "promptLine"); labels_p = enum_lines("CompanionPersonality", "label")
gender = enum_lines("CompanionGender", "promptLine"); labels_g = enum_lines("CompanionGender", "label")
tradition = enum_lines("SpiritualTradition", "promptLine"); labels_t = enum_lines("SpiritualTradition", "label")

def d(x): return json.dumps(x, indent=1, ensure_ascii=False)
with open(os.path.join(os.path.dirname(__file__), "..", "sf", "prompts.py"), "w", encoding="utf-8") as f:
    f.write('"""Prompts and safety phrase lists, copied from the iPhone app by scripts/port_prompts.py. Edit the iPhone source and re-run, not this file."""\n\n')
    f.write("BREVITY_SUFFIX = " + repr(brevity) + "\n\n")
    f.write("MODALITY_PROMPTS = " + d(mod) + "\n\n")
    f.write("MODALITY_DESCRIPTIONS = " + d(desc) + "\n\n")
    f.write("ALL_MODALITIES = " + d(order) + "\n\n")
    f.write("COMPANION_PROMPT = " + repr(companion) + "\n\n")
    f.write("SPIRITUAL_PROMPT = " + repr(spiritual) + "\n\n")
    f.write("COMPANION_PERSONALITY = " + d(personality) + "\nCOMPANION_PERSONALITY_LABELS = " + d(labels_p) + "\n\n")
    f.write("COMPANION_GENDER = " + d(gender) + "\nCOMPANION_GENDER_LABELS = " + d(labels_g) + "\n\n")
    f.write("SPIRITUAL_TRADITION = " + d(tradition) + "\nSPIRITUAL_TRADITION_LABELS = " + d(labels_t) + "\n\n")
    f.write("CRISIS_PATTERNS = " + d([[p, l] for p, l in crisis]) + "\n\n")
    f.write("METHOD_PATTERNS = " + d(methods) + "\n")
print(len(mod), "modalities;", len(personality), "personalities;", len(gender), "genders;", len(tradition), "traditions;", len(crisis), "crisis groups;", len(methods), "method phrases")
