/** What a spoken phrase means in a hands-free session. Pure, so it can be tested without a microphone. */

export type VoiceCmd = { kind: 'stop-listening' } | { kind: 'stop' } | { kind: 'text'; text: string };

const norm = (t: string) => t.toLowerCase().replace(/[^a-z' ]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/^(hey |ok |okay )?selfward,? ?/, '');
const STOP_LISTENING = new Set(['stop listening', 'turn off hands free', 'hands free off', 'stop hands free', 'goodbye', 'that is all', 'that\'s all', 'end hands free']);
const STOP = new Set(['stop', 'stop talking', 'stop reading', 'be quiet', 'quiet', 'never mind', 'nevermind', 'cancel', 'enough']);

export function parseVoice(said: string): VoiceCmd {
  const n = norm(said);
  if (STOP_LISTENING.has(n)) return { kind: 'stop-listening' };
  if (STOP.has(n)) return { kind: 'stop' };
  return { kind: 'text', text: said.trim() };
}

/** An answer as spoken sentences: no Markdown marks, no code, links as their words. */
export function plainForSpeech(md: string): string[] {
  const t = (md || '')
    .replace(/```[\s\S]*?```/g, ' (code omitted) ')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*(?:[-*•]|\d+[.)])\s+/gm, '')
    .replace(/(\*\*|__|\*|_)(\S[^*_]*?)\1/g, '$2')
    .replace(/[ \t]+/g, ' ');
  return t.split(/\n{2,}|\n/).map(p => p.trim()).filter(Boolean);
}
