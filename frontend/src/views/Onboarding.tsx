import { useState } from 'react';
import { errText, post } from '../api';
import { useLoad } from '../hooks';
import { Btn, Err, Field, inputCls, cx } from '../ui';

const STEPS = ['Welcome', 'About you', 'What brings you here', 'How you want to talk', 'Check the model'];

export default function Onboarding({ status, onDone }: { status: any; onDone: () => void }) {
  const { data: catalog } = useLoad<any>('/catalog');
  const [step, setStep] = useState(0);
  const [v, setV] = useState<any>({ user_name: '', user_pronouns: '', user_age: '', intake_concerns: '', intake_history: '', intake_goals: '', region: status.region || 'US', default_persona: 'therapist', default_modality: 'integrated', accept_disclaimer: false });
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setV((o: any) => ({ ...o, [k]: e.target.value }));
  const pre = status.preflight;
  const finish = async () => { setBusy(true); setErr(''); try { await post('/onboarding/complete', v); onDone(); } catch (e) { setErr(errText(e)); setBusy(false); } };
  const next = () => setStep(s => s + 1);
  const canNext = step === 0 ? v.accept_disclaimer : true;
  return (
    <div className="flex h-full items-center justify-center overflow-y-auto p-4">
      <div className="w-full max-w-xl">
        <div className="mb-1 text-xs text-zinc-500" aria-live="polite">Step {step + 1} of {STEPS.length} · {STEPS[step]}</div>
        <div className="mb-4 flex gap-1" aria-hidden>{STEPS.map((_, i) => <div key={i} className={cx('h-1 flex-1 rounded', i <= step ? 'bg-indigo-500' : 'bg-zinc-800')} />)}</div>
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          {step === 0 && <div className="space-y-4">
            <h1 className="text-2xl font-semibold">Welcome to Selfward</h1>
            <p className="text-sm text-zinc-300">A private place to reflect, with a guide who follows an approach you choose. Everything is stored on this computer, and the conversation is answered by a model running here (unless you pick a cloud model in Settings).</p>
            <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-3 text-sm text-amber-100">
              <div className="mb-1 font-medium">Please read this</div>
              Selfward is <b>not</b> a licensed therapist, psychologist or medical provider. It is a journaling and self-reflection tool. It cannot diagnose, treat or manage any mental health condition. If you are in crisis, use <b>Get help now</b> (always in the sidebar) or call your local emergency number.
            </div>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={v.accept_disclaimer} onChange={e => setV((o: any) => ({ ...o, accept_disclaimer: e.target.checked }))} /><span>I understand that Selfward is not a substitute for professional care.</span></label>
          </div>}
          {step === 1 && <div className="space-y-3">
            <h2 className="text-lg font-semibold">About you</h2><p className="text-sm text-zinc-400">All optional. It helps the guide address you properly.</p>
            <Field label="What should I call you?"><input className={inputCls} value={v.user_name} onChange={set('user_name')} autoFocus /></Field>
            <div className="grid grid-cols-2 gap-3"><Field label="Pronouns"><input className={inputCls} value={v.user_pronouns} onChange={set('user_pronouns')} placeholder="e.g. she/her, they/them" /></Field>
              <Field label="Age"><input className={inputCls} value={v.user_age} onChange={set('user_age')} inputMode="numeric" /></Field></div>
            <Field label="Where are you? (for the crisis lines Selfward shows)"><select className={inputCls} value={v.region} onChange={set('region')}>{(catalog?.regions || ['US']).map((r: string) => <option key={r}>{r}</option>)}<option value="OTHER">Somewhere else (international list)</option></select></Field>
          </div>}
          {step === 2 && <div className="space-y-3">
            <h2 className="text-lg font-semibold">What brings you here?</h2><p className="text-sm text-zinc-400">Share as much or as little as you like. You can change it later in Settings.</p>
            <Field label="What's on your mind lately?"><textarea rows={3} className={inputCls} value={v.intake_concerns} onChange={set('intake_concerns')} /></Field>
            <Field label="Any past experience with therapy or counselling?"><textarea rows={2} className={inputCls} value={v.intake_history} onChange={set('intake_history')} /></Field>
            <Field label="What would you like to get from this?"><textarea rows={2} className={inputCls} value={v.intake_goals} onChange={set('intake_goals')} /></Field>
          </div>}
          {step === 3 && <div className="space-y-3">
            <h2 className="text-lg font-semibold">How do you want to talk?</h2>
            <div role="radiogroup" aria-label="Default guide" className="space-y-2">{(catalog?.personas || []).map((p: any) => (
              <button key={p.id} role="radio" aria-checked={v.default_persona === p.id} onClick={() => setV((o: any) => ({ ...o, default_persona: p.id }))} className={cx('block w-full rounded-lg border px-3 py-2 text-left', v.default_persona === p.id ? 'border-indigo-500 bg-indigo-950/30' : 'border-zinc-700 hover:bg-zinc-800')}>
                <div className="text-sm font-medium">{p.label}</div><div className="text-xs text-zinc-500">{p.blurb}</div></button>))}</div>
            {v.default_persona === 'therapist' && <Field label="Approach" hint={catalog?.modalities.find((m: any) => m.id === v.default_modality)?.description}>
              <select className={inputCls} value={v.default_modality} onChange={set('default_modality')}>{(catalog?.modalities || []).map((m: any) => <option key={m.id} value={m.id}>{m.id.replace(/_/g, ' ')}</option>)}</select></Field>}
          </div>}
          {step === 4 && <div className="space-y-3">
            <h2 className="text-lg font-semibold">Check the model</h2>
            <ul className="space-y-1.5 text-sm">
              <li>{pre.ollama ? '✅' : '⚠️'} Ollama {pre.ollama ? 'is running' : 'isn’t running. Start it with `ollama serve`.'}</li>
              <li>{pre.chat_model ? '✅' : '⚠️'} Chat model <code className="rounded bg-zinc-800 px-1">{status.model}</code> {pre.chat_model ? 'is installed' : 'isn’t installed yet. Run `ollama pull llama3.2:3b`, or pick another model in Settings.'}</li>
              <li>{pre.embed_model ? '✅' : 'ℹ️'} Memory model {pre.embed_model ? 'is installed' : 'isn’t installed. Memory then falls back to matching words. `ollama pull nomic-embed-text` improves it.'}</li></ul>
            <p className="text-xs text-zinc-500">You can finish now and fix this afterwards.</p>
            <Err>{err}</Err>
          </div>}
          <div className="mt-6 flex justify-between">
            <Btn kind="ghost" disabled={step === 0} onClick={() => setStep(s => s - 1)}>Back</Btn>
            {step < STEPS.length - 1 ? <Btn kind="primary" disabled={!canNext} onClick={next}>Continue</Btn> : <Btn kind="primary" loading={busy} onClick={finish}>Start using Selfward</Btn>}
          </div>
        </div>
      </div>
    </div>
  );
}
