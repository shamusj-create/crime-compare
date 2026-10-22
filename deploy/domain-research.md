# crime.compare — Cloudflare registration record

Checked 22 October 2026. `crime.compare` follows the existing `politicians.compare` naming pattern and describes the site's comparison function.

Cloudflare Registrar supports `.compare`, as shown by its [TLD policies](https://www.cloudflare.com/tld-policies/) and [official extension price list](https://pricing.registrar.cloudflare.com/). The account checkout quoted:

| Item | Cloudflare quote |
|---|---|
| One-year registration | **US$25.20** |
| Annual renewal | **US$25.20/year** |

The user explicitly approved purchasing `crime.compare` at this price and accepting the displayed registration terms. **Cloudflare confirmed successful registration on 22 October 2026:** its success page displayed “Your domain is ready” and links to the receipt and domain management. The one-year purchase was US$25.20. Domain management confirms **Active** status and expiry on **22 October 2027**. Auto-renew is enabled, currently quoted at US$25.20/year, with the next one-year renewal scheduled for **22 September 2027**. The registry RDAP record also confirms registration through Cloudflare. Account identifiers, order identifiers, registrant contacts and receipt details are not stored here.

The app is live at [crime.compare](https://crime.compare/). Canonical and Open Graph metadata, robots and sitemap are deployed for that hostname in commit `17f803aeb95b6c34fe657532ca784d1456ef9bc7`, Cloudflare deployment `ca0865e4`; [CI run 39803909722](https://github.com/shamusj-create/crime-compare/actions/runs/39803909722) passed. Cloudflare reports Active status with SSL enabled; independent HTTPS checks matched HTML, assets, datasets, status hashes, robots and sitemap to the build. Browser verification confirmed 25 official categories, the default police-force view and remote data without fallback.

The approved [www.crime.compare](https://www.crime.compare/) hostname is also verified: HTTPS returns 200 over trusted TLS 1.3, its HTML matches the deployed build byte-for-byte, and its canonical URL is `https://crime.compare/`. It serves the same app. Both HTTP hosts return 301 to their corresponding HTTPS host while preserving query strings. Follow the [official Pages custom-domain guide](https://developers.cloudflare.com/pages/configuration/custom-domains/) for domain-management steps.

Cloudflare Pages static hosting and standard GitHub Actions runners for the public data repository remain on their free routes. Domain registration and renewal are the separate annual purchase. This setup adds no paid runtime service, analytics or redirect service.
