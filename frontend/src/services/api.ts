import type { HorizonBreakdownItem, KPIResponse, TimeSeriesPoint } from '../types/api';

const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : import.meta.env.DEV
      ? 'http://localhost:8000'
      : '';

function query(dateFrom: string, dateTo: string, cutoff: string): string {
  return new URLSearchParams({ date_from: dateFrom, date_to: dateTo, gate_cutoff: cutoff }).toString();
}

/** Turn FastAPI error bodies ({"detail": ...}) into a readable message. */
async function errorMessage(res: Response, what: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return `${what}: ${body.detail}`;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) return `${what}: ${body.detail[0].msg}`;
  } catch {
    // body was not JSON; fall through to the status code
  }
  return `${what} failed (HTTP ${res.status}).`;
}

async function getJson<T>(path: string, what: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new Error('Cannot reach the analytics API. If it was idle it may still be starting; retry in a few seconds.', { cause: err });
  }
  if (!res.ok) throw new Error(await errorMessage(res, what));
  return (await res.json()) as T;
}

export const fetchMetrics = (from: string, to: string, cutoff: string, signal?: AbortSignal) =>
  getJson<KPIResponse>(`/api/metrics?${query(from, to, cutoff)}`, 'Loading metrics', signal);

export const fetchSeries = (from: string, to: string, cutoff: string, signal?: AbortSignal) =>
  getJson<TimeSeriesPoint[]>(`/api/series?${query(from, to, cutoff)}`, 'Loading time series', signal);

export const fetchBreakdown = (from: string, to: string, cutoff: string, signal?: AbortSignal) =>
  getJson<HorizonBreakdownItem[]>(`/api/breakdown?${query(from, to, cutoff)}`, 'Loading breakdown', signal);

export function getExportUrl(dateFrom: string, dateTo: string, cutoff: string): string {
  return `${API_BASE}/api/export.csv?${query(dateFrom, dateTo, cutoff)}`;
}
