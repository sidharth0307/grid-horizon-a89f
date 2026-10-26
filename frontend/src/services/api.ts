import type { HorizonBreakdownItem, KPIResponse, MetaResponse, TimeSeriesPoint } from '../types/api';

// If VITE_API_BASE_URL is set (e.g. Vercel -> Render), use it.
// Otherwise, empty string routes to relative /api which NGINX or Vite proxy handles.
const API_BASE = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : (import.meta.env.DEV ? 'http://localhost:8000' : '');

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await fetch(`${API_BASE}/api/meta`);
  if (!res.ok) throw new Error(`Failed to fetch metadata (${res.status})`);
  return res.json();
}

export async function fetchMetrics(
  dateFrom?: string,
  dateTo?: string,
  cutoff: string = '09:20'
): Promise<KPIResponse> {
  const params = new URLSearchParams({ gate_cutoff: cutoff });
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);

  const res = await fetch(`${API_BASE}/api/metrics?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch metrics (${res.status})`);
  return res.json();
}

export async function fetchSeries(
  dateFrom?: string,
  dateTo?: string,
  cutoff: string = '09:20'
): Promise<TimeSeriesPoint[]> {
  const params = new URLSearchParams({ gate_cutoff: cutoff });
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);

  const res = await fetch(`${API_BASE}/api/series?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch time series (${res.status})`);
  return res.json();
}

export async function fetchBreakdown(
  dateFrom?: string,
  dateTo?: string,
  cutoff: string = '09:20'
): Promise<HorizonBreakdownItem[]> {
  const params = new URLSearchParams({ gate_cutoff: cutoff });
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);

  const res = await fetch(`${API_BASE}/api/breakdown?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch breakdown (${res.status})`);
  return res.json();
}

export function getExportUrl(dateFrom?: string, dateTo?: string, cutoff: string = '09:20'): string {
  const params = new URLSearchParams({ gate_cutoff: cutoff });
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);
  return `${API_BASE}/api/export.csv?${params.toString()}`;
}