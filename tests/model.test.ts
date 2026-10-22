import { test } from 'node:test'
import assert from 'node:assert/strict'
import { comparableValue, orderAreas, rankAreas, exportCsv } from '../src/model.ts'
import type { Area } from '../src/types.ts'
function area(id: string, rate: number | null, eligible = true): Area {
  return { id, code: id, name: id, type: 'force', population: 1000, populationYear: 2025, comparisonEligible: eligible, quality: [], metrics: { total: { count: rate === null ? null : 10, rate, previousCount: 12, changePercent: -16.7, history: [] } } }
}
test('missing and ineligible observations never become zero or rank', () => {
  const all = [area('Missing', null), area('High', 15), area('Excluded', 30, false), area('Low', 0)]
  assert.equal(comparableValue(all[0], 'total', 'rate'), null)
  assert.deepEqual(orderAreas(all, 'total', 'rate', 'lowest').map(a => a.id), ['Low', 'High', 'Excluded', 'Missing'])
  assert.equal(rankAreas(all, 'total', 'rate').has('Excluded'), false)
})
test('ties use displayed precision and standard competition ranking', () => {
  const ranks = rankAreas([area('A', 20.01), area('B', 20.03), area('C', 12)], 'total', 'rate')
  assert.deepEqual([...ranks.values()], [1, 1, 3])
})
test('rare offence rates scale before display rounding and preserve unscaled counts', () => {
  const low = area('Low', 0.005), high = area('High', 0.014)
  assert.equal(comparableValue(low, 'total', 'rate', 100), 0.5)
  assert.equal(comparableValue(high, 'total', 'rate', 100), 1.4)
  assert.equal(comparableValue(high, 'total', 'rate'), 0)
  assert.equal(comparableValue(high, 'total', 'count', 100), 10)
  assert.deepEqual(orderAreas([high, low], 'total', 'rate', 'lowest', 100).map(a => a.id), ['Low', 'High'])
  assert.deepEqual([...rankAreas([low, high], 'total', 'rate', false, 100)], [['High', 1], ['Low', 2]])
  assert.equal(high.metrics.total?.rate, 0.014)
})
test('scaled rates rank ties at displayed precision and retain zero and unavailable states', () => {
  const all = [area('B', 0.0144), area('A', 0.0136), area('C', 0.005), area('Zero', 0), area('Missing', null), area('Excluded', 0.04, false)]
  const ranks = rankAreas(all, 'total', 'rate', false, 100)
  assert.deepEqual([...ranks], [['A', 1], ['B', 1], ['C', 3], ['Zero', 4]])
  assert.equal(comparableValue(all[3], 'total', 'rate', 100), 0)
  assert.equal(comparableValue(all[4], 'total', 'rate', 100), null)
  assert.equal(comparableValue(all[5], 'total', 'rate', 100), null)
  assert.deepEqual([...rankAreas(all, 'total', 'rate', true, 100)], [['Zero', 1], ['C', 2], ['A', 3], ['B', 3]])
})
test('CSV keeps the stored rate per 1,000 after a scaled comparison', () => {
  const a = area('Homicide', 0.014)
  comparableValue(a, 'total', 'rate', 100)
  const csv = exportCsv([a], 'total', '2025-07-01', '2026-06-30')
  assert.ok(csv.includes('"Offences per 1,000 residents"'))
  assert.ok(csv.includes('"2026-06-30","10","0.014"'))
})
test('filters cannot mutate source data or change published values', () => {
  const all = [area('A', 20), area('B', 12)]
  orderAreas(all, 'total', 'rate', 'lowest')
  assert.equal(all[0].id, 'A')
})
test('CSV preserves missing fields and escapes quotes and commas', () => {
  const a = area('Area, "A"', null)
  const csv = exportCsv([a], 'total', '2025-07-01', '2026-06-30')
  assert.ok(csv.includes('"Area, ""A"""'))
  assert.ok(csv.includes('"2026-06-30","",""'))
})
