import { useEffect, useState } from 'react';
import { fetchBreakdown, fetchMetrics, fetchSeries } from '../services/api';
import type { DashboardData } from '../types/api';

interface Settled {
  key: string;
  data: DashboardData | null;
  error: string | null;
}

/**
 * Loads metrics, series and breakdown for one request window.
 *
 * `loading` is derived (the latest settled request does not match the current one) rather than
 * set inside the effect, so there is no synchronous setState in the effect and stale responses
 * can never overwrite a newer request: superseded requests are aborted and ignored.
 * Previously loaded data stays available while a new request is in flight.
 */
export function useDashboardData(dateFrom: string, dateTo: string, cutoff: string) {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled | null>(null);
  const key = `${dateFrom}|${dateTo}|${cutoff}|${attempt}`;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    Promise.all([
      fetchMetrics(dateFrom, dateTo, cutoff, signal),
      fetchSeries(dateFrom, dateTo, cutoff, signal),
      fetchBreakdown(dateFrom, dateTo, cutoff, signal),
    ])
      .then(([metrics, series, breakdown]) => {
        if (signal.aborted) return;
        setSettled({ key, data: { metrics, series, breakdown }, error: null });
      })
      .catch((err: unknown) => {
        if (signal.aborted || (err instanceof DOMException && err.name === 'AbortError')) return;
        const message = err instanceof Error ? err.message : 'Unexpected error while loading data.';
        setSettled((prev) => ({ key, data: prev?.data ?? null, error: message }));
      });

    return () => controller.abort();
  }, [dateFrom, dateTo, cutoff, key]);

  return {
    data: settled?.data ?? null,
    loading: settled?.key !== key,
    error: settled?.key === key ? settled.error : null,
    retry: () => setAttempt((n) => n + 1),
  };
}
