import { describe, expect, it } from 'vitest';
import { Endpointer, FRAME } from '../vad';
import { encodeWav, toRate16k } from '../wav';

const frames = (seconds: number, level: number) => Array.from({ length: Math.floor(seconds * 50) }, () => Float32Array.from({ length: FRAME }, () => (Math.random() * 2 - 1) * level));
const run = (ep: Endpointer, frs: Float32Array[]) => frs.map(f => ep.feed(f)).filter(Boolean) as any[];

describe('cutting speech into sentences on the phone', () => {
  it('a sentence between silences is one clip', () => {
    const ev = run(new Endpointer(), [...frames(2, 0.0003), ...frames(1.5, 0.15), ...frames(2, 0.0003)]);
    expect(ev.map(e => e.type)).toEqual(['start', 'end']); expect(ev[1].audio.length / 16000).toBeGreaterThan(1.5);
  });
  it('silence and a click send nothing', () => {
    expect(run(new Endpointer(), frames(8, 0.0003))).toEqual([]);
    expect(run(new Endpointer(), [...frames(2, 0.0003), ...frames(0.08, 0.15), ...frames(2, 0.0003)]).filter(e => e.type === 'end' && e.audio)).toEqual([]);
  });
});

describe('audio for the laptop', () => {
  it('writes a valid 16-bit mono WAV', async () => {
    const blob = encodeWav(Float32Array.from([0, 0.5, -0.5, 1, -1]), 16000); const b = new DataView(await blob.arrayBuffer());
    expect(blob.type).toBe('audio/wav'); expect(blob.size).toBe(44 + 10); expect(String.fromCharCode(b.getUint8(0), b.getUint8(1), b.getUint8(2), b.getUint8(3))).toBe('RIFF');
    expect(b.getUint32(24, true)).toBe(16000); expect(b.getInt16(46, true)).toBe(16383); expect(b.getInt16(52, true)).toBe(-32768);
  });
  it('brings 48 kHz down to 16 kHz without losing the tail between blocks', () => {
    const carry = { pos: 0 }; const a = toRate16k(new Float32Array(4096).fill(1), 48000, carry); const b = toRate16k(new Float32Array(4096).fill(1), 48000, carry);
    expect(a.length + b.length).toBeGreaterThanOrEqual(Math.floor(8192 / 3) - 1); expect(a.every(x => x === 1)).toBe(true);
  });
});

describe('a room that gets noisier', () => {
  it('does not hold the microphone open to the limit, and ends within a few seconds', () => {
    const ev: any[] = []; const ep = new Endpointer(); let i = 0;
    for (const f of [...frames(2, 0.0003), ...frames(40, 0.01)]) { const e = ep.feed(f); if (e) ev.push({ at: i / 50, ...e }); i++; }
    expect(ev.map(e => e.type)).toEqual(['start', 'end']); expect(ev[1].audio).toBeNull(); expect(ev[1].at).toBeLessThan(6);
  });
  it('still hears you talk over it, and keeps what you said', () => {
    const speech = Array.from({ length: 200 }, (_, k) => Float32Array.from({ length: FRAME }, () => (Math.random() * 2 - 1) * (0.05 + 0.2 * Math.abs(Math.sin(k / 6)))));       // moves by many dB, like speech
    const ev = run(new Endpointer(), [...frames(2, 0.0003), ...speech, ...frames(4, 0.01)]);
    expect(ev.filter(e => e.type === 'end' && e.audio).length).toBe(1); expect(ev.find(e => e.audio).audio.length / 16000).toBeGreaterThan(3);
  });
  it('a shorter pause ends a turn sooner', () => {
    const endAt = (silenceMs: number) => { const ep = new Endpointer({ silenceMs }); let i = 0; for (const f of [...frames(2, 0.0003), ...frames(1.5, 0.15).map((x, k) => x.map(v => v * (0.4 + 0.6 * Math.abs(Math.sin(k / 5))))), ...frames(3, 0.0003)]) { const e = ep.feed(f); if (e && e.type === 'end') return i; i++; } return -1; };
    expect(endAt(400)).toBeLessThan(endAt(1200)); expect(endAt(400)).toBeGreaterThan(0);
  });
});
