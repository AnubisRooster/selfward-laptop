import { useEffect, useState } from 'react';
import { BASE, ago, del, errText, get, http, post, put } from '../api';
import { speech, useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, Seg, Title, inputCls } from '../ui';
import { ask, toast } from '../feedback';
import { ThemePref, readPref, setPref } from '../theme';
import DesktopSettings from './DesktopSettings';
import RemoteSettings from './RemoteSettings';
import { openHelp } from '../HelpGuide';
import { onPhone } from '../device';

function useSettings() {
  const { data, reload } = useLoad<any>('/settings');
  const [v, setV] = useState<any>(null);
  useEffect(() => { if (data && !v) setV(data); }, [data]);
  const save = async (keys: string[], then?: string) => {
    try { const body: any = {}; keys.forEach(k => { body[k] = v[k]; }); const r = await put('/settings', { values: body }); setV((o: any) => ({ ...o, ...r })); reload(); toast.ok(then || 'Saved'); }
    catch (e) { toast.error(errText(e)); }
  };
  return { v, set: (k: string) => (e: any) => setV((o: any) => ({ ...o, [k]: e.target.value })), setKey: (k: string, val: any) => setV((o: any) => ({ ...o, [k]: val })), save, reload };
}

function download(path: string, name: string) { const a = document.createElement('a'); a.href = BASE + '/api' + path; a.download = name; a.click(); }

export default function Settings() {
  const { v, set, setKey, save, reload } = useSettings();
  const { data: catalog } = useLoad<any>('/catalog');
  const { data: models } = useLoad<any>('/models');
  const { data: events } = useLoad<any[]>('/safety/events');
  const [theme, setTheme] = useState<ThemePref>(readPref());
  const [testing, setTesting] = useState(false);
  const [pin, setPin] = useState({ current: '', next: '' }); const [pinErr, setPinErr] = useState('');
  const [pass, setPass] = useState(''); const [file, setFile] = useState<File | null>(null); const [busy, setBusy] = useState(false);
  if (!v || !catalog) return null;

  const test = async () => { setTesting(true); try { const r = await post('/models/test'); toast.ok(`${r.model} answered.`); } catch (e) { toast.error(errText(e)); } setTesting(false); };
  const setPinNow = async (remove = false) => {
    setPinErr('');
    try { await post('/lock/set', { pin: remove ? '' : pin.next, current: pin.current }); setPin({ current: '', next: '' }); reload(); toast.ok(remove ? 'PIN removed' : 'PIN set'); window.location.reload(); }
    catch (e) { setPinErr(errText(e)); }
  };
  const backup = async () => {
    if (pass.length < 8) return toast.error('Use a passphrase of at least 8 characters.');
    setBusy(true);
    try { const r = await http.post('/backup', { passphrase: pass }, { responseType: 'blob' }); const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = 'selfward-backup.sfbk'; a.click(); toast.ok('Backup saved. Keep the passphrase: it can’t be recovered.'); }
    catch (e) { toast.error(errText(e)); }
    setBusy(false);
  };
  const restore = async () => {
    if (!file) return;
    if (!await ask.confirm({ title: 'Restore this backup?', body: 'This replaces every session and memory on this computer with the ones in the backup.', confirmLabel: 'Restore', danger: true })) return;
    setBusy(true);
    try { const r = await http.post('/restore', await file.arrayBuffer(), { headers: { 'x-passphrase': pass, 'Content-Type': 'application/octet-stream' } }); toast.ok(`Restored ${r.data.restored.sessions} sessions.`); setFile(null); }
    catch (e) { toast.error(errText(e)); }
    setBusy(false);
  };
  const erase = async () => {
    const t = await ask.prompt({ title: 'Erase everything?', body: 'Deletes every session, message and memory from this computer. Type erase to confirm.', label: 'Type erase', confirmLabel: 'Erase all' });
    if (t !== 'erase') return;
    try { await post('/danger/erase', { confirm: 'erase' }); toast.ok('Everything was erased.'); } catch (e) { toast.error(errText(e)); }
  };

  return (
    <div className="h-full overflow-y-auto p-6"><div className="mx-auto max-w-2xl space-y-5">
      <Title right={<Btn small onClick={() => openHelp()}>Help guide</Btn>}>Settings</Title>

      <Card className="space-y-3"><h2 className="font-medium">Your guides</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="AI Reflection Guide name" hint="Blank keeps it unnamed."><input className={inputCls} value={v.therapist_name} onChange={set('therapist_name')} /></Field>
          <Field label="Companion name"><input className={inputCls} value={v.companion_name} onChange={set('companion_name')} /></Field>
          <Field label="Spiritual Advisor name"><input className={inputCls} value={v.spiritual_name} onChange={set('spiritual_name')} /></Field></div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Companion personality"><select className={inputCls} value={v.companion_personality} onChange={set('companion_personality')}>{catalog.personalities.map((p: any) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></Field>
          <Field label="Companion presence"><select className={inputCls} value={v.companion_gender} onChange={set('companion_gender')}>{catalog.genders.map((p: any) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></Field>
          <Field label="Advisor tradition"><select className={inputCls} value={v.spiritual_tradition} onChange={set('spiritual_tradition')}>{catalog.traditions.map((p: any) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></Field></div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="New sessions start with"><select className={inputCls} value={v.default_persona} onChange={set('default_persona')}>{catalog.personas.map((p: any) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></Field>
          <Field label="Default approach (for the guide)"><select className={inputCls} value={v.default_modality} onChange={set('default_modality')}>{catalog.modalities.map((m: any) => <option key={m.id} value={m.id}>{m.id.replace(/_/g, ' ')}</option>)}</select></Field></div>
        <Btn kind="primary" onClick={() => save(['therapist_name', 'companion_name', 'spiritual_name', 'companion_personality', 'companion_gender', 'spiritual_tradition', 'default_persona', 'default_modality'])}>Save guides</Btn>
      </Card>

      <Card className="space-y-3"><h2 className="font-medium">About you</h2><div className="text-xs text-zinc-500">Added to every conversation so the guide knows who it is talking with.</div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Name"><input className={inputCls} value={v.user_name} onChange={set('user_name')} /></Field>
          <Field label="Pronouns"><input className={inputCls} value={v.user_pronouns} onChange={set('user_pronouns')} /></Field>
          <Field label="Age"><input className={inputCls} value={v.user_age} onChange={set('user_age')} /></Field></div>
        <Field label="What's on your mind lately"><textarea rows={2} className={inputCls} value={v.intake_concerns} onChange={set('intake_concerns')} /></Field>
        <Field label="Past experience with therapy"><textarea rows={2} className={inputCls} value={v.intake_history} onChange={set('intake_history')} /></Field>
        <Field label="What you want from this"><textarea rows={2} className={inputCls} value={v.intake_goals} onChange={set('intake_goals')} /></Field>
        <Field label="Country for crisis lines"><select className={inputCls} value={v.region} onChange={set('region')}>{catalog.regions.map((r: string) => <option key={r}>{r}</option>)}<option value="OTHER">Somewhere else (international list)</option></select></Field>
        <Btn kind="primary" onClick={() => save(['user_name', 'user_pronouns', 'user_age', 'intake_concerns', 'intake_history', 'intake_goals', 'region'])}>Save</Btn>
      </Card>

      <Card className="space-y-3"><h2 className="font-medium">Model</h2>
        <div className="text-xs text-zinc-500">{v.model.startsWith('ollama') ? 'This model runs on this computer through Ollama. Nothing you write leaves it.' : <b className="text-amber-300">This is a cloud model: what you write in a session is sent to its provider.</b>}</div>
        <Field label="Chat model" hint="An Ollama model as ollama_chat/<name>, or any cloud model id (for example openrouter/…, anthropic/…)."><input className={inputCls} list="installed" value={v.model} onChange={set('model')} />
          <datalist id="installed">{(models?.ollama || []).map((m: string) => <option key={m} value={'ollama_chat/' + m} />)}</datalist></Field>
        <Field label="API key (cloud models only)" hint={v.api_key ? 'A key is saved. Type a new one to replace it, or clear it below.' : 'Stored on this computer only.'}><input type="password" autoComplete="off" className={inputCls} placeholder={v.api_key ? '••••••••' : ''} onChange={e => setKey('api_key', e.target.value)} /></Field>
        <Field label="Memory (embedding) model"><input className={inputCls} value={v.embed_model} onChange={set('embed_model')} /></Field>
        <Field label="Conversation window (tokens)" hint="How much of a chat the model reads at once. Longer chats are folded into a short recap so the guide still knows what came before. Bigger needs more memory on this computer; 8,192 suits a small model."><input type="number" min={2048} max={262144} step={1024} className={inputCls + ' !w-40'} value={v.context_tokens} onChange={e => setKey('context_tokens', Number(e.target.value))} /></Field>
        <div className="flex flex-wrap gap-2"><Btn kind="primary" onClick={() => save(['model', 'embed_model', 'context_tokens', ...(typeof v.api_key === 'string' ? ['api_key'] : [])])}>Save model</Btn><Btn onClick={test} loading={testing}>Test it</Btn>
          {v.api_key && <Btn kind="ghost" onClick={async () => { await put('/settings', { values: { api_key: '' } }); reload(); setKey('api_key', false); toast.ok('Key removed'); }}>Remove key</Btn>}</div>
        <div className="flex gap-2 text-xs">{models && <><Badge tone={models.ollama_up ? 'green' : 'amber'}>{models.ollama_up ? 'Ollama running' : 'Ollama not running'}</Badge></>}</div>
      </Card>

      {onPhone ? <ThisPhone /> : <RemoteSettings />}

      <VoiceCard v={v} setKey={setKey} />

      <OpenRouterPicker v={v} setKey={setKey} />

      <Remembered v={v} setKey={setKey} save={save} />

      <Card className="space-y-3"><h2 className="font-medium">Look</h2>
        <Seg label="Theme" value={theme} options={[['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]} onChange={t => { setPref(t as ThemePref); setTheme(t as ThemePref); }} /></Card>

      <Card className="space-y-3"><h2 className="font-medium">Privacy & lock</h2>
        <div className="text-xs text-zinc-500">{v.lock_enabled ? 'A PIN protects the window. It asks again after you have been away for the time below.' : 'Set a PIN to lock the window. It protects the screen, not the file on disk.'}</div>
        <Err>{pinErr}</Err>
        <div className="flex flex-wrap items-end gap-2">
          {v.lock_enabled && <Field label="Current PIN"><input type="password" inputMode="numeric" className={inputCls + ' !w-32'} value={pin.current} onChange={e => setPin(p => ({ ...p, current: e.target.value }))} /></Field>}
          <Field label={v.lock_enabled ? 'New PIN' : 'PIN (4+ digits)'}><input type="password" inputMode="numeric" className={inputCls + ' !w-32'} value={pin.next} onChange={e => setPin(p => ({ ...p, next: e.target.value }))} /></Field>
          <Btn kind="primary" disabled={pin.next.length < 4} onClick={() => setPinNow()}>{v.lock_enabled ? 'Change PIN' : 'Set PIN'}</Btn>
          {v.lock_enabled && <Btn kind="danger" onClick={() => setPinNow(true)}>Remove PIN</Btn>}</div>
        {v.lock_enabled && <Field label="Lock after being away (seconds)"><input type="number" min={10} className={inputCls + ' !w-32'} value={v.lock_after} onChange={e => setKey('lock_after', Number(e.target.value))} onBlur={() => save(['lock_after'])} /></Field>}
      </Card>

      <Card className="space-y-3"><h2 className="font-medium">Your data</h2>
        <div className="flex flex-wrap gap-2"><Btn onClick={() => download('/export/markdown', 'selfward-journal.md')}>Export as Markdown</Btn><Btn onClick={() => download('/export/json', 'selfward-journal.json')}>Export as JSON</Btn></div>
        <div className="text-xs text-zinc-500">An encrypted backup holds your sessions and memories (not your API key or PIN).</div>
        <div className="flex flex-wrap items-end gap-2"><Field label="Passphrase (8+ characters)"><input type="password" className={inputCls + ' !w-56'} value={pass} onChange={e => setPass(e.target.value)} autoComplete="off" /></Field>
          <Btn onClick={backup} loading={busy} disabled={pass.length < 8}>Back up…</Btn>
          <input type="file" accept=".sfbk" aria-label="Backup file" className="text-xs" onChange={e => setFile(e.target.files?.[0] || null)} />
          <Btn onClick={restore} disabled={!file || !pass} loading={busy}>Restore</Btn></div>
        <Btn kind="danger" onClick={erase}>Erase everything…</Btn>
      </Card>

      <Card className="space-y-2"><h2 className="font-medium">Safety log</h2><div className="text-xs text-zinc-500">When a crisis phrase or an unsafe reply was caught. Kept on this computer only.</div>
        {(events || []).length === 0 ? <div className="text-sm text-zinc-500">Nothing so far.</div> :
          <ul className="space-y-1 text-sm">{events!.slice(0, 20).map(e => <li key={e.id} className="flex items-center justify-between gap-2"><span><Badge tone={e.level === 'critical' ? 'red' : 'amber'}>{e.type.replace(/_/g, ' ')}</Badge> <span className="text-zinc-400">{e.message}</span></span><span className="shrink-0 text-xs text-zinc-500">{new Date(e.ts * 1000).toLocaleString()}</span></li>)}</ul>}
      </Card>

      <DesktopSettings />
      <div className="pb-6 text-center text-xs text-zinc-600">Selfward is a journaling and self-reflection tool, not a licensed therapist.</div>
    </div></div>
  );
}

function Remembered({ v, setKey, save }: { v: any; setKey: (k: string, val: any) => void; save: (keys: string[], then?: string) => Promise<void> }) {
  const { data, reload } = useLoad<any[]>('/global-memories');
  const [text, setText] = useState(''); const [err, setErr] = useState('');
  const add = async () => { setErr(''); try { await post('/global-memories', { content: text }); setText(''); reload(); } catch (e) { setErr(errText(e)); } };
  const remove = async (id: number) => { if (await ask.confirm({ title: 'Forget this?', body: 'It is removed from this computer and won’t be brought up again.', confirmLabel: 'Forget', danger: true })) { await del(`/global-memories/${id}`); reload(); } };
  return (
    <Card className="space-y-3"><h2 className="font-medium">What Selfward remembers</h2>
      <div className="text-xs text-zinc-500">Besides each chat, Selfward keeps the moments that seemed to matter (a parent, a loss, a realisation) and brings them up in later sessions when they are relevant. You decide: see them, add to them, forget any of them, or turn this off.</div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={!!v.remember_across_sessions} onChange={async e => { setKey('remember_across_sessions', e.target.checked); await put('/settings', { values: { remember_across_sessions: e.target.checked } }); toast.ok(e.target.checked ? 'Remembering across sessions' : 'Not keeping or using these any more'); }} />
        <span>Keep and use these across sessions<span className="block text-xs text-zinc-500">Turn off and nothing new is kept and none is used; what is already here stays until you forget it.</span></span></label>
      <Err>{err}</Err>
      <div className="flex gap-2"><input className={inputCls} value={text} onChange={e => setText(e.target.value)} placeholder="Something to always keep in mind, e.g. “My sister Ana is my anchor”" aria-label="Add something to remember" onKeyDown={e => { if (e.key === 'Enter' && text.trim()) add(); }} /><Btn onClick={add} disabled={!text.trim()}>Add</Btn></div>
      {(data || []).length === 0 ? <div className="text-sm text-zinc-500">Nothing kept yet.</div> :
        <ul className="space-y-2">{data!.map(m => (
          <li key={m.id} className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-sm">
            <div className="mb-1 flex items-center justify-between gap-2"><div className="flex items-center gap-1.5 text-xs text-zinc-500"><Badge tone={m.manual ? 'indigo' : m.kind === 'insight' ? 'amber' : 'zinc'}>{m.manual ? 'added by you' : m.kind}</Badge>{ago(m.ts)}{m.session_title && ` · ${m.session_title}`}</div>
              <button className="text-xs text-zinc-500 hover:text-red-400" onClick={() => remove(m.id)}>Forget</button></div>
            <p className="whitespace-pre-wrap text-zinc-300">{m.content}</p></li>))}</ul>}
    </Card>
  );
}

function OpenRouterPicker({ v, setKey }: { v: any; setKey: (k: string, val: any) => void }) {
  const current = String(v.model || '').startsWith('openrouter/');
  const [list, setList] = useState<any[] | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [q, setQ] = useState(''); const [testing, setTesting] = useState('');
  const load = async (refresh = false) => { setBusy(true); setErr(''); try { setList((await get('/openrouter/models', { refresh })).models); } catch (e) { setErr(errText(e)); } setBusy(false); };
  const choose = async (model: string, name: string) => {
    if (!current && !await ask.confirm({ title: 'Send your sessions to OpenRouter?', body: 'Free models run on OpenRouter’s servers. What you write in a session (and what the guide recalls from earlier ones) leaves this computer, and free providers may keep it or learn from it. Dreams, the Narrative and anything with crisis wording have their own safeguards, but your chats do go. The model on this computer keeps everything here.', confirmLabel: 'Use this model' })) return;
    try { await put('/settings', { values: { model } }); setKey('model', model); toast.ok(`Sessions now use ${name}.`); } catch (e) { toast.error(errText(e)); }
  };
  const back = async () => { const m = 'ollama_chat/llama3.2:3b'; try { await put('/settings', { values: { model: m } }); setKey('model', m); toast.ok('Back on the model on this computer.'); } catch (e) { toast.error(errText(e)); } };
  const test = async (model: string) => { setTesting(model); try { await post('/models/test', { model }); toast.ok('It answered.'); } catch (e) { toast.error(errText(e)); } setTesting(''); };
  const shown = (list || []).filter(m => !q.trim() || (m.name + ' ' + m.id).toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <Card className="space-y-3">
      <details open={current || undefined} onToggle={e => { if ((e.target as HTMLDetailsElement).open && list === null && !busy) load(); }}>
        <summary className="cursor-pointer font-medium">OpenRouter free models{current && <span className="ml-2 text-xs font-normal text-emerald-400">in use: {String(v.model).replace('openrouter/', '')}</span>}</summary>
        <div className="mt-3 space-y-3">
          <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-xs text-amber-100">Free models run on OpenRouter’s servers. What you write in sessions leaves this computer, and free providers may keep it or use it to train models. For private reflection the model on this computer is safer. Memory, the Inner Map, Insights and the crisis check always run here.</div>
          <div className="text-xs text-zinc-500">{v.api_key ? 'An API key is saved (see “Model” above).' : <>You need an OpenRouter key: create one at <a className="text-indigo-300 underline" href="https://openrouter.ai/keys" target="_blank" rel="noreferrer noopener">openrouter.ai/keys</a> and paste it into “API key” above.</>} Free models are often busy or gated; “Automatic” picks one that is answering. If you see “no endpoints match your data policy”, allow free models in your OpenRouter privacy settings.</div>
          <Err>{err}</Err>
          <div className="flex flex-wrap items-center gap-2"><input className={inputCls + ' !w-64'} placeholder="Search models" aria-label="Search models" value={q} onChange={e => setQ(e.target.value)} /><Btn small onClick={() => load(true)} loading={busy}>{list ? 'Refresh the list' : 'Show free models'}</Btn>{current && <Btn small kind="ghost" onClick={back}>Back to the model on this computer</Btn>}</div>
          {list && shown.length === 0 && <div className="text-sm text-zinc-500">No free models match.</div>}
          <ul className="space-y-2">{shown.map(m => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
              <div className="min-w-0"><div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">{m.name}{m.recommended && <Badge tone="green">recommended</Badge>}{v.model === m.model && <Badge tone="indigo">in use</Badge>}</div>
                <div className="truncate text-xs text-zinc-500">{m.id} · {m.context ? `${Math.round(m.context / 1000)}k context` : ''}</div></div>
              <div className="flex gap-2"><Btn small onClick={() => test(m.model)} loading={testing === m.model} disabled={!v.api_key} title={v.api_key ? 'Sends one tiny request to check it answers' : 'Save an API key first'}>Test</Btn>
                <Btn small kind="primary" onClick={() => choose(m.model, m.name)} disabled={v.model === m.model || !v.api_key}>Use</Btn></div></li>))}</ul>
        </div>
      </details>
    </Card>
  );
}

const VOICE_GROUPS: Record<string, string> = {
  af: 'American English · female', am: 'American English · male', bf: 'British English · female', bm: 'British English · male',
  ef: 'Spanish · female', em: 'Spanish · male', ff: 'French · female', hf: 'Hindi · female', hm: 'Hindi · male', if: 'Italian · female', im: 'Italian · male',
  jf: 'Japanese · female', jm: 'Japanese · male', pf: 'Portuguese · female', pm: 'Portuguese · male', zf: 'Mandarin · female', zm: 'Mandarin · male',
};
const voiceLabel = (v: string) => { const n = v.slice(3); return n.charAt(0).toUpperCase() + n.slice(1); };
function VoiceOptions({ voices, current }: { voices: string[]; current: string }) {
  const names = current && !voices.includes(current) ? [current, ...voices] : voices; const groups = new Map<string, string[]>();
  for (const x of names) { const g = VOICE_GROUPS[x.slice(0, 2)] || 'Other'; groups.set(g, [...(groups.get(g) || []), x]); }
  const order = Object.values(VOICE_GROUPS);
  return <>{[...groups.entries()].sort((a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99)).map(([g, vs]) => <optgroup key={g} label={g}>{vs.map(x => <option key={x} value={x}>{voiceLabel(x)}</option>)}</optgroup>)}</>;
}

function VoiceCard({ v, setKey }: { v: any; setKey: (k: string, val: any) => void }) {
  const { data: tts } = useLoad<any>('/tts/status', undefined, 5000);
  const { data: mic } = useLoad<any>('/voice/status');
  const { data: catalog } = useLoad<any>('/catalog');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(''); const [rate, setRate] = useState<number>(Number(v.voice_rate) || 1); const [pause, setPause] = useState<number>(Number(v.voice_pause_ms) || 800);
  const up = !!tts?.up; const voices: string[] = tts?.voices || []; const engine: string = v.tts_engine || 'auto'; const natural = engine === 'kokoro' || (engine === 'auto' && up);
  const save = async (values: any) => { setErr(''); try { await put('/settings', { values }); Object.entries(values).forEach(([k, x]) => setKey(k, x)); } catch (e) { setErr(errText(e)); } };
  const listen = async (voice: string, key: string) => { setErr(''); setBusy(key); try { const m = await speech.sample(natural ? 'kokoro' : 'browser', voice || v.tts_voice || 'af_heart', rate); if (m) setErr(m); } catch (e) { setErr(errText(e)); } setBusy(''); };
  const guides: [string, string][] = [['therapist', v.therapist_name || 'AI Reflection Guide'], ['companion', v.companion_name || 'Companion'], ['spiritual', v.spiritual_name || 'Spiritual Advisor']];
  return (
    <Card className="space-y-3"><h2 className="font-medium">Voice</h2>
      <div className="text-xs text-zinc-500">Reading aloud and hands-free talking both run on this computer: the voice (Kokoro) and the listening (Whisper) never send audio or words anywhere. The microphone is open only while hands-free is on in a session, and it closes when you leave, lock, or hide the window.</div>
      <Err>{err}</Err>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Natural voice</span>{up ? <Badge tone="green">Running · {voices.length} voices</Badge> : tts?.installed ? <Badge tone="amber">Starting… (it starts by itself)</Badge> : <Badge tone="red">Not installed</Badge>}</div>
      {!onPhone && <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Speech input (hands-free)</span>{mic?.installed ? <Badge tone="green">Installed · {mic.model}</Badge> : <Badge tone="red">Not installed</Badge>}</div>}
      {(!tts?.installed || (mic && !mic.installed)) && <div className="text-xs text-zinc-500">Step-by-step: <button className="text-indigo-300 underline" onClick={() => openHelp('voice-reading-aloud-and-talking')}>Help guide → Voice</button>. Selfward uses the voice and listening models from SmartWard’s folder (about 1 GB, so they aren’t copied). {tts?.home ? <>Found: <code>{tts.home}</code>.</> : <>None found: install SmartWard’s <code>tts/setup.sh</code> and <code>stt/setup.sh</code>, or set <code>SELFWARD_VOICE_HOME</code> to a folder that has them.</>} Without them, the browser’s own voice reads aloud and hands-free is unavailable.</div>}
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Voice</span><Seg label="Voice engine" value={engine} onChange={x => save({ tts_engine: x })} options={[['auto', 'Automatic'], ['kokoro', 'Natural'], ['browser', 'Browser']]} /></div>
      {natural && <>
        <Field label="Default voice"><div className="flex gap-2"><select className={inputCls} value={v.tts_voice || 'af_heart'} onChange={e => save({ tts_voice: e.target.value })}><VoiceOptions voices={voices} current={v.tts_voice || 'af_heart'} /></select><Btn onClick={() => listen(v.tts_voice, 'default')} loading={busy === 'default'}>▶ Listen</Btn></div></Field>
        <div className="space-y-2"><div className="text-xs font-medium text-zinc-400">A voice for each guide</div>
          {guides.map(([id, name]) => <div key={id} className="flex flex-wrap items-center gap-2"><span className="w-44 truncate text-sm">{name}</span>
            <select className={inputCls + ' !w-auto flex-1'} aria-label={`Voice for ${name}`} value={v['voice_' + id] || ''} onChange={e => save({ ['voice_' + id]: e.target.value })}><option value="">Default voice</option><VoiceOptions voices={voices} current={v['voice_' + id] || ''} /></select>
            <Btn small onClick={() => listen(v['voice_' + id], id)} loading={busy === id}>▶</Btn></div>)}</div></>}
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Speaking rate {rate.toFixed(2)}×</span>
        <input type="range" min="0.5" max="2" step="0.05" aria-label="Speaking rate" value={rate} onChange={e => setRate(Number(e.target.value))} onMouseUp={() => save({ voice_rate: rate })} onKeyUp={() => save({ voice_rate: rate })} onTouchEnd={() => save({ voice_rate: rate })} /></div>
      <div className="space-y-1"><div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Pause that ends your turn: {(pause / 1000).toFixed(1)} s</span>
        <input type="range" min="300" max="1500" step="100" aria-label="Pause that ends your turn" value={pause} onChange={e => setPause(Number(e.target.value))} onMouseUp={() => save({ voice_pause_ms: pause })} onKeyUp={() => save({ voice_pause_ms: pause })} onTouchEnd={() => save({ voice_pause_ms: pause })} /></div>
        <div className="text-xs text-zinc-500">How long you stay quiet before hands-free sends what you said. Shorter is snappier but may cut you off when you stop to think; longer waits for you. It applies the next time you switch hands-free on. If it stays open much longer than this, the room is probably noisy (a fan, music): see the Help guide → Troubleshooting. After the pause, turning your words into text takes a few seconds on a laptop.</div></div>
      {catalog && <div className="text-xs text-zinc-500">Start a session with <b>Talk</b> on the Sessions list, or press the microphone in a session.</div>}
    </Card>
  );
}

function ThisPhone() {
  return (
    <Card className="space-y-2"><h2 className="font-medium">This phone</h2>
      <div className="text-xs text-zinc-500">You are signed in to your laptop’s Selfward over your private network, for 7 days after you last use it. Remote access itself, and the laptop’s own microphone, can only be managed on the laptop.</div>
      <Btn kind="danger" onClick={async () => { try { await post('/remote/logout'); } catch { /* already signed out */ } location.reload(); }}>Sign out of this phone</Btn>
    </Card>
  );
}
