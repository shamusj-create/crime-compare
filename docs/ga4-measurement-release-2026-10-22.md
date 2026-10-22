# GA4 measurement release — 22 October 2026

## Status

The dedicated Google Analytics property, consent controller and privacy notice are deployed from [commit `a7ff826`](https://github.com/shamusj-create/crime-compare/commit/a7ff826) in Cloudflare deployment `77451b43`. [CI run 39810368507](https://github.com/shamusj-create/crime-compare/actions/runs/39810368507) passed. User-approved live tests on 22 October 2026 verified consent-gated collection transport, sanitized manual page views and cross-host withdrawal after correcting Google's saved stream settings. **The first complete measurement day is 23 October 2026.** This verification establishes the tested flow, not uninterrupted future collection or an audience count.

## Confirmed configuration

| Setting | Value |
|---|---|
| Website | https://crime.compare/ |
| Existing Analytics account | 368143065 |
| Dedicated property | crime.compare — 560206660 |
| Web stream | 16182898408 |
| Public measurement ID | G-6DZZ4SE8DG |
| Reporting timezone | Europe/London, shown as United Kingdom Time |
| Currency | GBP |
| Enhanced measurement | Off; individual interactions and advanced history disabled, saved and rechecked after a full settings reload |
| Google Signals | Off |
| User-provided data collection | Off |
| Advertising personalization | Allowed in 0 of 307 regions |
| Reporting identity | Device-based |
| User/event retention | 14 months; reset on new activity off |
| Internal Traffic exclusion | Active |
| Developer Traffic exclusion | Active |
| Granular location/device collection | Default setting remains on; reports use country and device category |

[Open the saved Advertiser audience overview](https://analytics.google.com/analytics/web/#/a368143065p560206660/reports/reportinghub) with existing authorised Google access. This saved overview is the property's default Reports snapshot. It covers active/new users, engagement and views, with nine cards for broad pages, acquisition, returning users, country, device category, channels, activity and retention. Its saved report ID is `16182938795`; the setup screenshot is `artifacts/analytics-2026-10-22/advertiser-overview.jpg`. The politicians.compare measurement ID is not used for this site.

These are property-specific settings. They were checked independently of the sister property's release record. Restricting the report breakdowns to country and device category does not mean Google's granular collection setting is disabled.

## Consent and data minimisation

The deployed controller follows the sister site's prior opt-in approach: no Google resources before permission, equally weighted allow/refuse buttons, a versioned choice expiring after 180 days, and a persistent way to change or withdraw consent. Advertising consent fields remain denied. Fresh live tests verified successful post-consent collection and withdrawal.

The measurement contract permits only seven generic paths: `/official/forces`, `/official/regions`, `/monthly/forces`, `/monthly/regions`, `/method`, `/sources` and `/privacy`. Event addresses use the canonical `https://crime.compare` origin. Titles are fixed; searches, query parameters, fragments, crime categories, individual areas and profile selections are excluded. Referrers are reduced to origins. Changing a crime filter must not create a duplicate page view; changing the broad source or geography can create one.

Permission requires a valid essential `crimeledger-audience-choice-v1` cookie, shared between apex and `www`. A local-storage mirror supplies immediate same-origin notifications; a newer or equal valid local refusal can veto an older cookie grant, but local storage can never grant permission. Tabs check the shared cookie on a one-second timer and on focus/visibility changes; browsers may delay timers, especially in background tabs. Permission is rechecked before manual events and after the Google tag's asynchronous load. If both preference stores prevent changes, refusal still stops that tab but cannot be guaranteed to survive reload or notify other tabs; the public notice explains this limit and browser controls. Separate owner/test and hard-exclusion controls are provided on the [privacy page](https://crime.compare/privacy/).

The public notice describes optional Google Analytics, its purpose, processing, retention, aggregate reporting, withdrawal and contact route. The footer's former unconditional no-tracking claim has been replaced. Reports describe measurable consenting browsers and must state their coverage and limitations; they do not establish a count of unique people or advertisement delivery.

## Publication and preservation

This app-code release preserved every file under `public/data`, confirmed by comparing commits `17f803a` and `a7ff826`. Live official/monthly datasets, manifests and `refresh-status.json` matched the production build; both dataset hashes matched the status record. No source refresh was required. The scheduled public-data workflow remains independent of Google Analytics, Google credentials and reporting exports.

The setup uses standard GA4 and the existing static Cloudflare Pages hosting. No paid Analytics upgrade, runtime service, database or recurring reporting service is required. The existing annual domain registration remains a separate cost.

The 12 controller lifecycle/privacy tests passed, including asynchronous-load withdrawal, safe URL/default ordering, cross-host refusal and owner-marker changes, expiry, failed-persistence reload and hard-exclusion removal. Independent source review found no remaining critical issues.

Live app and privacy checks found zero Google requests before consent and after **No thanks** followed by reload. The owner/test control was set before acceptance; `www` observed the shared declined choice and owner marker. At 390 × 844, the prompt had no horizontal overflow and both choices were equally sized, 42 pixels high. Desktop proof is `artifacts/analytics-2026-10-22/consent-desktop.jpg`. Scripts, configuration, data and manifests matched the build. Cloudflare transforms the privacy page's two email links and adds its same-origin email-decoding script; that expected transformation explains its HTML byte difference.

The initial opt-in test caught automatic history page views carrying detailed URLs: the Enhanced Measurement master was still on despite the setting attempted during stream creation. The activation gate failed. All six optional interactions and advanced browser-history measurement were then disabled and saved, the master was turned off, and a full settings reload confirmed persistence. There were zero connected site tags. No controller change or code deployment was needed. Google's [page-view guidance](https://developers.google.com/analytics/devguides/collection/ga4/views) confirms that `send_page_view: false` alone does not disable Enhanced Measurement history events.

Fresh cache-disabled tests after that correction passed:

- The Google tag returned 200; collection returned 204 for canonical `https://crime.compare/monthly/forces`, with `traffic_type=internal` and `debug_mode=true`.
- Changing crime type and search, then opening and closing an area profile, produced no additional page view, including after a 12-second delayed flush. No query string or profile identifier appeared in those events.
- Switching to the official source and then regions produced exactly two manual views: `/official/forces` and `/official/regions`.
- A fresh `www` privacy visit returned 204 using canonical `/privacy` and the owner/test flags.
- Withdrawing through `www` changed the shared choice to declined and removed accessible Analytics cookies on both hosts. A subsequent coarse comparison switch on the apex and activity on `www` produced no Google requests.
- A final monitor lasting more than 10 seconds found zero Google requests on both hosts; reloading the declined apex also produced zero. Accessible GA cookie counts remained zero on both hosts.

The setup browser was left marked as owner/test and hard excluded, with temporary cache overrides restored. Local QA evidence is saved under ignored `artifacts/analytics-2026-10-22/`: `collection-verification.json`, `verified-browser-excluded.jpg` and `enhanced-measurement-off.jpg`.

The setup now has verified initial transport and consent behaviour. Reporting still requires collection-health checks throughout each selected period; a 204 response is not a completed audience report. The production runbook includes the saved-settings and live-payload regression gates, because offline controller tests do not verify Google's remote configuration.

## Reports

The property is separate from politicians.compare, so its readership remains separate. Native GA4 reports and exports use the existing Google login. The [private reporting guide](analytics-advertiser-reporting.md) explains `scripts/report_ga4_audience.py`, its read-only API route using existing credentials and its browser-export fallback. The standard-library helper creates printable HTML, Markdown, JSON and CSVs privately, with source hashes, scope and quality checks. It sends nothing to an advertiser and creates no Google credentials or recurring task. Its 23 offline reporting tests passed; no real audience report has been generated.

Creating the property does not recover historical GA4 traffic. The first complete verified measurement day is 23 October 2026; 22 October is a partial setup/test day. Allow at least 48 elapsed hours after a selected period ends for Google processing. A one-day provisional report for 23 October is eligible on 26 October; the first 28-day period, 23 October–19 November, on 22 November. These are eligibility dates, subject to collection health and processing, rather than promises of usable audience figures.
