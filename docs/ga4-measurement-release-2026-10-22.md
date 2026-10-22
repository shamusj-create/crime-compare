# GA4 measurement release — 22 October 2026

## Status

The dedicated Google Analytics property has been created and the settings below confirmed in its dashboard. Website implementation, consent verification and publication are in progress. **Collection is not yet verified as deployed.** No analytics deployment is implied by the existing verified metadata release `17f803a` / Cloudflare deployment `ca0865e4`.

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
| Enhanced measurement | Off |
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

The prepared controller follows the sister site's prior opt-in approach: no Google resources before permission, equally weighted allow/refuse buttons, a versioned choice expiring after 180 days, and a persistent way to change or withdraw consent. Advertising consent fields remain denied. Final code and browser checks must establish these behaviours before publication is called verified.

The measurement contract permits only seven generic paths: `/official/forces`, `/official/regions`, `/monthly/forces`, `/monthly/regions`, `/method`, `/sources` and `/privacy`. Event addresses use the canonical `https://crime.compare` origin. Titles are fixed; searches, query parameters, fragments, crime categories, individual areas and profile selections are excluded. Referrers are reduced to origins. Changing a crime filter must not create a duplicate page view; changing the broad source or geography can create one.

The essential `crimeledger-audience-choice-v1` cookie is authoritative and shared between apex and `www`. A local-storage mirror supplies immediate same-origin notifications. Active tabs check the shared cookie every second and on focus/visibility changes; background timers may be delayed. Permission must also be rechecked before manual events and after the Google tag's asynchronous load. Refusal must fail closed even when a browser cannot persist a new choice. Withdrawal must stop subsequent events and remove accessible Analytics cookies. Separate owner/test and hard-exclusion controls are provided on the [privacy page](https://crime.compare/privacy/), pending publication of that page.

The public notice must describe optional Google Analytics, its purpose, processing, retention, aggregate reporting, withdrawal and contact route. It must not retain the former unconditional claim that the site has no visitor tracking once measurement is enabled. Reports describe measurable consenting browsers and must state their coverage and limitations; they do not establish a count of unique people or advertisement delivery.

## Publication and preservation

This is an app-code release. Preserve the statistics, source manifests and successful `refresh-status.json` record; analytics publication does not require a source refresh. The scheduled public-data workflow must remain independent of Google Analytics, Google credentials and reporting exports.

The setup uses standard GA4 and the existing static Cloudflare Pages hosting. No paid Analytics upgrade, runtime service, database or recurring reporting service is required. The existing annual domain registration remains a separate cost.

Before marking this release live, record the production commit, successful CI run, Cloudflare deployment and verified hostnames. Verify no Google requests before consent or after refusal; successful collection after permission; sanitized event addresses; no duplicate filter page views; reload/expiry handling; same-origin cross-tab withdrawal; cookie removal; and mobile consent controls. Record confirmed property settings and the first complete measurement day separately from the partial deployment day.

## Reports

The property is separate from politicians.compare, so its readership remains separate. Native GA4 reports and exports use the existing Google login. The [private reporting guide](analytics-advertiser-reporting.md) explains `scripts/report_ga4_audience.py`, its read-only API route using existing credentials and its browser-export fallback. The standard-library helper creates printable HTML, Markdown, JSON and CSVs privately, with source hashes, scope and quality checks. It sends nothing to an advertiser and creates no Google credentials or recurring task. Its 23 offline reporting tests passed; no real audience report has been generated.

Creating the property does not recover historical GA4 traffic. Reporting must use the actual first complete verified measurement day and allow at least 48 elapsed hours after a selected period ends for Google processing. If deployment and verification finish on 22 October, the first full day is 23 October: a one-day provisional report is eligible on 26 October, and the first 28-day period, 23 October–19 November, on 22 November. These dates remain conditional on verified activation and collection health.
