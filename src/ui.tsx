import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowRight, ArrowUpRight, ExternalLink, X } from 'lucide-react'
import type { Area, Category, HistoryPoint } from './types'
import { monthDate, number } from './format'

export function Change({ value, long = false }: { value: number | null | undefined; long?: boolean }) {
  if (value == null) return <span className="no-data">Unavailable</span>
  const Icon = value < 0 ? ArrowDownRight : value > 0 ? ArrowUpRight : ArrowRight
  return <span className={`change ${value < 0 ? 'change--down' : value > 0 ? 'change--up' : ''}`}><Icon size={15} aria-hidden="true" />{value !== 0 && Math.abs(value) < 0.05 ? '<0.1' : Math.abs(value).toFixed(1)}%{long && <span> {value < 0 ? 'fewer' : value > 0 ? 'more' : 'change'} offences</span>}<span className="sr-only"> {value < 0 ? 'decrease' : value > 0 ? 'increase' : 'change'} from the previous year</span></span>
}
export function Sparkline({ history, large = false }: { history: HistoryPoint[]; large?: boolean }) {
  const valid = history.filter(p => p.count !== null)
  if (valid.length < 2) return <span className="no-data">{history.length ? 'Incomplete' : '—'}</span>
  const w = large ? 620 : 92, h = large ? 150 : 28, pad = large ? 12 : 3
  const vals = valid.map(p => p.count!)
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1
  const startTime = Date.parse(history[0].periodEnd), timeSpan = Date.parse(history.at(-1)!.periodEnd) - startTime || 1
  const coords = history.map(p => p.count === null ? null : `${pad + (Date.parse(p.periodEnd) - startTime) / timeSpan * (w - pad * 2)},${h - pad - (p.count - min) / span * (h - pad * 2)}`)
  const segments: string[][] = []; let segment: string[] = []
  for (const point of coords) { if (point === null) { if (segment.length) segments.push(segment); segment = [] } else segment.push(point) }
  if (segment.length) segments.push(segment)
  const first = coords[0], last = coords.at(-1), start = history[0], end = history.at(-1)!
  return <div className={`trend-chart ${large ? 'trend-chart--large' : ''}`}><svg className={`sparkline ${large ? 'sparkline--large' : ''}`} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Rolling annual offence totals: ${history.map(p => `${monthDate(p.periodEnd)}, ${p.count === null ? 'unavailable' : number(p.count)}`).join('; ')}`}>
    <title>{`Annual totals: ${monthDate(start.periodEnd)}: ${number(start.count)}; ${monthDate(end.periodEnd)}: ${number(end.count)}. The dashed line marks the starting total. Each chart has its own vertical scale.`}</title>
    {large && <><line x1="0" x2={w} y1={h / 2} y2={h / 2} stroke="#e5e9f1" /><line x1="0" x2={w} y1={h - 1} y2={h - 1} stroke="#e5e9f1" /></>}
    {first && <line x1={pad} x2={w - pad} y1={first.split(',')[1]} y2={first.split(',')[1]} stroke="#aeb8ca" strokeWidth={large ? 1 : 0.7} strokeDasharray={large ? '5 5' : '2 3'} />}
    {segments.map((points, i) => <polyline key={i} points={points.join(' ')} fill="none" stroke="currentColor" strokeWidth={large ? 2.4 : 1.7} strokeLinejoin="round" strokeLinecap="round" />)}
    {first && <circle cx={first.split(',')[0]} cy={first.split(',')[1]} r={large ? 3.5 : 2.3} fill="white" stroke="currentColor" strokeWidth={large ? 1.8 : 1.2} />}
    {last && <circle cx={last.split(',')[0]} cy={last.split(',')[1]} r={large ? 3.5 : 2.3} fill="currentColor" />}
  </svg><div className="trend-endpoints" aria-hidden="true"><span title={`Year ending ${monthDate(start.periodEnd)}`}>{large && <span>{monthDate(start.periodEnd)}</span>}{number(start.count)}</span><span title={`Year ending ${monthDate(end.periodEnd)}`}>{large && <span>{monthDate(end.periodEnd)}</span>}{number(end.count)}</span></div></div>
}
export function AreaAvatar({ area, large = false }: { area: Area; large?: boolean }) {
  return <img className={`area-avatar ${large ? 'area-avatar--large' : ''}`} src={`/maps/${area.code}.svg`} alt={`${area.name} shaded within England and Wales`} width={large ? 160 : 50} height={large ? 192 : 60} loading={large ? 'eager' : 'lazy'} />
}

export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const d = ref.current!; if (!d.open) d.showModal(); return () => { if (d.open) d.close() } }, [])
  return <dialog ref={ref} className={`modal ${wide ? 'modal--wide' : ''}`} onCancel={e => { e.preventDefault(); onClose() }} onClick={e => { if (e.target === e.currentTarget) onClose() }} aria-labelledby="modal-title">
    <div className="modal-header"><h2 id="modal-title">{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog" autoFocus><X size={21} /></button></div>
    {children}
  </dialog>
}
export function OfficialLink({ href, children }: { href: string; children: ReactNode }) { return <a href={href} target="_blank" rel="noreferrer">{children}<ExternalLink size={13} aria-hidden="true" /></a> }

export function CategoryOptions({ categories }: { categories: Category[] }) {
  if (!categories.some(c => c.group)) return <>{categories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</>
  const groups = [...new Set(categories.map(c => c.group || 'Crime types'))]
  return <>{groups.map(group => <optgroup key={group} label={group}>{categories.filter(c => (c.group || 'Crime types') === group).map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</optgroup>)}</>
}
