# Release verification — 22 October 2026

Live app: https://crime.compare/
Source: https://github.com/shamusj-create/crime-compare

Verified metadata release: commit `17f803aeb95b6c34fe657532ca784d1456ef9bc7`, Cloudflare deployment `ca0865e4`; [CI run 39803909722](https://github.com/shamusj-create/crime-compare/actions/runs/39803909722) passed. The preceding rich-profile release `9d15808`, deployment `5a7f9324`, passed [CI run 39799183022](https://github.com/shamusj-create/crime-compare/actions/runs/39799183022).

Cloudflare Registrar confirmed registration of `crime.compare` on 22 October 2026 for US$25.20 for one year. Domain management shows Active status and expiry on 22 October 2027; auto-renew is on, currently quoted at US$25.20/year and scheduled for 22 September 2027. Pages reports the apex Active with SSL enabled. Independent HTTPS checks matched HTML, assets, datasets, status hashes, robots and sitemap to the deployed build. Browser verification at the apex confirmed 25 official categories, the default force view, remote data without fallback and the correct canonical URL. `www.crime.compare` independently returned HTTPS 200 over trusted TLS 1.3, with byte-identical built HTML and the apex canonical URL. Both HTTP hosts return 301 to their corresponding HTTPS host, preserving query strings.

## Verified behaviour

- Official quarterly data: 43 forces, 10 regional units, national reference and 25 crime measures; counts reconciled with current ONS and revised Home Office tables; exact ONS population denominators. Rare measures display per 100,000 residents; others display per 1,000. Parent groups, components and weapon collections overlap and are labelled accordingly.
- Actual monthly mapping data through August 2026. Missing force submissions suppress affected rolling-year comparisons, including their regional aggregates. City of London resident-rate ranking suppressed.
- Real ONS mini maps and interactive context map. Blue highlights match the politicians.compare visual family.
- Browser testing through the Codex in-app Chromium browser, at 1280×720, 768×1024 and 390×844. Inspected masthead, serif typography, palette/rules, controls, map silhouettes, row alignment, mobile wrapping, dialogs and visible focus. No horizontal body overflow or broken map assets observed.
- Geography/source/measure/category switching, missing-data detail, search/empty/reset state, Wales filtering, ascending rates, area detail and side-by-side comparisons work.
- Live CSV downloaded and parsed: four Welsh forces, correct dates and explicit monthly source provenance. Citation copy confirmed in the live app.
- Escape dismisses native dialogs. Focus outline visible on mobile search. Reduced-motion CSS disables smooth scrolling/transitions.
- Public raw GitHub data returned HTTP 200 with CORS allowed; both snapshot SHA-256 values matched check status. Production app loaded remote data without a fallback notice.
- Packaged-data fallback tested at a local preview with an unavailable online source. Area comparisons remained usable and the app explicitly labelled the packaged record and its source-check date.
- Live Cloudflare bundled JSON compared byte-for-byte against the build for crime, monthly, refresh-status and geography.

## Checks

- TypeScript and Vite production build passed.
- Sixteen Node comparison/profile/CSV tests passed.
- Twenty-nine Python ingestion and integrity tests passed.
- Workflow syntax passed actionlint. Shell and embedded Python syntax checked.
- GitHub app verification succeeded: https://github.com/shamusj-create/crime-compare/actions/runs/39788834819
- Full live refresh succeeded: https://github.com/shamusj-create/crime-compare/actions/runs/39788999483
- The live refresh used the built-in repository token only, published one validated data commit and skipped optional Cloudflare code upload.
- The rich-profile release passed CI: https://github.com/shamusj-create/crime-compare/actions/runs/39799183022
- The deployed metadata release passed CI: https://github.com/shamusj-create/crime-compare/actions/runs/39803909722

## Operational limits

Monthly checks run at 12:17 UTC on the fifth of each month. GitHub schedules are best effort; check failure notifications. Quarterly official releases and monthly provisional observations remain separate. GitHub public raw-file CDN propagation can delay visibility briefly. Cloudflare static serving and standard public-repository Actions use free tiers; the registered custom domain is an independent annual expense. Testing covered one browser engine and simulated sizes, not all physical devices or field performance.

## Rich force-profile update, 22 October 2026

Local browser checks confirmed that a fresh visit opens police force areas, while an explicit region selection survives reload. The official selector now contains 25 measures in three groups. Homicide displays per 100,000 and retains source-suppressed changes. Knife/firearm histories retain real dates; the firearm national reference correctly excludes BTP. Selecting a crime type in a profile updates the shareable URL and survives reload.

The monthly Dorset profile reconciles its annual total (41,899 versus 44,548, down 5.95%) and August counts (4,068 versus 3,563, up 14.17%). The grouped monthly bars, exact-figures disclosure, category navigation and full-area CSV download were exercised. Greater Manchester shows unavailable annual/monthly values and incomplete-coverage notes, with no invented zeros or trend. Desktop and 390px mobile layouts were checked, including horizontal scrolling inside data tables.

The production build, 16 Node tests, 29 Python tests and both published-snapshot validators passed. Both snapshot hashes match refresh-status; all monthly metric values remain unchanged after rebuilding their provenance against the expanded official snapshot. The rich-profile update was published from commit `9d15808` in deployment `5a7f9324` and passed CI run `39799183022`. Custom-domain metadata was subsequently deployed in commit `17f803a`, deployment `ca0865e4`, and verified over HTTPS at `crime.compare`.

## Optional GA4 release, 22 October 2026

The consent controller and public privacy notice were deployed from commit `a7ff826` in Cloudflare deployment `77451b43`; [CI run 39810368507](https://github.com/shamusj-create/crime-compare/actions/runs/39810368507) passed. The dedicated crime.compare property is `560206660`, measurement ID `G-6DZZ4SE8DG`. Settings and reporting links are in the [measurement release record](ga4-measurement-release-2026-10-22.md).

Live checks found no Google requests before consent or after **No thanks** and reload. The owner/test marker was set before acceptance; `www` observed the shared declined choice and marker. The 390 × 844 prompt fitted without horizontal overflow, with equally sized 42-pixel buttons. Desktop proof is `artifacts/analytics-2026-10-22/consent-desktop.jpg`. Twelve controller lifecycle/privacy tests passed, covering sanitized defaults, withdrawal, expiry, shared-host changes and failed-storage reloads.

Scripts, public configuration, datasets, manifests and status matched the build. The privacy HTML differs only through Cloudflare's expected email-protection substitutions and same-origin decoding script. A comparison of `17f803a` and `a7ff826` found no changed files under `public/data`; the statistics and monthly-refresh record were preserved. No paid upgrade or additional runtime service was added.

The first opt-in test failed its activation gate because Enhanced Measurement was still enabled remotely and emitted automatic history views. The individual interactions, advanced history setting and master switch were disabled and saved; a full settings reload confirmed the correction. The controller code was unchanged. Fresh cache-disabled tests then verified tag 200/collection 204, canonical manual-only page addresses, no extra view after crime/search/profile changes and a 12-second flush, and exactly the expected two views for official-source/region switching. A fresh `www` privacy visit collected only canonical `/privacy` with owner/test flags. Withdrawal through `www` declined both hosts, cleared their accessible GA cookies and stopped later Google requests.

Final delayed monitoring for more than 10 seconds found zero Google requests on both hosts, and reloading the declined apex also produced zero. The setup browser was left owner/test marked and hard excluded; cache overrides were restored. Local evidence is in ignored `artifacts/analytics-2026-10-22/collection-verification.json`, `verified-browser-excluded.jpg` and `enhanced-measurement-off.jpg`.

**The first complete verified measurement day is 23 October 2026.** These tests establish initial transport, sanitization and consent behaviour; ongoing collection health must be checked for every reporting period. No real advertiser report or historical audience claim has been generated.
