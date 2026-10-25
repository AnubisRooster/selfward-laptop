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
- Onboarding (notice you must accept, profile and intake that shape every prompt, country, default guide), PIN lock with a pause after repeated wrong PINs, light/dark/system theme,
  Markdown and JSON export, passphrase-encrypted backup and restore, erase everything, optional cloud model with an API key (clearly marked: then your words leave this computer).

## Not yet ported (next phases)

Knowledge graph and the Inner Map, dreams and notes capture, the Narrative page, insights, hands-free voice (the SmartWard setup of Kokoro + Whisper fits), rolling summaries for very long chats,
global memory promotion, and the model picker for free OpenRouter models.
Not carried over: Face ID, iOS backup/background tasks, on-device GGUF/Apple Foundation models (Ollama replaces them).

## Development

`scripts/check.sh` runs the Python tests (temporary data folder, a stubbed model: nothing touches your real journal), shell syntax, the TypeScript check and the front-end tests.
`scripts/check.sh --build` also rebuilds `ui/`; `--native` also runs `cargo check`. `scripts/smoke.sh` checks the running app.
