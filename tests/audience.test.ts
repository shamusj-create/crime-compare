import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../public/audience.js', import.meta.url), 'utf8')
const ID = 'G-6DZZ4SE8DG', KEY = 'crimeledger-audience-choice-v1', INTERNAL = 'crimeledger-analytics-internal', EXCLUDE = 'crimeledger-analytics-exclude'
const NOW = Date.UTC(2026, 9, 22, 12), DAY = 86400000
const saved = (choice = 'allow', chosenAt = NOW) => JSON.stringify({ revision: 1, choice, chosenAt })

function harness({ host = 'crime.compare', initial = null, local = null, referrer = '', pathname = '/', search = '', hash = '', shared = new Map(), internal = false, excluded = false, writable = true, duplicate = false } = {}) {
  if (initial) shared.set(KEY, encodeURIComponent(initial))
  if (internal) shared.set(INTERNAL, 'true')
  if (excluded) shared.set(EXCLUDE, 'true')
  const storage = new Map(local ? [[KEY, local]] : [])
  const cookies = new Map([['unrelated', 'preserved']]), writes = [], head = [], body = [], events = {}, documentEvents = {}, timers = new Map()
  let clock = NOW, timerId = 0, canWrite = writable, reloads = 0
  class ClockDate extends Date { constructor(...args) { super(...(args.length ? args : [clock])) } static now() { return clock } }
  const message = { textContent: '' }, button = { focus() {} }
  const controls = new Map(['[data-audience-status]', '[data-audience-internal]', '[data-audience-exclude]'].map(selector => [selector, [{ textContent: '' }]]))
  function element(tag) { return { tag, listeners: {}, hidden: false, removed: false, setAttribute(key, value) { this[key] = value }, addEventListener(key, listener) { this.listeners[key] = listener }, querySelector(selector) { return selector === '[data-audience-message]' ? message : button }, focus() {}, remove() { this.removed = true } } }
  const location = { hostname: host, origin: `https://${host}`, pathname, search, hash, reload() { reloads++ } }
  const document = { referrer, createElement: element, querySelectorAll(selector) { return controls.get(selector) || [] }, head: { appendChild(node) { head.push(node) } }, body: { appendChild(node) { body.push(node) } }, addEventListener(key, listener) { documentEvents[key] = listener } }
  Object.defineProperty(document, 'cookie', {
    get() { return [...shared, ...cookies].map(([name, value]) => `${name}=${value}`).join('; ') + (duplicate && shared.has(KEY) ? `; ${KEY}=malformed` : '') },
    set(value) {
      writes.push(value)
      if (!canWrite) return
      const [pair] = value.split(';'), at = pair.indexOf('='), name = pair.slice(0, at), content = pair.slice(at + 1)
      const target = [KEY, INTERNAL, EXCLUDE].includes(name) ? shared : cookies
      if (value.includes('Max-Age=0')) target.delete(name); else target.set(name, content)
    }
  })
  function navigate(url) { const next = new URL(url, location.origin); location.pathname = next.pathname; location.search = next.search; location.hash = next.hash }
  const history = { pushState(_state, _title, url) { navigate(url) }, replaceState(_state, _title, url) { navigate(url) } }
  const context = { document, location, history, crimeLedgerAudienceConfig: { measurementId: ID, policy: 'ga4-consent-v1' },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    addEventListener(key, listener) { events[key] = listener }, queueMicrotask(callback) { callback() },
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, { callback, at: clock + delay }); return id }, clearTimeout(id) { timers.delete(id) },
    setInterval(callback, delay) { const id = ++timerId; timers.set(id, { callback, at: clock + delay, interval: delay }); return id },
    URL, URLSearchParams, Date: ClockDate, console }
  context.window = context
  vm.runInNewContext(source, context, { filename: 'audience.js' })
  const choose = value => { context.crimeLedgerAudience?.manage(); body.findLast(node => node.tag === 'section' && !node.removed)?.listeners.click({ target: { closest() { return { dataset: { audienceChoice: value } } } } }) }
  const load = () => head.find(node => node.tag === 'script')?.onload()
  const commands = () => context.dataLayer ? Array.from(context.dataLayer, command => Array.from(command)) : []
  const views = () => commands().filter(command => command[0] === 'event' && command[1] === 'page_view')
  const advance = elapsed => { clock += elapsed; for (const [id, timer] of [...timers]) if (timer.at <= clock) { timers.delete(id); timer.callback(); if (timer.interval) timers.set(id, { ...timer, at: clock + timer.interval }) } }
  return { context, head, body, events, documentEvents, location, history, shared, storage, cookies, writes, message, controls, choose, load, commands, views, advance, setWritable(value) { canWrite = value }, reloads: () => reloads }
}

test('preview hosts, refusal and absent consent never load Google', () => {
  const preview = harness({ host: 'preview.pages.dev' })
  assert.equal(preview.body.length, 0)
  const run = harness()
  assert.equal(run.context.dataLayer, undefined)
  assert.equal(run.head.length, 0)
  run.choose('reject'); run.advance(1000)
  assert.equal(run.head.length, 0)
  assert.equal(JSON.parse(decodeURIComponent(run.shared.get(KEY))).choice, 'reject')
})

test('explicit consent loads once with advertising disabled and sanitized defaults', () => {
  const run = harness({ search: '?q=private-name&crime=sexual-offences&area=E23000001&compare=secret', referrer: 'https://example.net/article/123?private=true#fragment' })
  run.choose('allow')
  assert.equal(run.head.length, 1)
  assert.match(run.head[0].src, /^https:\/\/www\.googletagmanager\.com\/gtag\/js\?id=G-6DZZ4SE8DG$/)
  assert.deepEqual(run.commands().map(command => command[0]), ['consent'])
  run.load()
  const config = run.commands().find(command => command[0] === 'config')[2]
  assert.equal(config.send_page_view, false)
  assert.equal(config.allow_google_signals, false)
  assert.equal(config.allow_ad_personalization_signals, false)
  assert.equal(config.cookie_expires, 31536000)
  assert.equal(config.cookie_update, false)
  assert.equal(config.page_location, 'https://crime.compare/official/forces')
  assert.equal(config.page_referrer, 'https://example.net/')
  assert.equal(config.content_group, 'Official comparison')
  assert.equal(run.views().length, 1)
  assert.ok(run.commands().findIndex(command => command[0] === 'set') < run.commands().findIndex(command => command[0] === 'config'))
  assert.ok(run.commands().findIndex(command => command[0] === 'set') < run.commands().findIndex(command => command[0] === 'consent' && command[2].analytics_storage === 'granted'))
  assert.ok(!JSON.stringify(run.commands()).match(/private-name|sexual-offences|E23000001|article\/123|secret/))
  for (const command of run.commands().filter(command => command[0] === 'consent')) {
    assert.equal(command[2].ad_storage, 'denied'); assert.equal(command[2].ad_personalization, 'denied'); assert.equal(command[2].ad_user_data, 'denied')
  }
})

test('four broad comparison views and method/source sections ignore crime and profile changes', () => {
  const run = harness({ initial: saved() }); run.load()
  run.history.replaceState(null, '', '/?q=private&crime=homicide&area=private&compare=private')
  assert.equal(run.views().length, 1)
  run.history.replaceState(null, '', '/?areas=region&crime=private')
  run.history.replaceState(null, '', '/?areas=region&source=monthly&crime=private')
  run.history.replaceState(null, '', '/?source=monthly&crime=private')
  run.location.hash = '#methodology'; run.events.hashchange()
  run.location.hash = '#sources'; run.events.hashchange()
  assert.deepEqual(run.views().map(view => view[2].page_location), ['/official/forces', '/official/regions', '/monthly/regions', '/monthly/forces', '/method', '/sources'].map(path => `https://crime.compare${path}`))
  assert.equal(run.head.length, 1)
  assert.ok(!JSON.stringify(run.commands()).includes('private'))
})

test('privacy path is generic on www and unknown paths never load Google', () => {
  const privacy = harness({ host: 'www.crime.compare', initial: saved(), pathname: '/privacy/', search: '?secret=hidden' }); privacy.load()
  assert.equal(privacy.views()[0][2].page_location, 'https://crime.compare/privacy')
  assert.equal(privacy.views()[0][2].content_group, 'Privacy')
  assert.equal(harness({ initial: saved(), pathname: '/unknown/private' }).head.length, 0)
})

test('crawlable discovery routes do not load Google or disclose area and crime slugs', () => {
  for (const pathname of ['/areas/', '/areas/E23000013/', '/crime/', '/crime/homicide/', '/methodology/', '/sources/']) {
    const run = harness({ initial: saved(), pathname, search: '?q=private-name' })
    run.load()
    assert.equal(run.head.length, 0)
    assert.equal(run.views().length, 0)
    assert.equal(run.commands().length, 0)
  }
})

test('withdrawal during async loading prevents configuration and page views', () => {
  const run = harness(); run.choose('allow'); run.choose('reject'); run.load()
  assert.equal(run.views().length, 0)
  assert.equal(run.commands().filter(command => command[0] === 'config').length, 0)
  assert.equal(run.context[`ga-disable-${ID}`], true)
})

test('withdrawal clears GA cookies and consent denial is idempotent while polling', () => {
  const run = harness({ initial: saved() }); run.load(); run.cookies.set('_ga', 'browser-id'); run.cookies.set('_ga_6DZZ4SE8DG', 'session')
  run.choose('reject')
  assert.equal(run.cookies.has('_ga'), false)
  assert.equal(run.cookies.get('unrelated'), 'preserved')
  assert.ok(run.writes.some(write => write.startsWith('_ga=;') && write.includes('Domain=crime.compare')))
  const length = run.commands().length
  for (let i = 0; i < 5; i++) run.advance(1000)
  assert.equal(run.commands().length, length)
  run.history.replaceState(null, '', '/?source=monthly')
  assert.equal(run.views().length, 1)
})

test('shared-cookie withdrawal reaches another hostname within the bounded poll', () => {
  const shared = new Map(), apex = harness({ initial: saved(), shared }), www = harness({ host: 'www.crime.compare', shared })
  apex.load(); www.load(); www.cookies.set('_ga', 'www-host-cookie')
  apex.choose('reject'); www.advance(1000)
  assert.equal(www.context[`ga-disable-${ID}`], true)
  assert.equal(www.cookies.has('_ga'), false)
  www.history.replaceState(null, '', '/?source=monthly')
  assert.equal(www.views().length, 1)
})

test('stale localStorage cannot regrant after deleted, expired, malformed or duplicate authority cookies', () => {
  const noCookie = harness({ local: saved() }); assert.equal(noCookie.head.length, 0)
  for (const initial of [saved('allow', NOW - 180 * DAY), '{broken', saved()]) {
    const run = harness({ initial, local: saved(), duplicate: initial === saved() })
    assert.equal(run.head.length, 0)
  }
  const run = harness({ initial: saved() }); run.load(); run.shared.delete(KEY); run.advance(1000)
  assert.equal(run.context[`ga-disable-${ID}`], true)
  run.history.replaceState(null, '', '/?source=monthly'); assert.equal(run.views().length, 1)
})

test('cleared same-host storage and preference expiry withdraw consent without renewal', () => {
  const cleared = harness({ initial: saved() }); cleared.load(); cleared.events.storage({ key: null, newValue: null })
  assert.equal(cleared.context[`ga-disable-${ID}`], true)
  assert.equal(cleared.shared.has(KEY), false)
  const expired = harness({ initial: saved() }); expired.load(); const raw = expired.shared.get(KEY)
  expired.advance(180 * DAY)
  assert.equal(expired.context[`ga-disable-${ID}`], true)
  assert.equal(expired.shared.get(KEY), raw)
})

test('failed consent persistence fails closed and failed rejection cannot resume on navigation', () => {
  const blocked = harness({ writable: false }); blocked.choose('allow')
  assert.equal(blocked.head.length, 0); assert.match(blocked.message.textContent, /could not save/)
  const existing = harness({ initial: saved() }); existing.load(); existing.setWritable(false); existing.choose('reject')
  existing.advance(1000); existing.history.replaceState(null, '', '/?source=monthly')
  assert.equal(existing.context[`ga-disable-${ID}`], true)
  assert.equal(existing.views().length, 1)
  const reloaded = harness({ shared: existing.shared, local: existing.storage.get(KEY), writable: false })
  reloaded.history.replaceState(null, '', '/?source=monthly'); reloaded.advance(1000)
  assert.equal(reloaded.head.length, 0)
  assert.equal(reloaded.context[`ga-disable-${ID}`], true)
})

test('owner marker precedes acceptance; hard exclusion blocks Google even with an old grant', () => {
  const owner = harness(); owner.context.crimeLedgerAudience.setInternal(true); owner.choose('allow'); owner.load()
  assert.equal(owner.views()[0][2].traffic_type, 'internal')
  assert.equal(owner.views()[0][2].debug_mode, true)
  const excluded = harness({ initial: saved(), excluded: true })
  assert.equal(excluded.head.length, 0)
  excluded.choose('allow'); assert.equal(excluded.head.length, 0)
  excluded.context.crimeLedgerAudience.exclude(false)
  excluded.history.replaceState(null, '', '/?source=monthly'); excluded.load()
  assert.equal(excluded.head.length, 0)
  assert.equal(JSON.parse(decodeURIComponent(excluded.shared.get(KEY))).choice, 'reject')
})

test('cross-host owner changes reload configured tabs before stale public defaults persist', () => {
  const shared = new Map(), apex = harness({ initial: saved(), shared }), www = harness({ host: 'www.crime.compare', shared })
  apex.load(); www.load(); apex.context.crimeLedgerAudience.setInternal(true); www.advance(1000)
  assert.equal(apex.reloads(), 1); assert.equal(www.reloads(), 1)
  assert.equal(www.context[`ga-disable-${ID}`], true)
})
