// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { metricsFixture } from '../components/fixtures';
import { fetchBreakdown, fetchMetrics, fetchSeries } from '../services/api';
import type { HorizonBreakdownItem, KPIResponse, TimeSeriesPoint } from '../types/api';
import { useDashboardData } from './useDashboardData';

vi.mock('../services/api', () => ({
  fetchMetrics: vi.fn(),
  fetchSeries: vi.fn(),
  fetchBreakdown: vi.fn(),
}));

const metricsMock = vi.mocked(fetchMetrics);
const seriesMock = vi.mocked(fetchSeries);
const breakdownMock = vi.mocked(fetchBreakdown);

const point = (mw: number): TimeSeriesPoint => ({
  startTime: '2026-01-15T00:00:00Z', actual_mw: mw, forecast_mw: mw, error_mw: 0, abs_error_mw: 0, horizon_h: 16.5,
});
const breakdown: HorizonBreakdownItem[] = [{ horizon_bucket: 'Overnight (00-06)', mae_mw: 1, bias_mw: 1, count: 1 }];

/** A promise the test resolves or rejects by hand, to control response ordering. */
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

/** Make every endpoint answer immediately with data tagged by `mae`. */
function answer(mae: number) {
  metricsMock.mockResolvedValue(metricsFixture({ mae_mw: mae }));
  seriesMock.mockResolvedValue([point(mae)]);
  breakdownMock.mockResolvedValue(breakdown);
}

const run = (cutoff: string) => ({ initialProps: { cutoff } });
const useIt = ({ cutoff }: { cutoff: string }) => useDashboardData('2026-01-02T00:00:00Z', '2026-02-01T23:30:00Z', cutoff);

beforeEach(() => {
  vi.resetAllMocks();
});

describe('useDashboardData', () => {
  it('starts loading, then exposes metrics, series and breakdown', async () => {
    answer(1);
    const { result } = renderHook(useIt, run('09:20'));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data?.metrics.mae_mw).toBe(1);
    expect(result.current.data?.series).toHaveLength(1);
    expect(result.current.data?.breakdown).toEqual(breakdown);
    expect(result.current.error).toBeNull();
  });

  it('passes the window and gate to every endpoint', async () => {
    answer(1);
    const { result } = renderHook(useIt, run('09:50'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    for (const mock of [metricsMock, seriesMock, breakdownMock]) {
      expect(mock.mock.calls[0].slice(0, 3)).toEqual(['2026-01-02T00:00:00Z', '2026-02-01T23:30:00Z', '09:50']);
    }
  });

  it('keeps the previous data (marked loading) while a new request is in flight', async () => {
    answer(1);
    const { result, rerender } = renderHook(useIt, run('09:20'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const slow = deferred<KPIResponse>();
    metricsMock.mockReturnValue(slow.promise);
    rerender({ cutoff: '09:50' });

    expect(result.current.loading).toBe(true);
    expect(result.current.data?.metrics.mae_mw).toBe(1); // stale data still available

    await act(async () => { slow.resolve(metricsFixture({ mae_mw: 2 })); });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data?.metrics.mae_mw).toBe(2);
  });

  it('never lets a slow, superseded response overwrite a newer one', async () => {
    const slowFirst = deferred<KPIResponse>();
    metricsMock.mockReturnValueOnce(slowFirst.promise);
    seriesMock.mockResolvedValue([point(1)]);
    breakdownMock.mockResolvedValue(breakdown);
    const { result, rerender } = renderHook(useIt, run('09:20'));

    answer(2); // the newer request answers straight away
    rerender({ cutoff: '09:50' });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data?.metrics.mae_mw).toBe(2);

    await act(async () => { slowFirst.resolve(metricsFixture({ mae_mw: 999 })); });
    expect(result.current.data?.metrics.mae_mw).toBe(2); // the late first response was ignored
  });

  it('does not report an error for requests it aborted itself', async () => {
    const aborted = deferred<KPIResponse>();
    metricsMock.mockReturnValueOnce(aborted.promise);
    seriesMock.mockResolvedValue([point(1)]);
    breakdownMock.mockResolvedValue(breakdown);
    const { result, rerender } = renderHook(useIt, run('09:20'));

    answer(3);
    rerender({ cutoff: '09:50' });
    await act(async () => { aborted.reject(new DOMException('Aborted', 'AbortError')); });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.data?.metrics.mae_mw).toBe(3);
  });

  it('reports a failure, keeps no stale data on first load, and recovers on retry', async () => {
    metricsMock.mockRejectedValueOnce(new Error('Loading metrics failed (HTTP 503).'));
    seriesMock.mockResolvedValue([point(1)]);
    breakdownMock.mockResolvedValue(breakdown);
    const { result } = renderHook(useIt, run('09:20'));

    await waitFor(() => expect(result.current.error).toBe('Loading metrics failed (HTTP 503).'));
    expect(result.current.data).toBeNull();

    answer(4);
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data?.metrics.mae_mw).toBe(4));
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('keeps the last good data visible when a later request fails', async () => {
    answer(1);
    const { result, rerender } = renderHook(useIt, run('09:20'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    metricsMock.mockRejectedValue(new Error('Cannot reach the analytics API.'));
    rerender({ cutoff: '11:00' });
    await waitFor(() => expect(result.current.error).toBe('Cannot reach the analytics API.'));
    expect(result.current.data?.metrics.mae_mw).toBe(1);
  });
});
