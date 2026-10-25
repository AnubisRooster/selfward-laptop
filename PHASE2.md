# Selfward for Linux: phase 2 plan

Phase 1 gave us guides, safety, memory, lock and backup. Phase 2 ports what the iPhone app builds *from* the conversations.
Each step below is one commit, ends with tests (stubbed model, temp data folder) and a real check against Ollama, and is independent enough to stop after.

## Step 1. Knowledge graph and Inner Map (DONE) (iPhone: GraphService, GraphExportService, DashboardService, GraphVisualizationView)
- **Tables:** `graph_nodes(id, session_id, type, label, strength, props)` and `graph_edges(id, session_id, source, target, type, weight)`.
- **Extraction:** the phone uses keyword lists (emotions, "my mother/boss…", belief phrases like "I always…", life events) and wires edges person/event → TRIGGERS → emotion, emotion → CAUSES → belief, co-occurring emotions. Port it as plain code, run after each turn (no model call). Done, with three deliberate changes: whole-word matching, variants merged, and the phone's cycle list dropped (it only reported artefacts of the linking rules; the map shows the strongest connections instead), with the "recent messages still in play" window. Upgrade path, not in this step: a model pass for entities the lists miss.
- **UI:** an "Inner Map" tab: force-directed graph (`react-force-graph-2d` is already a dependency in the shell), filter by type and by session, click a node for its sessions and neighbours, stats cards (top emotions, people, beliefs). Export GraphML and Cytoscape JSON like the phone.
- **Privacy:** graph stays in the same SQLite file; erased and backed up with the rest (add the tables to `TABLES`).
- Risk: low. Roughly 400 lines of Python, one view.

## Step 2. Dreams and notes (DONE; the phone's canned per-approach insight paragraphs and SOAP/DAP note templates were left out, as clinician-facing text that doesn't suit a self-reflection app) (iPhone: InsightCaptureService, DreamService, NoteService, InsightService, InsightsView)
- **Dream capture:** the cue phrases ("I had a dream", "nightmare"…) in a user message create a dream record (narrative, feelings, symbols) and badge the reply, as on the phone. Optional "Interpret" button that asks the model for a Jungian-style reading, clearly labelled as reflection, not diagnosis.
- **Notes:** one auto "Session summary" note per session (updated each turn from the graph) plus manual notes. Insights tab lists dreams, notes and patterns with search.
- **Message badges** in the chat view (moon for dream, note icon), matching the phone.
- Needs Step 1 for the summary note. Risk: low.

## Step 3. Global memory and long-chat summaries (DONE; adds a window setting passed to Ollama as num_ctx, a plausibility check on recaps, and a switch plus a list in Settings) (iPhone: GlobalMemoryService, ConversationCompactor)
- **Global memory:** tiered keyword importance (0.45 / 0.65 / 0.85) promotes personally significant statements to a durable memory that is always eligible for recall, ranked by similarity and importance. View and delete them in Settings (the user must be able to see and remove what the app "remembers").
- **Rolling summary:** when history exceeds the budget, summarise the older turns with the model into `sessions.summary` and keep recent turns verbatim, replacing today's plain truncation. Fall back to truncation if the summariser fails.
- Risk: medium (prompt quality with a 3B model). Tests with a stubbed summariser, then a real long-chat run.

## Step 4. Narrative page (DONE) (iPhone: NarrativeService, NarrativeView, NarrativeExportService)
- A life story written by the model from session notes, dream analyses and global memories, updated incrementally with a watermark (only new material since the last build), at most once an hour unless asked, in the voice of the guide of the latest session.
- Sensitive material is never sent to a cloud model: if the chat model is a cloud one, narrative building uses the local model or asks first. Export as Markdown.
- Needs Steps 2 and 3. Risk: medium (long prompts on a small model; test with `qwen2.5:7b` if installed).

## Step 5. Voice (iPhone: SpeechService, TTSCoordinator, VoiceConversationController)
- **Reuse SmartWard's stack instead of rewriting:** Kokoro read-aloud server (`tts/`, port 8880) and Whisper microphone listener (`stt/`), with the hands-free loop (`useHandsFree.ts`, `voiceInput.ts`, `voiceIntent.ts`).
- **Choice to make before starting:** share SmartWard's already installed servers (nothing extra to download, but Selfward then needs SmartWard's folder) or install a second copy (about 1 GB). Recommended: make the folder a setting and default to SmartWard's if present.
- **Per-guide voices** (therapist, companion, advisor each keep a voice) as on the phone.
- **Safety:** the crisis check already runs on text in `chat.send`, so spoken input gets the same protection; crisis resources are read aloud. The microphone is only open while hands-free is on and closes when the window hides or locks (as in SmartWard).
- Needs real microphone testing by you. Risk: medium.

## Smaller items to fold in
- Reminder notification ("time to check in") through the tray shell.
- Free OpenRouter model picker (copy from SmartWard's `sw/openrouter.py`).
- Optional model pass for graph entities (after Step 1).
- A real tray/dock check of the installed launcher.

## Suggested order and checkpoints
1 → 2 → 3 → 4 → 5, stopping after each for you to try it. Steps 1 to 3 can be built in one sitting; Steps 4 and 5 want your testing (narrative quality, microphone).
