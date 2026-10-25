/** Where you are in the app, and how that is written in the address (`#/chats/12`) so Back, Forward and Reload work. */
export type Tab = 'chats' | 'settings';
export const TABS: Tab[] = ['chats', 'settings'];

export interface Place { tab: Tab; sessionId: number | null }
export const HOME: Place = { tab: 'chats', sessionId: null };

export function hashFor(p: Place): string {
  return p.tab === 'chats' && p.sessionId != null ? `#/chats/${p.sessionId}` : `#/${p.tab}`;
}

/** The place an address stands for, or null when it isn't one of ours. */
export function parseHash(hash: string): Place | null {
  const m = /^#\/([a-z]+)(?:\/(\d+))?$/.exec(hash || '');
  if (!m || !(TABS as string[]).includes(m[1])) return null;
  const tab = m[1] as Tab;
  if (m[2] !== undefined && tab !== 'chats') return null;
  return { tab, sessionId: m[2] !== undefined ? Number(m[2]) : null };
}
