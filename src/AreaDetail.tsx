import { useRef, useState } from 'react'
import { ChevronDown, Download, Info, Layers2, X } from 'lucide-react'
import type { Area, Category, CrimeData, Metric } from './types'
import { comparableValue, rankAreas } from './model'
import { exportAreaDetailCsv, getMonthlyComparisons, percentageChange } from './detail-model'
import { categoryRate, monthDate, number, rate, rateDenominator, rateLabel, rateMultiplier, shortDate } from './format'
import { AreaAvatar, CategoryOptions, Change, Modal, OfficialLink, Sparkline } from './ui'

type DetailProps = {
  area: Area; data: CrimeData; category: Category; selected: boolean;
  onClose: () => void; onCompare: () => void; onCategoryChange: (id: string) => void;
}

function ExactHistory({ metric, category }: { metric: Metric; category: Category }) {
  return <details className="detail-disclosure">
    <summary>View all rolling-year figures <ChevronDown size={15} /></summary>
    <div className="detail-table-wrap" tabIndex={0} role="region" aria-label="Rolling-year figures, scroll horizontally if needed">
      <table className="detail-data-table"><caption className="sr-only">Rolling annual offence totals and population rates</caption>
        <thead><tr><th scope="col">Year ending</th><th scope="col">Offences</th><th scope="col">Per {number(rateDenominator(category))} residents</th></tr></thead>
        <tbody>{[...metric.history].reverse().map(p => <tr key={p.periodEnd}><th scope="row">{monthDate(p.periodEnd)}</th><td>{number(p.count)}</td><td>{categoryRate(p.rate, category)}</td></tr>)}</tbody>
      </table>
    </div>
  </details>
}

function MonthlyActivity({ metric, category }: { metric: Metric; category: Category }) {
  const months = getMonthlyComparisons(metric)
  const [selectedMonth, setSelectedMonth] = useState(months.at(-1)?.month || '')
  const current = months.find(m => m.month === selectedMonth) || months.at(-1)
  if (!current) return null
  const maximum = Math.max(1, ...months.flatMap(m => [m.count ?? 0, m.previousCount ?? 0]))
  return <section className="detail-section monthly-activity" aria-labelledby="monthly-activity-title">
    <div className="detail-section-heading"><div><span className="section-label">Month by month</span><h3 id="monthly-activity-title">Monthly recorded offences</h3></div><span className="detail-period">{monthDate(months[0].month)}–{monthDate(months.at(-1)!.month)}</span></div>
    <p className="detail-explainer">{category.label}. Each blue bar is one month, paired with the same month a year earlier. These are monthly counts, without seasonal adjustment.</p>
    <div className="monthly-readout" aria-live="polite" aria-atomic="true"><div><span>{monthDate(current.month)}</span><strong>{number(current.count)}</strong><small>recorded offences</small></div><div><span>{monthDate(current.previousMonth)}</span><strong>{number(current.previousCount)}</strong><small>same month last year</small></div><div><span>Monthly year-on-year</span><Change value={current.changePercent} /><small>{current.changePercent == null ? 'Requires both months and a nonzero earlier count' : 'Compares these two months only'}</small></div></div>
    <div className="monthly-chart-legend"><span><i />Current year</span><span><i />Previous year</span><span>Choose a month for exact figures</span></div>
    <div className="monthly-bars" role="group" aria-label="Monthly offence counts compared with the same month last year">
      {months.map(m => <button key={m.month} className={`monthly-bar-group ${m.month === current.month ? 'monthly-bar-group--selected' : ''}`} aria-pressed={m.month === current.month} aria-label={`${monthDate(m.month)}: ${m.count == null ? 'unavailable' : number(m.count)} offences; ${monthDate(m.previousMonth)}: ${m.previousCount == null ? 'unavailable' : number(m.previousCount)} offences`} onClick={() => setSelectedMonth(m.month)} onFocus={() => setSelectedMonth(m.month)} onMouseEnter={() => setSelectedMonth(m.month)}>
        <span className="monthly-bar-pair" aria-hidden="true"><span className={`monthly-bar monthly-bar--previous ${m.previousCount == null ? 'monthly-bar--missing' : ''}`} style={{ height: m.previousCount == null ? '100%' : `${m.previousCount / maximum * 100}%` }} /><span className={`monthly-bar ${m.count == null ? 'monthly-bar--missing' : ''}`} style={{ height: m.count == null ? '100%' : `${m.count / maximum * 100}%` }} /></span>
        <span className="monthly-bar-label" aria-hidden="true">{monthDate(m.month).split(' ')[0]}</span>
      </button>)}
    </div>
    <p className="chart-scale-note">Bars start at zero. Striped columns indicate unavailable data. Select a month or open the table for its exact value.</p>
    <details className="detail-disclosure"><summary>View all monthly figures <ChevronDown size={15} /></summary>
      <div className="detail-table-wrap" tabIndex={0} role="region" aria-label="Monthly figures, scroll horizontally if needed"><table className="detail-data-table"><caption className="sr-only">The latest twelve months paired with the same months of the previous year</caption><thead><tr><th scope="col">Month</th><th scope="col">Offences</th><th scope="col">Same month last year</th><th scope="col">Change</th></tr></thead><tbody>{[...months].reverse().map(m => <tr key={m.month}><th scope="row">{monthDate(m.month)}</th><td>{number(m.count)}</td><td>{number(m.previousCount)}</td><td><Change value={m.changePercent} /></td></tr>)}</tbody></table></div>
    </details>
  </section>
}

function PeerComparison({ area, data, category }: { area: Area; data: CrimeData; category: Category }) {
  const multiplier = rateMultiplier(category)
  const peers = data.areas.filter(a => a.type === area.type)
  const rank = rankAreas(peers, category.id, 'rate', false, multiplier).get(area.id)
  const eligible = peers.filter(a => comparableValue(a, category.id, 'rate', multiplier) !== null).length
  const parent = area.type === 'force' ? data.areas.find(a => a.id === area.regionId) : null
  const national = data.areas.find(a => a.type === 'nation' && /england and wales/i.test(a.name))
  const references = [area, parent, national].filter((a): a is Area => !!a)
  const ownRate = comparableValue(area, category.id, 'rate', multiplier)
  const maximum = Math.max(1, ...references.map(a => comparableValue(a, category.id, 'rate', multiplier) ?? 0))
  return <section className="detail-section" aria-labelledby="peer-title"><div className="detail-section-heading"><div><span className="section-label">On the same basis</span><h3 id="peer-title">How this area compares</h3></div>{rank != null && <span className="detail-rank"><strong>#{rank}</strong> of {eligible} comparable {area.type === 'force' ? 'force areas' : 'regions'}</span>}</div>
    <p className="detail-explainer">{category.label}, year ending {monthDate(data.coverage.end)}. Rates are recorded offences {rateLabel(category)}. Rank 1 has the highest displayed rate.</p>
    <div className="benchmark-list">{references.map(reference => {
      const value = comparableValue(reference, category.id, 'rate', multiplier)
      const difference = reference.id === area.id || ownRate == null || value == null ? null : percentageChange(area.metrics[category.id]?.rate, reference.metrics[category.id]?.rate)
      return <div className={`benchmark-row ${reference.id === area.id ? 'benchmark-row--own' : ''}`} key={reference.id}><div><span>{reference.name}</span><strong>{rate(value)}</strong></div><div className="benchmark-track" aria-hidden="true"><span style={{ width: `${(value ?? 0) / maximum * 100}%` }} /></div><small>{value == null ? 'Rate unavailable for comparison; see coverage notes.' : reference.id === area.id ? 'Selected area' : difference == null ? 'Percentage comparison unavailable' : difference === 0 ? 'No difference at this precision' : `This area is ${Math.abs(difference) < 0.05 ? '<0.1' : Math.abs(difference).toFixed(1)}% ${difference > 0 ? 'higher' : 'lower'}`}</small></div>
    })}</div>
    <p className="chart-scale-note">Percentage comparisons use unrounded rates; ranks use the displayed rates.</p>
    {data.coverage.frequency !== 'monthly' && <p className="chart-scale-note">{category.nationalIncludesBtp === false ? 'The national official reference excludes British Transport Police.' : 'The national official reference includes British Transport Police; force and regional rates exclude it.'}</p>}
  </section>
}

export function AreaDetail({ area, data, category, onClose, onCompare, onCategoryChange, selected }: DetailProps) {
  const selectRef = useRef<HTMLSelectElement>(null)
  const chosen = category
  const metric = area.metrics[chosen.id]
  const monthly = data.coverage.frequency === 'monthly'
  const total = area.metrics[data.categories[0].id]?.count
  const categories = data.categories.filter(c => c.id !== data.categories[0].id).sort((a, b) => (area.metrics[b.id]?.count ?? -1) - (area.metrics[a.id]?.count ?? -1))
  const difference = metric?.count != null && metric.previousCount != null ? metric.count - metric.previousCount : null
  function selectCategory(id: string) { onCategoryChange(id); selectRef.current?.focus() }
  function download() {
    const url = URL.createObjectURL(new Blob([exportAreaDetailCsv(area, data)], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `crimeledger-${area.code}-${monthly ? 'monthly' : 'official'}-profile-${data.coverage.end}.csv`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <Modal title={area.name} onClose={onClose} wide><div className="modal-body area-profile">
    <div className="profile-source"><span className="section-label">{monthly ? 'Monthly provisional record' : 'Official quarterly record'}</span><span>Published {shortDate(data.coverage.sourcePublishedAt)}</span></div>
    <div className="profile-category-control"><label htmlFor="profile-category">Explore a crime type</label><div className="select-wrap"><select ref={selectRef} id="profile-category" value={chosen.id} onChange={e => onCategoryChange(e.target.value)}><CategoryOptions categories={data.categories} /></select><ChevronDown size={16} aria-hidden="true" /></div></div>
    <div className="detail-top"><AreaAvatar area={area} large /><div><span className="section-label">{area.type === 'region' ? 'Regional record' : 'Police force record'}</span><p className="modal-subtitle">{chosen.label} · Year ending {monthDate(data.coverage.end)}</p><div className="detail-value">{rate(comparableValue(area, chosen.id, 'rate', rateMultiplier(chosen)))}<span>offences {rateLabel(chosen)}</span></div><Change value={metric?.changePercent} long /></div></div>
    {metric?.changeSuppressedReason && <p className="profile-suppression-note">{metric.changeSuppressedReason}</p>}
    <p className="profile-definition">{chosen.description || 'Police-recorded offences in the selected category.'}</p>
    <div className="detail-stats profile-stats"><div><span>Annual offences</span><strong>{number(metric?.count)}</strong><small>{monthDate(data.coverage.start)}–{monthDate(data.coverage.end)}</small></div><div><span>Previous annual total</span><strong>{number(metric?.previousCount)}</strong><small>The preceding 12 months</small></div><div><span>Annual count change</span><strong>{difference == null ? '—' : `${difference > 0 ? '+' : difference < 0 ? '−' : ''}${number(Math.abs(difference))}`}</strong><small>{difference == null ? 'Requires two complete years' : difference < 0 ? 'Fewer recorded offences' : difference > 0 ? 'More recorded offences' : 'No change in recorded offences'}</small></div><div><span>Resident population</span><strong>{number(area.population)}</strong><small>{area.populationYear ? `Mid-${area.populationYear} estimate` : 'Not available'}</small></div></div>
    {area.monthlyCoverage && !area.monthlyCoverage.currentComplete && <div className="profile-coverage-warning"><Info size={17} /><p>The latest annual total is incomplete and this area is unranked. Available months remain visible below. Missing submissions are shown as unavailable.</p></div>}
    <PeerComparison area={area} data={data} category={chosen} />
    {(metric?.history.length || 0) >= 2 && <section className="detail-section detail-history" aria-labelledby="annual-trend-title"><div className="detail-section-heading"><div><span className="section-label">The annual view</span><h3 id="annual-trend-title">Rolling-year trend</h3></div></div><p className="detail-explainer">Each point counts the preceding 12 months. {monthly ? 'Annual change compares the first and last points.' : 'The chart spans more than one year; annual change compares the latest total with a year earlier.'}{metric?.history.some(p => p.count === null) && ' Gaps indicate unavailable periods.'}</p>{metric!.history.filter(p => p.count !== null).length >= 2 ? <><Sparkline history={metric!.history} large /><p className="chart-scale-note">The dashed line marks the starting annual total. The vertical scale fits this area’s values.</p></> : <p className="profile-no-trend">No complete rolling-year trend is available for this area.</p>}<ExactHistory metric={metric!} category={chosen} /></section>}
    {monthly && metric?.monthlyCounts?.length ? <MonthlyActivity key={chosen.id} metric={metric} category={chosen} /> : null}
    <section className="detail-section profile-crime-types" aria-labelledby="crime-types-title"><div className="detail-section-heading"><div><span className="section-label">The offence breakdown</span><h3 id="crime-types-title">Crime types in this area</h3></div></div><p className="detail-explainer">Year ending {monthDate(data.coverage.end)}. Choose a crime type to explore its trend. {monthly ? 'Shares use all recorded crime in this feed.' : 'Parent groups, subgroups and weapon measures overlap. Do not add their counts or shares together.'}</p>
      <div className="detail-table-wrap" tabIndex={0} role="region" aria-label="Crime-type figures, scroll horizontally if needed"><table className="detail-data-table category-data-table"><caption className="sr-only">Annual offence counts, population rates, shares and changes by crime type</caption><thead><tr><th scope="col">Crime type</th><th scope="col">Offences</th><th scope="col">Population rate</th><th scope="col">Share of total</th><th scope="col">Year change</th></tr></thead><tbody>{categories.map(c => {
        const m = area.metrics[c.id], share = total != null && total > 0 && m?.count != null ? m.count / total * 100 : null
        return <tr key={c.id} className={chosen.id === c.id ? 'category-row--selected' : ''}><th scope="row"><button onClick={() => selectCategory(c.id)} aria-label={`Explore ${c.label}`} aria-pressed={chosen.id === c.id}>{c.label}</button></th><td>{number(m?.count)}</td><td>{categoryRate(m?.rate, c)}<small className="cell-unit">per {number(rateDenominator(c))}</small></td><td>{share == null ? '—' : `${share > 0 && share < 0.05 ? '<0.1' : share.toFixed(1)}%`}</td><td title={m?.changeSuppressedReason}><Change value={m?.changePercent} /></td></tr>
      })}</tbody></table></div><p className="chart-scale-note">Scroll the table sideways on a narrow screen. Missing figures stay unavailable.</p>
    </section>
    <section className="detail-section profile-evidence" aria-labelledby="profile-evidence-title"><div className="detail-section-heading"><div><span className="section-label">Coverage and provenance</span><h3 id="profile-evidence-title">Read the record</h3></div></div><dl className="profile-provenance"><div><dt>Geography</dt><dd>{area.type === 'force' ? 'Police force area' : 'Region'} · {area.code}</dd></div><div><dt>Annual coverage</dt><dd>{shortDate(data.coverage.start)}–{shortDate(data.coverage.end)}</dd></div><div><dt>Publication</dt><dd>{shortDate(data.coverage.sourcePublishedAt)}</dd></div>{area.monthlyCoverage && <div><dt>Submission coverage</dt><dd>Latest year: {area.monthlyCoverage.currentComplete ? 'complete' : 'incomplete'} · Previous year: {area.monthlyCoverage.previousComplete ? 'complete' : 'incomplete'}</dd></div>}</dl>
      {area.quality.length > 0 && <div className="quality-notes"><Info size={17} /><div>{area.quality.map((q, i) => <p key={i}>{q}</p>)}</div></div>}
      <p className="detail-explainer">Rates use resident population. They do not measure individual victimisation risk or police effectiveness. Reporting, recording practices and visitors affect comparisons.</p>
      <div className="profile-source-links">{data.sources.map(source => <OfficialLink href={source.url} key={source.id}>{source.title}</OfficialLink>)}</div>
    </section>
    <div className="modal-actions profile-actions"><button className="button button--primary" onClick={onCompare}>{selected ? <X size={15} /> : <Layers2 size={15} />}{selected ? 'Remove from comparison' : 'Add to comparison'}</button><button className="button" onClick={download}><Download size={15} />Download full area data</button></div><p className="modal-footnote">The CSV includes every crime type, annual history and all available monthly counts, with source and coverage notes.</p>
  </div></Modal>
}
