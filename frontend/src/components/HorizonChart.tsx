import React, { useMemo } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TimeSeriesPoint } from '../types/api';
import { formatLondon } from '../lib/dates';
import { formatMw } from '../lib/format';

interface HorizonChartProps {
  data: TimeSeriesPoint[];
  loading: boolean;
  showDebiased: boolean;
  runLabel: string | null;
}

interface ChartRow extends TimeSeriesPoint {
  timeLabel: string;
  publishLabel: string;
}

export const HorizonChart: React.FC<HorizonChartProps> = ({ data, loading, showDebiased, runLabel }) => {
  const rows = useMemo<ChartRow[]>(
    () =>
      data.map((d) => ({
        ...d,
        timeLabel: formatLondon(d.startTime),
        publishLabel: d.publishTime ? formatLondon(d.publishTime) : '—',
      })),
    [data],
  );

  if (rows.length === 0) {
    return (
      <div className="h-80 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center text-slate-500 mb-6">
        {loading ? 'Loading settlement series…' : 'No data for this selection.'}
      </div>
    );
  }

  return (
    <div aria-busy={loading} className={`bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6 transition-opacity ${loading ? 'opacity-50' : ''}`}>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-white">Wind generation: actual outturn vs day-ahead forecast</h2>
        <p className="text-xs text-slate-400">
          Times in Europe/London · each forecast is the latest run published before gate closure
          {runLabel ? ` (${runLabel} UK on D-1)` : ''}
        </p>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} tickLine={false} interval="preserveStartEnd" minTickGap={50} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
              formatter={(val: unknown, name: unknown, item: { payload?: ChartRow }) => {
                const label = String(name);
                const text = `${formatMw(Number(val))} MW`;
                if (label === 'Day-ahead forecast' && item?.payload) {
                  const { horizon_h: lead, publishLabel } = item.payload;
                  const extra = [`issued ${publishLabel} UK`, lead ? `${lead.toFixed(1)}h lead` : ''].filter(Boolean).join(', ');
                  return [`${text} (${extra})`, label];
                }
                return [text, label];
              }}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" />
            <Line type="monotone" dataKey="actual_mw" name="Actual wind outturn" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="forecast_mw" name="Day-ahead forecast" stroke="#38bdf8" strokeWidth={2} strokeDasharray="4 2" dot={false} isAnimationActive={false} />
            {showDebiased && (
              <Line type="monotone" dataKey="bias_adjusted_mw" name="Bias-adjusted forecast (7-day walk-forward)" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
