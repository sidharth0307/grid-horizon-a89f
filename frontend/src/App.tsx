import { useCallback, useEffect, useState } from 'react';
import { Header } from './components/Header';
import { MetricCards } from './components/MetricCards';
import { HorizonChart } from './components/HorizonChart';
import { ResidualChart } from './components/ResidualChart';
import { HorizonBreakdown } from './components/HorizonBreakdown';
import { fetchBreakdown, fetchMetrics, fetchSeries } from './services/api';
import type { HorizonBreakdownItem, KPIResponse, TimeSeriesPoint } from './types/api';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function App() {
  const [viewMode, setViewMode] = useState<'month' | 'day'>('month');
  const [decisionDate, setDecisionDate] = useState<string>('2026-01-14');
  const [cutoff, setCutoff] = useState<string>('09:20');
  const [showDebiased, setShowDebiased] = useState<boolean>(false);

  const [metrics, setMetrics] = useState<KPIResponse | null>(null);
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);
  const [breakdown, setBreakdown] = useState<HorizonBreakdownItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      let dateFrom: string | undefined;
      let dateTo: string | undefined;

      if (viewMode === 'day') {
        const d = new Date(decisionDate);
        d.setDate(d.getDate() + 1);
        const deliveryDay = d.toISOString().split('T')[0];
        dateFrom = `${deliveryDay}T00:00:00Z`;
        dateTo = `${deliveryDay}T23:30:00Z`;
      } else {
        dateFrom = '2026-01-02T00:00:00Z';
        dateTo = '2026-02-01T23:30:00Z';
      }

      const [kpiRes, seriesRes, breakdownRes] = await Promise.all([
        fetchMetrics(dateFrom, dateTo, cutoff, signal),
        fetchSeries(dateFrom, dateTo, cutoff, signal),
        fetchBreakdown(dateFrom, dateTo, cutoff, signal),
      ]);

      setMetrics(kpiRes);
      setSeries(seriesRes);
      setBreakdown(breakdownRes);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return; // Request was aborted by newer filter action
      }
      const message = err instanceof Error ? err.message : 'Failed to connect to analytics backend.';
      console.error('Failed to load dashboard data:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [viewMode, decisionDate, cutoff]);

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, [loadData]);

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col font-sans">
      <Header
        viewMode={viewMode}
        setViewMode={setViewMode}
        decisionDate={decisionDate}
        setDecisionDate={setDecisionDate}
        cutoff={cutoff}
        setCutoff={setCutoff}
        showDebiased={showDebiased}
        setShowDebiased={setShowDebiased}
        coveragePct={metrics?.coverage_pct ?? 100}
        pairedCount={metrics?.paired_periods ?? 0}
        totalCount={metrics?.total_periods ?? 0}
      />

      <main className="max-w-7xl mx-auto px-6 py-6 flex-1 w-full">
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
            <button
              onClick={() => loadData()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-xs font-semibold text-white transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        )}

        {/* Executive KPI Summary Grid */}
        <MetricCards metrics={metrics} loading={loading} />

        {/* Forecast vs Outturn Line Chart */}
        <HorizonChart data={series} loading={loading} showDebiased={showDebiased} />

        {/* Residual Shortfall/Surplus Bar Chart */}
        <ResidualChart data={series} loading={loading} />

        {/* Error Breakdown Across Trading Blocks */}
        <HorizonBreakdown breakdown={breakdown} loading={loading} />
      </main>

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        Data Source: Elexon Insights Solution (BMRS) Open API • UK Electricity Market Wholesale Decision Analytics
      </footer>
    </div>
  );
}