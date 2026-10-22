# Domain check — 22 October 2026

**Preferred name: `crime.compare`.** It directly describes the site and matches the existing `politicians.compare` naming pattern.

A live [Porkbun registrar search for crime.compare](https://porkbun.com/checkout/search?q=crime.compare), checked on 22 October 2026, displayed an available **Add to cart** result with:

| Item | Quoted price |
|---|---|
| One-year registration | **US$26.26** |
| Annual renewal | **US$26.26/year** |

The result was labelled “At Cost”, with no premium-name surcharge shown. These are the displayed USD prices, before any applicable checkout tax or currency conversion. Recheck both registration and renewal in the registrar's final quote. No cart, registration, purchase, DNS or account change was made.

The registry's [RDAP endpoint for crime.compare](https://rdap.nic.compare/domain/crime.compare) returned HTTP 404 (no registration record). The `.compare` endpoint was discovered from [IANA's RDAP bootstrap](https://data.iana.org/rdap/dns.json). RDAP alone does not prove a name is registrable: names can be reserved or premium, so the live registrar result is the stronger availability/price check.

Other plausible names returned no registration record from the same registry lookup:

| Candidate | Check result |
|---|---|
| `ukcrime.compare` | No RDAP record; registrar availability/price not separately checked |
| `crimes.compare` | No RDAP record; registrar availability/price not separately checked |
| `safer.compare` | No RDAP record; registrar availability/price not separately checked |
| `crimeuk.compare` | No RDAP record; registrar availability/price not separately checked |

These are alternatives if the preferred name changes availability. `safer.compare` is less literal and may imply an overall safety judgement beyond police recorded crime, so `crime.compare` is the clearer product name.

Cloudflare Pages hosting can remain free. Domain registration and renewal are a separate recurring purchase; the free `*.pages.dev` hostname works without one. No domain has been reserved for this project.
