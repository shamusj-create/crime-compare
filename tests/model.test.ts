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
