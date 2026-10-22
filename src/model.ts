import type { Area, Measure, Sort } from './types.ts'
export const normalise = (s: string) => s.toLocaleLowerCase('en-GB').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/g, '')
export function comparableValue(area: Area, category: string, measure: Measure): number | null {
  if (!area.comparisonEligible) return null
  const v = area.metrics[category]?.[measure]
  return v == null || !Number.isFinite(v) ? null : measure === 'rate' ? Math.round(v * 10) / 10 : v
}
export function orderAreas(areas: Area[], category: string, measure: Measure, sort: Sort): Area[] {
  return [...areas].sort((a, b) => {
    const av = comparableValue(a, category, measure), bv = comparableValue(b, category, measure)
    if (av === null || bv === null) return av === bv ? a.name.localeCompare(b.name) : av === null ? 1 : -1
    if (sort === 'name') return a.name.localeCompare(b.name)
    if (sort === 'rising' || sort === 'falling') {
      const ac = a.metrics[category]?.changePercent, bc = b.metrics[category]?.changePercent
      if (ac == null || bc == null) return ac == bc ? a.name.localeCompare(b.name) : ac == null ? 1 : -1
      return (ac - bc) * (sort === 'rising' ? -1 : 1) || a.name.localeCompare(b.name)
    }
    return (av - bv) * (sort === 'highest' ? -1 : 1) || a.name.localeCompare(b.name)
  })
}
export function rankAreas(areas: Area[], category: string, measure: Measure, lowFirst = false): Map<string, number> {
  const sorted = orderAreas(areas, category, measure, lowFirst ? 'lowest' : 'highest')
  const ranks = new Map<string, number>()
  let last: number | null = null, rank = 0
  sorted.forEach((area, index) => {
    const value = comparableValue(area, category, measure)
    if (value === null) return
    if (value !== last) rank = index + 1
    ranks.set(area.id, rank); last = value
  })
  return ranks
}
export function csvCell(value: unknown): string { return `"${String(value ?? '').replaceAll('"', '""')}"` }
export function exportCsv(areas: Area[], category: string, start: string, end: string, provenance?: { series: string; sourceUrl: string; publishedAt: string }): string {
  const rows: unknown[][] = [['Area', 'ONS code', 'Geography', 'Crime category', 'Period start', 'Period end', 'Recorded offences', 'Offences per 1,000 residents', 'Change in offences (%)', 'Population', 'Population year', 'Comparable', 'Notes', 'Data series', 'Source URL', 'Source publication']]
  for (const a of areas) {
    const m = a.metrics[category]
    rows.push([a.name, a.code, a.type, category, start, end, m?.count, m?.rate, m?.changePercent, a.population, a.populationYear, a.comparisonEligible, a.quality.join('; '), provenance?.series, provenance?.sourceUrl, provenance?.publishedAt])
  }
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n')
}
