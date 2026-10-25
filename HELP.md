# Selfward help guide

Selfward is a private reflection companion that runs on your own computer: the guide you talk to, your sessions, your memories and your mood check-ins all stay here unless you choose a cloud model or open it from your phone. It is a journaling and self-reflection tool, **not** a licensed therapist, and it cannot diagnose or treat anything. If you are in crisis, press **Get help now** (always in the sidebar) or call your local emergency number.

This guide covers installing it, setting it up, and the optional extras (voice, free cloud models, phone access). Commands go in a terminal.

## What you need

- A Linux laptop (these steps are written for Ubuntu) with about 6 GB of free disk space for the models, and 8 GB of RAM or more.
- [Ollama](https://ollama.com), which runs the language model on your computer.
- Python 3.10 or newer, Node.js with npm, and Rust (only to build the window).

## Install

1. Install the system packages:

```bash
sudo apt install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential pkg-config nodejs npm curl
```

2. Install Rust (needed once, to build the window). Accept the defaults:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

3. Install Ollama and download the two models Selfward uses: a small chat model and a memory (embedding) model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

4. Get Selfward and install its Python packages:

```bash
git clone https://github.com/AnubisRooster/selfward-laptop.git ~/SelfwardApp   # a private repository: sign in with your GitHub account when asked
cd ~/SelfwardApp
python3 -m pip install --break-system-packages -r requirements.txt
```

5. Build the interface and the window, then add Selfward to your applications menu:

```bash
scripts/build_ui.sh
scripts/build_native.sh
scripts/install_desktop.sh
```

The first build downloads packages and compiles the window, which takes several minutes. `install_desktop.sh` adds a **Selfward** entry and icon for your user only (no sudo).

6. Open **Selfward** from your applications menu. It starts its own background service and shows the welcome screen. If you would rather use a browser tab than the window, run `SELFWARD_BROWSER=1 ~/SelfwardApp/bin/start_selfward.sh` and open `http://localhost:8100`.

## First run

The welcome screen has five short steps. The first asks you to read and accept the notice that Selfward is not a therapist. Then:

1. **About you**: a name, pronouns and age (all optional) and your country, which decides which crisis lines are shown.
2. **What brings you here**: what is on your mind, any past therapy, what you want from this. This is added to every conversation so the guide knows who it is talking with. You can change it later in Settings.
3. **How you want to talk**: your default guide and, for the AI Reflection Guide, its approach.
4. **Check the model**: shows whether Ollama is running and the models are installed. You can finish with warnings and fix them afterwards.

Then press **+ New** on the Sessions page, pick a guide, and write.

## The guides and approaches

- **AI Reflection Guide**: follows one of 15 approaches that you choose per session (integrated, free form, CBT, DBT, ACT, psychodynamic, humanistic, existential, Gestalt, somatic, narrative, IFS, Adlerian, Jungian, active imagination). You can change the approach during a session.
- **Companion**: a warm, chatty friend. Choose its name, personality and presence in Settings → Your guides.
- **Spiritual Advisor**: draws on a wisdom tradition you pick (interfaith, Stoic, Buddhist, Christian, Jewish, Islamic, Hindu, Taoist or secular).

All three share the same memory. Their names and settings are in **Settings → Your guides**.

**Changing things mid-session.** Under a session's title are three pills: the guide you are talking with, the approach (for the AI Reflection Guide) and the model. Press any of them to change it from your next message on. The conversation and everything remembered come along, and each earlier reply keeps the name, approach and model that wrote it. The guide's portrait next to the title opens the same picker.

**Naming a session.** Give it a title when you start it (the box at the top of **+ New**), or press the pencil next to the title at any time. Without one, it is named from your first message; a title you choose is never overwritten.

**The small pills under a reply** show what that exchange added: **memories** (it was remembered so a later session can recall it), **nodes** and **edges** (new things and connections on your Inner Map), **dream logged**, **note**, and **insight saved** (the moment carries weight, so it is kept for good). Press one to go to where it lives. The row of icons at the top right of a session opens that session's Insights, Notes, Dreams and Patterns (its Inner Map). In the list, each session shows its guide's portrait, approach, model, message count, and the number of map nodes and memories.

## Choosing the model

Open **Settings → Model**.

- **Chat model**: the default is `ollama_chat/llama3.2:3b`, a small model that runs well on a laptop. A larger one such as `ollama_chat/qwen2.5:7b` (after `ollama pull qwen2.5:7b`) writes noticeably better but needs more memory and time.
- **Memory (embedding) model**: `nomic-embed-text`. Without it, memory falls back to matching words.
- **Conversation window**: how much of a chat the model reads at once (8,192 tokens by default). Longer chats are folded into a short recap. Raise it only if your model and memory can handle it.
- Press **Test it** to send one tiny request and check the model answers.

**Change the model for one session** with the small chip under a session's title. It takes effect from your next message, the conversation comes along, and each reply says which model wrote it.

### Free cloud models (OpenRouter)

Local models keep everything on your computer. If you want a stronger model for free, you can use [OpenRouter](https://openrouter.ai):

1. Create an account and an API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. In **Settings → Model**, paste the key into **API key** and press **Save model**. The key is stored only on this computer and is never shown back.
3. Open **Settings → OpenRouter free models → Show free models**. **Automatic** (recommended) picks a free model that is answering right now. Press **Test**, then **Use**.

**Think before using it:** with a cloud model, what you write in sessions (and what the guide recalls from earlier ones) leaves your computer, and free providers may keep it or learn from it. Selfward asks before switching a session to a cloud model. If you see "no endpoints match your data policy", allow free models in your OpenRouter privacy settings. Free models are often busy or gated; if one fails, pick Automatic or another.

Memory, the Inner Map, Insights, mood and the crisis check always run on your computer. The Narrative and dream readings ask before sending anything to a cloud model.

## Voice (reading aloud and talking)

Reading replies aloud and talking hands-free use the natural voice (Kokoro) and speech listening (Whisper) from SmartWard's folder, so nothing is downloaded twice. If you do not have SmartWard installed, set these up once from a SmartWard checkout:

```bash
sudo apt install -y libespeak-ng1 espeak-ng-data alsa-utils
~/SmartWardApp/tts/setup.sh     # about 480 MB
~/SmartWardApp/stt/setup.sh     # about 500 MB
```

Selfward finds `~/SmartWardApp` by itself, or the folder named in the `SELFWARD_VOICE_HOME` environment variable (a folder that contains `tts/` and `stt/`). The voice server starts by itself when needed.

- **Read aloud** appears under each reply.
- **Hands-free**: press the microphone in a session, or **Talk** on the Sessions list. It listens, sends each sentence when you pause, reads the answer, and listens again. Say "stop" to interrupt and "stop listening" to finish. It never listens while it speaks, and the microphone closes when you leave the session, lock the app or hide the window.
- **Settings → Voice** shows what is installed, lets you choose the voice engine, a voice for each guide, and the speaking rate.

## Your data and privacy

- Everything is in one database: `~/.local/share/selfward/selfward.db` (owner-only permissions). Logs: `~/.local/state/selfward/api.log`.
- **Settings → Privacy & lock**: set a PIN to lock the window (it protects the screen, not the file on disk). After five wrong PINs it makes you wait.
- **Settings → Your data**: export as Markdown or JSON, make an **encrypted backup** (needs a passphrase of 8+ characters; keep it, it cannot be recovered), restore one, or **erase everything**. Backups leave out your API key, PIN and remote-access settings.
- **Settings → What Selfward remembers**: see, add to, forget, or switch off the memories kept across sessions.
- Deleting a session also deletes its messages, notes, dreams, graph and memories. A Narrative already written from it is not edited; edit or delete it on its page.

## The other pages

- **Inner Map**: the feelings, people, beliefs and events you write about, and how they connect. Built from your own words on this computer, with no model.
- **Insights**: highlights, dreams (saved when you tell one in a session) and notes.
- **Narrative**: a story your model writes from your notes, dreams and kept memories. Press **Write the story** or **Update**. It can take minutes on a laptop.
- **Mood**: tap how you feel, optionally with a word or two, and watch the line of your days.

## Open it from your phone (Tailscale)

This reaches your laptop over your own private network. It is never on the public internet. The laptop must be on and running Selfward.

1. Install [Tailscale](https://tailscale.com/download) on the laptop and on your phone, and sign in to the same account on both. In the Tailscale admin page, turn on **MagicDNS** and **HTTPS certificates**.
2. In Selfward, open **Settings → Remote access (phone)**. Enter your Tailscale login (only that account may connect) and a **remote passphrase** (8+ characters, separate from the PIN), and press Save.
3. Publish Selfward to your own devices. In a terminal on the laptop:

```bash
tailscale serve --bg --https=8443 127.0.0.1:8100
```

Use the `--https=8443` port so SmartWard (which uses the default 443) is not disturbed. Never use `tailscale funnel`: that is public.

4. Tick **Allow my phone to connect**. A QR code and the address appear (`https://<laptop>.<tailnet>.ts.net:8443`).
5. On the phone, with Tailscale connected, scan the code or open the address, sign in with the passphrase, then **Add to Home Screen** (iPhone: Share → Add to Home Screen; Android: menu → Install app).

What to know:

- It is **off by default**. Turning it off, or changing the passphrase, signs every phone out. Settings shows the signed-in phones and lets you sign any of them out.
- A phone stays signed in for **7 days after you last use it**. If a phone is lost, sign it out from the laptop at once.
- A signed-in phone can do everything in the app, including settings, backup, export and erase. Only managing remote access and the laptop's own microphone stay on the laptop.
- Talking from the phone uses the phone's microphone; the laptop's Whisper turns it into text. Nothing goes to Apple or Google.
- The laptop must be awake. **Keep this laptop awake while remote access is on** (in the same card) stops it sleeping when idle, but closing the lid still suspends it.

## Updating

```bash
cd ~/SelfwardApp
git pull
python3 -m pip install --break-system-packages -r requirements.txt
scripts/build_ui.sh          # always
scripts/build_native.sh      # only if the window itself changed (frontend/src-tauri)
```

Then quit Selfward from its tray icon and open it again. An open window that was left running across an update reloads itself.

## Starting, stopping, and starting at login

- Closing the window keeps Selfward running in the **tray**. Use the tray icon's **Open**, **Lock now** or **Quit** (Quit stops the background service too).
- **Settings → This computer** can start Selfward when you log in (hidden in the tray).
- From a terminal: `~/SelfwardApp/bin/start_selfward.sh` to start, `~/SelfwardApp/bin/start_selfward.sh stop` to stop.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| "Ollama isn't running" banner | Start it: `ollama serve` (or `sudo systemctl start ollama`). |
| "That model isn't installed" | `ollama pull llama3.2:3b` (or choose another model in Settings). |
| Replies are very slow | A larger model or a long chat takes minutes on a CPU. Try the 3B model, a shorter chat, or a free OpenRouter model. |
| A white page after an update | Press Ctrl+R. It also reloads by itself once. If it keeps happening, the details are in the log. |
| "Selfward's backend isn't running" | Quit from the tray icon and open it again. The log is `~/.local/state/selfward/api.log`. |
| No sound when reading aloud | Check Settings → Voice. If the natural voice is not installed, the browser voice is used. |
| Hands-free stays open ("Hearing you…") for a long time | Usually the room: a fan, music or a vacuum that came on while you were quiet. It now lets go within a few seconds, but a very noisy room still confuses it; move the microphone or quiet the noise. Also see the next row. |
| Hands-free cuts you off, or waits too long after you stop | Settings → Voice → **Pause that ends your turn** (0.3 to 1.5 s, 0.8 by default). Shorter is snappier, longer waits while you think. It applies the next time you switch hands-free on. After the pause, turning speech into text takes a few seconds on a laptop; a smaller speech model is faster: `MODEL=base.en ~/SmartWardApp/stt/setup.sh`. |
| Hands-free says speech input isn't installed | Run `~/SmartWardApp/stt/setup.sh` and `sudo apt install alsa-utils`. |
| The phone can't connect | Is the laptop awake and Selfward running? Tailscale connected on both? `tailscale serve status` should show port 8443 pointing at 127.0.0.1:8100. |
| "This Tailscale account isn't allowed" | The login in Settings → Remote access must be the account your phone uses. |
| Free OpenRouter model fails | Use **Automatic**, or press Test to find one that answers. Check your key and OpenRouter privacy settings. |

## Where things are

| | Selfward |
| --- | --- |
| Program folder | `~/SelfwardApp` |
| Your journal | `~/.local/share/selfward/selfward.db` |
| Log | `~/.local/state/selfward/api.log` |
| Address | `http://localhost:8100` (and `:8443` over Tailscale) |
| Menu entry | `~/.local/share/applications/com.mikefink.selfward.desktop` |

To remove Selfward: quit it, delete `~/SelfwardApp`, delete the menu entry, and (only if you also want to delete your journal) `~/.local/share/selfward`. Make an encrypted backup first if you might want it back.
