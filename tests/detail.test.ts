import { test } from 'node:test'
import assert from 'node:assert/strict'
import { exportAreaDetailCsv, getMonthlyComparisons, percentageChange } from '../src/detail-model.ts'
import type { Area, CrimeData, Metric } from '../src/types.ts'

const metric: Metric = { count: 120, rate: 12, previousCount: 100, changePercent: 20, history: [
  { periodEnd: '2024-02-29', count: 100, rate: 10 }, { periodEnd: '2025-02-28', count: 120, rate: 12 },
], monthlyCounts: [{ month: '2024-02', count: 7 }, { month: '2025-02', count: 0 }, { month: '2025-01', count: null }] }
const area: Area = { id: 'E23000002', code: 'E23000002', name: 'Cumbria, "example"', type: 'force', regionId: 'E12000002',
  population: 10000, populationYear: 2025, comparisonEligible: false, quality: ['Missing data is unavailable; never zero.'],
  monthlyCoverage: { currentComplete: false, previousComplete: true, missingForceMonths: { E23000002: ['2025-01'] } },
  metrics: { 'all-crime': metric, burglary: null } }
const data: CrimeData = { schemaVersion: 1, generatedAt: '2025-04-01T00:00:00Z', datasetLabel: 'Monthly provisional',
  coverage: { start: '2024-03-01', end: '2025-02-28', label: 'Mar 2024 – Feb 2025', frequency: 'monthly', sourcePublishedAt: '2025-03-31' },
  categories: [{ id: 'all-crime', label: 'All crime' }, { id: 'burglary', label: 'Burglary' }], areas: [area],
  sources: [{ id: 'police-uk', title: 'Police.uk archive', url: 'https://data.police.uk/data/archive/2025-02.zip', publishedAt: '2025-03-31' }] }

function parseCsv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cell = '', quoted = false
  const body = text.replace(/^\uFEFF/, '')
  for (let i = 0; i < body.length; i++) {
    const char = body[i]
    if (char === '"') { if (quoted && body[i + 1] === '"') { cell += '"'; i++ } else quoted = !quoted }
    else if (char === ',' && !quoted) { row.push(cell); cell = '' }
    else if (char === '\r' && body[i + 1] === '\n' && !quoted) { row.push(cell); rows.push(row); row = []; cell = ''; i++ }
    else cell += char
  }
  row.push(cell); rows.push(row)
  return rows
}

test('percentage changes preserve zero, suppress missing and zero denominators', () => {
  assert.equal(percentageChange(0, 10), -100)
  assert.equal(percentageChange(0, 0), null)
  assert.equal(percentageChange(10, 0), null)
  assert.equal(percentageChange(null, 10), null)
  assert.equal(percentageChange(10, undefined), null)
  assert.equal(percentageChange(Number.NaN, 10), null)
  assert.equal(percentageChange(4, 3), 33.33)
})

test('monthly comparisons pair calendar years despite unordered and absent records', () => {
  const original = JSON.stringify(metric)
  const comparisons = getMonthlyComparisons(metric)
  assert.equal(comparisons.length, 12)
  assert.equal(comparisons[0].month, '2024-03')
  assert.deepEqual(comparisons.at(-1), { month: '2025-02', count: 0, previousMonth: '2024-02', previousCount: 7, changePercent: -100 })
  assert.deepEqual(comparisons.at(-2), { month: '2025-01', count: null, previousMonth: '2024-01', previousCount: null, changePercent: null })
  assert.equal(comparisons.find(point => point.month === '2024-12')?.count, null)
  assert.equal(JSON.stringify(metric), original)
  assert.deepEqual(getMonthlyComparisons(null), [])
})

test('same-month comparison against reported zero remains unavailable', () => {
  const comparisons = getMonthlyComparisons({ ...metric, monthlyCounts: [{ month: '2024-02', count: 0 }, { month: '2025-02', count: 5 }] })
  assert.equal(comparisons.at(-1)?.previousCount, 0)
  assert.equal(comparisons.at(-1)?.changePercent, null)
})

test('detail CSV includes every category, rolling point and raw month with rectangular provenance', () => {
  const output = exportAreaDetailCsv(area, data)
  assert.ok(output.startsWith('\uFEFF'))
  const [header, ...rows] = parseCsv(output)
  assert.ok(rows.every(row => row.length === header.length))
  const records = rows.map(row => Object.fromEntries(header.map((key, i) => [key, row[i]])))
  assert.equal(records.length, 2 * data.categories.length + metric.history.length + metric.monthlyCounts!.length)
  assert.equal(records.filter(row => row['Category ID'] === 'burglary').length, 2)
  assert.equal(records.filter(row => row['Observation type'] === 'Rolling-year history').length, 2)
  assert.equal(records.filter(row => row['Observation type'] === 'Monthly offences').length, 3)
  for (const row of records) {
    assert.equal(row.Area, area.name)
    assert.equal(row['Data series'], 'Monthly provisional')
    assert.equal(row['Source URL'], data.sources[0].url)
    assert.equal(row['Source publication'], '2025-03-31')
    assert.equal(row['Series publication frequency'], 'monthly')
    assert.equal(row['Display rate denominator'], '1000')
    assert.equal(row['Resident population (latest estimate)'], '10000')
    assert.ok(row['Coverage notes'].includes('Missing submissions (E23000002): 2025-01'))
  }
  const previous = records.find(row => row['Category ID'] === 'all-crime' && row['Observation type'] === 'Previous rolling year')!
  assert.equal(previous['Recorded offences'], '100')
  assert.equal(previous['Offences per 1,000 residents'], '10')
  assert.equal(previous['Period start'], '2023-03-01')
  assert.equal(previous['Period end'], '2024-02-29')
})

test('raw monthly CSV dates respect leap years, preserve nulls and retain reported zero', () => {
  const [header, ...rows] = parseCsv(exportAreaDetailCsv(area, data))
  const records = rows.map(row => Object.fromEntries(header.map((key, i) => [key, row[i]])))
  const monthly = records.filter(row => row['Observation type'] === 'Monthly offences')
  assert.equal(monthly.find(row => row['Period start'] === '2024-02-01')?.['Period end'], '2024-02-29')
  const latest = monthly.find(row => row['Period start'] === '2025-02-01')!
  assert.equal(latest['Period end'], '2025-02-28')
  assert.equal(latest['Recorded offences'], '0')
  assert.equal(latest['Previous equivalent offences'], '7')
  assert.equal(latest['Change in offences (%)'], '-100')
  assert.equal(monthly.find(row => row['Period start'] === '2025-01-01')?.['Recorded offences'], '')
})

test('source-suppressed annual changes remain blank in current and matching history rows', () => {
  const reason = 'Percentage change withheld by the source because the earlier count is below 50.'
  const suppressed: Metric = { ...metric, count: 8, previousCount: 2, changePercent: null, changeSuppressedReason: reason,
    history: [{ periodEnd: '2023-02-28', count: 1, rate: 0.1 }, { periodEnd: '2024-02-29', count: 2, rate: 0.2 }, { periodEnd: '2025-02-28', count: 8, rate: 0.8 }] }
  const [header, ...rows] = parseCsv(exportAreaDetailCsv({ ...area, metrics: { 'all-crime': suppressed } }, data))
  const records = rows.map(row => Object.fromEntries(header.map((key, i) => [key, row[i]])))
  const annual = records.filter(row => row['Category ID'] === 'all-crime' && row['Observation type'] !== 'Monthly offences')
  assert.ok(annual.every(row => row['Change in offences (%)'] === ''))
  const current = annual.filter(row => row['Period end'] === data.coverage.end)
  assert.equal(current.length, 2)
  assert.ok(current.every(row => row['Change suppression reason'] === reason))
  const monthly = records.find(row => row['Observation type'] === 'Monthly offences' && row['Period start'] === '2025-02-01')!
  assert.equal(monthly['Change in offences (%)'], '-100')
  assert.equal(monthly['Change suppression reason'], '')
})

test('historical annual percentages are not inferred while explicit current change is retained', () => {
  const published: Metric = { ...metric, changePercent: 19.9,
    history: [{ periodEnd: '2023-02-28', count: 80, rate: 8 }, ...metric.history] }
  const [header, ...rows] = parseCsv(exportAreaDetailCsv({ ...area, metrics: { 'all-crime': published } }, data))
  const annual = rows.map(row => Object.fromEntries(header.map((key, i) => [key, row[i]])))
    .filter(row => row['Category ID'] === 'all-crime' && row['Observation type'] !== 'Monthly offences')
  assert.ok(annual.filter(row => row['Period end'] !== data.coverage.end).every(row => row['Change in offences (%)'] === ''))
  assert.ok(annual.filter(row => row['Period end'] === data.coverage.end).every(row => row['Change in offences (%)'] === '19.9'))
})

test('irregular annual history retains its actual dates and labels publication frequency separately', () => {
  const weapon: Metric = { count: 20, rate: 2, previousCount: 10, changePercent: 100, history: [
    { periodEnd: '2024-03-31', count: 8, rate: 0.8 },
    { periodEnd: '2025-03-31', count: 9, rate: 0.9 },
    { periodEnd: '2025-06-30', count: 10, rate: 1 },
    { periodEnd: '2026-06-30', count: 20, rate: 2 },
  ] }
  const quarterly: CrimeData = { ...data, datasetLabel: 'Official quarterly', categories: [{ id: 'firearms', label: 'Firearms', ratePer: 100000, group: 'Knife and firearm offences', description: 'Overlaps other offence groups.' }],
    coverage: { ...data.coverage, start: '2025-07-01', end: '2026-06-30', frequency: 'quarterly' } }
  const [header, ...rows] = parseCsv(exportAreaDetailCsv({ ...area, metrics: { firearms: weapon } }, quarterly))
  const records = rows.map(row => Object.fromEntries(header.map((key, i) => [key, row[i]])))
  assert.ok(records.every(row => row['Series publication frequency'] === 'quarterly'))
  assert.ok(records.every(row => row['Display rate denominator'] === '100000' && row['Category handling'].includes('overlap')))
  assert.ok(records.every(row => row['Category group'] === 'Knife and firearm offences'))
  const history = records.filter(row => row['Observation type'] === 'Rolling-year history')
  assert.deepEqual(history.map(row => row['Period end']), weapon.history.map(point => point.periodEnd))
  assert.deepEqual(history.map(row => row['Period start']), ['2023-04-01', '2024-04-01', '2024-07-01', '2025-07-01'])
  assert.equal(history.at(-1)?.['Change in offences (%)'], '100')
  assert.ok(history.slice(0, -1).every(row => row['Change in offences (%)'] === ''))
})
