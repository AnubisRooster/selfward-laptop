# Selfward for Linux

A private reflection companion, ported from the iPhone app ([therAIpist](https://github.com/AnubisRooster/therAIpist), called Selfward on the phone). Everything runs on this laptop:
the model (Ollama), the database (SQLite) and the window. Built with the same shell as SmartWard: a Python API, a React interface and a small Tauri window with a tray icon.

> Selfward is **not** a licensed therapist, psychologist or medical provider. It is a journaling and self-reflection tool and cannot diagnose or treat anything.
> **Get help now** (always in the sidebar) lists the crisis lines for the country chosen in Settings.

## Run

- Open **Selfward** from the applications menu (or `bin/start_selfward.sh`). It starts and watches the API (`http://localhost:8100`; SmartWard uses 8000, so both can run).
  Closing the window keeps it in the tray; tray → Quit stops it.
- Browser version: `SELFWARD_BROWSER=1 bin/start_selfward.sh`. `bin/start_selfward.sh stop` stops the API.
- Data lives in `~/.local/share/selfward/` (SQLite, owner-only permissions). Logs: `~/.local/state/selfward/api.log`.
- First time on a machine: `scripts/build_ui.sh`, `scripts/build_native.sh`, then `scripts/install_desktop.sh` (menu entry and icons).

## Requirements

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential pkg-config nodejs npm
python3 -m pip install --break-system-packages -r requirements.txt
ollama pull llama3.2:3b && ollama pull nomic-embed-text   # chat + memory embeddings
```

## What carried over from the iPhone app (phase 1)

- **Three guides** sharing one memory: the AI Reflection Guide (unnamed by default; 15 approaches: integrated, free form, CBT, DBT, ACT, psychodynamic, humanistic, existential, Gestalt, somatic, narrative, IFS, Adlerian, Jungian, active imagination), the Companion (7 personalities, 4 presences, a name) and the Spiritual Advisor (9 traditions, a name). The prompts are copied from the Swift source by `scripts/port_prompts.py`.
- **Safety, in code, not in a prompt:** crisis phrases and requests for self-harm methods are answered locally with the crisis lines for your country and never reach the model; replies that diagnose, prescribe or push a faith are replaced and logged. Settings → Safety log shows what was caught.
- **Memory:** each exchange is embedded (Ollama, `nomic-embed-text`) and recalled in later sessions, across guides. Without the embedding model it falls back to matching words.
- **Inner Map** (sidebar): the feelings, people, beliefs and events you write about, and how they connect, as a map or a list; filter by kind or session, click a thing to see its connections and the sessions it came up in; export GraphML (Gephi) or Cytoscape JSON. It is built from your own words with plain keyword rules, no model, and crisis messages are kept out. Differences from the phone: variants of one feeling are one node (Anger, not Angry and Anger), words inside other words don't match, a belief is one clause, and the phone's "cycles" are left out because the rules link every feeling and belief in a message both ways, so they were not real patterns. "Rebuild from my sessions" builds the map from sessions written before it existed.
- **Insights** (sidebar): *Highlights* read the map aloud ("You often feel anxiety when Mother comes up"); *Dreams* are saved when you tell one in a session ("I had a dream…"), with the feelings and symbols picked out, or added by hand, and "Offer a reading" asks your model for a tentative Jungian reading (crisis wording is never sent; the reply gets the same boundary check as chat); *Notes* include one summary per session that starts after your second message and updates until you edit it, plus your own. Chat messages show a small "Dream saved" / "Note started" badge. All of it is found in your own words with plain rules, so it also works when the model is down, and "Look in older sessions" fills in sessions written before it existed.
- **Memory you can see** (Settings → What Selfward remembers): besides every exchange, moments that carry weight (a parent, a loss, shame, a realisation, "growing up…") are kept for good and brought up in later sessions when they are relevant, under their own heading. Only your own words decide what is kept (not the guide's reply), words are matched whole, and you can add your own, forget any, or switch it off. Deleting a session deletes the memories it created.
- **Long chats:** the prompt is sized to the model's window (Settings → Model → Conversation window, 8,192 tokens by default, also sent to Ollama as `num_ctx`, because Ollama's own default is small and silently cuts the start of a long prompt, where the guide's instructions are). When a chat outgrows it, the newest turns stay word for word and older exchanges that bear on what you just wrote are brought back from this chat's own memory. After each answer, older turns are folded into a short recap by the model (never before it, so you don't wait; on a CPU-only laptop a recap can take minutes), and the next long turn uses it. A recap that is not about the conversation (a complaint about the input, a refusal) is thrown away; if the model is down the chat just trims. Measured with llama3.2 3B on this laptop: it recalled a dog's vet advice and a class from 20 turns back through the in-chat memory, while the recap alone kept themes but dropped specifics, which is why both exist.
- Onboarding (notice you must accept, profile and intake that shape every prompt, country, default guide), PIN lock with a pause after repeated wrong PINs, light/dark/system theme,
  Markdown and JSON export, passphrase-encrypted backup and restore, erase everything, optional cloud model with an API key (clearly marked: then your words leave this computer).

## Not yet ported (next phases)

The Narrative page, hands-free voice, mood check-ins (the phone's MoodStore; the SmartWard setup of Kokoro + Whisper fits for voice), and the model picker for free OpenRouter models.
Not carried over: Face ID, iOS backup/background tasks, on-device GGUF/Apple Foundation models (Ollama replaces them).

## Development

`scripts/check.sh` runs the Python tests (temporary data folder, a stubbed model: nothing touches your real journal), shell syntax, the TypeScript check and the front-end tests.
`scripts/check.sh --build` also rebuilds `ui/`; `--native` also runs `cargo check`. `scripts/smoke.sh` checks the running app.
