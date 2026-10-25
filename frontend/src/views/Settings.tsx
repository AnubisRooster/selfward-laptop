import { useEffect, useState } from 'react';
import { BASE, errText, http, post, put } from '../api';
import { useLoad } from '../hooks';
import { Badge, Btn, Card, Err, Field, Seg, Title, inputCls } from '../ui';
import { ask, toast } from '../feedback';
import { ThemePref, readPref, setPref } from '../theme';
import DesktopSettings from './DesktopSettings';

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
      <Title>Settings</Title>

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
        <div className="flex flex-wrap gap-2"><Btn kind="primary" onClick={() => save(['model', 'embed_model', ...(typeof v.api_key === 'string' ? ['api_key'] : [])])}>Save model</Btn><Btn onClick={test} loading={testing}>Test it</Btn>
          {v.api_key && <Btn kind="ghost" onClick={async () => { await put('/settings', { values: { api_key: '' } }); reload(); setKey('api_key', false); toast.ok('Key removed'); }}>Remove key</Btn>}</div>
        <div className="flex gap-2 text-xs">{models && <><Badge tone={models.ollama_up ? 'green' : 'amber'}>{models.ollama_up ? 'Ollama running' : 'Ollama not running'}</Badge></>}</div>
      </Card>

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
