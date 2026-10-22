import type { CrimeData } from './types'
export type RefreshStatus = { schemaVersion: number; checkedAt: string; datasetSha256: string; monthlyDatasetSha256?: string; result: string }
export type Snapshots = { official: CrimeData; monthly: CrimeData | null; status: RefreshStatus | null; baseUrl: string; fallback: boolean }
function validData(data: CrimeData) {
  if (data.schemaVersion !== 1 || !Array.isArray(data.areas) || !data.areas.length || !Array.isArray(data.categories) || !data.categories.length || !/^\d{4}-\d{2}-\d{2}$/.test(data.coverage?.end)) throw new Error('Invalid crime snapshot')
}
async function hash(text: string) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('')
}
async function fetchText(url: string, signal: AbortSignal, optional = false): Promise<string | null> {
  const result = await fetch(url, { signal, cache: 'no-cache' })
  if (optional && result.status === 404) return null
  if (!result.ok) throw new Error(`Snapshot unavailable (${result.status})`)
  return result.text()
}
async function bundle(baseUrl: string, remote: boolean, signal: AbortSignal): Promise<Snapshots> {
  const [officialText, monthlyText, statusText] = await Promise.all([
    fetchText(`${baseUrl}/crime.json`, signal), fetchText(`${baseUrl}/monthly.json`, signal, true), fetchText(`${baseUrl}/refresh-status.json`, signal, !remote),
  ])
  const official: CrimeData = JSON.parse(officialText!), monthly: CrimeData | null = monthlyText ? JSON.parse(monthlyText) : null
  const status: RefreshStatus | null = statusText ? JSON.parse(statusText) : null
  validData(official); if (monthly) validData(monthly)
  if (status) {
    if (status.datasetSha256 !== await hash(officialText!)) throw new Error('Snapshots are being refreshed; use packaged record')
    if (monthlyText && status.monthlyDatasetSha256 && status.monthlyDatasetSha256 !== await hash(monthlyText)) throw new Error('Monthly snapshot integrity mismatch')
    if (Number.isNaN(Date.parse(status.checkedAt))) throw new Error('Invalid check timestamp')
  }
  return { official, monthly, status, baseUrl, fallback: false }
}
export async function loadSnapshots(signal: AbortSignal): Promise<Snapshots> {
  const remoteBase = (import.meta.env.VITE_DATA_BASE_URL || '').replace(/\/$/, '')
  if (remoteBase) {
    try { return await bundle(remoteBase, true, AbortSignal.any([signal, AbortSignal.timeout(8000)])) }
    catch (error) { if (signal.aborted) throw error }
  }
  const local = await bundle('/data', false, signal)
  return { ...local, fallback: !!remoteBase }
}
