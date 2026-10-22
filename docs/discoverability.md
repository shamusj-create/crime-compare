# Static discovery pages

Crime.compare's discovery pages present readable HTML from the same validated public data used by the comparison app. They do not require JavaScript to read the tables, definitions, source links or navigation. Search inclusion and ranking remain decisions made by search services; these pages do not establish that the site has been indexed.

## Scope

The bounded discovery set contains **84 canonical URLs**:

- The homepage and existing privacy notice.
- `/areas/` and 53 `/areas/{ONS-code}/` profiles: 43 police force areas and nine English regions plus Wales.
- `/crime/` and 25 `/crime/{category-id}/` official category comparisons.
- `/methodology/` and `/sources/`.

One area profile provides its crime measures together; one category comparison provides the relevant force and regional tables. Search strings, filters, sorting, area/category combinations, comparison selections and dates do not create additional discovery pages. These are England and Wales comparisons, rather than coverage of all UK nations or every local authority.

The official snapshot currently compares July 2025–June 2026, published on 22 October 2026. Its population denominators, per-1,000 or per-100,000 display units, suppressed annual changes, overlapping categories and area-specific limitations must remain visible. City of London's count is available, but its resident-based rate is unsuitable for ranking. The official national reference includes British Transport Police for most measures; firearms excludes it. Regional and force comparisons exclude BTP.

The app also offers a distinct provisional Police.uk monthly layer. Its categories, reporting coverage and observation periods differ from the official dataset. Monthly gaps must not become zero, and official figures must not be presented as monthly observations. Discovery pages use the stated official snapshot and link to the interactive comparisons for the separately labelled monthly layer. A future source release may revise historical values.

## Metadata and provenance

Each discovery page has its own initial title, description, canonical URL, Open Graph/Twitter sharing metadata and structured data. Canonical addresses use `https://crime.compare/` with the generated route, without queries or fragments. The social card is the local 1,200 × 630 PNG at `/social-card.png`. Structured data describes the page, breadcrumbs and supported public facts; it does not add reviews, ratings, personal-risk estimates or an overall safety score.

`discovery-manifest.json` binds the canonical page set, page paths, titles, descriptions, semantic content hashes and meaningful modification dates. The sitemap contains the same canonical URLs and dates. Page snapshot markers identify the comparison period. The semantic hash excludes routine source-check timestamps; a successful monthly check with unchanged figures does not create a new observation period or pretend every page's substance changed.

Visible tables and structured data must describe the same snapshot. A checked-at timestamp, source publication date, comparison start/end and population reference year have different meanings. Keep those dates separate. Source links and the public source manifests allow readers to trace the derived comparison back to the official release. Map attribution remains separate from the crime-data licence.

## Build and monthly publication

`scripts/build_discovery_pages.py` generates the pages after Vite builds the app and validates them against the committed semantic manifest. Its offline `validate(output, public_dir)` function checks the candidate directory without making network requests. After an intentional source-data or page-copy change, refresh the manifest and build:

```sh
python3 scripts/build_discovery_pages.py --write-manifest
npm run build
python3 scripts/build_discovery_pages.py --check --output dist
```

The monthly workflow first retrieves and validates the official and Police.uk sources, records their real source-check status and runs the existing tests. Discovery generation must use those exact local snapshots. Publication must upload the resulting verified static directory in the **same workflow run**. A GitHub data commit on its own cannot update HTML or the sitemap already hosted on Cloudflare.

The existing app's raw-GitHub JSON refresh and packaged fallback continue to work. Static discovery snapshots require Cloudflare publication as well. During a failed deployment, the preceding static pages remain explicitly dated; a newer interactive remote snapshot does not change the period printed in older static HTML.

**Release status:** this guide describes the candidate implementation. A production deployment, successful live discovery checks and working scheduled static publication must be recorded separately before calling those outcomes verified. At the time this draft was prepared, the deployment credential and scheduled publication configuration were being finalized. See the maintained [deployment guide](../deploy/cloudflare-pages.md) for the final configuration and release evidence. Do not copy a credential into this guide, source files, reports or browser assets.

This route uses static builds, the existing free-hosting pipeline and a dedicated deployment credential; it adds no paid search, rendering or reporting service. Scheduled runs are best effort. Keep workflow failure notifications enabled and inspect missed or failed source/publication checks.

## Verification

The generator's offline checks validate all generated pages. The live verifier then reconciles the public responses with that verified directory:

```sh
python3 -m unittest discover -s scripts -p 'test_discovery_live.py' -v
python3 scripts/verify_discovery_live.py --site-dir dist
python3 scripts/verify_discovery_live.py --site-dir dist --all
```

The default live check covers the homepage, both directories, an area profile, a category comparison, methodology, sources and privacy. `--all` checks every manifest/sitemap HTML page. It compares the public manifest bytes, sitemap URLs/dates, title, canonical, metadata, parsed JSON-LD, visible initial text, snapshot markers, links and scripts. It also verifies the exact social-card bytes and PNG dimensions. Wrong content types, unexpected redirects, altered figures, unsafe executable markup and production indexing blocks fail verification. Sitemap XML may differ in insignificant whitespace.

Cloudflare's email protection can rewrite contact links and add its same-origin decoder script. The verifier decodes and compares the protected address and mailto target; it does not ignore contact content or accept arbitrary injected scripts. Full HTML byte checks are intentionally avoided for this transform.

To inspect an exact deployment before production:

```sh
python3 scripts/verify_discovery_live.py --site-dir dist --origin https://DEPLOYMENT.crime-compare.pages.dev --all
```

`--origin` aliases `--base-url`; `--output` aliases `--site-dir`. Preview canonical metadata must still point to crime.compare. Cloudflare may correctly add a preview-only `X-Robots-Tag: noindex`; that response header is allowed on Pages preview origins, while noindex in the built HTML is rejected everywhere. Run production verification separately after publication. The verifier makes ordinary read-only HTTP requests, executes no scripts and sends no analytics events.

## Analytics and reporting scope

New area/category/directory/reference discovery paths are deliberately **untracked** by the existing GA4 controller. The controller's seven approved coarse virtual paths remain unchanged; detailed physical area or crime URLs must not be added as GA4 page locations, page titles or custom parameters. A reader who follows a link into the existing app is subject to the app's normal consent choices.

Consequently, the [private advertiser reporting pack](analytics-advertiser-reporting.md) measures consenting activity within that existing contract; it is not a count of all visits to these discovery pages. Do not silently treat unmeasured discovery traffic as zero audience, infer consent acceptance, or extrapolate the measured subset into total readership. Any later change to measurement coverage requires explicit review of the controller, privacy notice, reporting allowlist and release record.
