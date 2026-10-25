import { Component, ReactNode } from 'react';
import { BASE } from './api';

/** Where an error in the window goes: on screen (so a blank page explains itself) and into the API log. */
export function reportError(kind: string, err: unknown) {
  const text = err instanceof Error ? `${err.message}\n${err.stack || ''}` : String(err);
  try { fetch(BASE + '/api/client-log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, text: text.slice(0, 4000), url: location.href }) }).catch(() => {}); } catch { /* logging must never break the page */ }
}

/** A window left open across an update asks for page files that no longer exist (they are renamed on every build). Loading the page again fetches the new ones; once only, so a real fault can't loop. */
export function reloadForUpdate(): boolean {
  try {
    const last = Number(sessionStorage.getItem('sf.reloaded') || 0);
    if (Date.now() - last < 15000) return false;
    sessionStorage.setItem('sf.reloaded', String(Date.now()));
  } catch { /* storage blocked: still try once */ }
  location.reload(); return true;
}

export function watchErrors() {
  window.addEventListener('vite:preloadError', e => { e.preventDefault(); reloadForUpdate(); });
  window.addEventListener('error', e => reportError('error', e.error || e.message));
  window.addEventListener('unhandledrejection', e => reportError('rejection', e.reason));
}

export default class ErrorBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  componentDidCatch(err: Error) { reportError('render', err); }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div role="alert" className="flex h-full items-center justify-center p-8">
        <div className="max-w-xl text-center">
          <div className="mb-2 text-lg font-semibold">Selfward hit a problem</div>
          <p className="mb-3 text-sm text-zinc-500">Your sessions are safe. Reload the window; if it comes back, the details below are also in <code>~/.local/state/selfward/api.log</code>.</p>
          <pre className="mb-3 max-h-48 overflow-auto rounded-lg bg-zinc-900 p-3 text-left text-xs text-red-300">{String(this.state.err.message)}</pre>
          <button onClick={() => location.reload()} className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm hover:bg-zinc-700">Reload</button>
        </div>
      </div>
    );
  }
}
