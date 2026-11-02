/* Cloudflare Web Analytics only: aggregate statistics, no visitor cookies or persistent IDs. */
(() => {
  'use strict';
  const config = /* CWA_CONFIG */ {"domain":"crime.compare","hosts":["crime.compare","www.crime.compare"],"token":"c4407d54c6474bb7a8f18698d06dd74d","legacyChoices":["crimeledger-audience-choice-v1"],"exclusions":["crimeledger-analytics-internal","crimeledger-analytics-exclude"]};
  if (!config.hosts?.includes(location.hostname) || window.cloudflareAnalytics) return;
  const preferenceKey = 'cloudflare-analytics-choice-v1';
  let beacon = null;
  const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const cookies = key => document.cookie.split(';').map(item => item.trim()).filter(item => item.startsWith(key + '=')).map(item => { try { return decodeURIComponent(item.slice(key.length + 1)); } catch { return ''; } });
  const signal = () => navigator.globalPrivacyControl === true || ['1', 'yes'].includes(navigator.doNotTrack);
  const excluded = () => (config.exclusions || []).some(key => [read(key), ...cookies(key)].some(value => ['1', 'true'].includes(value)));
  const legacyRefusal = () => (config.legacyChoices || []).some(key => {
    return [read(key), ...cookies(key)].some(raw => {
      if (['declined', 'deny', 'reject', 'false'].includes(raw)) return true;
      try { return ['declined', 'deny', 'reject'].includes(JSON.parse(raw)?.choice); } catch { return false; }
    });
  });
  const choice = () => read(preferenceKey) || (legacyRefusal() ? 'off' : 'on');
  const sensitive = value => {
    try {
      const url = new URL(value, location.origin);
      return /(?:^|\/)(?:api|auth|account|billing|checkout|login|logout|signin|signup|reset-password|verify)(?:\/|$)/i.test(url.pathname) ||
        [...url.searchParams.keys()].some(key => /^(?:access|access_token|token|code|session_id|email|password|reset_token|invite|secret)$/i.test(key)) ||
        /(?:access|token|password|secret)=/i.test(url.hash);
    } catch { return true; }
  };
  const eligible = () => !signal() && !excluded() && choice() !== 'off' && !navigator.webdriver &&
    !sensitive(location.href) && (!document.referrer || !sensitive(document.referrer));

  // Retire only the old analytics cookies; authentication and payment cookies are untouched.
  for (const item of document.cookie.split(';')) {
    const name = item.trim().split('=')[0];
    if (!/^(?:_ga(?:_|$)|_gid$|_gat(?:_|$)|civicledger_ml_(?:vid|sid)$|minilytics_(?:vid|sid)$|ml_(?:vid|sid)$)/.test(name)) continue;
    for (const domain of ['', location.hostname, '.' + config.domain]) {
      document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax; Secure${domain ? '; Domain=' + domain : ''}`;
    }
  }

  function start() {
    if (beacon || !eligible() || !/^[a-f0-9]{32}$/.test(config.token || '')) return;
    beacon = document.createElement('script');
    beacon.defer = true;
    beacon.src = 'https://static.cloudflareinsights.com/beacon.min.js';
    beacon.dataset.cfBeacon = JSON.stringify({ token: config.token, spa: config.spa !== false });
    document.head.appendChild(beacon);
  }

  function loadPreferencesStyle() {
    if (document.getElementById('cwa-preferences-css')) return;
    const style = document.createElement('link'); style.id = 'cwa-preferences-css'; style.rel = 'stylesheet'; style.href = config.stylesheet || '/cloudflare-analytics.css'; document.head.appendChild(style);
  }

  function setEnabled(enabled) {
    try { localStorage.setItem(preferenceKey, enabled ? 'on' : 'off'); }
    catch { return false; }
    // The provider has no unload API. Reload removes its listeners and queued measurements.
    location.reload();
    return true;
  }

  function openPreferences() {
    if (document.getElementById('cloudflare-analytics-preferences')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'cloudflare-analytics-preferences';
    dialog.setAttribute('aria-labelledby', 'cloudflare-analytics-title');
    dialog.className = 'cwa-preferences';
    loadPreferencesStyle();
    const heading = document.createElement('h2'); heading.id = 'cloudflare-analytics-title'; heading.textContent = 'Analytics choices';
    const description = document.createElement('p');
    description.textContent = 'We use Cloudflare Web Analytics for aggregate page visits and performance statistics. It does not use analytics cookies, persistent visitor IDs or advertising profiles.';
    const status = document.createElement('p');
    status.textContent = signal() ? 'Analytics is off because your browser sends a privacy preference.' : excluded() ? 'This owner/test browser is excluded from analytics.' : choice() === 'off' ? 'Analytics is off in this browser.' : 'Aggregate analytics is on in this browser.';
    const controls = document.createElement('div'); controls.className = 'cwa-preferences-actions';
    for (const [label, enabled] of [['Turn analytics off', false], ['Turn analytics on', true], ['Close', null]]) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
      if (enabled === true) button.disabled = signal() || excluded();
      button.addEventListener('click', () => {
        if (enabled === null) { dialog.close(); dialog.remove(); }
        else if (!setEnabled(enabled)) { status.textContent = 'Your browser could not save this choice. Use its privacy controls to block measurement.'; }
      });
      controls.appendChild(button);
    }
    dialog.appendChild(heading); dialog.appendChild(description); dialog.appendChild(status); dialog.appendChild(controls);
    dialog.addEventListener('cancel', () => dialog.remove());
    document.body.appendChild(dialog); dialog.showModal();
  }

  window.cloudflareAnalytics = { openPreferences, setEnabled };
  document.addEventListener('click', event => {
    if (!event.target.closest?.('[data-audience-manage], [data-cwa-manage]')) return;
    event.preventDefault(); openPreferences();
  });
  addEventListener('macropulse-consent-open', openPreferences);
  addEventListener('storage', event => {
    if (event.key === null || event.key === preferenceKey || (config.legacyChoices || []).includes(event.key) || (config.exclusions || []).includes(event.key)) location.reload();
  });
  if (config.manageButton) {
    const mount = () => {
      if (document.getElementById('cwa-manage')) return;
      loadPreferencesStyle();
      const button = document.createElement('button'); button.id = 'cwa-manage'; button.type = 'button'; button.className = 'cwa-manage'; button.textContent = 'Analytics choices';
      button.addEventListener('click', openPreferences); document.body.appendChild(button);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true}); else mount();
  }
  start();
})();
