import { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { MetricCards } from './components/MetricCards';
import { HorizonChart } from './components/HorizonChart';
import { ResidualChart } from './components/ResidualChart';
import { HorizonBreakdown } from './components/HorizonBreakdown';
import { fetchBreakdown, fetchMetrics, fetchSeries } from './services/api';
import type { HorizonBreakdownItem, KPIResponse, TimeSeriesPoint } from './types/api';

export default function App() {
  const [decisionDate, setDecisionDate] = useState<string>('2026-01-05');
  const [cutoff, setCutoff] = useState<string>('09:20');
  
  const [metrics, setMetrics] = useState<KPIResponse | null>(null);
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);
  const [breakdown, setBreakdown] = useState<HorizonBreakdownItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // When decisionDate is chosen, target delivery day is D = decisionDate + 1
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        let dateFrom: string | undefined;
        let dateTo: string | undefined;

        if (decisionDate) {
          const d = new Date(decisionDate);
          d.setDate(d.getDate() + 1);
          const deliveryDay = d.toISOString().split('T')[0];
          dateFrom = `${deliveryDay}T00:00:00Z`;
          dateTo = `${deliveryDay}T23:30:00Z`;
        }

        const [kpiRes, seriesRes, breakdownRes] = await Promise.all([
          fetchMetrics(dateFrom, dateTo, cutoff),
          fetchSeries(dateFrom, dateTo, cutoff),
          fetchBreakdown(dateFrom, dateTo, cutoff),
        ]);

        setMetrics(kpiRes);
        setSeries(seriesRes);
        setBreakdown(breakdownRes);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [decisionDate, cutoff]);

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col font-sans">
      <Header
        decisionDate={decisionDate}
        setDecisionDate={setDecisionDate}
        cutoff={cutoff}
        setCutoff={setCutoff}
        coveragePct={metrics?.coverage_pct ?? 100}
        pairedCount={metrics?.paired_periods ?? 0}
        totalCount={metrics?.total_periods ?? 0}
      />

      <main className="max-w-7xl mx-auto px-6 py-6 flex-1 w-full">
        {/* KPI Summary Grid */}
        <MetricCards metrics={metrics} loading={loading} />

        {/* Forecast vs Outturn Line Chart */}
        <HorizonChart data={series} loading={loading} />

        {/* Residual Shortfall/Surplus Bar Chart */}
        <ResidualChart data={series} loading={loading} />

        {/* Error Degradation by Lead Time */}
        <HorizonBreakdown breakdown={breakdown} loading={loading} />
      </main>

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        UK Day-Ahead Wind Evaluation Platform • Powered by Elexon BMRS Stream API & FastAPI
      </footer>
    </div>
  );
}