import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { get, post } from './api';
import { useHashSync, useLoad, useNav } from './hooks';
import { Modal, Spin, cx } from './ui';
import { FeedbackHost } from './feedback';
import { LifeBuoy, MessageSquare, Settings as SettingsIcon, Lock } from 'lucide-react';
import { onDesktopEvent } from './desktop';
import Onboarding from './views/Onboarding';
const Chats = lazy(() => import('./views/Chats'));
const Settings = lazy(() => import('./views/Settings'));

function LockScreen({ onUnlock }: { onUnlock: () => void }) {
  const [pin, setPin] = useState(''); const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true); setErr('');
    try {
      const r = await post('/lock/verify', { pin });
      if (r.ok) onUnlock(); else { setErr(r.wait ? `Too many tries. Wait ${r.wait} seconds.` : 'Wrong PIN.'); setPin(''); }
    } catch { setErr('Can’t reach the backend.'); }
    setBusy(false);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950">
      <form onSubmit={e => { e.preventDefault(); submit(); }} className="w-72 text-center">
        <div className="mb-2 text-4xl">🔒</div><div className="mb-4 text-lg font-semibold">Selfward is locked</div>
        <input autoFocus type="password" inputMode="numeric" value={pin} onChange={e => setPin(e.target.value)} placeholder="PIN" aria-label="PIN"
          className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-center text-lg tracking-widest outline-none focus:border-indigo-500" />
        {err && <div role="alert" className="mb-2 text-sm text-red-400">{err}</div>}
        <button disabled={busy || !pin} className="w-full rounded-lg bg-indigo-600 py-2 font-medium disabled:opacity-40">Unlock</button>
      </form>
    </div>
  );
}

/** Always one click away: the lines to call or text, for the region chosen in Settings. */
export function HelpNow({ resources, onClose }: { resources: { name: string; contact: string }[]; onClose: () => void }) {
  return (
    <Modal title="Get help now" onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-300">Selfward is a journaling and reflection tool, not a therapist or a crisis service. If you are in danger or thinking about harming yourself, please reach a person right now:</p>
      <ul className="mb-3 space-y-2 text-sm">{resources.map(r => <li key={r.name} className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2"><div className="font-medium">{r.name}</div><div className="text-zinc-400">{r.contact}</div></li>)}</ul>
      <p className="text-xs text-zinc-500">These services are free, confidential and open all day. You can change your country in Settings.</p>
    </Modal>
  );
}

export default function App() {
  useHashSync();
  const { tab, go } = useNav();
  const { data: st, error, reload } = useLoad<any>('/status', undefined, 4000);
  const [locked, setLocked] = useState(() => { try { return sessionStorage.getItem('sf.unlocked') !== '1'; } catch { return true; } });
  const [help, setHelp] = useState(false);
  const idle = useRef<any>(null);
  const firstBuild = useRef<number | null>(null);
  useEffect(() => { if (st?.ui_build == null) return; if (firstBuild.current == null) firstBuild.current = st.ui_build; }, [st?.ui_build]);
  const stale = st?.ui_build != null && firstBuild.current != null && st.ui_build !== firstBuild.current;
  const lockOn = !!st?.lock_enabled;
  const lockNow = () => { setLocked(true); try { sessionStorage.removeItem('sf.unlocked'); } catch {} };
  useEffect(() => { const f = () => lockNow(); window.addEventListener('sf-lock', f); return () => window.removeEventListener('sf-lock', f); }, []);

  useEffect(() => {
    let off = () => {};
    onDesktopEvent('lock-now', () => { if (lockOn) lockNow(); }).then(f => { off = f; });
    return () => off();
  }, [lockOn]);

  // Lock on launch, after the grace period away, and after a long idle spell.
  useEffect(() => {
    if (!lockOn) return;
    let hiddenAt = 0;
    const lockAfter = async () => { const s = await get('/settings'); return (s.lock_after ?? 60) * 1000; };
    const onVis = async () => {
      if (document.hidden) hiddenAt = Date.now();
      else if (hiddenAt && Date.now() - hiddenAt > await lockAfter()) lockNow();
    };
    const reset = () => { clearTimeout(idle.current); lockAfter().then(ms => { idle.current = setTimeout(lockNow, Math.max(ms, 60000) * 5); }); };
    document.addEventListener('visibilitychange', onVis); window.addEventListener('pointerdown', reset); window.addEventListener('keydown', reset); reset();
    return () => { document.removeEventListener('visibilitychange', onVis); window.removeEventListener('pointerdown', reset); window.removeEventListener('keydown', reset); clearTimeout(idle.current); };
  }, [lockOn]);

  if (!st) {
    return <><div className="flex h-full items-center justify-center p-8 text-center" role={error ? 'alert' : 'status'}>
      <div><div className="mb-2 text-lg">{error ? 'Selfward’s backend isn’t running' : 'Starting…'}</div>
        {error && <>
          <div className="mb-3 text-sm text-zinc-500">Selfward normally restarts it by itself. If this stays, quit Selfward from the tray icon and open it again.<br />The log is in <code className="rounded bg-zinc-800 px-1">~/.local/state/selfward/api.log</code>.</div>
          <button onClick={() => reload()} className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm hover:bg-zinc-700">Try again</button></>}</div></div><FeedbackHost /></>;
  }
  if (lockOn && locked) return <><LockScreen onUnlock={() => { try { sessionStorage.setItem('sf.unlocked', '1'); } catch {} setLocked(false); }} /><FeedbackHost /></>;
  if (!st.onboarding_completed) return <><Onboarding status={st} onDone={reload} /><FeedbackHost /></>;

  const Body = { chats: Chats, settings: Settings }[tab];
  const navBtn = (active: boolean, label: string, Icon: typeof Lock, onClick: () => void) => (
    <button key={label} onClick={onClick} aria-current={active ? 'page' : undefined}
      className={cx('flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] md:flex-none md:flex-row md:gap-2 md:px-3 md:py-2 md:text-sm', active ? 'bg-zinc-800 text-zinc-50' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200')}>
      <Icon size={16} aria-hidden className="shrink-0" /><span>{label}</span></button>);

  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav className="flex shrink-0 gap-0.5 border-b border-zinc-800 bg-zinc-950 p-1.5 md:w-48 md:flex-col md:gap-1 md:border-b-0 md:border-r md:p-3" aria-label="Main">
        <div className="hidden px-2 pb-3 pt-1 md:block"><div className="text-lg font-semibold">Selfward</div><div className="text-xs text-zinc-500">Private, on this computer</div></div>
        {navBtn(tab === 'chats', 'Sessions', MessageSquare, () => go('chats'))}
        <div className="hidden flex-1 md:block" />
        {navBtn(tab === 'settings', 'Settings', SettingsIcon, () => go('settings'))}
        <button onClick={() => setHelp(true)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-amber-300 hover:bg-zinc-900" title="Crisis lines and emergency numbers"><LifeBuoy size={16} aria-hidden /><span>Get help now</span></button>
        {lockOn && <button onClick={lockNow} title="Lock Selfward" aria-label="Lock Selfward" className="hidden items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-900 md:flex"><Lock size={16} aria-hidden /><span>Lock</span></button>}
      </nav>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {stale && <div role="status" className="flex items-center justify-between gap-3 border-b border-indigo-800 bg-indigo-950/40 px-4 py-2 text-sm">Selfward was updated. <button className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500" onClick={() => location.reload()}>Reload to use the new version</button></div>}
        {!st.preflight.ollama && st.model.startsWith('ollama') && <div role="status" className="border-b border-amber-900 bg-amber-950/40 px-4 py-2 text-sm text-amber-200">Ollama isn’t running, so I can’t answer yet. Start it (<code>ollama serve</code>) or choose another model in Settings.</div>}
        <div className="min-h-0 flex-1 overflow-hidden"><Suspense fallback={<div className="p-6" role="status"><Spin /></div>}><Body /></Suspense></div>
      </main>
      {help && <HelpNow resources={st.resources} onClose={() => setHelp(false)} />}
      <FeedbackHost />
    </div>
  );
}
