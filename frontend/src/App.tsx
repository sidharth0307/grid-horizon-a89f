import { useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Header } from './components/Header';
import { MetricCards } from './components/MetricCards';
import { HorizonChart } from './components/HorizonChart';
import { ResidualChart } from './components/ResidualChart';
import { HorizonBreakdown } from './components/HorizonBreakdown';
import { useDashboardData } from './hooks/useDashboardData';
import { dominantRun, windowFor } from './lib/dates';
import type { ViewMode } from './lib/dates';

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('month');
  const [decisionDate, setDecisionDate] = useState<string>('2026-01-14');
  const [cutoff, setCutoff] = useState<string>('09:20');
  const [showDebiased, setShowDebiased] = useState<boolean>(false);

  const { dateFrom, dateTo } = useMemo(() => windowFor(viewMode, decisionDate), [viewMode, decisionDate]);
  const { data, loading, error, retry } = useDashboardData(dateFrom, dateTo, cutoff);

  const runLabel = useMemo(() => (data ? dominantRun(data.series) : null), [data]);

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col font-sans">
      <Header
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        decisionDate={decisionDate}
        onDecisionDateChange={setDecisionDate}
        cutoff={cutoff}
        onCutoffChange={setCutoff}
        showDebiased={showDebiased}
        onToggleDebiased={() => setShowDebiased((v) => !v)}
        metrics={data?.metrics ?? null}
        runLabel={runLabel}
      />

      <main className="max-w-7xl mx-auto px-6 py-6 flex-1 w-full">
        {error && (
          <div role="alert" className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
            <button
              onClick={retry}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-xs font-semibold text-white transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        )}

        <MetricCards metrics={data?.metrics ?? null} loading={loading} />
        <HorizonChart data={data?.series ?? []} loading={loading} showDebiased={showDebiased} runLabel={runLabel} />
        <ResidualChart data={data?.series ?? []} loading={loading} />
        <HorizonBreakdown breakdown={data?.breakdown ?? []} loading={loading} />
      </main>

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        Contains BMRS data © Elexon Limited · Source: Elexon Insights Solution (BMRS) API · Day-ahead wind forecast evaluation
      </footer>
    </div>
  );
}
