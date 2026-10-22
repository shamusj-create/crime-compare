import { csvCell } from './model.ts'
import type { Area, CrimeData, Metric } from './types.ts'

export type MonthlyComparison = { month: string; count: number | null; previousMonth: string; previousCount: number | null; changePercent: number | null }

export function percentageChange(current: number | null | undefined, previous: number | null | undefined): number | null {
  if (current == null || previous == null || previous === 0 || !Number.isFinite(current) || !Number.isFinite(previous)) return null
  return Math.round((current / previous - 1) * 10000) / 100
}

function offsetMonth(month: string, offset: number): string {
  const [year, value] = month.split('-').map(Number)
  const date = new Date(Date.UTC(year, value - 1 + offset, 1))
  return date.toISOString().slice(0, 7)
}
function monthEnd(month: string): string {
  const [year, value] = month.split('-').map(Number)
  return new Date(Date.UTC(year, value, 0)).toISOString().slice(0, 10)
}
const annualStart = (end: string) => `${offsetMonth(end.slice(0, 7), -11)}-01`
const yearBefore = (end: string) => monthEnd(offsetMonth(end.slice(0, 7), -12))

export function getMonthlyComparisons(metric: Metric | null | undefined): MonthlyComparison[] {
  const records = metric?.monthlyCounts?.filter(point => /^\d{4}-(0[1-9]|1[0-2])$/.test(point.month)) || []
  if (!records.length) return []
  const byMonth = new Map(records.map(point => [point.month, point.count]))
  const latest = records.map(point => point.month).sort().at(-1)!
  return Array.from({ length: 12 }, (_, i) => {
    const month = offsetMonth(latest, i - 11), previousMonth = offsetMonth(month, -12)
    const count = byMonth.get(month) ?? null, previousCount = byMonth.get(previousMonth) ?? null
    return { month, count, previousMonth, previousCount, changePercent: percentageChange(count, previousCount) }
  })
}

export function exportAreaDetailCsv(area: Area, data: CrimeData): string {
  const source = data.sources[0]
  const series = data.datasetLabel || (data.coverage.frequency === 'monthly' ? 'Monthly provisional' : 'Official quarterly')
  const coverage = area.monthlyCoverage
  const coverageNotes = [...area.quality]
  if (coverage) {
    coverageNotes.push(`Current year coverage: ${coverage.currentComplete ? 'complete' : 'incomplete'}; previous year coverage: ${coverage.previousComplete ? 'complete' : 'incomplete'}`)
    for (const [code, months] of Object.entries(coverage.missingForceMonths)) {
      if (months.length) coverageNotes.push(`Missing submissions (${code}): ${months.join(', ')}`)
    }
  }
  const rows: unknown[][] = [[
    'Area', 'ONS code', 'Geography', 'Category ID', 'Crime category', 'Observation type', 'Series publication frequency', 'Period start', 'Period end',
    'Recorded offences', 'Offences per 1,000 residents', 'Previous equivalent offences', 'Change in offences (%)', 'Change suppression reason',
    'Resident population (latest estimate)', 'Population year (latest estimate)', 'Comparable', 'Coverage notes',
    'Data series', 'Source', 'Source URL', 'Source publication',
    'Category group', 'Category definition', 'Display rate denominator', 'Category handling',
  ]]
  function add(categoryId: string, label: string, observation: string, start: string, end: string,
    count: number | null | undefined, rate: number | null | undefined, previous: number | null | undefined, change: number | null | undefined, suppressionReason?: string) {
    const category = data.categories.find(c => c.id === categoryId)
    rows.push([area.name, area.code, area.type, categoryId, label, observation, data.coverage.frequency, start, end, count, rate, previous, change, suppressionReason,
      area.population, area.populationYear, area.comparisonEligible, coverageNotes.join('; '), series,
      source?.title, source?.url, source?.publishedAt || data.coverage.sourcePublishedAt,
      category?.group, category?.description, category?.ratePer || 1000,
      data.coverage.frequency === 'monthly' ? 'Monthly Police.uk categories use different definitions from the official series.' : 'Parent groups, subgroups and weapon measures overlap. Do not add these categories together.'])
  }
  for (const category of data.categories) {
    const metric = area.metrics[category.id]
    const history = new Map(metric?.history.map(point => [point.periodEnd, point]) || [])
    const previousEnd = yearBefore(data.coverage.end), earlier = history.get(yearBefore(previousEnd))
    const currentChange = metric?.changeSuppressedReason ? null : metric?.changePercent
    add(category.id, category.label, 'Current rolling year', data.coverage.start, data.coverage.end,
      metric?.count, metric?.rate, metric?.previousCount, currentChange, metric?.changeSuppressedReason)
    add(category.id, category.label, 'Previous rolling year', annualStart(previousEnd), previousEnd,
      metric?.previousCount, history.get(previousEnd)?.rate, earlier?.count, null)
    for (const point of metric?.history || []) {
      const previous = history.get(yearBefore(point.periodEnd))?.count
      // Only the current annual change is supplied explicitly. Recalculating
      // older percentages could bypass source suppression for small counts.
      const current = point.periodEnd === data.coverage.end
      add(category.id, category.label, 'Rolling-year history', annualStart(point.periodEnd), point.periodEnd,
        point.count, point.rate, previous, current ? currentChange : null, current ? metric?.changeSuppressedReason : undefined)
    }
    const monthly = new Map(metric?.monthlyCounts?.map(point => [point.month, point.count]) || [])
    for (const point of metric?.monthlyCounts || []) {
      const previous = monthly.get(offsetMonth(point.month, -12))
      add(category.id, category.label, 'Monthly offences', `${point.month}-01`, monthEnd(point.month),
        point.count, null, previous, percentageChange(point.count, previous))
    }
  }
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n')
}
