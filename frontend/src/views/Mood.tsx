import { useMemo, useState } from 'react';
import { ago, del, errText, post } from '../api';
import { useLoad } from '../hooks';
import { Btn, Card, Empty, Err, Seg, Title, inputCls, cx } from '../ui';
import { ask, toast } from '../feedback';

const FACES = ['😞', '😕', '😐', '🙂', '😄'];
const LABELS = ['Very low', 'Low', 'Okay', 'Good', 'Great'];

/** The daily averages as a line over the chosen days; single check-ins are the faint dots. Days without one are gaps, not zeros. */
function Trend({ data, days }: { data: any; days: number }) {
  const W = 640, H = 200, L = 34, R = 12, T = 10, B = 24;
  const start = new Date(); start.setHours(0, 0, 0, 0); start.setDate(start.getDate() - (days - 1));
  const day = (d: string) => Math.round((new Date(d + 'T00:00:00').getTime() - start.getTime()) / 86400000);
  const x = (i: number) => L + (days <= 1 ? (W - L - R) / 2 : (i / (days - 1)) * (W - L - R));
  const y = (v: number) => T + (1 - (v - 1) / 4) * (H - T - B);
  const pts = (data.daily as any[]).map(d => ({ ...d, i: day(d.day) })).filter(d => d.i >= 0 && d.i < days);
  const path = pts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.average).toFixed(1)}`).join(' ');
  const ticks = [0, Math.floor((days - 1) / 2), days - 1].filter((v, k, a) => a.indexOf(v) === k);
  const label = (i: number) => { const d = new Date(start); d.setDate(d.getDate() + i); return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Mood over the last ${days} days: ${pts.length} days with check-ins`}>
      {[1, 2, 3, 4, 5].map(v => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity={0.12} /><text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="13">{FACES[v - 1]}</text></g>)}
      {ticks.map(i => <text key={i} x={x(i)} y={H - 6} textAnchor={i === 0 ? 'start' : i === days - 1 ? 'end' : 'middle'} fontSize="11" fill="currentColor" fillOpacity={0.55}>{label(i)}</text>)}
      {(data.entries as any[]).map(e => { const i = day(new Date(e.ts * 1000).toLocaleDateString('sv-SE')); return i >= 0 && i < days ? <circle key={e.id} cx={x(i)} cy={y(e.value)} r={3} fill="#818cf8" fillOpacity={0.3} /> : null; })}
      {pts.length > 1 && <path d={path} fill="none" stroke="#818cf8" strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />}
      {pts.map(p => <circle key={p.day} cx={x(p.i)} cy={y(p.average)} r={4.2} fill="#818cf8"><title>{`${p.day}: ${p.average.toFixed(1)} (${p.count} check-in${p.count === 1 ? '' : 's'})`}</title></circle>)}
    </svg>
  );
}

export default function Mood() {
  const [days, setDays] = useState(30);
  const { data, error, reload } = useLoad<any>('/mood', { days });
  const [note, setNote] = useState(''); const [busy, setBusy] = useState(0); const [err, setErr] = useState(''); const [support, setSupport] = useState('');
  const log = async (value: number) => {
    setBusy(value); setErr('');
    try { const r = await post('/mood', { value, note }); setNote(''); setSupport(r.support || ''); toast.ok(`Saved: ${LABELS[value - 1].toLowerCase()}.`); reload(); } catch (e) { setErr(errText(e)); }
    setBusy(0);
  };
  const remove = async (id: number) => { if (await ask.confirm({ title: 'Delete this check-in?', confirmLabel: 'Delete', danger: true })) { await del(`/mood/${id}`); reload(); } };
  const s = data?.stats; const empty = !!data && data.entries.length === 0;
  const groups = useMemo(() => (data?.entries || []).slice(0, 40), [data]);
  return (
    <div className="h-full overflow-y-auto p-6"><div className="mx-auto max-w-3xl space-y-4">
      <Title right={<Seg label="Range" value={String(days)} onChange={v => setDays(Number(v))} options={[['14', '2 weeks'], ['30', 'Month'], ['90', '3 months']]} />}>Mood</Title>

      <Card className="space-y-3">
        <h2 className="font-medium">How are you right now?</h2>
        <div className="grid grid-cols-5 gap-2" role="group" aria-label="Mood">{FACES.map((f, i) => (
          <button key={i} onClick={() => log(i + 1)} disabled={!!busy} className={cx('flex flex-col items-center gap-0.5 rounded-xl border border-zinc-700 bg-zinc-900/60 py-2.5 hover:bg-zinc-800 disabled:opacity-50', busy === i + 1 && 'opacity-70')}>
            <span className="text-2xl" aria-hidden>{f}</span><span className="text-[11px] text-zinc-400">{LABELS[i]}</span></button>))}</div>
        <input className={inputCls} value={note} onChange={e => setNote(e.target.value)} maxLength={500} placeholder="A word or two about it (optional, then tap how you feel)" aria-label="Note for this check-in" />
        <div className="text-xs text-zinc-500">Check-ins and notes stay on this computer, and are never given to a model.</div>
        <Err>{err}</Err>
        {support && <div role="alert" className="whitespace-pre-wrap rounded-lg border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-50">{support}</div>}
      </Card>

      <Err>{error}</Err>
      {empty ? <Empty icon="☺" title="No check-ins in this range">Tap how you feel above, as often as you like. A line of your days builds up here.</Empty> : data && <>
        <Card className="space-y-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-medium">Your days</h2>
            <div className="text-xs text-zinc-500">{s.count} check-in{s.count === 1 ? '' : 's'} on {s.days_logged} day{s.days_logged === 1 ? '' : 's'}{s.average != null && <> · average {s.average.toFixed(1)} of 5</>}</div></div>
          <Trend data={data} days={days} />
          <div className="text-xs text-zinc-500">The line joins each day’s average across the days you checked in; the faint dots are single check-ins. This is a picture of what you tapped, not a measure of how you are.</div>
        </Card>
        <Card className="space-y-1">
          <h2 className="mb-1 font-medium">Recent check-ins</h2>
          <ul className="divide-y divide-zinc-800">{groups.map((e: any) => (
            <li key={e.id} className="flex items-start gap-3 py-2"><span className="text-xl" aria-hidden>{FACES[e.value - 1]}</span>
              <div className="min-w-0 flex-1"><div className="text-sm">{LABELS[e.value - 1]}<span className="ml-2 text-xs text-zinc-500">{ago(e.ts)} · {new Date(e.ts * 1000).toLocaleString()}</span></div>{e.note && <div className="whitespace-pre-wrap text-sm text-zinc-400">{e.note}</div>}</div>
              <button className="text-xs text-zinc-500 hover:text-red-400" onClick={() => remove(e.id)} aria-label="Delete check-in">Delete</button></li>))}</ul>
        </Card>
      </>}
    </div></div>
  );
}
