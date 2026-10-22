# Free Cloudflare Pages setup

Cloudflare Pages serves the static application. A dedicated public GitHub repository holds the app and its validated JSON snapshots. The hosted app fetches those public static files and falls back to the data packaged with its last code deployment if the remote snapshot is unavailable or fails integrity checks.

The scheduled GitHub workflow updates the repository's data. **Monthly data publication needs no Cloudflare secret, GitHub app installation or code redeployment.** App-code releases are a separate operation.

## Costs and limits

| Component | Default setup |
|---|---|
| Static application | Cloudflare Pages Free plan |
| Public data snapshots | Static files in the public GitHub repository |
| Monthly source collection | Standard GitHub-hosted Ubuntu runner in the public repository |
| Scheduled deployment credentials | None; the workflow uses its built-in repository token |
| Database, paid API or runtime server | None |
| Hostname | Free `*.pages.dev`; a custom domain is an optional annual purchase |

Cloudflare lists unlimited static requests/bandwidth, 500 builds per month, one concurrent build, 20,000 files per site and 25 MiB per file. The application uses no Pages Functions, Workers, database or storage service. See [Pages pricing](https://www.cloudflare.com/developer-platform/products/pages/) and [current limits](https://developers.cloudflare.com/pages/platform/limits/).

GitHub [does not charge for standard hosted runners in public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). This workflow uses `ubuntu-latest`, no larger runners and no uploaded workflow artifacts. Private repositories have an included quota and can incur charges beyond it. Keep this data repository public for the documented free route and browser access to its raw JSON.

GitHub's public file service is an external dependency. The app's bundled fallback keeps the site usable when it is unavailable and must be presented as the fallback snapshot, with its own actual dates. CDN propagation can delay the appearance of a new data commit. Free plans and their limits can change; this configuration enables no paid subscription.

## 1. Create the publication repository

Create a dedicated public GitHub repository named `shamusj-create/crime-compare`, with default branch `main`, and push this project. Include the source, lockfile, generated `public/data/` JSON, `scripts/`, `.github/` and static map assets. Keep local environments, source download caches, `node_modules/`, `dist/` and credentials out of Git.

The workflow must exist on the default branch. It uses `GITHUB_TOKEN` with `contents: write` only in its publication job. Repository or organisation rules must allow that job to push its data commit. If every commit requires a pull request, arrange an approved bot publication path before enabling automatic refresh; do not weaken unrelated protections to make the job pass.

The data base URL is:

```text
https://raw.githubusercontent.com/shamusj-create/crime-compare/main/public/data
```

If the owner, repository or branch changes, rebuild the application with the corresponding URL.

## 2. Build the application against public static data

After reviewing the source snapshots, run:

```bash
npm ci
npm run typecheck
npm test
VITE_DATA_BASE_URL=https://raw.githubusercontent.com/shamusj-create/crime-compare/main/public/data npm run build
```

`VITE_DATA_BASE_URL` is a public build setting, not a credential. The `dist/` directory contains the app plus bundled fallback data. The monthly workflow builds against its own repository/default-branch URL automatically.

Check that the public raw JSON URLs work without sign-in and that browser requests can read them. Test the app with the source reachable and unavailable: successful remote data must match the hashes in its refresh status; fallback data must retain their real observation dates.

## 3. Create and upload to a dedicated Pages project

Use a Cloudflare account on the Free plan. In **Workers & Pages**, create a **Pages / Direct Upload** project named `crime-compare` (or another available name), with production branch `main`. Upload the verified `dist/` directory.

Alternatively, use Cloudflare's official Wrangler CLI with the operator's existing interactive login:

```bash
npx wrangler@4.136.3 login
npx wrangler@4.136.3 pages project create crime-compare --production-branch main --force
npx wrangler@4.136.3 pages deploy dist --project-name crime-compare --branch main
```

The committed `wrangler.jsonc` points to `dist/` and contains no account identifier or secret. Change its `name` if you choose a different project name.

The `--force` flag on initial project creation selects the existing Pages platform when Wrangler otherwise delegates a new project to Workers. It is only for creation; the normal upload command above needs no such flag. This is a Direct Upload project: no Cloudflare GitHub integration is needed. Cloudflare documents that it cannot later be converted into a Git-integrated project; a new project would be required. See [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/).

Verify the Pages production address, interface, source periods, raw source links and remote-data/fallback behaviour. Code releases require another static upload; monthly data commits are consumed by the existing application.

## 4. Enable and verify monthly updates

In GitHub **Actions → Refresh public crime data → Run workflow**, select `main` and leave **Also publish app code** disabled. No repository secret or Cloudflare variable is required.

The job:

1. Retrieves and validates the official quarterly England and Wales sources.
2. Refreshes the separate monthly police.uk data layer.
3. Writes `refresh-status.json` with the successful check time, updated/unchanged result, official dataset hash and monthly dataset hash. Observation periods and source publication dates remain separate.
4. Runs both offline validators, Python tests, type checks, app tests and the static build.
5. Rejects a branch that moved during the run, then commits only changed `crime.json`, `source-manifest.json`, `monthly.json`, `monthly-manifest.json` and `refresh-status.json`. It never force-pushes.

A download, parsing, validation, test, build or push failure stops publication. The preceding complete remote snapshot and the existing Cloudflare app remain available. After a successful run, verify that the public raw JSON files contain the new status/hash set and that the live app loads the same values. A complete refresh is published by one Git commit.

The schedule runs at **12:17 UTC on the 5th of every month**. A successful check can find unchanged sources; it does not invent a new month of observations. The status file supplies a real monthly check record even between quarterly releases.

GitHub schedules are best effort: runs can be delayed or dropped, and public scheduled workflows can be disabled after 60 days without repository activity. Successful monthly status commits provide regular activity. Keep GitHub failure notifications enabled and verify the first scheduled run. After a failed/missed run, run it manually; if scheduling is disabled, re-enable the workflow in Actions. See [GitHub schedule behaviour](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

No second push-triggered workflow is required. GitHub's [restriction on workflows triggered by `GITHUB_TOKEN` pushes](https://docs.github.com/en/actions/concepts/security/github_token) therefore does not interrupt this update route.

## Optional: automate app-code releases

The same workflow can upload a newly verified app build on a **manual** run when **Also publish app code** is enabled. Scheduled data checks never use Cloudflare credentials.

To enable that option, create a dedicated Cloudflare API token with **Account → Cloudflare Pages → Edit**, restricted to the intended Cloudflare account. This normal scope grants account-level Pages access; the project name selects the destination. Do not claim a one-project token restriction unless your account provides one.

Under GitHub **Settings → Secrets and variables → Actions**, add:

| Kind | Name | Value |
|---|---|---|
| Repository secret | `CLOUDFLARE_API_TOKEN` | Dedicated Pages deployment token |
| Repository secret | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account identifier |
| Repository variable | `CLOUDFLARE_PAGES_PROJECT` | Exact dedicated project name, e.g. `crime-compare` |

Enter the token directly into GitHub's encrypted secret field. Keep it out of the repository, command history, data and browser bundle. See [Cloudflare's CI guide](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).

An explicitly requested code publication fails before committing if any deployment setting is missing. When configured, it uploads the verified `dist/` in the same run and compares the live JSON bytes with the build. An upload failure does not erase the previous Cloudflare deployment. If upload succeeds but byte verification fails, inspect the deployment before retrying; the workflow does not call that result verified. Use [Cloudflare rollback](https://developers.cloudflare.com/pages/configuration/rollbacks/) for an incorrect app release.

Rotate this optional token independently of any other site's credentials. The `politicians.compare` repository and deployment must not be modified by this setup.

## Optional: attach a custom domain

The free `*.pages.dev` address works without buying a domain. [Domain research](domain-research.md) found `crime.compare` available on 22 October 2026 at US$26.26 registration and US$26.26/year renewal, before applicable tax/FX. Nothing was purchased.

After separately registering a chosen name, open the Pages project's **Custom domains → Set up a custom domain** and enter it there first. For an apex such as `crime.compare`, the domain must be a zone in the same Cloudflare account with Cloudflare authoritative nameservers. A subdomain on external DNS can instead use a CNAME to the Pages project. See [Cloudflare's custom-domain guide](https://developers.cloudflare.com/pages/configuration/custom-domains/).

Wait for TLS to become active, then verify HTTPS, the interface and data status on the final hostname. Update the app's canonical/social-share origin when that hostname is known.
