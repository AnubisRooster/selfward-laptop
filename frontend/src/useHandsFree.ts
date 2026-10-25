import { useCallback, useEffect, useRef, useState } from 'react';
import { errText, get, http, post } from './api';
import { BrowserMic } from './browserMic';
import { onPhone } from './device';
import { encodeWav } from './wav';
import { speech, useSpeech } from './hooks';
import { toast } from './feedback';
import { parseVoice, plainForSpeech } from './voiceInput';
import { takeAudioChat } from './voiceIntent';

export type HandsFreeStatus = 'off' | 'loading' | 'listening' | 'hearing' | 'thinking' | 'speaking';

interface Args {
  running: boolean;                 // the guide is answering
  messages: any[];
  persona: string;                  // who is speaking: therapist, companion or spiritual (each can have its own voice)
  send: (text: string) => Promise<void>;
  stop: () => Promise<void>;        // cancel the answer in progress
}

/**
 * Hands-free: listens (on this computer, through the local speech model), sends each sentence when you pause, reads the answer aloud,
 * then listens again. It never listens while it speaks, and it switches itself off when the window is hidden, the app locks or the session is left.
 * The microphone is open only while this is on. What you say goes through the same crisis check as typed text.
 */
export function useHandsFree(a: Args) {
  const [on, setOn] = useState(false); const [server, setServer] = useState<string>('off'); const [error, setError] = useState('');
  const sp = useSpeech();
  const cursor = useRef(0); const voiceTurn = useRef(false); const wasRunning = useRef(false); const latest = useRef(a); latest.current = a;
  const wasSpeaking = useRef(false); const pauseMs = useRef(800);
  const mic = useRef<BrowserMic | null>(null); const queue = useRef<Promise<void>>(Promise.resolve()); const transcribing = useRef(0); const [busy, setBusy] = useState(false);

  useEffect(() => { if (takeAudioChat()) setOn(true); }, []);

  const turnOff = useCallback(() => { setOn(false); speech.stop(); }, []);
  useEffect(() => () => { speech.stop(); if (!onPhone) post('/voice/stop').catch(() => {}); }, []);          // leaving the session closes the microphone

  // The microphone follows `on`.
  useEffect(() => {
    if (!on) { if (!onPhone) post('/voice/stop').catch(() => {}); setServer('off'); return; }
    let alive = true; setError(''); setServer('loading');
    if (onPhone) {            // the phone's own microphone: each sentence is cut out on the phone and sent to the laptop to be turned into text
      const m = new BrowserMic(pauseMs.current); mic.current = m;
      const sendClip = (audio: Float32Array) => {
        transcribing.current++; setBusy(true);
        queue.current = queue.current.then(async () => {
          try { const r = await http.post('/voice/transcribe', encodeWav(audio), { headers: { 'Content-Type': 'audio/wav' }, timeout: 120000 }); if (alive && r.data.text) handle(r.data.text); }
          catch (e) { if (alive) setError(errText(e)); }
          finally { transcribing.current--; if (alive && transcribing.current === 0) setBusy(false); }
        });
      };
      m.start(st => alive && setServer(st), sendClip).catch(e => { if (alive) { setError(e?.name === 'NotAllowedError' ? 'The microphone is blocked. Allow it for this site in the phone’s settings, then try again.' : errText(e)); setOn(false); } });
      const hidePhone = () => { if (document.hidden) turnOff(); };
      document.addEventListener('visibilitychange', hidePhone); window.addEventListener('sf-lock', turnOff);
      return () => { alive = false; m.stop(); mic.current = null; document.removeEventListener('visibilitychange', hidePhone); window.removeEventListener('sf-lock', turnOff); };
    }
    (async () => {
      try { await post('/voice/start'); const first = await get('/voice/poll', { after: 0 }); cursor.current = first.seq; }
      catch (e) { if (alive) { setError(errText(e)); setOn(false); } return; }
    })();
    const timer = setInterval(async () => {
      try {
        const r = await get('/voice/poll', { after: cursor.current });
        if (!alive) return;
        cursor.current = r.seq; setServer(r.ready ? r.state : 'loading');
        if (r.error) { setError(r.error); setOn(false); return; }
        for (const e of r.events) if (e.type === 'text') handle(e.text);
      } catch { /* the next poll will try again */ }
    }, 400);
    const hide = () => { if (document.hidden) turnOff(); };
    document.addEventListener('visibilitychange', hide); window.addEventListener('sf-lock', turnOff);
    return () => { alive = false; clearInterval(timer); document.removeEventListener('visibilitychange', hide); window.removeEventListener('sf-lock', turnOff); post('/voice/stop').catch(() => {}); };
  }, [on]);

  function handle(said: string) {
    const { running, send, stop } = latest.current;
    const cmd = parseVoice(said);
    if (cmd.kind === 'stop-listening') { toast.info('Hands-free is off.'); turnOff(); }
    else if (cmd.kind === 'stop') { speech.stop(); if (running) stop(); }
    else if (running) toast.info(`Heard “${cmd.text}”, but the guide is still answering. Say “stop” to interrupt.`);
    else { voiceTurn.current = true; send(cmd.text); }
  }

  // Never listen to our own voice: pause while reading, resume a moment after.
  useEffect(() => {
    if (!on) { wasSpeaking.current = false; return; }
    if (sp.on && !wasSpeaking.current) { if (onPhone) mic.current?.pause(); else post('/voice/pause').catch(() => {}); }
    if (!sp.on && wasSpeaking.current) { if (onPhone) mic.current?.resume(); else post('/voice/resume').catch(() => {}); }
    wasSpeaking.current = sp.on;
  }, [sp.on, on]);

  // Read the answer to a spoken message (including the crisis lines, which are the reply when the words call for them).
  useEffect(() => {
    if (wasRunning.current && !a.running && voiceTurn.current && on) {
      voiceTurn.current = false;
      const last = [...a.messages].reverse().find(m => m.role === 'assistant');
      if (last?.content && !last.meta?.cancelled) speech.speak(plainForSpeech(last.content), 1, '', a.persona);
    }
    wasRunning.current = a.running;
  }, [a.running, on]);

  // A crisis reply is answered at once (no model run): read it as soon as it appears.
  useEffect(() => {
    if (!on || !voiceTurn.current || a.running) return;
    const last = a.messages[a.messages.length - 1];
    if (last?.role === 'assistant' && last.meta?.safety && last.content) { voiceTurn.current = false; speech.speak(plainForSpeech(last.content), 1, '', a.persona); }
  }, [a.messages.length, on]);

  const status: HandsFreeStatus = !on ? 'off' : sp.on ? 'speaking' : a.running || busy ? 'thinking' : server === 'loading' ? 'loading' : server === 'hearing' ? 'hearing' : 'listening';
  return { on, status, error, toggle: () => { if (on) turnOff(); else { speech.unlock(); setError(''); get('/settings').then(st => { if (Number.isFinite(st?.voice_pause_ms)) pauseMs.current = st.voice_pause_ms; }).catch(() => {}).finally(() => setOn(true)); } }, turnOff };
}
