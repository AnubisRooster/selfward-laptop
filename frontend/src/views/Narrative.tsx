import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { BASE, ago, del, errText, post, put } from '../api';
import { useLoad } from '../hooks';
import { Btn, Card, Empty, Err, Spin, Title, inputCls } from '../ui';
import { ask, toast } from '../feedback';

export default function Narrative() {
  const { data: n, error, reload } = useLoad<any>('/narrative', undefined, 3000);
  const [local, setLocal] = useState(false); const [edit, setEdit] = useState(false); const [text, setText] = useState(''); const [err, setErr] = useState('');
  const running = !!n?.state?.running;
  useEffect(() => { if (n && !edit) setText(n.content); }, [n?.content, edit]);
  if (!n) return error ? <div className="p-6"><Err>{error}</Err></div> : null;
  const cloud = !n.model_is_local;
  const build = async () => {
    setErr('');
    if (cloud && !local && !await ask.confirm({ title: 'Send this to a cloud model?', body: 'Your notes, dreams and kept memories since the last update will be sent to your cloud model’s provider to write the story. Anything with crisis wording is never sent. You can instead choose “Write it on this computer”.', confirmLabel: 'Send and write' })) return;
    try { await post('/narrative/build', { local }); reload(); } catch (e) { setErr(errText(e)); }
  };
  const save = async () => { try { await put('/narrative', { content: text }); setEdit(false); reload(); toast.ok('Saved. The next update will build on your version.'); } catch (e) { setErr(errText(e)); } };
  const undo = async () => { try { await post('/narrative/restore'); reload(); toast.ok('Went back to the earlier version.'); } catch (e) { setErr(errText(e)); } };
  const reset = async () => { if (await ask.confirm({ title: 'Delete the Narrative?', body: 'The story is removed from this computer. Your sessions, notes and dreams stay. The next update starts the story again from everything.', confirmLabel: 'Delete', danger: true })) { await del('/narrative'); reload(); } };
  return (
    <div className="h-full overflow-y-auto p-6"><div className="mx-auto max-w-3xl space-y-4">
      <Title right={n.content && !edit ? <><Btn small onClick={() => { const a = document.createElement('a'); a.href = BASE + '/api/narrative/export'; a.click(); }}>Export</Btn><Btn small onClick={() => setEdit(true)}>Edit</Btn></> : null}>Narrative</Title>
      <div className="text-sm text-zinc-400">A story of your inner life, written by your model from your notes, dreams and the moments Selfward kept, and revised as more comes in. It describes what you wrote, not who you are. Small models sometimes add details that were not in your words: edit anything that isn’t true.</div>

      <Card className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <Btn kind="primary" onClick={build} disabled={running || n.pending === 0} loading={running}>{n.content ? 'Update the story' : 'Write the story'}</Btn>
          <span className="text-sm text-zinc-400">{running ? 'Writing. On a laptop this can take a few minutes; you can use the rest of Selfward meanwhile.' : n.pending === 0 ? (n.content ? 'Up to date.' : 'Nothing to write from yet. Notes, dreams and kept memories will appear here as you use Selfward.') : `${n.pending} new thing${n.pending === 1 ? '' : 's'} to add.`}</span>
          {n.updated && <span className="ml-auto text-xs text-zinc-500">Last updated {ago(n.updated)}</span>}
        </div>
        {cloud && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={local} onChange={e => setLocal(e.target.checked)} /><span>Write it on this computer<span className="block text-xs text-amber-300/90">Your chat model is a cloud model. Without this, the material is sent to its provider (crisis wording never is).</span></span></label>}
        {n.withheld > 0 && <div className="text-xs text-amber-300">The next item has wording that is never sent to a cloud model, so the story stops before it. {cloud ? 'Tick “Write it on this computer” to include it.' : ''}</div>}
        {n.state?.error && !running && <Err>{n.state.error}</Err>}
        {n.state?.message && !running && !n.state.error && <div className="text-xs text-emerald-400">{n.state.message}</div>}
        <Err>{err}</Err>
      </Card>

      {edit ? <Card className="space-y-2">
        <textarea rows={22} className={inputCls + ' font-serif leading-relaxed'} value={text} onChange={e => setText(e.target.value)} aria-label="The narrative" />
        <div className="flex gap-2"><Btn kind="primary" onClick={save}>Save</Btn><Btn onClick={() => { setEdit(false); setText(n.content); }}>Cancel</Btn></div></Card>
        : n.content ? <Card><div className="font-serif text-[16px] leading-relaxed [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:font-sans [&_h2]:text-lg [&_h2]:font-semibold [&_h2:first-child]:mt-0 [&_p]:mb-3"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{n.content}</ReactMarkdown></div></Card>
        : running ? <div className="p-6"><Spin /></div> : <Empty icon="❦" title="No story yet">When you have a few notes or dreams, or after some sessions, write the first version here.</Empty>}

      {(n.can_undo || n.content) && !edit && <div className="flex flex-wrap gap-2">
        {n.can_undo && <Btn small onClick={undo}>Go back to the version before the last change</Btn>}
        {n.content && <Btn small kind="ghost" onClick={reset}>Delete the Narrative</Btn>}</div>}
    </div></div>
  );
}
