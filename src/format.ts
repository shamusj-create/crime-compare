import type { Category } from './types'

const nf = new Intl.NumberFormat('en-GB')
export const number = (n: number | null | undefined) => n == null ? '—' : nf.format(n)
export const rate = (n: number | null | undefined) => n == null ? '—' : n.toFixed(1)
export const shortDate = (s: string) => !s ? 'Unavailable' : new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(s.slice(0, 10) + 'T12:00:00Z'))
export const monthDate = (s: string) => new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date((s.length === 7 ? `${s}-01` : s.slice(0, 10)) + 'T12:00:00Z'))
export const rateDenominator = (category?: Category) => category?.ratePer || 1000
export const rateMultiplier = (category?: Category) => rateDenominator(category) / 1000
export const rateLabel = (category?: Category) => `per ${number(rateDenominator(category))} residents`
export const categoryRate = (value: number | null | undefined, category: Category) => rate(value == null ? null : Math.round(value * rateMultiplier(category) * 10) / 10)
