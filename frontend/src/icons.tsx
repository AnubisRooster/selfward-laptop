import { Activity, ArrowUpRight, Brain, BrainCircuit, BookOpen, CircleHelp, Drama, Eye, Footprints, Heart, Hexagon, Link2, MessagesSquare, MoonStar, Sparkles, Star, Users, Moon, NotebookPen } from 'lucide-react';
import { cx } from './ui';

/** The iPhone app's SF Symbols, as the nearest icons here. */
export const MODALITY_ICONS: Record<string, any> = {
  adlerian: Footprints, jungian: MoonStar, active_imagination: Drama, dbt: Brain, integrated: Sparkles, free_form: MessagesSquare, cbt: BrainCircuit, humanistic: Heart,
  existential: CircleHelp, gestalt: Hexagon, somatic: Activity, narrative: BookOpen, act: ArrowUpRight, psychodynamic: Eye, ifs: Users,
};
export const ModalityIcon = ({ id, size = 13, className }: { id: string; size?: number; className?: string }) => { const I = MODALITY_ICONS[id] || Sparkles; return <I size={size} aria-hidden className={className} />; };

/** The guides' own portraits (copied from the iPhone app). */
export const PersonaAvatar = ({ kind, size = 32, className }: { kind: string; size?: number; className?: string }) =>
  <img src={`/avatar-${['therapist', 'companion', 'spiritual'].includes(kind) ? kind : 'therapist'}.png`} alt="" width={size} height={size} className={cx('shrink-0 rounded-full', className)} style={{ width: size, height: size }} />;

const TONES: Record<string, string> = {
  teal: 'bg-teal-500/15 text-teal-300', purple: 'bg-purple-500/15 text-purple-300', indigo: 'bg-indigo-500/15 text-indigo-300', green: 'bg-emerald-500/15 text-emerald-300', orange: 'bg-amber-500/15 text-amber-300',
};
/** A small pill under a reply, like the phone's: what that exchange added. */
export function BadgePill({ icon: Icon, label, tone, title, onClick }: { icon: any; label: string; tone: keyof typeof TONES; title: string; onClick?: () => void }) {
  const cls = cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]', TONES[tone], onClick && 'hover:brightness-125');
  return onClick ? <button onClick={onClick} title={title} className={cls}><Icon size={11} aria-hidden />{label}</button> : <span title={title} className={cls}><Icon size={11} aria-hidden />{label}</span>;
}
export const BADGE_ICONS = { memory: Brain, nodes: Hexagon, edges: Link2, dream: Moon, note: NotebookPen, insight: Star };
