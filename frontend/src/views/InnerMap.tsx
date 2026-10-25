import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { ask, toast } from '../feedback';
import { BASE, errText, post } from '../api';
import { useLoad, useNav } from '../hooks';
import { isLight } from '../theme';
import { Badge, Btn, Card, Empty, Err, Seg, Title, cx } from '../ui';

const download = (path: string) => { const a = document.createElement('a'); a.href = BASE + '/api' + path; a.click(); };

export default function InnerMap() {
  const { sessionId, go } = useNav();
  const [hidden, setHidden] = useState<string[]>([]);
  const [sel, setSel] = useState<{ type: string; label: string } | null>(null);
  const [mode, setMode] = useState(typeof window !== 'undefined' && window.innerWidth < 900 ? 'list' : 'graph');
  const [busy, setBusy] = useState(false);
  const { data: sessions } = useLoad<any[]>('/sessions');
  const all = useLoad<any>('/graph', { session_id: sessionId ?? undefined });
  const data = all.data;
  const types: any[] = data?.types || [];
  const shown = useMemo(() => {
    if (!data) return { nodes: [] as any[], edges: [] as any[] };
    const nodes = data.nodes.filter((n: any) => !hidden.includes(n.type)); const keep = new Set(nodes.map((n: any) => n.id));
    return { nodes, edges: data.edges.filter((e: any) => keep.has(e.source) && keep.has(e.target)) };
  }, [data, hidden]);
  const box = useRef<HTMLDivElement>(null); const fg = useRef<any>(null); const [sz, setSz] = useState({ w: 400, h: 400 });
  useEffect(() => { fg.current?.d3Force?.('charge')?.strength(-140); fg.current?.d3Force?.('link')?.distance(60); }, [data]);
  useEffect(() => { const el = box.current; if (!el) return; const ro = new ResizeObserver(() => setSz({ w: el.clientWidth, h: el.clientHeight })); ro.observe(el); return () => ro.disconnect(); }, [mode, data]);
  // Keep each node's object (and so its position) across refreshes: the map updates in place instead of re-laying out.
  const cache = useRef(new Map<string, any>()); const fitted = useRef('');
  const gdata = useMemo(() => {
    const seen = new Set<string>();
    const nodes = shown.nodes.map((n: any) => { seen.add(n.id); const old = cache.current.get(n.id); const v = old ? Object.assign(old, n) : { ...n }; cache.current.set(n.id, v); return v; });
    for (const k of [...cache.current.keys()]) if (!seen.has(k)) cache.current.delete(k);
    return { nodes, links: shown.edges.map((e: any) => ({ source: e.source, target: e.target, w: e.weight, phrase: e.phrase })) };
  }, [shown]);
  const selId = sel ? `${sel.type}:${sel.label.toLowerCase()}` : '';
  const toggle = (t: string) => setHidden(h => h.includes(t) ? h.filter(x => x !== t) : [...h, t]);
  const rebuild = async () => {
    if (!await ask.confirm({ title: 'Rebuild the map?', body: 'Clears the map and builds it again from everything you have written in your sessions. Your sessions are not changed.', confirmLabel: 'Rebuild' })) return;
    setBusy(true); try { const r = await post('/graph/rebuild'); toast.ok(`Rebuilt from ${r.messages} messages.`); setSel(null); all.reload(); } catch (e) { toast.error(errText(e)); } setBusy(false);
  };
  const empty = data && data.nodes.length === 0;
  return (
    <div className="flex h-full flex-col md:flex-row">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="space-y-2 border-b border-zinc-800 p-3">
          <Title right={<Seg label="View" value={mode} onChange={setMode} options={[['graph', 'Map'], ['list', 'List']]} />}>Inner Map</Title>
          <div className="flex flex-wrap items-center gap-2">
            <select className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs" aria-label="Which sessions" value={sessionId ?? ''} onChange={e => { setSel(null); go('map', { sessionId: e.target.value ? Number(e.target.value) : null }); }}>
              <option value="">All sessions</option>{(sessions || []).map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
            <ul className="flex flex-wrap gap-1.5" aria-label="Show these kinds">{types.map(t => (
              <li key={t.id}><button aria-pressed={!hidden.includes(t.id)} onClick={() => toggle(t.id)} className={cx('flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs', hidden.includes(t.id) ? 'border-zinc-800 text-zinc-600' : 'border-zinc-700 text-zinc-300')}>
                <span className="h-2 w-2 rounded-full" style={{ background: hidden.includes(t.id) ? 'transparent' : t.color, border: `1px solid ${t.color}` }} />{t.label}</button></li>))}</ul>
          </div>
          {data && !empty && <div className="text-xs text-zinc-500">{data.stats.nodes} things across {data.stats.sessions} session{data.stats.sessions === 1 ? '' : 's'}, {data.stats.edges} connections. Bigger means it came up more. Built from your own words on this computer; no model is involved.</div>}
        </div>
        <Err>{all.error}</Err>
        <div ref={box} className="relative min-h-0 flex-1 overflow-hidden">
          {empty ? <Empty icon="⁂" title="Nothing on the map yet">As you write about feelings, people, beliefs and events, they appear here and connect. Already have sessions from before?
            <div className="mt-3"><Btn onClick={rebuild} loading={busy}>Build it from my sessions</Btn></div></Empty>
          : shown.nodes.length === 0 ? <Empty icon="⁂" title="Everything is hidden">Turn a kind back on above.</Empty>
          : mode === 'graph' ? (
            <ForceGraph2D ref={fg} width={sz.w} height={sz.h} graphData={gdata} d3VelocityDecay={0.3} backgroundColor="rgba(0,0,0,0)" enableNodeDrag={false} cooldownTicks={200}
              onEngineStop={() => { const k = `${sessionId}:${hidden.join()}`; if (fitted.current !== k) { fitted.current = k; fg.current?.zoomToFit(400, 40); } }}
              nodeLabel={(n: any) => `${n.label} (${n.type})`} onNodeClick={(n: any) => setSel({ type: n.type, label: n.label })} onBackgroundClick={() => setSel(null)}
              linkColor={() => 'rgba(113,113,122,.5)'} linkWidth={(l: any) => Math.min(4, 0.6 + l.w * 0.6)} linkDirectionalArrowLength={4} linkDirectionalArrowRelPos={0.95}
              nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, k: number) => {
                const r = 3 + Math.min(n.strength, 6) * 1.6; ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = n.color; ctx.fill();
                if (n.id === selId) { ctx.lineWidth = 1.5 / k; ctx.strokeStyle = isLight() ? '#000' : '#fff'; ctx.stroke(); }
                if (k < 0.8 && n.strength < 2 && n.id !== selId) return;
                ctx.font = `${Math.max(3, 11 / k)}px sans-serif`; ctx.fillStyle = isLight() ? '#27272a' : '#e4e4e7'; ctx.textAlign = 'center'; ctx.fillText(n.label, n.x, n.y + r + 9 / k);
              }} />
          ) : (
            <ul className="h-full overflow-y-auto" aria-label="Things on the map">{[...shown.nodes].sort((a: any, b: any) => b.strength - a.strength).map((n: any) => (
              <li key={n.id}><button onClick={() => setSel({ type: n.type, label: n.label })} className={cx('flex w-full items-center gap-3 border-b border-zinc-800/70 px-4 py-2.5 text-left hover:bg-zinc-900', selId === n.id && 'bg-zinc-900')}>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: n.color }} /><span className="flex-1 text-sm">{n.label}</span><Badge>{n.type}</Badge>
                <span className="w-28 text-right text-xs text-zinc-500">{n.strength.toFixed(1)} · {n.sessions.length} session{n.sessions.length === 1 ? '' : 's'}</span></button></li>))}</ul>)}
        </div>
        {!empty && data && <Overview data={data} onPick={(type, label) => setSel({ type, label })} onExport={download} onRebuild={rebuild} busy={busy} sessionId={sessionId} />}
      </section>
      {sel && <Detail sel={sel} sessionId={sessionId} onClose={() => setSel(null)} onPick={(type, label) => setSel({ type, label })} onOpen={(id: number) => go('chats', { sessionId: id })} />}
    </div>
  );
}

function Overview({ data, onPick, onExport, onRebuild, busy, sessionId }: { data: any; onPick: (t: string, l: string) => void; onExport: (p: string) => void; onRebuild: () => void; busy: boolean; sessionId: number | null }) {
  const [open, setOpen] = useState(false);
  const q = sessionId ? `?session_id=${sessionId}` : '';
  return (
    <div className="border-t border-zinc-800">
      <button className="flex w-full items-center justify-between px-4 py-2 text-left text-xs text-zinc-400 hover:bg-zinc-900" aria-expanded={open} onClick={() => setOpen(o => !o)}><span>Strongest connections, themes and export</span><span aria-hidden>{open ? '▾' : '▸'}</span></button>
      {open && <div className="max-h-64 space-y-3 overflow-y-auto px-4 pb-3">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{data.types.filter((t: any) => data.stats.top[t.id]).map((t: any) => (
          <Card key={t.id} className="!p-3"><div className="mb-1 text-xs font-medium" style={{ color: t.color }}>{t.label}</div>
            <ul className="space-y-0.5">{data.stats.top[t.id].map((n: any) => <li key={n.label} className="flex justify-between gap-2 text-sm"><button className="truncate text-left hover:underline" onClick={() => onPick(t.id, n.label)}>{n.label}</button><span className="text-xs text-zinc-500">{n.strength}</span></li>)}</ul></Card>))}</div>
        {data.links.length > 0 && <div><div className="mb-1 text-xs font-medium text-zinc-400">Connections that came up most</div>
          <ul className="space-y-0.5 text-sm text-zinc-300">{data.links.map((l: any, i: number) => <li key={i} className="flex justify-between gap-3"><span>{l.text}</span><span className="text-xs text-zinc-500">{l.weight}</span></li>)}</ul></div>}
        <div className="flex flex-wrap gap-2"><Btn small onClick={() => onExport('/graph/export/graphml' + q)}>Export GraphML (Gephi)</Btn><Btn small onClick={() => onExport('/graph/export/cytoscape' + q)}>Export Cytoscape JSON</Btn><Btn small kind="ghost" onClick={onRebuild} loading={busy}>Rebuild from my sessions</Btn></div>
      </div>}
    </div>
  );
}

function Detail({ sel, sessionId, onClose, onPick, onOpen }: { sel: { type: string; label: string }; sessionId: number | null; onClose: () => void; onPick: (t: string, l: string) => void; onOpen: (id: number) => void }) {
  const { data, error } = useLoad<any>('/graph/node', { type: sel.type, label: sel.label, session_id: sessionId ?? undefined });
  const dir = (l: any) => l.direction === 'out' ? `${sel.label} ${l.relation} ${l.label}` : `${l.label} ${l.relation} ${sel.label}`;
  return (
    <aside className="min-h-0 w-full overflow-y-auto border-t border-zinc-800 p-4 md:w-80 md:border-l md:border-t-0" aria-label="Details">
      <div className="mb-2 flex items-start justify-between"><div><h2 className="text-lg font-semibold">{sel.label}</h2><div className="text-xs text-zinc-500">{sel.type}{data && ` · came up ${data.node.strength.toFixed(1)}`}</div></div>
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200" aria-label="Close details">✕</button></div>
      <Err>{error}</Err>
      {data && <>
        <h3 className="mb-1 mt-3 text-xs font-medium uppercase tracking-wide text-zinc-500">Connections</h3>
        {data.links.length === 0 ? <div className="text-sm text-zinc-500">Nothing linked yet.</div> :
          <ul className="space-y-1">{data.links.map((l: any, i: number) => <li key={i} className="text-sm"><button className="text-left text-indigo-300 hover:underline" onClick={() => onPick(l.type, l.label)}>{dir(l)}</button></li>)}</ul>}
        <h3 className="mb-1 mt-4 text-xs font-medium uppercase tracking-wide text-zinc-500">Where it came up</h3>
        <ul className="space-y-1">{data.sessions.map((s: any) => <li key={s.id}><button className="text-left text-sm text-zinc-300 hover:text-zinc-50 hover:underline" onClick={() => onOpen(s.id)}>{s.title}</button></li>)}</ul>
      </>}
    </aside>
  );
}
