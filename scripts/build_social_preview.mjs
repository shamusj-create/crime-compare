import { readFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// Factual typographic artwork; real ONS geometry, no stock art or generated imagery.
// Reuse an installed sharp; the committed PNG needs no runtime dependency.
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(import.meta.url)
let sharp
for (const candidate of ['sharp', process.env.SHARP_MODULE_PATH, join(homedir(), 'Documents/PoliticiansRanked/node_modules/sharp')].filter(Boolean)) {
  try { sharp = require(candidate); break } catch { /* Try the next existing installation. */ }
}
if (!sharp) throw new Error('An existing sharp installation is needed to rebuild artwork. Set SHARP_MODULE_PATH to its module path; the committed social-card.png can be used without regeneration.')
const geography = JSON.parse(await readFile(join(root, 'public/data/geography.json'), 'utf8'))
const regions = Object.values(geography.areas).filter(area => area.type === 'region')
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#ffffff"/><rect width="1200" height="8" fill="#0a3fb7"/>
<path d="M64 56h36v36H64zM82 56v36M64 74h36" stroke="#101624" stroke-width="1.6" fill="none"/><path d="M83 57h16v16H83z" fill="#dce6fb"/>
<text x="116" y="88" font-family="Georgia,serif" font-size="39" fill="#101624">CrimeLedger<tspan fill="#0a3fb7">.</tspan></text>
<text x="64" y="176" font-family="Arial,Helvetica,sans-serif" font-size="18" font-weight="700" letter-spacing="3.5" fill="#0a3fb7">ENGLAND &amp; WALES</text>
<text x="60" y="264" font-family="Georgia,serif" font-size="78" letter-spacing="-2" fill="#101624">Crime, in</text>
<text x="60" y="350" font-family="Georgia,serif" font-size="78" letter-spacing="-2" fill="#101624">perspective<tspan fill="#0a3fb7">.</tspan></text>
<text x="64" y="407" font-family="Arial,Helvetica,sans-serif" font-size="25" fill="#526078">Official crime data.</text>
<text x="64" y="446" font-family="Arial,Helvetica,sans-serif" font-size="25" fill="#526078">Clear regional comparisons.</text>
<g transform="translate(816 107) scale(.98)"><path d="${geography.outline}" fill="#0a3fb7"/>${regions.map(area => `<path d="${area.path}" fill="#0a3fb7" stroke="#ffffff" stroke-width="1.2" fill-rule="evenodd"/>`).join('')}</g>
<path d="M64 505H1136" stroke="#cbd2de"/>
<text x="64" y="562" font-family="Arial,Helvetica,sans-serif" font-size="28" font-weight="600" fill="#0a3fb7">crime.compare</text>
<text x="1136" y="560" text-anchor="end" font-family="Arial,Helvetica,sans-serif" font-size="18" fill="#526078">Recorded offences. Sources you can inspect.</text>
</svg>`
await mkdir(join(root, 'public'), { recursive: true })
await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(join(root, 'public/social-card.png'))
console.log('Built public/social-card.png (1200 × 630), with ONS England/Wales map geometry.')
