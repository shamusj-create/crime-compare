import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { applyPageMetadata, buildPageMetadata, CANONICAL_URL, DEFAULT_PAGE_METADATA, SOCIAL_IMAGE, SOCIAL_IMAGE_ALT } from '../src/pageMetadata.ts'

test('unloaded comparison has a consistent root title, description and canonical', () => {
  const metadata = buildPageMetadata({ kind: 'force', mode: 'official' })
  assert.deepEqual(metadata, DEFAULT_PAGE_METADATA)
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.ok(html.includes(`<title>${metadata.title}</title>`))
  assert.ok(html.includes(`<meta name="description" content="${metadata.description}"`))
  assert.ok(html.includes(`<link rel="canonical" href="${CANONICAL_URL}"`))
})

test('comparison metadata distinguishes source and geography without inventing an observation date', () => {
  const official = buildPageMetadata({ category: { label: 'Burglary' }, kind: 'force', mode: 'official', periodEnd: '2026-06-30' })
  assert.equal(official.title, 'Burglary by police force | CrimeLedger')
  assert.match(official.description, /England and Wales police force areas/)
  assert.match(official.description, /Official police-recorded/)
  assert.match(official.description, /Year ending June 2026\./)
  const monthly = buildPageMetadata({ category: { label: 'All recorded crime' }, kind: 'region', mode: 'monthly', periodEnd: '2026-08-31' })
  assert.equal(monthly.title, 'All recorded crime by region | CrimeLedger')
  assert.match(monthly.description, /Provisional Police\.uk/)
  assert.match(monthly.description, /Year ending August 2026\./)
  for (const periodEnd of ['2026-02-31', '2026-13-01', '2026-06', 'invalid']) {
    const invalid = buildPageMetadata({ category: { label: 'Burglary' }, kind: 'force', mode: 'official', periodEnd })
    assert.doesNotMatch(invalid.description, /Year ending|Invalid Date/)
  }
})

test('area metadata describes the selection but every interactive view remains canonical to the app', () => {
  for (const mode of ['official', 'monthly'] as const) {
    for (const kind of ['force', 'region'] as const) {
      const metadata = buildPageMetadata({ category: { label: 'All recorded crime' }, kind, mode, area: { name: 'Dorset' }, periodEnd: '2026-08-31' })
      assert.equal(metadata.title, 'Dorset: All recorded crime | CrimeLedger')
      assert.match(metadata.description, /^Dorset: all recorded crime counts, population rates and rolling-year trends\./)
      assert.equal(metadata.canonical, CANONICAL_URL)
      assert.doesNotMatch(metadata.canonical, /[?#]|Dorset|monthly|official/)
    }
  }
})

function documentHarness() {
  type Element = { tagName: string; attributes: Record<string, string>; content: string; href: string; rel: string; setAttribute: (name: string, value: string) => void }
  const elements: Element[] = []
  const createElement = (tagName: string): Element => ({ tagName, attributes: {}, content: '', href: '', rel: '', setAttribute(name, value) { this.attributes[name] = value } })
  const document = {
    title: '', createElement,
    head: {
      querySelector(selector: string) {
        if (selector === 'link[rel="canonical"]') return elements.find(e => e.tagName === 'link' && e.rel === 'canonical') ?? null
        const match = /^meta\[(name|property)="([^"]+)"\]$/.exec(selector)
        return match ? elements.find(e => e.tagName === 'meta' && e.attributes[match[1]] === match[2]) ?? null : null
      },
      appendChild(element: Element) { elements.push(element) },
    },
  }
  const canonical = createElement('link'); canonical.rel = 'canonical'; canonical.href = 'https://crime.compare/areas/dorset/'
  elements.push(canonical)
  return { document: document as unknown as Document, elements }
}

test('metadata application updates reusable social tags and canonical without duplicates', () => {
  const { document, elements } = documentHarness()
  const official = buildPageMetadata({ category: { label: 'Burglary' }, kind: 'force', mode: 'official' })
  applyPageMetadata(document, official)
  assert.equal(document.title, official.title)
  assert.equal(document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href, CANONICAL_URL)
  assert.equal(document.head.querySelector<HTMLMetaElement>('meta[property="og:url"]')?.content, CANONICAL_URL)
  assert.equal(document.head.querySelector<HTMLMetaElement>('meta[property="og:image"]')?.content, SOCIAL_IMAGE)
  assert.equal(document.head.querySelector<HTMLMetaElement>('meta[name="twitter:image:alt"]')?.content, SOCIAL_IMAGE_ALT)
  const count = elements.length
  const monthly = buildPageMetadata({ category: { label: 'Robbery' }, kind: 'region', mode: 'monthly' })
  applyPageMetadata(document, monthly)
  assert.equal(elements.length, count)
  for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
    assert.equal(document.head.querySelector<HTMLMetaElement>(selector)?.content, monthly.description)
  }
  assert.equal(document.head.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.content, monthly.title)
  assert.equal(document.head.querySelector<HTMLMetaElement>('meta[name="twitter:title"]')?.content, monthly.title)
})

test('static root advertises the real social image and factual structured site identity', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.ok(html.includes(`<meta property="og:image" content="${SOCIAL_IMAGE}"`))
  assert.ok(html.includes('<!--discovery-root:start-->'))
  assert.ok(html.includes('<!--discovery-root:end-->'))
  const json = JSON.parse(html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)?.[1] ?? 'null')
  const website = json['@graph'].find((entry: { '@type': string }) => entry['@type'] === 'WebSite')
  assert.equal(website.url, CANONICAL_URL)
  assert.equal(website.name, 'CrimeLedger')
  assert.equal(website.inLanguage, 'en-GB')
  const png = readFileSync(new URL('../public/social-card.png', import.meta.url))
  assert.equal(png.subarray(1, 4).toString(), 'PNG')
  assert.equal(png.readUInt32BE(16), 1200)
  assert.equal(png.readUInt32BE(20), 630)
})
