/** Where you are in the app, and how that is written in the address (`#/chats/12`) so Back, Forward and Reload work. */
export type Tab = 'chats' | 'map' | 'insights' | 'narrative' | 'mood' | 'settings';
export const TABS: Tab[] = ['chats', 'map', 'insights', 'narrative', 'mood', 'settings'];

/** `sessionId` is the open session on the Sessions tab, and the session the Inner Map and Insights are limited to (null = all of them). */
export interface Place { tab: Tab; sessionId: number | null }
export const HOME: Place = { tab: 'chats', sessionId: null };

export function hashFor(p: Place): string {
  return p.tab !== 'settings' && p.sessionId != null ? `#/${p.tab}/${p.sessionId}` : `#/${p.tab}`;
}

/** The place an address stands for, or null when it isn't one of ours. */
export function parseHash(hash: string): Place | null {
  const m = /^#\/([a-z]+)(?:\/(\d+))?$/.exec(hash || '');
  if (!m || !(TABS as string[]).includes(m[1])) return null;
  const tab = m[1] as Tab;
  if (m[2] !== undefined && (tab === 'settings' || tab === 'narrative' || tab === 'mood')) return null;
  return { tab, sessionId: m[2] !== undefined ? Number(m[2]) : null };
}
