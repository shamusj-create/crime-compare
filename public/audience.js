/* Optional consent-first GA4. No Google resource is requested before permission. */
(() => {
  'use strict';
  const config = window.crimeLedgerAudienceConfig || {};
  const id = config.measurementId || '';
  if (!['crime.compare', 'www.crime.compare'].includes(location.hostname) || !/^G-[A-Z0-9]{7,15}$/.test(id) || config.policy !== 'ga4-consent-v1') return;
  const choiceKey = 'crimeledger-audience-choice-v1';
  const internalKey = 'crimeledger-analytics-internal';
  const excludeKey = 'crimeledger-analytics-exclude';
  const revision = 1, lifetime = 180 * 86400000;
  const disabledKey = `ga-disable-${id}`;
  const denied = { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied' };
  const pages = {
    '/official/forces': ['Official force comparison', 'Official comparison'],
    '/official/regions': ['Official region comparison', 'Official comparison'],
    '/monthly/forces': ['Monthly force comparison', 'Monthly comparison'],
    '/monthly/regions': ['Monthly region comparison', 'Monthly comparison'],
    '/method': ['Crime statistics methodology', 'Method'],
    '/sources': ['Crime statistics sources', 'Sources'],
    '/privacy': ['CrimeLedger privacy notice', 'Privacy']
  };
  const initialReferrer = (() => { try { const url = new URL(document.referrer); return /^https?:$/.test(url.protocol) ? `${url.origin}/` : ''; } catch { return ''; } })();
  let section = location.hash === '#methodology' ? 'method' : location.hash === '#sources' ? 'sources' : 'comparison';
  let preference, prompt, manage, preferenceTimer;
  let tagState = 'unloaded', configured = false, lastPage = null, sentAnyPageview = false;
  let lastCookie = null, lastInternal = null, memoryRejection = false;
  window[disabledKey] = true;

  function readCookie(key) {
    const values = document.cookie.split(';').map(item => item.trim()).filter(item => item.startsWith(`${key}=`));
    if (values.length !== 1) return null; // Duplicate or malformed consent fails closed.
    try { return decodeURIComponent(values[0].slice(key.length + 1)); } catch { return null; }
  }
  function writeCookie(key, value, days) {
    document.cookie = `${key}=${encodeURIComponent(value)}; Max-Age=${days * 86400}; Path=/; Domain=crime.compare; SameSite=Lax; Secure`;
    return readCookie(key) === value;
  }
  function removeCookie(key) {
    for (const domain of ['', '; Domain=crime.compare', '; Domain=www.crime.compare']) {
      document.cookie = `${key}=; Max-Age=0; Path=/${domain}; SameSite=Lax; Secure`;
    }
  }
  function mirror(key, value) {
    try { if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value); } catch { /* Shared cookie remains authoritative. */ }
  }
  function parsePreference(raw) {
    try {
      const next = JSON.parse(raw), age = Date.now() - next.chosenAt;
      return next.revision === revision && ['allow', 'reject'].includes(next.choice) && Number.isFinite(next.chosenAt) && age >= 0 && age < lifetime ? next : null;
    } catch { return null; }
  }
  function readPreference() {
    const shared = parsePreference(readCookie(choiceKey));
    let local = null;
    try { local = parsePreference(localStorage.getItem(choiceKey)); } catch { /* Cookie grant still requires explicit saved consent. */ }
    // A newer refusal can veto an old grant when cookie writes failed. Local
    // storage never grants permission, even after a reload or cookie deletion.
    return local?.choice === 'reject' && (!shared || local.chosenAt >= shared.chosenAt) ? local : shared;
  }
  function currentPage() {
    const path = location.pathname.replace(/\/+$/, '') || '/';
    if (path === '/privacy' || path === '/privacy.html') return '/privacy';
    if (!['/', '/index.html'].includes(path)) return null;
    if (section !== 'comparison') return section === 'method' ? '/method' : '/sources';
    const params = new URLSearchParams(location.search);
    return `/${params.get('source') === 'monthly' ? 'monthly' : 'official'}/${params.get('areas') === 'region' ? 'regions' : 'forces'}`;
  }
  function comparisonKey() {
    const params = new URLSearchParams(location.search);
    return `${location.pathname}|${params.get('source') === 'monthly' ? 'monthly' : 'official'}|${params.get('areas') === 'region' ? 'regions' : 'forces'}`;
  }
  function gtag() { window.dataLayer.push(arguments); }
  function clearAnalyticsCookies() {
    for (const item of document.cookie.split(';')) {
      const name = item.trim().split('=')[0];
      if (/^_ga(?:_|$)/.test(name)) removeCookie(name);
    }
  }
  function disableMeasurement() {
    const wasDisabled = window[disabledKey];
    window[disabledKey] = true;
    if (configured && !wasDisabled) gtag('consent', 'update', denied);
    clearAnalyticsCookies();
    lastPage = null;
  }
  function permission() {
    const choice = readPreference();
    return !memoryRejection && preference?.choice === 'allow' && choice?.choice === 'allow' && readCookie(excludeKey) !== 'true';
  }
  function startIfAllowed() {
    // Recheck the shared cookie at every event boundary and after async loading.
    if (!permission()) { disableMeasurement(); return; }
    const page = currentPage();
    if (!page) { disableMeasurement(); return; }
    if (tagState === 'loading') return;
    if (tagState === 'unloaded') {
      window.dataLayer = window.dataLayer || [];
      gtag('consent', 'default', denied);
      tagState = 'loading';
      const script = document.createElement('script');
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
      script.onload = () => { tagState = 'loaded'; startIfAllowed(); };
      script.onerror = () => { tagState = 'unloaded'; script.remove(); };
      document.head.appendChild(script);
      return;
    }
    if (lastPage === page) return;
    window[disabledKey] = false;
    const fields = {
      page_location: `https://crime.compare${page}`,
      page_title: `CrimeLedger — ${pages[page][0]}`,
      page_referrer: sentAnyPageview ? 'https://crime.compare/' : initialReferrer,
      content_group: pages[page][1],
      ...(readCookie(internalKey) === 'true' ? { traffic_type: 'internal', debug_mode: true } : {})
    };
    if (!configured) gtag('js', new Date());
    // Safe defaults also cover Google's subsequent session/engagement events.
    gtag('set', fields);
    gtag('consent', 'update', { ...denied, analytics_storage: 'granted' });
    gtag('config', id, { send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false,
      cookie_expires: 31536000, cookie_update: false, cookie_flags: 'SameSite=Lax;Secure', ...fields });
    configured = true;
    if (!permission()) { disableMeasurement(); return; }
    gtag('event', 'page_view', { send_to: id, ...fields });
    lastPage = page;
    sentAnyPageview = true;
  }
  function updateOwnerControls() {
    const internal = readCookie(internalKey) === 'true', excluded = readCookie(excludeKey) === 'true';
    for (const element of document.querySelectorAll('[data-audience-internal]')) element.textContent = internal ? 'Remove owner/test marker' : 'Mark as owner/test browser';
    for (const element of document.querySelectorAll('[data-audience-exclude]')) element.textContent = excluded ? 'Remove hard exclusion' : 'Exclude this browser completely';
    for (const element of document.querySelectorAll('[data-audience-status]')) element.textContent = `Analytics: ${excluded ? 'hard excluded' : preference?.choice === 'allow' ? 'allowed' : preference?.choice === 'reject' ? 'declined' : 'not allowed yet'}. Owner/test marker: ${internal ? 'on' : 'off'}.`;
  }
  function scheduleExpiry() {
    clearTimeout(preferenceTimer);
    if (!preference) return;
    preferenceTimer = setTimeout(syncPreference, Math.min(Math.max(preference.chosenAt + lifetime - Date.now(), 1), 2147483647));
  }
  function applyPreference(next, focusManage = false) {
    preference = next;
    prompt?.remove(); prompt = null;
    if (next?.choice === 'allow') startIfAllowed(); else disableMeasurement();
    scheduleExpiry(); updateOwnerControls();
    if (manage) {
      manage.hidden = !next;
      if (!next && readCookie(excludeKey) !== 'true') showPrompt();
      else if (focusManage) manage.focus();
    }
  }
  function syncPreference() {
    const internal = readCookie(internalKey);
    if (internal !== lastInternal) {
      lastInternal = internal;
      if (configured) { disableMeasurement(); location.reload(); return; }
    }
    const raw = readCookie(choiceKey), next = readPreference();
    if (raw !== lastCookie || (next?.choice === 'reject' && preference?.choice === 'allow') || (!!preference && ((!next && !memoryRejection) || Date.now() >= preference.chosenAt + lifetime))) {
      lastCookie = raw;
      memoryRejection = false;
      mirror(choiceKey, next ? JSON.stringify(next) : null);
      applyPreference(next);
    }
    if (!permission()) disableMeasurement();
    scheduleExpiry(); updateOwnerControls();
  }
  function choose(value) {
    const next = { revision, choice: value, chosenAt: Date.now() }, raw = JSON.stringify(next);
    if (value === 'allow' && readCookie(excludeKey) === 'true') {
      disableMeasurement();
      if (prompt) prompt.querySelector('[data-audience-message]').textContent = 'This browser is hard excluded. Remove that setting on the privacy page before allowing analytics.';
      return;
    }
    if (value === 'reject') removeCookie(choiceKey);
    const stored = writeCookie(choiceKey, raw, 180);
    if (value === 'allow' && !stored) {
      memoryRejection = true; disableMeasurement();
      if (prompt) prompt.querySelector('[data-audience-message]').textContent = 'Your browser could not save this choice. Analytics remains off; the site is fully available.';
      return;
    }
    memoryRejection = value === 'reject' && !stored;
    lastCookie = readCookie(choiceKey);
    mirror(choiceKey, raw);
    applyPreference(next, true);
  }
  function showPrompt() {
    if (prompt) return;
    if (manage) manage.hidden = true;
    prompt = document.createElement('section');
    prompt.className = 'audience-choice'; prompt.setAttribute('aria-labelledby', 'audience-choice-heading');
    prompt.innerHTML = '<strong id="audience-choice-heading">Help us count readers</strong><p>With your permission, Google Analytics uses cookies to measure visits and broad sections. We use aggregate audience reports to improve this site and inform potential sponsors. Your choice does not affect access. <a href="/privacy/">Privacy and settings</a></p><p class="audience-message" data-audience-message role="status"></p><div class="audience-choice__actions"><button type="button" data-audience-choice="reject">No thanks</button><button type="button" data-audience-choice="allow">Allow analytics</button></div>';
    prompt.addEventListener('click', event => {
      const value = event.target.closest('[data-audience-choice]')?.dataset.audienceChoice;
      if (['allow', 'reject'].includes(value)) choose(value);
    });
    document.body.appendChild(prompt);
  }
  function setInternal(value) {
    if (value) writeCookie(internalKey, 'true', 365); else removeCookie(internalKey);
    lastInternal = readCookie(internalKey);
    mirror(internalKey, value ? 'true' : null); updateOwnerControls();
    // A reload prevents existing GA defaults from retaining a removed QA flag.
    if (configured) { disableMeasurement(); location.reload(); }
  }
  function exclude(value) {
    if (value) { writeCookie(excludeKey, 'true', 365); choose('reject'); }
    else { removeCookie(excludeKey); choose('reject'); }
    mirror(excludeKey, value ? 'true' : null); syncPreference(); updateOwnerControls();
  }
  window.crimeLedgerAudience = { manage: showPrompt, setInternal, exclude };
  document.addEventListener('click', event => {
    if (event.target.closest('[data-audience-manage]')) { event.preventDefault(); showPrompt(); prompt?.querySelector('button')?.focus(); }
    if (event.target.closest('[data-audience-internal]')) setInternal(readCookie(internalKey) !== 'true');
    if (event.target.closest('[data-audience-exclude]')) exclude(readCookie(excludeKey) !== 'true');
  });
  addEventListener('storage', event => {
    if (event.key === choiceKey || event.key === null) {
      // Cleared storage is a withdrawal signal, not a stale local grant.
      if (event.newValue === null) { removeCookie(choiceKey); memoryRejection = false; }
      if (parsePreference(event.newValue)?.choice === 'reject') {
        memoryRejection = true; applyPreference(parsePreference(event.newValue));
      }
      syncPreference();
    }
    if ([internalKey, excludeKey].includes(event.key)) {
      if (event.key === internalKey && configured) { disableMeasurement(); location.reload(); }
      else syncPreference();
    }
  });
  for (const method of ['pushState', 'replaceState']) {
    const original = history[method];
    history[method] = function (...args) {
      const before = comparisonKey(), previousPath = location.pathname;
      const result = original.apply(this, args);
      if (comparisonKey() !== before || location.pathname !== previousPath) { section = 'comparison'; queueMicrotask(startIfAllowed); }
      return result;
    };
  }
  function navigation() {
    section = location.hash === '#methodology' ? 'method' : location.hash === '#sources' ? 'sources' : 'comparison';
    startIfAllowed();
  }
  addEventListener('popstate', navigation); addEventListener('hashchange', navigation);
  addEventListener('focus', syncPreference);
  document.addEventListener('visibilitychange', syncPreference);
  // The shared essential cookie synchronizes apex/www; no network polling.
  setInterval(syncPreference, 1000);
  manage = document.createElement('button'); manage.type = 'button'; manage.className = 'audience-manage';
  manage.textContent = 'Analytics choices'; manage.addEventListener('click', () => { showPrompt(); prompt.querySelector('button').focus(); });
  document.body.appendChild(manage);
  lastCookie = readCookie(choiceKey);
  lastInternal = readCookie(internalKey);
  applyPreference(readPreference());
})();
