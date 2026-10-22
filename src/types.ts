export type HistoryPoint = { periodEnd: string; count: number | null; rate: number | null }
export type Metric = { count: number | null; rate: number | null; previousCount: number | null; changePercent: number | null; history: HistoryPoint[] }
export type Area = {
  id: string; code: string; name: string; type: 'force' | 'region' | 'nation'; regionId?: string | null;
  population: number | null; populationYear: number | string | null; comparisonEligible: boolean;
  metrics: Record<string, Metric | null>; quality: string[]; country?: string;
}
export type Category = { id: string; label: string; description?: string }
export type Source = { id: string; title: string; url: string; publishedAt?: string; [key: string]: unknown }
export type CrimeData = {
  schemaVersion: number; generatedAt: string;
  coverage: { start: string; end: string; label: string; frequency: string; sourcePublishedAt: string };
  sources: Source[]; categories: Category[]; areas: Area[];
  notes?: string[]; methodology?: unknown;
}
export type Geography = { viewBox: string; outline: string; areas: Record<string, { name: string; type: string; path: string; centroid: [number, number] }> }
export type Measure = 'rate' | 'count'
export type Sort = 'highest' | 'lowest' | 'name' | 'rising' | 'falling'
