# Private advertiser reporting for crime.compare

The dedicated GA4 property is **560206660**, in account **368143065**; the web stream is **16182898408** for `https://crime.compare`. Its public measurement ID is `G-6DZZ4SE8DG`. Reporting uses the **numeric property ID**, not the measurement ID. [Open the source property](https://analytics.google.com/analytics/web/#/p560206660/reports/intelligenthome).

This is an on-demand reporting tool, **not an audience claim or a claim that collection is already healthy**. No historical audience is recovered by creating a property, and no real advertiser report has been generated as part of this implementation. The release record must verify consent-gated production collection before a first complete measurement day is used.

`scripts/report_ga4_audience.py` produces a private pack containing printable, self-contained HTML, Markdown, JSON, the aggregate source bundle and nine CSV tables. It uses only Python's standard library. It adds no website payload, database, recurring job, paid reporting dependency, advertising integration or reader-level export. It sends no report to an advertiser and never creates or saves Google credentials.

## Evidence in the pack

| Question | Available evidence |
| --- | --- |
| How much measured readership is there? | Page views, period Total users, period Active users, daily user/page-view means and medians, sessions |
| Is attention sustained? | Engaged sessions, engagement rate, average foreground engagement seconds per session, views per session |
| Do readers return? | GA4 new and returning users, with their possible overlap explained |
| Where is the measured audience? | Country-level session counts and shares; unknown categories stay visible |
| Which screens are used? | Device category: desktop, mobile, tablet and any unknown categories returned by GA4 |
| How do readers arrive? | Session channel group and source/medium, including search, direct, social and referrals |
| Which broad content is viewed? | Official/monthly comparison and reference-section shares, plus seven approved coarse virtual page paths |
| Can the report be checked? | Property, period, London timezone, export time, exact queries, response quality metadata, source hashes and reconciled totals |

These figures describe consenting measured browsers, not certified unique humans, crime-area interests, ad inventory or delivered advertising impressions. Views cannot establish an advertisement's viewability, clicks, campaign reach or conversions. Actual paid placements require their own delivery measurement. No arbitrary “human percentage”, uplift for declined consent, monthly extrapolation, age, gender, occupation, wealth or inferred interest is added.

## Measurement contract

The consent controller and report allowlist share these exact virtual paths and built-in `content_group` values:

| Virtual page path | Content group |
| --- | --- |
| `/official/regions` | `Official comparison` |
| `/official/forces` | `Official comparison` |
| `/monthly/regions` | `Monthly comparison` |
| `/monthly/forces` | `Monthly comparison` |
| `/method` | `Method` |
| `/sources` | `Sources` |
| `/privacy` | `Privacy` |

The physical home page maps to `/official/forces`; `/` is not an additional measured page. Switching official/monthly source or region/force geography can create a coarse page view. Crime types, individual areas, ONS codes, comparisons, searches, filters, profiles and selections are not sent. No custom interaction events are required for this pack. Referrers are reduced to their origin by the controller; query strings, fragments and referring page paths are not part of its measurement contract.

The report rejects unapproved detailed paths and query strings. An unknown GA4 page-context bucket is retained as `Unclassified` and marked for review. Section shares describe visited site sections; country reports describe the visitor-country classification returned by GA4. They do not establish residence, nationality, which local crime figures someone researched or any personal circumstances. URL sanitisation means this setup is not evidence for detailed UTM campaign attribution or advertiser conversions.

Before sharing, verify the actual production release and collection settings. The configuration recorded during setup on 22 October 2026 was Europe/London, GBP, Device-based reporting identity, 14-month user/event retention with reset on new activity off, enhanced measurement off, Google Signals and user-provided data off, advertising personalization disallowed, and Internal/Developer exclusion filters Active. Country/device-category **reporting** does not mean Google's underlying granular location/device collection is disabled; do not claim that it is. The service still receives ordinary network and browser information after consent.

## Periods and readiness

A full pack covers **28 complete Europe/London calendar days**, allowing at least **48 elapsed hours after the last day finishes** for processing. Earlier settled dates can be selected with `--start` and `--end`. The first period can be shorter, but is prominently labelled **Provisional** and never extrapolated into a monthly readership estimate.

`--measurement-start` means the first complete **verified production** measurement day. It is not the property-creation date. If collection is deployed and verified partway through 22 October 2026, use **23 October 2026**. Move the date if the actual release or verification happens later. Do not enter pre-installation or partial days as zero traffic.

Subject to that verified start and continuous collection health, the earliest settled periods are:

| Period | Earliest eligibility with the 48-hour allowance |
| --- | --- |
| One day: 23 October | 26 October 2026 |
| Three days: 23–25 October | 28 October 2026 |
| Full 28 days: 23 October–19 November | 22 November 2026 |

These are processing eligibility dates, not promises of usable audience data. Actual elapsed time across UK clock changes is used. If processing or quality issues persist, wait and re-query. A zero-audience report is flagged for investigation.

The tool rejects wrong hostname/timezone filters, dates before measurement, immature exports, future dates, malformed values, duplicate rows, incomplete pagination, unexpected fields/reports and page-view totals that fail reconciliation. Sampling, privacy thresholds, `(other)` grouping, truncation, metric restrictions, unknown content groups and inconsistent session breakdowns are disclosed in the HTML and JSON. Missing GA4 daily rows are shown as zero **recorded** activity and listed explicitly; that does not establish whether collection worked on those days.

## Read-only API workflow

The default property ID is `560206660`; `--property-id` or the non-secret `CRIME_GA4_PROPERTY_ID` environment variable can override it. The report always filters hostname exactly to `crime.compare`. `--measurement-start` remains explicit so the operator must use the verified release day.

The Google user needs property Viewer access or greater, an enabled Analytics Data API project and the `analytics.readonly` OAuth scope. An existing browser login does not grant the script an OAuth token. The helper does not provision accounts, keys or credentials. Google's [user-account quickstart](https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart) describes authentication.

With existing local Application Default Credentials, and only after the period is ready:

```sh
python3 scripts/report_ga4_audience.py --fetch --property-id 560206660 --measurement-start 2026-10-23 --use-adc --output-dir /private/path/new-advertiser-report
```

`--use-adc` captures `gcloud auth application-default print-access-token` privately. Alternatively, supply an existing short-lived OAuth access token securely through `GA4_ACCESS_TOKEN` (or choose its variable name with `--access-token-env`). Never put a token in a command argument, chat, repository, report manifest or checked-in `.env`. The optional `GA4_QUOTA_PROJECT` variable is a non-secret Google Cloud project ID for a required quota header.

Ten small aggregate reports are queried, with bounded pagination and one retry for temporary API errors. Credentials and HTTP error bodies are not printed or saved. Missing authentication or access stops generation. No BigQuery export, paid dependency or advertising connection is used.

The output directory must be new and outside this website and every Git checkout. The directory is private (`0700`), with private files (`0600`), and existing packs are never overwritten. Outputs are:

- `audience-report.html`, suitable for browser printing or Save as PDF; it loads no scripts, trackers or external assets.
- `audience-report.md` and `audience-report.json`.
- `source-bundle.json`, containing only aggregate source reports, scope, timestamps and quality metadata.
- `summary.csv`, `daily.csv`, `sections.csv`, `countries.csv`, `devices.csv`, `channels.csv`, `sources.csv`, `landing_pages.csv` and `pages.csv`, when their respective tables have rows.

The report's SHA-256 matches the exact saved `source-bundle.json` bytes. Treat that as a provenance check, rather than independent audience certification. Review the chosen report files privately before sharing; keep credentials, original exports and the source bundle private. CSV text beginning with formula tokens is protected for spreadsheet opening, and HTML labels are escaped.

To reproduce a saved pack without calling Google:

```sh
python3 scripts/report_ga4_audience.py --bundle /private/path/original-report/source-bundle.json --output-dir /private/path/new-reviewed-report
```

## Browser-export fallback without API credentials

The existing [Google Analytics browser](https://analytics.google.com/analytics/web/#/p560206660/reports/intelligenthome) can export reports independently of local OAuth. Select property **560206660**, identical dates and an exact **Hostname = crime.compare** filter for every export. Preserve original exports and source report links/screenshots privately. Check GA4's quality indicators, sampling, privacy thresholds and export row limits. Use an undimensioned whole-period report for distinct users; never sum daily or page users to obtain reach.

Prepare normalized private CSV copies using these exact columns, in order. Case, spaces, underscores and hyphens in headers are ignored; rename UI labels such as `Views` to the API names shown. Leading `#` metadata lines are accepted. Values must be non-negative numbers; `daily.csv` dates use `YYYY-MM-DD`. Preserve unknown buckets and all rows. Where a standard browser report does not offer the required combination, use a GA4 Exploration with the corresponding dimensions and metrics.

| File | Required columns |
| --- | --- |
| `overview.csv` | `screenPageViews,totalUsers,activeUsers,newUsers,sessions,engagedSessions,userEngagementDuration` — one row for the whole period |
| `daily.csv` | `date,screenPageViews,totalUsers,activeUsers,newUsers,sessions,engagedSessions,userEngagementDuration` |
| `countries.csv` | `country,totalUsers,sessions,engagedSessions,userEngagementDuration` |
| `devices.csv` | `deviceCategory,totalUsers,sessions,engagedSessions,userEngagementDuration` |
| `channels.csv` | `sessionDefaultChannelGroup,totalUsers,sessions,engagedSessions,userEngagementDuration` |
| `sources.csv` | `sessionSourceMedium,totalUsers,sessions,engagedSessions,userEngagementDuration` |
| `landing_pages.csv` | `landingPage,totalUsers,sessions,engagedSessions,userEngagementDuration` |
| `pages.csv` | `pagePath,screenPageViews,totalUsers` |
| `content_groups.csv` | `contentGroup,screenPageViews,totalUsers` |
| `returning.csv` | `newVsReturning,totalUsers` — preserve `new`, `returning` and unknown rows as exported |

Create a private manifest alongside the CSVs. This is a **schema example, not an audience observation**. Its dates assume a verified first full day of 23 October; replace them if the release differs. Quality booleans must reflect checks actually performed, not values copied unquestioningly:

```json
{
  "property_id": "560206660",
  "property_timezone": "Europe/London",
  "hostname_filter": "crime.compare",
  "measurement_start": "2026-10-23",
  "report_start": "2026-10-23",
  "report_end": "2026-11-19",
  "exported_at": "2026-11-22T10:00:00+00:00",
  "manual_quality_review": {
    "sampling": false,
    "thresholding": false,
    "other_row": false,
    "row_limit": false,
    "scope_and_filters_checked": true
  }
}
```

```sh
python3 scripts/report_ga4_audience.py --csv-directory /private/path/ga4-exports --manifest /private/path/ga4-exports/manifest.json --output-dir /private/path/new-advertiser-report
```

The result explicitly identifies manually exported CSVs; their normalized envelope is not represented as a direct API response. The pack records hashes of every normalized CSV and its manifest. No fake audience figures or historical backfill are provided.

## Definitions and review

**Total users** is queried once for the entire period and reflects GA4's reporting identity and estimation. Daily mean users are a different measure. User rows by country, device, page and new/returning status can overlap; adding them does not produce distinct readers. A visitor may be new and return within the same period.

**Engagement rate** is total engaged sessions divided by total sessions. **Average engagement seconds per session** is total `userEngagementDuration` divided by sessions. Ratios are computed from period totals, rather than averages of daily averages. Undefined ratios remain unavailable. Foreground engagement time is not time viewing an advertisement.

Country, device and source shares use sessions; broad-content shares use page views. GA4 excludes known bots, but remaining activity is not certified human traffic. Declined consent, blockers, measurement gaps, internal testing and unknown bots can affect the figures. No acceptance rate or total unmeasured audience is inferred from consenting-browser data.

Every generated pack is a **private draft pending review**, even if its data-quality status is `standard`. Before external use, verify collection health throughout the period, consent coverage, active exclusion filters, unusual referral spikes, quality flags, source totals and any setting changes. Share selected aggregate files, rather than reader histories, credentials or access to unrelated properties. This tool does not authorize an advertising claim or send anything externally.

The implementation follows Google's [dimensions and metrics](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema), [`runReport` contract](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport) and [response quality metadata](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData). Its API dimensions do not request city, age, gender, page titles, query strings, referring page URLs, search terms, user IDs or event-level records.

Verification is offline and uses synthetic test fixtures only:

```sh
python3 -m unittest discover -s scripts -p 'test_report_ga4_audience.py' -v
```
