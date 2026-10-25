import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ago, del, errText, get, patch, post, put } from '../api';
import { speech, useLoad, useNav } from '../hooks';
import { Badge, Btn, Empty, Err, Field, Modal, Spin, inputCls, cx } from '../ui';
import { ask, toast } from '../feedback';
import { useHandsFree } from '../useHandsFree';
import { plainForSpeech } from '../voiceInput';
import { wantAudioChat } from '../voiceIntent';
import { wantInsights } from '../insightsIntent';
import { touch } from '../activity';
import { BADGE_ICONS, BadgePill, ModalityIcon, PersonaAvatar } from '../icons';
import { Archive, Brain, ChevronDown, Cloud, Cpu, Heart, Hexagon, Lightbulb, Mic, MicOff, Moon, NotebookPen, Pencil, Square, Trash2, Volume2 } from 'lucide-react';

export const shortModel = (m: string) => (m || '').replace(/^ollama_chat\//, '').replace(/^openrouter\/openrouter\/free$/, 'OpenRouter · automatic free').replace(/^openrouter\//, 'OpenRouter · ').replace(/:free$/, '');
const isLocalModel = (m: string) => (m || '').startsWith('ollama');
const label = (m: string) => m.replace(/_/g, ' ').replace(/\b(cbt|dbt|act|ifs)\b/i, s => s.toUpperCase()).replace(/^./, c => c.toUpperCase());

function NewSession({ catalog, settings, onClose, onCreated }: { catalog: any; settings: any; onClose: () => void; onCreated: (id: number) => void }) {
  const [persona, setPersona] = useState<string>(settings.default_persona || 'therapist');
  const [modality, setModality] = useState<string>(settings.default_modality || 'integrated'); const [title, setTitle] = useState('');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { const r = await post('/sessions', { persona, modality, ...(title.trim() ? { title: title.trim() } : {}) }); onCreated(r.id); } catch (e) { setErr(errText(e)); setBusy(false); } };
  return (
    <Modal title="New session" onClose={onClose}>
      <div className="space-y-4">
        <Field label="Title (optional)" hint="You can rename it any time. Without one, it is named from your first message."><input className={inputCls} value={title} onChange={e => setTitle(e.target.value)} maxLength={80} placeholder="For example: Dealing with Dana" autoFocus /></Field>
        <div role="radiogroup" aria-label="Who to talk with" className="space-y-2">
          {catalog.personas.map((p: any) => (
            <button key={p.id} role="radio" aria-checked={persona === p.id} onClick={() => setPersona(p.id)}
              className={cx('flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left', persona === p.id ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
              <PersonaAvatar kind={p.id} size={40} />
              <span className="min-w-0"><div className="text-sm font-medium">{(settings[p.id + '_name'] || p.default_name || p.label)}<span className="ml-2 text-xs font-normal text-zinc-500">{p.label}</span></div>
              <div className="text-xs text-zinc-500">{p.blurb}</div></span></button>))}
        </div>
        {persona === 'therapist' && <div><div className="mb-1 text-xs font-medium text-zinc-400">Approach</div>
          <ApproachGrid catalog={catalog} value={modality} onPick={setModality} /></div>}
        <Err>{err}</Err>
        <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={go} loading={busy}>Start</Btn></div>
      </div>
    </Modal>
  );
}

function ApproachGrid({ catalog, value, onPick }: { catalog: any; value: string; onPick: (m: string) => void }) {
  return (
    <div role="radiogroup" aria-label="Approach" className="grid max-h-64 grid-cols-1 gap-1.5 overflow-y-auto sm:grid-cols-2">
      {catalog.modalities.map((m: any) => (
        <button key={m.id} role="radio" aria-checked={value === m.id} onClick={() => onPick(m.id)} className={cx('flex items-start gap-2 rounded-lg border px-2.5 py-2 text-left', value === m.id ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
          <ModalityIcon id={m.id} size={16} className="mt-0.5 shrink-0 text-indigo-300" /><span className="min-w-0"><span className="block text-sm font-medium">{label(m.id)}</span><span className="block text-[11px] leading-snug text-zinc-500">{m.description}</span></span></button>))}
    </div>
  );
}

function GuideDialog({ s, catalog, onClose, onChanged }: { s: any; catalog: any; onClose: () => void; onChanged: () => void }) {
  const { data: settings } = useLoad<any>('/settings'); const [err, setErr] = useState('');
  const change = async (body: any, done: string) => { try { await patch(`/sessions/${s.id}`, body); toast.ok(done); onChanged(); onClose(); } catch (e) { setErr(errText(e)); } };
  return (
    <Modal title="Who you are talking with" onClose={onClose}>
      <div className="space-y-4">
        <div className="text-xs text-zinc-500">Changes from your next message on. The conversation and everything remembered come along, and each earlier reply keeps the name of whoever wrote it.</div>
        <Err>{err}</Err>
        <div role="radiogroup" aria-label="Guide" className="space-y-2">{catalog.personas.map((p: any) => {
          const name = (settings && settings[p.id + '_name']) || p.default_name || p.label;
          return <button key={p.id} role="radio" aria-checked={s.persona === p.id} disabled={s.persona === p.id} onClick={() => change({ persona: p.id }, `Now talking with ${name}.`)}
            className={cx('flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left', s.persona === p.id ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
            <PersonaAvatar kind={p.id} size={40} /><span className="min-w-0"><div className="text-sm font-medium">{name}<span className="ml-2 text-xs font-normal text-zinc-500">{p.label}</span>{s.persona === p.id && <span className="ml-2"><Badge tone="indigo">now</Badge></span>}</div><div className="text-xs text-zinc-500">{p.blurb}</div></span></button>; })}</div>
      </div>
    </Modal>
  );
}

function ApproachDialog({ s, catalog, onClose, onChanged }: { s: any; catalog: any; onClose: () => void; onChanged: () => void }) {
  const [err, setErr] = useState('');
  const pick = async (m: string) => { if (m === s.modality) return onClose(); try { await patch(`/sessions/${s.id}`, { modality: m }); toast.ok(`Approach is now ${label(m)}.`); onChanged(); onClose(); } catch (e) { setErr(errText(e)); } };
  return (
    <Modal title="Approach" onClose={onClose}>
      <div className="space-y-3"><div className="text-xs text-zinc-500">The way the guide works with you. It changes from your next message on; each earlier reply keeps the approach it was written in.</div><Err>{err}</Err>
        <ApproachGrid catalog={catalog} value={s.modality} onPick={pick} /></div>
    </Modal>
  );
}

function WarmthDialog({ s, catalog, onClose, onChanged }: { s: any; catalog: any; onClose: () => void; onChanged: () => void }) {
  const { data: settings, reload } = useLoad<any>('/settings'); const [err, setErr] = useState('');
  const pick = async (n: number) => {
    try {
      if (n > 0 && !settings?.companion_adult) {
        if (!await ask.confirm({ title: 'Are you 18 or older?', body: 'Warmer Companion settings include flirting and romantic feeling. They are for adults only.', confirmLabel: 'I am 18 or older' })) return;
        await put('/settings', { values: { companion_adult: true } }); reload();
      }
      await patch(`/sessions/${s.id}`, { flirt: n }); toast.ok(n === 0 ? 'Back to friends.' : `Warmth: ${catalog.warmth[n].label}.`); onChanged(); onClose();
    } catch (e) { setErr(errText(e)); }
  };
  const cur = s.flirt_effective ?? 0;
  return (
    <Modal title="Warmth" onClose={onClose}>
      <div className="space-y-3">
        <div className="text-xs text-zinc-500">How affectionate {s.persona_name} is, from your next message on. It is an AI and says so if you ask, it never pressures you to stay, and it softens when you sound low. Change it or turn it off whenever you like.</div>
        <Err>{err}</Err>
        <div role="radiogroup" aria-label="Warmth" className="space-y-1.5">{catalog.warmth.map((w: any) => (
          <button key={w.id} role="radio" aria-checked={cur === w.id} onClick={() => cur === w.id ? onClose() : pick(w.id)} className={cx('flex w-full items-start gap-3 rounded-lg border px-3 py-2 text-left', cur === w.id ? 'border-rose-500 bg-rose-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
            <span className="mt-0.5 flex shrink-0 gap-0.5 text-rose-300" aria-hidden>{[0, 1, 2].map(i => <Heart key={i} size={12} fill={i < w.id ? 'currentColor' : 'none'} />)}</span>
            <span className="min-w-0"><span className="block text-sm font-medium">{w.label}{cur === w.id && <span className="ml-2"><Badge tone="indigo">now</Badge></span>}</span><span className="block text-xs text-zinc-500">{w.blurb}</span></span></button>))}</div>
        {s.flirt >= 0 && <Btn small onClick={async () => { try { await patch(`/sessions/${s.id}`, { flirt: -1 }); toast.ok('Following Settings again.'); onChanged(); onClose(); } catch (e) { setErr(errText(e)); } }}>Follow the default in Settings</Btn>}
        {cur >= 2 && !s.model_is_local && <div className="text-xs text-amber-300">This session is on a cloud model, so these personal messages go to its provider. A provider that does not keep or train on your messages is the safer choice; free models often keep them.</div>}
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

function Bubble({ m, session }: { m: any; session: any }) {
  const { go } = useNav(); const cap = m.meta?.captured || {};
  const mine = m.role === 'user'; const safety = m.meta?.safety; const failed = m.meta?.error;
  const kind: string = m.meta?.persona || session.persona; const who: string = m.meta?.persona_name || session.persona_name; const approach: string | undefined = m.meta?.persona ? m.meta.modality : (kind === 'therapist' ? session.modality : undefined);
  const toInsights = (section: 'dreams' | 'notes' | 'highlights') => () => { wantInsights(section); go('insights', { sessionId: session.id }); };
  const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  const hasBadges = !mine && (cap.memory || cap.nodes || cap.edges || cap.dream || cap.note || cap.insight);
  return (
    <div className={cx('flex items-start gap-2', mine ? 'justify-end' : 'justify-start')}>
      {!mine && <PersonaAvatar kind={kind} size={28} className="mt-1" />}
      <div className="max-w-[85%] min-w-0">
        <div className={cx('rounded-2xl px-4 py-2.5 text-[15px]', mine ? 'bg-indigo-600 text-white' : safety === 'crisis' || safety === 'method' ? 'border border-amber-700 bg-amber-950/40 text-amber-50' : failed ? 'border border-red-900 bg-red-950/30 text-red-200' : 'bg-zinc-800 text-zinc-100')}>
          {!mine && <div className="mb-0.5 flex flex-wrap items-center gap-x-2 text-[11px] font-medium text-zinc-400">{who}
            {approach && <span className="inline-flex items-center gap-1 font-normal text-zinc-500" title="The approach this reply was written in"><ModalityIcon id={approach} size={11} />{label(approach)}</span>}
            {m.meta?.model && <span className="inline-flex items-center gap-1 font-normal text-zinc-500" title={m.meta.model}>{isLocalModel(m.meta.model) ? <Cpu size={11} aria-hidden /> : <Cloud size={11} aria-hidden />}{shortModel(m.meta.model)}</span>}
            {safety && <Badge tone="amber">{safety === 'boundary' ? 'kept within safe limits' : String(safety).startsWith('companion_') ? 'kept kind' : 'support resources'}</Badge>}</div>}
          {m.meta?.streaming && !m.content ? <span className="text-zinc-400">…</span> :
            <div className="prose-sw !text-inherit [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:ml-5 [&_ul]:list-disc [&_ol]:ml-5 [&_ol]:list-decimal"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown></div>}
          {!mine && m.content && !m.meta?.streaming && speech.supported && <button className="mt-1 flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300 focus:text-zinc-300" onClick={() => speech.speak(plainForSpeech(m.content), 1, '', kind)}><Volume2 size={11} aria-hidden /> Read aloud</button>}
          {!mine && m.meta?.tone_dropped && <div className="mt-1 text-[11px] text-zinc-400">Kept gentle because you sounded low. The warmth comes back when you do.</div>}
          {!mine && m.meta?.refused && <div className="mt-1 text-[11px] text-amber-300">This model stepped out of the role. Another model may suit it better (the model pill above).</div>}
          {m.meta?.cancelled && <div className="mt-1 text-[11px] text-zinc-400">stopped</div>}
        </div>
        {hasBadges && <div className="mt-1 flex flex-wrap gap-1.5 pl-1" aria-label="What this exchange added">
          {cap.memory > 0 && <BadgePill icon={BADGE_ICONS.memory} tone="teal" label={count(cap.memory, 'memory', 'memories')} title="This exchange was remembered, so a later session can recall it." />}
          {cap.nodes > 0 && <BadgePill icon={BADGE_ICONS.nodes} tone="purple" label={count(cap.nodes, 'node', 'nodes')} title={cap.by_model ? "New things on your Inner Map from what you wrote (some found by the model on this computer)." : "New things on your Inner Map from what you wrote."} onClick={() => go('map', { sessionId: session.id })} />}
          {cap.edges > 0 && <BadgePill icon={BADGE_ICONS.edges} tone="indigo" label={count(cap.edges, 'edge', 'edges')} title="New connections on your Inner Map." onClick={() => go('map', { sessionId: session.id })} />}
          {cap.dream && <BadgePill icon={BADGE_ICONS.dream} tone="purple" label="dream logged" title="This sounded like a dream, so it was saved. See it in Insights." onClick={toInsights('dreams')} />}
          {cap.note && <BadgePill icon={BADGE_ICONS.note} tone="green" label="note" title="A summary note for this session was started. See it in Insights." onClick={toInsights('notes')} />}
          {cap.insight && <BadgePill icon={BADGE_ICONS.insight} tone="orange" label="insight saved" title="This moment carries weight, so it is kept for good and can come back in later sessions. See it in Settings → What Selfward remembers." onClick={() => go('settings')} />}
        </div>}
      </div>
    </div>
  );
}

function Conversation({ id, catalog, onGone }: { id: number; catalog: any; onGone: () => void }) {
  const { data: s, error, reload } = useLoad<any>(`/sessions/${id}`, undefined, 1000);
  const [text, setText] = useState(''); const [err, setErr] = useState(''); const [sending, setSending] = useState(false);
  const [pickModel, setPickModel] = useState(false); const [pickGuide, setPickGuide] = useState(false); const [pickApproach, setPickApproach] = useState(false); const [pickWarmth, setPickWarmth] = useState(false);
  const end = useRef<HTMLDivElement>(null); const box = useRef<HTMLTextAreaElement>(null);
  const running = s?.status === 'running';
  const n = s?.messages?.length || 0; const last = s?.messages?.[n - 1]?.content?.length || 0;
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [n, last]);
  useEffect(() => { setText(''); setErr(''); box.current?.focus(); }, [id]);
  useEffect(() => { if (!running) box.current?.focus(); }, [running]);
  useEffect(() => { if (!running) return; touch(); const t = setInterval(touch, 5000); return () => clearInterval(t); }, [running]);       // waiting for an answer is use
  const sendText = async (t: string) => {
    t = t.trim(); if (!t) return;
    setSending(true); setErr('');
    try { await post(`/sessions/${id}/send`, { text: t }); await reload(); } catch (e) { setErr(errText(e)); }
    setSending(false);
  };
  const send = async () => { const t = text.trim(); if (!t || running || sending) return; setText(''); await sendText(t); };
  const stopAnswer = async () => { await post(`/sessions/${id}/cancel`); reload(); };
  const { go } = useNav();
  const hf = useHandsFree({ running: !!running, messages: s?.messages || [], persona: s?.persona || '', send: sendText, stop: stopAnswer });
  if (error && !s) return <Empty icon="⚠" title="Couldn’t open this session">{error}</Empty>;
  if (!s) return null;
  const set = async (body: any) => { try { await patch(`/sessions/${id}`, body); reload(); } catch (e) { toast.error(errText(e)); } };
  const rename = async () => { const t = await ask.prompt({ title: 'Rename this session', body: 'Give it a name you will recognise later.', initial: s.title, label: 'Title', confirmLabel: 'Save' }); if (t?.trim() && t.trim() !== s.title) set({ title: t.trim().slice(0, 80) }); };
  const remove = async () => {
    if (!await ask.confirm({ title: 'Delete this session?', body: 'Its messages, notes, dreams and what it taught the memory are removed from this computer. If you have written your Narrative, it may still mention what was in this session: edit or reset it on its page. This can’t be undone.', confirmLabel: 'Delete', danger: true })) return;
    try { await del(`/sessions/${id}`); onGone(); } catch (e) { toast.error(errText(e)); }
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="space-y-1.5 border-b border-zinc-800 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <button className="mr-1 text-zinc-400 hover:text-zinc-100 md:hidden" onClick={onGone} aria-label="Back to sessions">←</button>
          <button onClick={() => setPickGuide(true)} title="Change who you are talking with" aria-label="Change who you are talking with" className="shrink-0 rounded-full ring-offset-2 hover:ring-2 hover:ring-indigo-500"><PersonaAvatar kind={s.persona} size={34} /></button>
          <div className="min-w-0 flex-1"><div className="flex items-center gap-1.5"><h1 className="truncate text-sm font-semibold">{s.title}</h1>
            <button onClick={rename} title="Rename this session" aria-label="Rename this session" className="shrink-0 rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"><Pencil size={13} aria-hidden /></button></div>
            <div className="text-xs text-zinc-500">{s.message_count} message{s.message_count === 1 ? '' : 's'}{s.node_count > 0 && <span className="ml-2 inline-flex items-center gap-1 text-purple-300/80"><Hexagon size={10} aria-hidden />{s.node_count}</span>}{s.memory_count > 0 && <span className="ml-2 inline-flex items-center gap-1 text-teal-300/80"><Brain size={10} aria-hidden />{s.memory_count}</span>}</div></div>
          <Btn small kind={hf.on ? 'primary' : 'ghost'} title={hf.on ? 'Hands-free is on: turn it off' : 'Hands-free: talk to the guide and hear the answers'} label="Hands-free" onClick={hf.toggle}>{hf.on ? <Mic size={14} aria-hidden /> : <MicOff size={14} aria-hidden />}</Btn>
          <Btn small kind="ghost" title="Archive" label="Archive" onClick={async () => { await set({ archived: true }); onGone(); }}><Archive size={14} aria-hidden /></Btn>
          <Btn small kind="ghost" title="Delete" label="Delete" onClick={remove}><Trash2 size={14} aria-hidden /></Btn>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <button onClick={() => setPickGuide(true)} title="Change who you are talking with" className="flex items-center gap-1 rounded-full border border-zinc-700 px-2.5 py-1 hover:bg-zinc-800">{s.persona_name}<ChevronDown size={11} aria-hidden /></button>
          {s.persona === 'therapist' && <button onClick={() => setPickApproach(true)} title="Change the approach" className="flex items-center gap-1 rounded-full border border-zinc-700 px-2.5 py-1 hover:bg-zinc-800"><ModalityIcon id={s.modality} size={12} />{label(s.modality)}<ChevronDown size={11} aria-hidden /></button>}
          {s.persona === 'companion' && (s.flirt_effective > 0 ?
            <span className="flex items-center overflow-hidden rounded-full border border-rose-700 bg-rose-950/30 text-rose-200"><button onClick={() => setPickWarmth(true)} title="Change the warmth" className="flex items-center gap-1 px-2.5 py-1 hover:bg-rose-900/40"><Heart size={12} fill="currentColor" aria-hidden />Warmth {s.flirt_effective} · {catalog.warmth[s.flirt_effective]?.label}</button>
              <button onClick={() => set({ flirt: 0 })} title="Turn the warmth off for this session" aria-label="Turn the warmth off for this session" className="border-l border-rose-700 px-2 py-1 hover:bg-rose-900/40">Off</button></span> :
            <button onClick={() => setPickWarmth(true)} title="Make the Companion warmer" className="flex items-center gap-1 rounded-full border border-zinc-700 px-2.5 py-1 hover:bg-zinc-800"><Heart size={12} aria-hidden />Warmth<ChevronDown size={11} aria-hidden /></button>)}
          <button onClick={() => setPickModel(true)} title="Change the model that writes the replies in this session" className="flex items-center gap-1 rounded-full border border-zinc-700 px-2.5 py-1 hover:bg-zinc-800">{s.model_is_local ? <Cpu size={12} aria-hidden /> : <Cloud size={12} aria-hidden />}{shortModel(s.model_effective)}{!s.model && <span className="text-zinc-500"> · default</span>}<ChevronDown size={11} aria-hidden /></button>
          <span className="ml-auto flex items-center gap-0.5">
            <Btn small kind="ghost" title="Insights for this session" label="Insights" onClick={() => { wantInsights('highlights'); go('insights', { sessionId: id }); }}><Lightbulb size={14} aria-hidden /></Btn>
            <Btn small kind="ghost" title="Notes for this session" label="Notes" onClick={() => { wantInsights('notes'); go('insights', { sessionId: id }); }}><NotebookPen size={14} aria-hidden /></Btn>
            <Btn small kind="ghost" title="Dreams from this session" label="Dreams" onClick={() => { wantInsights('dreams'); go('insights', { sessionId: id }); }}><Moon size={14} aria-hidden /></Btn>
            <Btn small kind="ghost" title="Patterns: this session's Inner Map" label="Patterns" onClick={() => go('map', { sessionId: id })}><Hexagon size={14} aria-hidden /></Btn></span>
        </div>
      </header>
      {pickGuide && <GuideDialog s={s} catalog={catalog} onClose={() => setPickGuide(false)} onChanged={reload} />}
      {pickApproach && <ApproachDialog s={s} catalog={catalog} onClose={() => setPickApproach(false)} onChanged={reload} />}
      {pickWarmth && <WarmthDialog s={s} catalog={catalog} onClose={() => setPickWarmth(false)} onChanged={reload} />}
      {pickModel && <ModelDialog s={s} onClose={() => setPickModel(false)} onChanged={reload} />}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {n === 0 && <Empty icon="✎" title={`Say hello to ${s.persona_name}`}>Whatever is on your mind. This stays on this computer; the model runs here unless you chose a cloud model in Settings.</Empty>}
        {s.messages.map((m: any) => <Bubble key={m.id} m={m} session={s} />)}
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
        <div className="flex items-center justify-between gap-2 border-b border-zinc-800 p-3"><h1 className="truncate text-lg font-semibold">{showArchived ? 'Archived' : 'Sessions'}</h1>
          <div className="flex gap-1.5"><Btn small title="Start a new session and just talk: it listens and speaks the answers" disabled={!catalog || !settings} onClick={async () => { try { const r = await post('/sessions', { persona: settings.default_persona, modality: settings.default_modality }); wantAudioChat(); reload(); open(r.id); } catch (e) { toast.error(errText(e)); } }}><Mic size={13} aria-hidden /> Talk</Btn><Btn small kind="ghost" label={showArchived ? 'Back to sessions' : 'Show archived sessions'} title={showArchived ? 'Back to sessions' : 'Show archived sessions'} onClick={() => setShowArchived(a => !a)}>{showArchived ? 'Back' : <Archive size={14} aria-hidden />}</Btn><Btn small kind="primary" disabled={!catalog || !settings} onClick={() => setCreating(true)}>+ New</Btn></div></div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(list || []).length === 0 && <Empty icon="✎" title={showArchived ? 'Nothing archived' : 'No sessions yet'}>{showArchived ? '' : 'Start one when you are ready. You choose who to talk with, and for the therapist, which approach.'}</Empty>}
          {(list || []).map(c => (
            <div key={c.id} role="button" tabIndex={0} onClick={() => open(c.id)} onKeyDown={e => e.key === 'Enter' && open(c.id)}
              className={cx('cursor-pointer border-b border-zinc-800/60 px-3 py-2.5 hover:bg-zinc-900', sessionId === c.id && 'bg-zinc-900')}>
              <div className="flex items-start gap-3">
                <PersonaAvatar kind={c.persona} size={40} className="mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{c.title || 'Untitled session'}</span><span className="shrink-0 text-[11px] text-zinc-500">{ago(c.updated)}</span></div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11px] text-zinc-500">
                    <span>{c.persona_name}</span>
                    {c.persona === 'therapist' && <span className="inline-flex items-center gap-1"><ModalityIcon id={c.modality} size={11} />{label(c.modality)}</span>}
                    <span className="inline-flex items-center gap-1" title={c.model_effective}>{c.model_is_local ? <Cpu size={11} aria-hidden /> : <Cloud size={11} aria-hidden />}{shortModel(c.model_effective)}</span></div>
                  <div className="mt-0.5 flex items-center gap-2.5 text-[11px] text-zinc-500"><span>{c.message_count} message{c.message_count === 1 ? '' : 's'}</span>
                    {c.node_count > 0 && <span className="inline-flex items-center gap-1 text-purple-300/80" title="Things on this session's Inner Map"><Hexagon size={10} aria-hidden />{c.node_count}</span>}
                    {c.memory_count > 0 && <span className="inline-flex items-center gap-1 text-teal-300/80" title="Exchanges remembered"><Brain size={10} aria-hidden />{c.memory_count}</span>}</div>
                  {c.preview && <div className="mt-1 truncate text-xs text-zinc-500">{c.preview}</div>}
                </div>
              </div>
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
