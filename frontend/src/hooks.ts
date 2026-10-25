import { useCallback, useEffect, useRef, useState } from 'react';
import { create } from 'zustand';
import { get, http } from './api';
import { HOME, Place, Tab, hashFor, parseHash } from './nav';

export type { Tab } from './nav';

interface Nav extends Place {
  go: (t: Tab, extra?: Partial<Place>) => void;
}
export const useNav = create<Nav>((set) => ({
  ...(parseHash(typeof location !== 'undefined' ? location.hash : '') || HOME),
  go: (tab, extra = {}) => set({ tab, sessionId: null, ...extra }),
}));

/** Keeps the address and the screen in step: Back, Forward and Reload land where you were. Call once. */
export function useHashSync() {
  useEffect(() => {
    const place = (s: Place): Place => ({ tab: s.tab, sessionId: s.sessionId });
    const fromAddress = () => { const p = parseHash(location.hash); if (p) useNav.setState(p); };
    const toAddress = () => { const h = hashFor(place(useNav.getState())); if (location.hash !== h) location.hash = h; };
    toAddress();
    window.addEventListener('hashchange', fromAddress);
    const unsubscribe = useNav.subscribe(toAddress);
    return () => { window.removeEventListener('hashchange', fromAddress); unsubscribe(); };
  }, []);
}

/** Fetch + refetch helper. `deps` re-run; `every` polls (ms). */
/** True when two payloads are the same JSON, so an unchanged poll doesn't re-render. */
export const sameData = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b);

/**
 * Loads `url`, optionally every `every` ms. Polling pauses while the window is hidden and catches up
 * when it comes back; an unchanged payload is ignored; an older response never overwrites a newer one;
 * data stays on screen while the same endpoint reloads (no spinner flash).
 */
export function useLoad<T = any>(url: string | null, params?: any, every?: number) {
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify([url, params]);
  const seq = useRef(0); const lastUrl = useRef(url); const current = useRef<T | null>(null);
  const put = useCallback((u: T | null | ((d: T | null) => T | null)) => { const v = typeof u === 'function' ? (u as any)(current.current) : u; if (!sameData(current.current, v)) { current.current = v; setDataState(v); } }, []);
  const reload = useCallback(async () => {
    if (!url) return;
    const mine = ++seq.current;
    try { const r = await get<T>(url, params); if (mine === seq.current) { put(r); setError(null); } }
    catch (e: any) { if (mine === seq.current) setError(e?.response?.data?.detail || e?.message || 'Failed'); }
    finally { if (mine === seq.current) setLoading(false); }
  }, [key]);
  useEffect(() => {
    if (lastUrl.current !== url) { lastUrl.current = url; put(null); setLoading(true); }
    reload();
    if (!every) return () => { seq.current++; };
    const tick = () => { if (!document.hidden) reload(); };
    const id = setInterval(tick, every);
    document.addEventListener('visibilitychange', tick);
    return () => { seq.current++; clearInterval(id); document.removeEventListener('visibilitychange', tick); };
  }, [reload, every]);
  return { data, error, loading, reload, setData: put };
}
