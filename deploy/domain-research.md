# crime.compare — Cloudflare registration record

Checked 22 October 2026. `crime.compare` follows the existing `politicians.compare` naming pattern and describes the site's comparison function.

Cloudflare Registrar supports `.compare`, as shown by its [TLD policies](https://www.cloudflare.com/tld-policies/) and [official extension price list](https://pricing.registrar.cloudflare.com/). The account checkout quoted:

| Item | Cloudflare quote |
|---|---|
| One-year registration | **US$25.20** |
| Annual renewal | **US$25.20/year** |

The user explicitly approved purchasing `crime.compare` at this price and accepting the displayed registration terms. **Cloudflare confirmed successful registration on 22 October 2026:** its success page displayed “Your domain is ready” and links to the receipt and domain management. The one-year purchase was US$25.20. Domain management confirms **Active** status and expiry on **22 October 2027**. Auto-renew is enabled, currently quoted at US$25.20/year, with the next one-year renewal scheduled for **22 September 2027**. The registry RDAP record also confirms registration through Cloudflare. Account identifiers, order identifiers, registrant contacts and receipt details are not stored here.

The canonical and Open Graph hostname in the app, robots file and sitemap is prepared as `https://crime.compare/`. The current verified deployment remains [crime-compare.pages.dev](https://crime-compare.pages.dev/), release commit `9d15808`, Cloudflare deployment `5a7f9324`. [CI run 39799183022](https://github.com/shamusj-create/crime-compare/actions/runs/39799183022) passed.

Pages association and HTTPS activation are still being verified; registration success alone does not establish that the site is live at the hostname. Associate `crime.compare` through **Workers & Pages → crime-compare → Custom domains → Set up a domain** in the same Cloudflare account. Cloudflare Registrar supplies Cloudflare nameservers. Confirm the apex zone, Pages domain status and HTTPS certificate, then test the live app and source-data behaviour on the hostname. Follow the [official Pages custom-domain guide](https://developers.cloudflare.com/pages/configuration/custom-domains/).

Cloudflare Pages static hosting and standard GitHub Actions runners for the public data repository remain on their free routes. Domain registration and renewal are the separate annual purchase. This setup adds no paid runtime service, analytics or redirect service.
