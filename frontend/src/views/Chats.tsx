import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ago, del, errText, get, patch, post } from '../api';
import { speech, useLoad, useNav } from '../hooks';
import { Badge, Btn, Empty, Err, Field, Modal, Spin, inputCls, cx } from '../ui';
import { ask, toast } from '../feedback';
import { useHandsFree } from '../useHandsFree';
import { plainForSpeech } from '../voiceInput';
import { wantAudioChat } from '../voiceIntent';
import { Archive, Cloud, Cpu, Mic, MicOff, Moon, NotebookPen, Square, Trash2, Volume2 } from 'lucide-react';

export const shortModel = (m: string) => (m || '').replace(/^ollama_chat\//, '').replace(/^openrouter\/openrouter\/free$/, 'OpenRouter · automatic free').replace(/^openrouter\//, 'OpenRouter · ').replace(/:free$/, '');
const isLocalModel = (m: string) => (m || '').startsWith('ollama');
const label = (m: string) => m.replace(/_/g, ' ').replace(/\b(cbt|dbt|act|ifs)\b/i, s => s.toUpperCase()).replace(/^./, c => c.toUpperCase());

function NewSession({ catalog, settings, onClose, onCreated }: { catalog: any; settings: any; onClose: () => void; onCreated: (id: number) => void }) {
  const [persona, setPersona] = useState<string>(settings.default_persona || 'therapist');
  const [modality, setModality] = useState<string>(settings.default_modality || 'integrated');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { const r = await post('/sessions', { persona, modality }); onCreated(r.id); } catch (e) { setErr(errText(e)); setBusy(false); } };
  return (
    <Modal title="New session" onClose={onClose}>
      <div className="space-y-4">
        <div role="radiogroup" aria-label="Who to talk with" className="space-y-2">
          {catalog.personas.map((p: any) => (
            <button key={p.id} role="radio" aria-checked={persona === p.id} onClick={() => setPersona(p.id)}
              className={cx('block w-full rounded-lg border px-3 py-2 text-left', persona === p.id ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
              <div className="text-sm font-medium">{(settings[p.id + '_name'] || p.default_name || p.label)}<span className="ml-2 text-xs font-normal text-zinc-500">{p.label}</span></div>
              <div className="text-xs text-zinc-500">{p.blurb}</div></button>))}
        </div>
        {persona === 'therapist' && <Field label="Approach" hint={catalog.modalities.find((m: any) => m.id === modality)?.description}>
          <select className={inputCls} value={modality} onChange={e => setModality(e.target.value)}>{catalog.modalities.map((m: any) => <option key={m.id} value={m.id}>{label(m.id)}</option>)}</select></Field>}
        <Err>{err}</Err>
        <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={go} loading={busy}>Start</Btn></div>
      </div>
    </Modal>
  );
}

function ModelDialog({ s, onClose, onChanged }: { s: any; onClose: () => void; onChanged: () => void }) {
  const { data: models } = useLoad<any>('/models'); const { data: settings } = useLoad<any>('/settings');
  const [free, setFree] = useState<any[] | null>(null); const [loading, setLoading] = useState(false); const [err, setErr] = useState(''); const [busy, setBusy] = useState(''); const [other, setOther] = useState('');
  const current: string = s.model_effective; const own: string = s.model || '';
  const loadFree = async () => { setLoading(true); setErr(''); try { setFree((await get('/openrouter/models')).models); } catch (e) { setErr(errText(e)); } setLoading(false); };
  const apply = async (model: string) => {
    setErr('');
    const target = model || models?.current || '';
    if (!isLocalModel(target)) {
      if (!settings?.api_key) { setErr('A cloud model needs an API key. Save one in Settings → Model first.'); return; }
      if (isLocalModel(current) && !await ask.confirm({ title: 'Send this session to a cloud model?', body: `From the next message, what you write here goes to ${shortModel(target)}’s provider, together with the earlier messages in this session, a recap of them, and anything Selfward recalls from other sessions. Free providers may keep it. Replies already written stay as they are, and you can switch back any time.`, confirmLabel: 'Switch' })) return;
      setBusy(model || 'default');
      try { await post('/models/test', { model: target }); } catch (e) { setErr(`That model didn’t answer, so the session was not changed. ${errText(e)}`); setBusy(''); return; }
    }
    setBusy(model || 'default');
    try { await patch(`/sessions/${s.id}`, { model }); toast.ok(model ? `Replies now come from ${shortModel(model)}.` : 'This session follows the default model again.'); onChanged(); onClose(); } catch (e) { setErr(errText(e)); }
    setBusy('');
  };
  const row = (id: string, name: string, sub: string, value: string, local: boolean) => {
    const active = value === own || (value === '' && own === '');
    return <li key={id}><button disabled={!!busy || active} onClick={() => apply(value)} className={cx('flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm', active ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
      <span className="min-w-0"><span className="flex items-center gap-1.5">{local ? <Cpu size={13} aria-hidden /> : <Cloud size={13} aria-hidden />}<span className="truncate">{name}</span>{active && <Badge tone="indigo">in use</Badge>}</span><span className="block truncate text-xs text-zinc-500">{sub}</span></span>
      {busy === (value || 'default') && <Spin />}</button></li>;
  };
  const installed: string[] = (models?.ollama || []).filter((n: string) => !/embed/i.test(n));
  return (
    <Modal title="Model for this session" onClose={onClose}>
      <div className="space-y-3">
        <div className="text-xs text-zinc-500">Choose who writes the replies from your next message on. Earlier replies stay as they are (each says which model wrote it). This only changes this session; the default for new ones is in Settings.</div>
        <Err>{err}</Err>
        <ul className="space-y-1.5">
          {row('default', 'Follow the default', models ? shortModel(models.current) : '', '', isLocalModel(models?.current || 'ollama'))}
          {installed.map(n => row(n, n, 'On this computer', 'ollama_chat/' + n, true))}
        </ul>
        {!models?.ollama_up && <div className="text-xs text-amber-300">Ollama isn’t running, so models on this computer can’t be listed.</div>}
        <div><div className="mb-1 text-xs font-medium text-zinc-400">Free models on OpenRouter (your sessions leave this computer)</div>
          {free === null ? <Btn small onClick={loadFree} loading={loading}>Show free models</Btn> :
            <ul className="max-h-56 space-y-1.5 overflow-y-auto">{free.map(m => row(m.id, m.name, `${m.id}${m.context ? ` · ${Math.round(m.context / 1000)}k context` : ''}`, m.model, false))}</ul>}</div>
        <Field label="Another model id (advanced)" hint="A litellm id, for example anthropic/claude-sonnet-4-5 or gpt-4o. It uses the API key saved in Settings."><div className="flex gap-2"><input className={inputCls} value={other} onChange={e => setOther(e.target.value)} spellCheck={false} placeholder="provider/model" /><Btn onClick={() => apply(other.trim())} disabled={!other.trim() || !!busy}>Use</Btn></div></Field>
      </div>
    </Modal>
  );
}

function Bubble({ m, who, sessionId, persona }: { m: any; who: string; sessionId: number; persona: string }) {
  const { go } = useNav(); const cap = m.meta?.captured || {};
  const mine = m.role === 'user'; const safety = m.meta?.safety; const failed = m.meta?.error;
  return (
    <div className={cx('flex', mine ? 'justify-end' : 'justify-start')}>
      <div className={cx('max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px]', mine ? 'bg-indigo-600 text-white' : safety === 'crisis' || safety === 'method' ? 'border border-amber-700 bg-amber-950/40 text-amber-50' : failed ? 'border border-red-900 bg-red-950/30 text-red-200' : 'bg-zinc-800 text-zinc-100')}>
        {!mine && <div className="mb-0.5 text-[11px] font-medium text-zinc-400">{who}{m.meta?.model && <span className="ml-2 font-normal text-zinc-500" title={m.meta.model}>{shortModel(m.meta.model)}</span>}{safety && <span className="ml-2"><Badge tone="amber">{safety === 'boundary' ? 'kept within safe limits' : 'support resources'}</Badge></span>}</div>}
        {m.meta?.streaming && !m.content ? <span className="text-zinc-400">…</span> :
          <div className="prose-sw !text-inherit [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:ml-5 [&_ul]:list-disc [&_ol]:ml-5 [&_ol]:list-decimal"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown></div>}
        {(cap.dream || cap.note) && <div className="mt-1.5 flex flex-wrap gap-1.5">
          {cap.dream && <button onClick={() => go('insights', { sessionId })} className="flex items-center gap-1 rounded-full bg-zinc-700/60 px-2 py-0.5 text-[11px] hover:bg-zinc-700" title="This sounded like a dream, so it was saved. See it in Insights."><Moon size={11} aria-hidden /> Dream saved</button>}
          {cap.note && <button onClick={() => go('insights', { sessionId })} className="flex items-center gap-1 rounded-full bg-zinc-700/60 px-2 py-0.5 text-[11px] hover:bg-zinc-700" title="A summary note for this session was started. See it in Insights."><NotebookPen size={11} aria-hidden /> Note started</button>}</div>}
        {!mine && m.content && !m.meta?.streaming && speech.supported && <button className="mt-1 flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300 focus:text-zinc-300" onClick={() => speech.speak(plainForSpeech(m.content), 1, '', persona)}><Volume2 size={11} aria-hidden /> Read aloud</button>}
        {m.meta?.cancelled && <div className="mt-1 text-[11px] text-zinc-400">stopped</div>}
      </div>
    </div>
  );
}

function Conversation({ id, catalog, onGone }: { id: number; catalog: any; onGone: () => void }) {
  const { data: s, error, reload } = useLoad<any>(`/sessions/${id}`, undefined, 1000);
  const [text, setText] = useState(''); const [err, setErr] = useState(''); const [sending, setSending] = useState(false);
  const [pickModel, setPickModel] = useState(false);
  const end = useRef<HTMLDivElement>(null); const box = useRef<HTMLTextAreaElement>(null);
  const running = s?.status === 'running';
  const n = s?.messages?.length || 0; const last = s?.messages?.[n - 1]?.content?.length || 0;
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [n, last]);
  useEffect(() => { setText(''); setErr(''); box.current?.focus(); }, [id]);
  useEffect(() => { if (!running) box.current?.focus(); }, [running]);
  const sendText = async (t: string) => {
    t = t.trim(); if (!t) return;
    setSending(true); setErr('');
    try { await post(`/sessions/${id}/send`, { text: t }); await reload(); } catch (e) { setErr(errText(e)); }
    setSending(false);
  };
  const send = async () => { const t = text.trim(); if (!t || running || sending) return; setText(''); await sendText(t); };
  const stopAnswer = async () => { await post(`/sessions/${id}/cancel`); reload(); };
  const hf = useHandsFree({ running: !!running, messages: s?.messages || [], persona: s?.persona || '', send: sendText, stop: stopAnswer });
  if (error && !s) return <Empty icon="⚠" title="Couldn’t open this session">{error}</Empty>;
  if (!s) return null;
  const set = async (body: any) => { try { await patch(`/sessions/${id}`, body); reload(); } catch (e) { toast.error(errText(e)); } };
  const rename = async () => { const t = await ask.prompt({ title: 'Rename session', initial: s.title, confirmLabel: 'Save' }); if (t?.trim()) set({ title: t.trim() }); };
  const remove = async () => {
    if (!await ask.confirm({ title: 'Delete this session?', body: 'Its messages, notes, dreams and what it taught the memory are removed from this computer. If you have written your Narrative, it may still mention what was in this session: edit or reset it on its page. This can’t be undone.', confirmLabel: 'Delete', danger: true })) return;
    try { await del(`/sessions/${id}`); onGone(); } catch (e) { toast.error(errText(e)); }
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
        <button className="mr-1 text-zinc-400 hover:text-zinc-100 md:hidden" onClick={onGone} aria-label="Back to sessions">←</button>
        <div className="min-w-0 flex-1"><button onClick={rename} className="block max-w-full truncate text-left text-sm font-semibold hover:underline" title="Rename">{s.title}</button>
          <div className="flex flex-wrap items-center gap-x-2 text-xs text-zinc-500"><span>{s.persona_name}{s.persona === 'therapist' && ` · ${label(s.modality)}`}</span>
            <button onClick={() => setPickModel(true)} title="Change the model that writes the replies in this session" className="flex items-center gap-1 rounded-full border border-zinc-700 px-2 py-0.5 hover:bg-zinc-800 hover:text-zinc-200">{s.model_is_local ? <Cpu size={11} aria-hidden /> : <Cloud size={11} aria-hidden />}{shortModel(s.model_effective)}{!s.model && <span className="text-zinc-600"> · default</span>}</button></div></div>
        {s.persona === 'therapist' && <select aria-label="Approach" className={cx(inputCls, '!w-auto !py-1 text-xs')} value={s.modality} onChange={e => set({ modality: e.target.value })}>{catalog.modalities.map((m: any) => <option key={m.id} value={m.id}>{label(m.id)}</option>)}</select>}
        <Btn small kind={hf.on ? 'primary' : 'ghost'} title={hf.on ? 'Hands-free is on: turn it off' : 'Hands-free: talk to the guide and hear the answers'} label="Hands-free" onClick={hf.toggle}>{hf.on ? <Mic size={14} aria-hidden /> : <MicOff size={14} aria-hidden />}</Btn>
        <Btn small kind="ghost" title="Archive" label="Archive" onClick={async () => { await set({ archived: true }); onGone(); }}><Archive size={14} aria-hidden /></Btn>
        <Btn small kind="ghost" title="Delete" label="Delete" onClick={remove}><Trash2 size={14} aria-hidden /></Btn>
      </header>
      {pickModel && <ModelDialog s={s} onClose={() => setPickModel(false)} onChanged={reload} />}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {n === 0 && <Empty icon="✎" title={`Say hello to ${s.persona_name}`}>Whatever is on your mind. This stays on this computer; the model runs here unless you chose a cloud model in Settings.</Empty>}
        {s.messages.map((m: any) => <Bubble key={m.id} m={m} who={s.persona_name} sessionId={id} persona={s.persona} />)}
        <div ref={end} />
      </div>
      <div className="border-t border-zinc-800 p-3">
        <Err>{err || hf.error}</Err>
        {hf.on && <div role="status" className="mb-2 flex items-center gap-2 rounded-lg border border-emerald-800 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-200"><Mic size={12} aria-hidden /> {{ off: '', loading: 'Getting the microphone ready…', listening: 'Listening. Just talk; pause when you are done.', hearing: 'Hearing you…', thinking: `${s.persona_name} is answering…`, speaking: `${s.persona_name} is speaking. I am not listening meanwhile.` }[hf.status]}
          <span className="text-emerald-300/70">Everything is heard and spoken on this computer. Say “stop” to interrupt, “stop listening” to finish.</span>
          {hf.status === 'speaking' && <button type="button" className="ml-auto rounded border border-emerald-700 px-2 py-0.5 hover:bg-emerald-900/40" onClick={() => speech.stop()}>Stop talking</button>}</div>}
        <div className="flex items-end gap-2">
          <textarea ref={box} rows={2} value={text} onChange={e => setText(e.target.value)} aria-label="Message" placeholder={running ? `${s.persona_name} is answering…` : 'Write here. Enter sends, Shift+Enter adds a line.'}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} className={cx(inputCls, 'resize-none')} />
          {running ? <Btn onClick={async () => { await post(`/sessions/${id}/cancel`); reload(); }} label="Stop"><Square size={13} aria-hidden /> Stop</Btn>
            : <Btn kind="primary" onClick={send} disabled={!text.trim()} loading={sending}>Send</Btn>}
        </div>
        <div className="mt-1.5 text-[11px] text-zinc-500">Selfward is a reflection tool, not a licensed therapist. In a crisis use “Get help now”.</div>
      </div>
    </div>
  );
}

export default function Chats() {
  const { sessionId, go } = useNav();
  const [showArchived, setShowArchived] = useState(false);
  const { data: list, reload } = useLoad<any[]>('/sessions', { archived: showArchived }, 4000);
  const { data: catalog } = useLoad<any>('/catalog');
  const { data: settings } = useLoad<any>('/settings');
  const [creating, setCreating] = useState(false);
  const open = (id: number | null) => go('chats', { sessionId: id });
  return (
    <div className="flex h-full">
      <section className={cx('flex min-h-0 w-full flex-col border-zinc-800 md:w-80 md:shrink-0 md:border-r', sessionId != null && 'hidden md:flex')}>
        <div className="flex items-center justify-between border-b border-zinc-800 p-3"><h1 className="text-lg font-semibold">{showArchived ? 'Archived' : 'Sessions'}</h1>
          <div className="flex gap-1.5"><Btn small title="Start a new session and just talk: it listens and speaks the answers" disabled={!catalog || !settings} onClick={async () => { try { const r = await post('/sessions', { persona: settings.default_persona, modality: settings.default_modality }); wantAudioChat(); reload(); open(r.id); } catch (e) { toast.error(errText(e)); } }}><Mic size={13} aria-hidden /> Talk</Btn><Btn small kind="ghost" onClick={() => setShowArchived(a => !a)}>{showArchived ? 'Back' : 'Archive'}</Btn><Btn small kind="primary" disabled={!catalog || !settings} onClick={() => setCreating(true)}>+ New</Btn></div></div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(list || []).length === 0 && <Empty icon="✎" title={showArchived ? 'Nothing archived' : 'No sessions yet'}>{showArchived ? '' : 'Start one when you are ready. You choose who to talk with, and for the therapist, which approach.'}</Empty>}
          {(list || []).map(c => (
            <div key={c.id} role="button" tabIndex={0} onClick={() => open(c.id)} onKeyDown={e => e.key === 'Enter' && open(c.id)}
              className={cx('cursor-pointer border-b border-zinc-800/60 px-3 py-2.5 hover:bg-zinc-900', sessionId === c.id && 'bg-zinc-900')}>
              <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{c.title}</span><span className="shrink-0 text-[11px] text-zinc-500">{ago(c.updated)}</span></div>
              <div className="mt-0.5 flex items-center gap-1.5"><Badge tone="indigo">{c.persona_name}</Badge>{c.persona === 'therapist' && <Badge>{label(c.modality)}</Badge>}</div>
              {c.preview && <div className="mt-1 truncate text-xs text-zinc-500">{c.preview}</div>}
            </div>))}
        </div>
      </section>
      <section className={cx('min-h-0 min-w-0 flex-1', sessionId == null && 'hidden md:block')}>
        {sessionId == null ? <Empty icon="✎" title="Pick a session or start a new one">Everything you write stays in a database on this computer.</Empty>
          : catalog && <Conversation key={sessionId} id={sessionId} catalog={catalog} onGone={() => { open(null); reload(); }} />}
      </section>
      {creating && catalog && settings && <NewSession catalog={catalog} settings={settings} onClose={() => setCreating(false)} onCreated={id => { setCreating(false); reload(); open(id); }} />}
    </div>
  );
}
