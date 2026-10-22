import { test } from 'node:test'
import assert from 'node:assert/strict'
import { categoryRate, rateLabel } from '../src/format.ts'

test('rare offence rates keep the same rounding in headlines, breakdowns and histories', () => {
  const homicide = { id: 'homicide', label: 'Homicide', ratePer: 100000 as const }
  assert.equal(categoryRate(0.0045, homicide), '0.5')
  assert.equal(categoryRate(0.0095, homicide), '1.0')
  assert.equal(categoryRate(null, homicide), '—')
  assert.equal(rateLabel(homicide), 'per 100,000 residents')
  assert.equal(categoryRate(132.6513, { id: 'all-crime', label: 'All crime' }), '132.7')
})
