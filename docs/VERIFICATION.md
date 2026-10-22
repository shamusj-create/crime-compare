# Release verification — 22 October 2026

Live app: https://crime-compare.pages.dev/
Source: https://github.com/shamusj-create/crime-compare

## Verified behaviour

- Official quarterly data: 43 forces, 10 regional units, national reference and 12 crime categories; counts reconciled with current ONS and revised Home Office tables; exact ONS population denominators.
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
- Four comparison-model/CSV tests passed.
- Nineteen Python ingestion and integrity tests passed.
- Workflow syntax passed actionlint. Shell and embedded Python syntax checked.
- GitHub app verification succeeded: https://github.com/shamusj-create/crime-compare/actions/runs/39788834819
- Full live refresh succeeded: https://github.com/shamusj-create/crime-compare/actions/runs/39788999483
- The live refresh used the built-in repository token only, published one validated data commit and skipped optional Cloudflare code upload.

## Operational limits

Monthly checks run at 12:17 UTC on the fifth of each month. GitHub schedules are best effort; check failure notifications. Quarterly official releases and monthly provisional observations remain separate. GitHub public raw-file CDN propagation can delay visibility briefly. Cloudflare static serving and standard public-repository Actions use free tiers; a custom domain is an independent annual expense. No domain was purchased. Testing covered one browser engine and simulated sizes, not all physical devices or field performance.
