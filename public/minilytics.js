/* Consent-gated Minilytics. No identity, query-string, click or payment tracking. */
export function createTracker(config) {
  const prefix = config.cookiePrefix || 'minilytics';
  const origin = new URL(config.origin).origin;
  const domain = config.cookieDomain || '';
  let stopped = false, lastKey = null, lastPath = null, first = true;
  let visibleSince = 0, timer, pings = 0;
  const initialReferrer = (() => {
    try { const u = new URL(document.referrer); return /^https?:$/.test(u.protocol) ? u.origin + '/' : ''; }
    catch { return ''; }
  })();
  const permitted = () => {
    try { return !stopped && config.permitted() && !navigator.webdriver && !navigator.globalPrivacyControl && !['1', 'yes'].includes(navigator.doNotTrack); }
    catch { return false; }
  };
  function cookie(name, value, seconds) {
    if (value !== undefined) document.cookie = `${name}=${value}; Path=/; Max-Age=${seconds}; SameSite=Lax; Secure${domain ? '; Domain=' + domain : ''}`;
    const values = document.cookie.split(';').map(v => v.trim()).filter(v => v.startsWith(name + '='));
    return values.length === 1 ? values[0].slice(name.length + 1) : null;
  }
  function clearCookies() {
    for (const name of [prefix + '_vid', prefix + '_sid']) {
      for (const scope of ['', ...(domain ? ['; Domain=' + domain] : [])]) {
        document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax; Secure${scope}`;
      }
    }
  }
  function status(value) { config.onStatus?.(value); }
  function send(type, path, extra = {}) {
    if (!permitted() || !config.path()) return false;
    try {
      const url = new URL(path, origin);
      if (url.origin !== origin) return false;
      url.search = ''; url.hash = '';
      let vid = cookie(prefix + '_vid'), sid = cookie(prefix + '_sid');
      if (!/^[\w-]{8,64}$/.test(vid || '')) vid = cookie(prefix + '_vid', crypto.randomUUID(), 31536000);
      sid = cookie(prefix + '_sid', /^[\w-]{8,64}$/.test(sid || '') ? sid : crypto.randomUUID(), 1800);
      if (!vid || !sid) return false;
      fetch('https://minilytics.sjehan.workers.dev/api/event', {
        method: 'POST', headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify({ w: config.siteId, t: type, u: url.href, vid, sid, ...extra }),
        credentials: 'omit', referrerPolicy: 'no-referrer', keepalive: true,
      }).then(r => status(r.status === 202 ? 'active' : 'unavailable'), () => status('unavailable'));
      return true;
    } catch { status('unavailable'); return false; }
  }
  function flush() {
    const now = Date.now(), elapsed = visibleSince ? now - visibleSince : 0;
    visibleSince = lastKey && document.visibilityState === 'visible' ? now : 0;
    if (lastPath && elapsed >= 1000) send('ping', lastPath, { d: Math.min(elapsed, 600000) });
  }
  function pause() {
    clearTimeout(timer); lastKey = lastPath = null; visibleSince = 0;
  }
  function schedule() {
    clearTimeout(timer);
    if (!lastKey || pings >= 30 || stopped) return;
    timer = setTimeout(() => { if (!permitted()) { pause(); return; } flush(); pings++; schedule(); }, 60000);
  }
  function update() {
    const path = config.path();
    if (!permitted() || !path) { pause(); return; }
    // The key stays in memory; only the configured broad category is transmitted.
    const key = path + '|' + (config.key ? config.key() : location.pathname);
    if (key === lastKey) return;
    flush();
    if (!send('pageview', path, { r: first ? initialReferrer : origin + '/' })) return;
    first = false; lastKey = key; lastPath = path; pings = 0;
    visibleSince = document.visibilityState === 'visible' ? Date.now() : 0;
    schedule();
  }
  const wrappers = [];
  for (const method of ['pushState', 'replaceState']) {
    const original = history[method];
    const wrapper = function (...args) { const result = original.apply(this, args); queueMicrotask(update); return result; };
    history[method] = wrapper; wrappers.push({ method, original, wrapper });
  }
  document.addEventListener('visibilitychange', flush);
  addEventListener('pagehide', flush); addEventListener('popstate', update);
  update();
  return {
    update,
    stop() {
      stopped = true; pause(); clearCookies(); status('off');
      document.removeEventListener('visibilitychange', flush);
      removeEventListener('pagehide', flush); removeEventListener('popstate', update);
      for (const { method, original, wrapper } of wrappers) if (history[method] === wrapper) history[method] = original;
    },
  };
}

/** For sites without an existing consent UI. Existing consent managers use createTracker directly. */
export function mountConsent(config) {
  if (![config.domain, 'www.' + config.domain].includes(location.hostname)) return;
  const key = 'minilytics-audience-choice-v1', lifetime = 180 * 86400000;
  const privacySignal = navigator.globalPrivacyControl || ['1', 'yes'].includes(navigator.doNotTrack);
  let tracker, prompt, expiry;
  const read = () => {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      const age = Date.now() - value.chosenAt;
      return value.revision === 1 && ['allow', 'reject'].includes(value.choice) && age >= 0 && age < lifetime ? value : null;
    } catch { return null; }
  };
  const permitted = () => !privacySignal && read()?.choice === 'allow';
  const style = document.createElement('style');
  style.textContent = '.ml-consent-notice,.ml-consent-manage{font:13px/1.5 system-ui,sans-serif;color:#17243a;background:white;border:1px solid #bcc8d9;border-radius:12px;box-sizing:border-box;z-index:10001}.ml-consent-notice{position:fixed;right:16px;bottom:16px;width:min(420px,calc(100vw - 32px));padding:18px;box-shadow:0 12px 36px #0002}.ml-consent-notice p{margin:8px 0 14px}.ml-consent-notice strong{font-size:16px}.ml-consent-notice a{color:#1745a5;text-decoration:underline}.ml-consent-actions{display:flex;gap:8px}.ml-consent-actions button{flex:1;padding:10px;border:1px solid #b7c5da;border-radius:8px;background:white;color:#17243a;font:600 13px system-ui;cursor:pointer}.ml-consent-manage{position:fixed;bottom:10px;left:10px;padding:6px 11px;cursor:pointer}.ml-consent-notice button:focus-visible,.ml-consent-manage:focus-visible{outline:3px solid #c38522;outline-offset:3px}';
  document.head.appendChild(style);
  const manage = document.createElement('button');
  manage.className = 'ml-consent-manage'; manage.type = 'button'; manage.textContent = 'Analytics choices';
  function show() {
    if (prompt) return;
    prompt = document.createElement('section'); prompt.className = 'ml-consent-notice'; prompt.setAttribute('aria-label', 'Optional analytics');
    const title = document.createElement('strong'); title.textContent = 'Help us understand visits'; prompt.appendChild(title);
    const copy = document.createElement('p');
    copy.textContent = privacySignal ? 'Analytics is off because your browser sends a privacy preference. ' : 'With your permission, our self-hosted Minilytics uses cookies to count visits, engagement, country and device category. You can decline and keep using the whole site. ';
    const link = document.createElement('a'); link.href = config.privacyPath; link.textContent = 'Privacy details'; copy.appendChild(link); prompt.appendChild(copy);
    const actions = document.createElement('div'); actions.className = 'ml-consent-actions';
    for (const [choice, label] of [['reject', 'No thanks'], ['allow', 'Allow analytics']]) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
      button.disabled = choice === 'allow' && privacySignal;
      button.addEventListener('click', () => {
        try { localStorage.setItem(key, JSON.stringify({ revision: 1, choice, chosenAt: Date.now() })); } catch { return; }
        apply();
      });
      actions.appendChild(button);
    }
    prompt.appendChild(actions); document.body.appendChild(prompt); manage.hidden = true;
  }
  function apply() {
    prompt?.remove(); prompt = null; clearTimeout(expiry);
    const choice = read();
    if (permitted()) {
      tracker ||= createTracker({ ...config, origin: 'https://' + config.domain, path: config.path || (() => '/'), permitted });
    } else { tracker?.stop(); tracker = null; }
    manage.hidden = !choice && !privacySignal;
    if (!choice && !privacySignal) show();
    if (choice) expiry = setTimeout(apply, Math.min(Math.max(choice.chosenAt + lifetime - Date.now(), 1), 2147483647));
  }
  manage.addEventListener('click', show); document.body.appendChild(manage);
  addEventListener('storage', event => { if (event.key === key || event.key === null) apply(); });
  apply();
}
