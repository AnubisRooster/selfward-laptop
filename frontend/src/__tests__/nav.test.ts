import { describe, expect, it } from 'vitest';
import { hashFor, parseHash, HOME } from '../nav';

describe('addresses', () => {
  it('round-trips every place', () => {
    for (const p of [HOME, { tab: 'chats' as const, sessionId: 12 }, { tab: 'map' as const, sessionId: null }, { tab: 'map' as const, sessionId: 3 }, { tab: 'insights' as const, sessionId: 5 }, { tab: 'narrative' as const, sessionId: null }, { tab: 'settings' as const, sessionId: null }]) expect(parseHash(hashFor(p))).toEqual(p);
  });
  it('ignores addresses that are not ours', () => {
    for (const h of ['', '#', '#/graph', '#/map/x', '#/chats/abc', '#/settings/3', '#/narrative/2', '#/chats/1/2']) expect(parseHash(h)).toBeNull();
  });
});
