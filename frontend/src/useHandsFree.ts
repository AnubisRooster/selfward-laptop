import { useCallback, useEffect, useRef, useState } from 'react';
import { errText, get, post } from './api';
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
  const wasSpeaking = useRef(false);

  useEffect(() => { if (takeAudioChat()) setOn(true); }, []);

  const turnOff = useCallback(() => { setOn(false); speech.stop(); }, []);
  useEffect(() => () => { speech.stop(); post('/voice/stop').catch(() => {}); }, []);          // leaving the session closes the microphone

  // The microphone follows `on`.
  useEffect(() => {
    if (!on) { post('/voice/stop').catch(() => {}); setServer('off'); return; }
    let alive = true; setError(''); setServer('loading');
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
    if (sp.on && !wasSpeaking.current) post('/voice/pause').catch(() => {});
    if (!sp.on && wasSpeaking.current) post('/voice/resume').catch(() => {});
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

  const status: HandsFreeStatus = !on ? 'off' : sp.on ? 'speaking' : a.running ? 'thinking' : server === 'loading' ? 'loading' : server === 'hearing' ? 'hearing' : 'listening';
  return { on, status, error, toggle: () => (on ? turnOff() : (setError(''), setOn(true))), turnOff };
}
