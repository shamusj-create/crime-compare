# CrimeLedger

A static crime comparison website using official public data. The first edition compares police force areas in England and Wales, with recorded counts, population rates, offence categories and historical trends. It labels the period covered separately from the date the sources were checked.

The site is designed for free static hosting on Cloudflare Pages. A public GitHub repository runs a monthly source check through GitHub Actions. The hosted app reads validated static JSON from that repository, with packaged data as a fallback. Monthly data updates need no Cloudflare token or redeployment. There is no paid data API, database or server.

Police force areas are the default comparison; an explicit region selection is preserved in the URL. Clicking a row opens its profile, with annual counts and changes, rate rank, regional/national references, exact rolling-year history, a full crime-type breakdown, coverage and source notes, and a CSV of every available observation. Crime choices inside a profile are shareable in the URL.

The official series has 25 measures, including homicide, stalking and harassment, burglary subtypes, knife-enabled crime and firearm offences. Grouped selectors distinguish main groups, detailed components and weapon collections, which overlap and must not be added together. Rare measures display per 100,000 residents; other measures display per 1,000. ONS-suppressed percentage changes stay unavailable. The monthly series retains its 14 Police.uk categories and adds a paired month-by-month view of the latest year against the same calendar months one year earlier. All 24 raw monthly counts remain in the profile CSV. These views use the existing source files and static JSON; they add no runtime services or refresh dependencies.

## Run locally

Use Node.js 22 and Python 3.12 or newer.

```bash
npm ci
npm run dev
```

For the production build:

```bash
npm run typecheck
npm test
npm run build
npm run preview
```

## Update the statistics

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/requirements.txt
python scripts/refresh_data.py
python scripts/refresh_monthly.py
npm run build
```

The official-statistics refresh writes `public/data/crime.json` and `public/data/source-manifest.json`; the monthly reader writes `public/data/monthly.json` and `public/data/monthly-manifest.json`. The workflow publishes the complete set only after both refreshes, data validation, tests and the build pass. Source URLs, publication dates and hashes are retained with the data. An unchanged source snapshot produces no rewritten statistics.

The workflow in [`.github/workflows/refresh-data.yml`](.github/workflows/refresh-data.yml) runs at 12:17 UTC on the 5th of each month and can also be started manually. It records successful check status in a separate `refresh-status.json`, runs the app checks and commits only changed public data files. Cloudflare credentials are optional and used only when a manual run explicitly requests app-code publication.

**The two data layers have different meanings.** The official quarterly England and Wales series supports the main comparisons. The monthly police.uk layer provides more recent provisional management data and its own coverage notes. New observations appear when their publisher releases them; source revisions can change earlier values. Scottish and Northern Irish sources have different publication schedules and definitions, so they should be added with their own clearly labelled coverage rather than silently merged into a UK league table.

## Free hosting and domain

The application is live at [crime.compare](https://crime.compare/) and [www.crime.compare](https://www.crime.compare/) from the public [crime-compare repository](https://github.com/shamusj-create/crime-compare). The verified metadata release is commit `17f803a`, Cloudflare deployment `ca0865e4`; [CI run 39803909722](https://github.com/shamusj-create/crime-compare/actions/runs/39803909722) passed. HTTPS, HTML, assets, dataset hashes, robots and sitemap were checked against the build. See the [verification record](docs/VERIFICATION.md).

The canonical hostname is `https://crime.compare/`. Both apex and `www` serve the verified app over HTTPS with the apex canonical URL. **Cloudflare Registrar registration succeeded on 22 October 2026 for US$25.20 for one year, expiring 22 October 2027.** Auto-renew is enabled, currently quoted at US$25.20/year. Domain registration is a separate annual expense from free static hosting. See the [domain record](deploy/domain-research.md).

The [Cloudflare setup guide](deploy/cloudflare-pages.md) describes this deployment and monthly public-data updates. The default update route uses only GitHub's built-in repository token and needs no Cloudflare secret. The guide also covers optional automated code deployments.

## Optional audience measurement

A separate crime.compare GA4 property, consent controller and public privacy notice are deployed in release `a7ff826`, Cloudflare deployment `77451b43`; [CI run 39810368507](https://github.com/shamusj-create/crime-compare/actions/runs/39810368507) passed. Live checks found no Google requests before consent or after refusal and reload. **The operator's live opt-in collection test is pending; collection health and the first full measurement day are not yet verified.** The [measurement release record](docs/ga4-measurement-release-2026-10-22.md) tracks the evidence.

The owner can open the saved [Advertiser audience overview](https://analytics.google.com/analytics/web/#/a368143065p560206660/reports/reportinghub) using their existing Google access. The [private reporting guide](docs/analytics-advertiser-reporting.md) explains on-demand printable reports and spreadsheet exports once collection is verified and the period has settled.

Collection requires prior opt-in, offers refusal and withdrawal, and removes URL searches and selections from reported page addresses. It uses standard GA4 with the existing static hosting, without a paid upgrade or extra runtime service. Analytics does not collect crime statistics or participate in the monthly source refresh. This release preserved every existing public data file and successful source-check record.

## Data and interpretation

Police recorded crime measures offences recorded by police. Reporting behaviour, recording practices, legal changes and police activity affect the figures. The values do not measure every crime that happened, individual risk or police effectiveness. Population rates help compare differently sized areas; resident population does not fully capture commuters, tourists or local footfall.

Official data are attributed in the interface and source manifest. Reused government statistics remain subject to the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Do not infer a licence for this application's source code from the data licence.
