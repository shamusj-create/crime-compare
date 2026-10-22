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

Follow [the Cloudflare setup guide](deploy/cloudflare-pages.md) to create a dedicated Pages project and enable monthly public-data updates. The default update route uses only GitHub's built-in repository token and needs no Cloudflare secret. The guide also describes optional automated code deployments.

The site can use the included free `*.pages.dev` address. A custom domain is a separate annual purchase. On 22 October 2026, a live registrar check showed **crime.compare available for US$26.26 for one year, renewing at US$26.26/year**, before any applicable checkout tax or currency conversion. Availability and prices can change. No domain has been bought. See the [domain research record](deploy/domain-research.md).

## Data and interpretation

Police recorded crime measures offences recorded by police. Reporting behaviour, recording practices, legal changes and police activity affect the figures. The values do not measure every crime that happened, individual risk or police effectiveness. Population rates help compare differently sized areas; resident population does not fully capture commuters, tourists or local footfall.

Official data are attributed in the interface and source manifest. Reused government statistics remain subject to the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Do not infer a licence for this application's source code from the data licence.
