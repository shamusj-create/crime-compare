import type { Area, Category } from './types.ts'

export const CANONICAL_URL = 'https://crime.compare/'
export const SOCIAL_IMAGE = 'https://crime.compare/social-card.png'
export const SOCIAL_IMAGE_ALT = 'CrimeLedger: crime statistics for England and Wales, with a map of the covered area.'
export const DEFAULT_PAGE_METADATA = {
  title: 'CrimeLedger — Compare crime in England and Wales',
  description: 'Compare crime across England and Wales with population-adjusted rates per 1,000 or 100,000 residents, official force and regional trends, and source evidence.',
  canonical: CANONICAL_URL,
}
export type PageMetadata = typeof DEFAULT_PAGE_METADATA
type ComparisonMetadata = { category?: Pick<Category, 'label'>; kind: 'force' | 'region'; mode: 'official' | 'monthly'; area?: Pick<Area, 'name'>; periodEnd?: string }

export function buildPageMetadata({ category, kind, mode, area, periodEnd }: ComparisonMetadata): PageMetadata {
  if (!category) return { ...DEFAULT_PAGE_METADATA }
  const label = category.label.trim(), subject = label.toLocaleLowerCase('en-GB')
  const geography = kind === 'region' ? 'regions' : 'police force areas'
  let period = ''
  if (periodEnd && /^\d{4}-\d{2}-\d{2}$/.test(periodEnd)) {
    const date = new Date(`${periodEnd}T12:00:00Z`)
    if (!Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === periodEnd) period = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date)
  }
  const source = mode === 'monthly' ? 'Provisional Police.uk' : 'Official police-recorded'
  return {
    title: area ? `${area.name}: ${label} | CrimeLedger` : `${label} by ${kind === 'region' ? 'region' : 'police force'} | CrimeLedger`,
    description: area
      ? `${area.name}: ${subject} counts, population rates and rolling-year trends. ${source} data${period ? ` for the year ending ${period}` : ''}, with source links.`
      : `${label} across England and Wales ${geography}. ${source} counts, population rates, trends and sources.${period ? ` Year ending ${period}.` : ''}`,
    // Interactive query views remain canonical to the app. Standalone discovery
    // pages have their own canonical URLs and do not render this React module.
    canonical: CANONICAL_URL,
  }
}

export function applyPageMetadata(document: Document, metadata: PageMetadata): void {
  document.title = metadata.title
  const fields = [
    ['name', 'description', metadata.description], ['property', 'og:title', metadata.title],
    ['property', 'og:description', metadata.description], ['property', 'og:url', metadata.canonical],
    ['property', 'og:image', SOCIAL_IMAGE], ['property', 'og:image:alt', SOCIAL_IMAGE_ALT],
    ['name', 'twitter:title', metadata.title], ['name', 'twitter:description', metadata.description],
    ['name', 'twitter:card', 'summary_large_image'], ['name', 'twitter:image', SOCIAL_IMAGE], ['name', 'twitter:image:alt', SOCIAL_IMAGE_ALT],
  ]
  for (const [attribute, key, value] of fields) {
    let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`)
    if (!element) { element = document.createElement('meta'); element.setAttribute(attribute, key); document.head.appendChild(element) }
    element.content = value
  }
  let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!canonical) { canonical = document.createElement('link'); canonical.rel = 'canonical'; document.head.appendChild(canonical) }
  canonical.href = metadata.canonical
}
