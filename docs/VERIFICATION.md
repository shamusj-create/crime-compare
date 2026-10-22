# Release verification — 22 October 2026

Live app: https://crime-compare.pages.dev/
Source: https://github.com/shamusj-create/crime-compare

Verified release: commit `9d15808`, Cloudflare deployment `5a7f9324`; [CI run 39799183022](https://github.com/shamusj-create/crime-compare/actions/runs/39799183022) passed.

Cloudflare Registrar confirmed successful registration of `crime.compare` on 22 October 2026 for US$25.20 for one year. Domain management shows Active status and expiry on 22 October 2027; auto-renew is on, currently quoted at US$25.20/year and scheduled for 22 September 2027. The canonical URL, Open Graph URL, robots file and sitemap are prepared for `https://crime.compare/`. Pages association and final HTTPS verification are still in progress; registration success is not recorded as proof of a live custom hostname.

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

## Operational limits

Monthly checks run at 12:17 UTC on the fifth of each month. GitHub schedules are best effort; check failure notifications. Quarterly official releases and monthly provisional observations remain separate. GitHub public raw-file CDN propagation can delay visibility briefly. Cloudflare static serving and standard public-repository Actions use free tiers; the registered custom domain is an independent annual expense. Testing covered one browser engine and simulated sizes, not all physical devices or field performance.

## Rich force-profile update, 22 October 2026

Local browser checks confirmed that a fresh visit opens police force areas, while an explicit region selection survives reload. The official selector now contains 25 measures in three groups. Homicide displays per 100,000 and retains source-suppressed changes. Knife/firearm histories retain real dates; the firearm national reference correctly excludes BTP. Selecting a crime type in a profile updates the shareable URL and survives reload.

The monthly Dorset profile reconciles its annual total (41,899 versus 44,548, down 5.95%) and August counts (4,068 versus 3,563, up 14.17%). The grouped monthly bars, exact-figures disclosure, category navigation and full-area CSV download were exercised. Greater Manchester shows unavailable annual/monthly values and incomplete-coverage notes, with no invented zeros or trend. Desktop and 390px mobile layouts were checked, including horizontal scrolling inside data tables.

The production build, 16 Node tests, 29 Python tests and both published-snapshot validators passed. Both snapshot hashes match refresh-status; all monthly metric values remain unchanged after rebuilding their provenance against the expanded official snapshot. This update was published from commit `9d15808` in Cloudflare deployment `5a7f9324` and passed CI run `39799183022`. The custom-domain metadata update is prepared locally while Pages association and final HTTPS checks are completed.
