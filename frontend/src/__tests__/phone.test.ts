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
