import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ago, del, errText, get, patch, post } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Empty, Err, Field, Modal, inputCls, cx } from '../ui';
import { ask, toast } from '../feedback';
import { Archive, Square, Trash2 } from 'lucide-react';

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

function Bubble({ m, who }: { m: any; who: string }) {
  const mine = m.role === 'user'; const safety = m.meta?.safety; const failed = m.meta?.error;
  return (
    <div className={cx('flex', mine ? 'justify-end' : 'justify-start')}>
      <div className={cx('max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px]', mine ? 'bg-indigo-600 text-white' : safety === 'crisis' || safety === 'method' ? 'border border-amber-700 bg-amber-950/40 text-amber-50' : failed ? 'border border-red-900 bg-red-950/30 text-red-200' : 'bg-zinc-800 text-zinc-100')}>
        {!mine && <div className="mb-0.5 text-[11px] font-medium text-zinc-400">{who}{safety && <span className="ml-2"><Badge tone="amber">{safety === 'boundary' ? 'kept within safe limits' : 'support resources'}</Badge></span>}</div>}
        {m.meta?.streaming && !m.content ? <span className="text-zinc-400">…</span> :
          <div className="prose-sw !text-inherit [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:ml-5 [&_ul]:list-disc [&_ol]:ml-5 [&_ol]:list-decimal"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown></div>}
        {m.meta?.cancelled && <div className="mt-1 text-[11px] text-zinc-400">stopped</div>}
      </div>
    </div>
  );
}

function Conversation({ id, catalog, onGone }: { id: number; catalog: any; onGone: () => void }) {
  const { data: s, error, reload } = useLoad<any>(`/sessions/${id}`, undefined, 1000);
  const [text, setText] = useState(''); const [err, setErr] = useState(''); const [sending, setSending] = useState(false);
  const end = useRef<HTMLDivElement>(null); const box = useRef<HTMLTextAreaElement>(null);
  const running = s?.status === 'running';
  const n = s?.messages?.length || 0; const last = s?.messages?.[n - 1]?.content?.length || 0;
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [n, last]);
  useEffect(() => { setText(''); setErr(''); box.current?.focus(); }, [id]);
  useEffect(() => { if (!running) box.current?.focus(); }, [running]);
  if (error && !s) return <Empty icon="⚠" title="Couldn’t open this session">{error}</Empty>;
  if (!s) return null;
  const send = async () => {
    const t = text.trim(); if (!t || running || sending) return;
    setSending(true); setErr('');
    try { await post(`/sessions/${id}/send`, { text: t }); setText(''); await reload(); } catch (e) { setErr(errText(e)); }
    setSending(false);
  };
  const set = async (body: any) => { try { await patch(`/sessions/${id}`, body); reload(); } catch (e) { toast.error(errText(e)); } };
  const rename = async () => { const t = await ask.prompt({ title: 'Rename session', initial: s.title, confirmLabel: 'Save' }); if (t?.trim()) set({ title: t.trim() }); };
  const remove = async () => {
    if (!await ask.confirm({ title: 'Delete this session?', body: 'Its messages and what it taught the memory are removed from this computer. This can’t be undone.', confirmLabel: 'Delete', danger: true })) return;
    try { await del(`/sessions/${id}`); onGone(); } catch (e) { toast.error(errText(e)); }
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
        <button className="mr-1 text-zinc-400 hover:text-zinc-100 md:hidden" onClick={onGone} aria-label="Back to sessions">←</button>
        <div className="min-w-0 flex-1"><button onClick={rename} className="block max-w-full truncate text-left text-sm font-semibold hover:underline" title="Rename">{s.title}</button>
          <div className="text-xs text-zinc-500">{s.persona_name}{s.persona === 'therapist' && ` · ${label(s.modality)}`}</div></div>
        {s.persona === 'therapist' && <select aria-label="Approach" className={cx(inputCls, '!w-auto !py-1 text-xs')} value={s.modality} onChange={e => set({ modality: e.target.value })}>{catalog.modalities.map((m: any) => <option key={m.id} value={m.id}>{label(m.id)}</option>)}</select>}
        <Btn small kind="ghost" title="Archive" label="Archive" onClick={async () => { await set({ archived: true }); onGone(); }}><Archive size={14} aria-hidden /></Btn>
        <Btn small kind="ghost" title="Delete" label="Delete" onClick={remove}><Trash2 size={14} aria-hidden /></Btn>
      </header>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {n === 0 && <Empty icon="✎" title={`Say hello to ${s.persona_name}`}>Whatever is on your mind. This stays on this computer; the model runs here unless you chose a cloud model in Settings.</Empty>}
        {s.messages.map((m: any) => <Bubble key={m.id} m={m} who={s.persona_name} />)}
        <div ref={end} />
      </div>
      <div className="border-t border-zinc-800 p-3">
        <Err>{err}</Err>
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
          <div className="flex gap-1.5"><Btn small kind="ghost" onClick={() => setShowArchived(a => !a)}>{showArchived ? 'Back' : 'Archive'}</Btn><Btn small kind="primary" disabled={!catalog || !settings} onClick={() => setCreating(true)}>+ New</Btn></div></div>
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
