import { describe, expect, it } from 'vitest';
import { parseVoice, plainForSpeech } from '../voiceInput';

describe('what a spoken phrase means', () => {
  it('ends hands-free on the finishing phrases, with or without the name and punctuation', () => {
    for (const t of ['Stop listening.', 'stop listening', 'Selfward, stop listening', 'Hey Selfward stop listening', 'Goodbye!', "That's all"]) expect(parseVoice(t).kind).toBe('stop-listening');
  });
  it('interrupts on stop and its friends', () => {
    for (const t of ['Stop.', 'be quiet', 'Never mind!', 'enough']) expect(parseVoice(t).kind).toBe('stop');
  });
  it('sends everything else, including sentences that merely contain those words', () => {
    for (const t of ['I want to stop worrying so much', 'Yes', 'No thanks', 'I feel like I should stop listening to my boss']) expect(parseVoice(t)).toEqual({ kind: 'text', text: t });
  });
});

describe('an answer as speech', () => {
  it('drops Markdown marks, code and link targets', () => {
    expect(plainForSpeech('## Title\n\nThis is **bold** and _soft_.\n\n- one\n- two\n\n```js\nx=1\n```\n\nSee [the guide](https://example.com).')).toEqual(['Title', 'This is bold and soft.', 'one', 'two', '(code omitted)', 'See the guide.']);
  });
  it('keeps the crisis lines readable', () => {
    const s = plainForSpeech('If you are in distress, please reach out:\n- 988 Suicide & Crisis Lifeline: Call or text 988\n- Emergency Services: Call 911');
    expect(s).toContain('988 Suicide & Crisis Lifeline: Call or text 988'); expect(s).toContain('Emergency Services: Call 911');
  });
});
