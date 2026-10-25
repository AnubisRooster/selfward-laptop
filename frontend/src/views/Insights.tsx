import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ago, del, errText, patch, post } from '../api';
import { useLoad, useNav } from '../hooks';
import { Badge, Btn, Card, Empty, Err, Field, Modal, Seg, Title, inputCls } from '../ui';
import { ask, toast } from '../feedback';

export default function Insights() {
  const { sessionId, go } = useNav();
  const [tab, setTab] = useState('highlights');
  const q = { session_id: sessionId ?? undefined };
  const { data: sessions } = useLoad<any[]>('/sessions');
  const ins = useLoad<any>('/insights', q);
  const dreams = useLoad<any[]>('/dreams', q);
  const notes = useLoad<any[]>('/notes', q);
  const [dlg, setDlg] = useState<'' | 'dream' | 'note'>('');
  const reloadAll = () => { ins.reload(); dreams.reload(); notes.reload(); };
  const rebuild = async () => {
    try { const r = await post('/insights/rebuild'); toast.ok(r.dreams_found ? `Found ${r.dreams_found} dream${r.dreams_found === 1 ? '' : 's'} in older sessions.` : 'Nothing new in older sessions.'); reloadAll(); } catch (e) { toast.error(errText(e)); }
  };
  return (
    <div className="h-full overflow-y-auto p-6"><div className="mx-auto max-w-3xl space-y-4">
      <Title right={<Seg label="Section" value={tab} onChange={setTab} options={[['highlights', 'Highlights'], ['dreams', `Dreams${dreams.data ? ` · ${dreams.data.length}` : ''}`], ['notes', `Notes${notes.data ? ` · ${notes.data.length}` : ''}`]]} />}>Insights</Title>
      <div className="flex flex-wrap items-center gap-2">
        <select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs" aria-label="Which sessions" value={sessionId ?? ''} onChange={e => go('insights', { sessionId: e.target.value ? Number(e.target.value) : null })}>
          <option value="">All sessions</option>{(sessions || []).map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
        <span className="text-xs text-zinc-500">Kept on this computer. Dreams and notes are found in your own words; nothing is sent to a model unless you ask for a reading.</span>
      </div>

      {tab === 'highlights' && <Card className="space-y-2">
        <h2 className="font-medium">What your words show</h2>
        {(ins.data?.highlights || []).length === 0 ? <div className="text-sm text-zinc-500">Nothing yet. These appear as feelings, people and events come up in your sessions.</div> :
          <ul className="list-disc space-y-1.5 pl-5 text-sm">{ins.data.highlights.map((h: string) => <li key={h}>{h}</li>)}</ul>}
        <div className="pt-1 text-xs text-zinc-500">These are patterns in what you wrote, not conclusions about you. See them on the <button className="underline" onClick={() => go('map', { sessionId })}>Inner Map</button>.</div>
      </Card>}

      {tab === 'dreams' && <div className="space-y-3">
        <div className="flex flex-wrap gap-2"><Btn kind="primary" small onClick={() => setDlg('dream')}>+ Add a dream</Btn><Btn small kind="ghost" onClick={rebuild} title="Look through sessions written before this feature for dreams">Look in older sessions</Btn></div>
        <Err>{dreams.error}</Err>
        {(dreams.data || []).length === 0 && <Empty icon="☾" title="No dreams yet">When you tell a dream in a session (“I had a dream…”), it is saved here. You can also add one yourself.</Empty>}
        {(dreams.data || []).map(d => <Dream key={d.id} d={d} onChanged={dreams.reload} onOpen={() => d.session_id && go('chats', { sessionId: d.session_id })} />)}
      </div>}

      {tab === 'notes' && <div className="space-y-3">
        <div className="flex gap-2"><Btn kind="primary" small onClick={() => setDlg('note')}>+ New note</Btn></div>
        <Err>{notes.error}</Err>
        {(notes.data || []).length === 0 && <Empty icon="✎" title="No notes yet">A summary note starts by itself after your second message in a session. You can write your own too.</Empty>}
        {(notes.data || []).map(n => <Note key={n.id} n={n} onChanged={notes.reload} />)}
      </div>}

      {dlg === 'dream' && <AddDialog kind="dream" sessionId={sessionId} onClose={() => setDlg('')} onDone={() => { setDlg(''); reloadAll(); }} />}
      {dlg === 'note' && <AddDialog kind="note" sessionId={sessionId} onClose={() => setDlg('')} onDone={() => { setDlg(''); reloadAll(); }} />}
    </div></div>
  );
}

function Dream({ d, onChanged, onOpen }: { d: any; onChanged: () => void; onOpen: () => void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const read = async () => { setBusy(true); setErr(''); try { await post(`/dreams/${d.id}/interpret`); onChanged(); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const remove = async () => { if (await ask.confirm({ title: 'Delete this dream?', body: 'It is removed from this computer.', confirmLabel: 'Delete', danger: true })) { await del(`/dreams/${d.id}`); onChanged(); } };
  return (
    <Card className="space-y-2">
      <div className="flex items-start justify-between gap-2"><div className="text-xs text-zinc-500">{ago(d.ts)}{d.session_title && <> · <button className="underline" onClick={onOpen}>{d.session_title}</button></>}</div>
        <button onClick={remove} className="text-xs text-zinc-500 hover:text-red-400" aria-label="Delete dream">Delete</button></div>
      <p className="whitespace-pre-wrap text-sm">{d.narrative}</p>
      {(d.feelings.length > 0 || d.symbols.length > 0) && <div className="flex flex-wrap gap-1.5">{d.feelings.map((f: string) => <Badge key={'f' + f} tone="red">{f}</Badge>)}{d.symbols.map((s: string) => <Badge key={'s' + s} tone="indigo">{s}</Badge>)}</div>}
      {d.analysis ? <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-sm"><div className="mb-1 text-xs font-medium text-zinc-400">One reading, not a conclusion</div><div className="[&_p]:mb-2 [&_ul]:ml-5 [&_ul]:list-disc [&_ol]:ml-5 [&_ol]:list-decimal"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{d.analysis}</ReactMarkdown></div></div> : null}
      <Err>{err}</Err>
      <Btn small onClick={read} loading={busy} title="Asks your chosen model for a Jungian-style reading">{d.analysis ? 'Read it again' : 'Offer a reading'}</Btn>
    </Card>
  );
}

function Note({ n, onChanged }: { n: any; onChanged: () => void }) {
  const [edit, setEdit] = useState(false); const [title, setTitle] = useState(n.title); const [content, setContent] = useState(n.content);
  const save = async () => { try { await patch(`/notes/${n.id}`, { title, content }); setEdit(false); onChanged(); } catch (e) { toast.error(errText(e)); } };
  const remove = async () => { if (await ask.confirm({ title: 'Delete this note?', confirmLabel: 'Delete', danger: true })) { await del(`/notes/${n.id}`); onChanged(); } };
  return (
    <Card className="space-y-2">
      {edit ? <>
        <input className={inputCls} value={title} onChange={e => setTitle(e.target.value)} aria-label="Title" />
        <textarea rows={6} className={inputCls} value={content} onChange={e => setContent(e.target.value)} aria-label="Note" />
        <div className="flex gap-2"><Btn kind="primary" small onClick={save}>Save</Btn><Btn small onClick={() => { setEdit(false); setTitle(n.title); setContent(n.content); }}>Cancel</Btn></div>
      </> : <>
        <div className="flex items-start justify-between gap-2"><div><div className="font-medium">{n.title}</div><div className="text-xs text-zinc-500">{ago(n.updated || n.ts)}{n.session_title && ` · ${n.session_title}`}{n.auto === 1 && ' · written automatically'}</div></div>
          <div className="flex gap-3 text-xs text-zinc-500"><button className="hover:text-zinc-200" onClick={() => setEdit(true)}>Edit</button><button className="hover:text-red-400" onClick={remove}>Delete</button></div></div>
        <p className="whitespace-pre-wrap text-sm text-zinc-300">{n.content}</p>
        {n.auto === 1 && <div className="text-[11px] text-zinc-500">Updates as the session goes on. Edit it and it becomes yours and stops changing.</div>}
      </>}
    </Card>
  );
}

function AddDialog({ kind, sessionId, onClose, onDone }: { kind: 'dream' | 'note'; sessionId: number | null; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(''); const [text, setText] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { await post(kind === 'dream' ? '/dreams' : '/notes', kind === 'dream' ? { narrative: text, session_id: sessionId } : { title, content: text, session_id: sessionId }); onDone(); } catch (e) { setErr(errText(e)); setBusy(false); } };
  return (
    <Modal title={kind === 'dream' ? 'Add a dream' : 'New note'} onClose={onClose}>
      <div className="space-y-3">
        {kind === 'note' && <Field label="Title"><input className={inputCls} value={title} onChange={e => setTitle(e.target.value)} autoFocus /></Field>}
        <Field label={kind === 'dream' ? 'What do you remember?' : 'Note'} hint={kind === 'dream' ? 'Symbols and feelings are picked out for you.' : undefined}><textarea rows={6} className={inputCls} value={text} onChange={e => setText(e.target.value)} autoFocus={kind === 'dream'} /></Field>
        {sessionId != null && <div className="text-xs text-zinc-500">It will be attached to the session chosen above.</div>}
        <Err>{err}</Err>
        <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" onClick={save} loading={busy} disabled={!text.trim() && !title.trim()}>Save</Btn></div>
      </div>
    </Modal>
  );
}
