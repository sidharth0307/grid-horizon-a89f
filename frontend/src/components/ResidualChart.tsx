import React, { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TimeSeriesPoint } from '../types/api';
import { formatLondon } from '../lib/dates';
import { formatMw } from '../lib/format';

interface ResidualChartProps {
  data: TimeSeriesPoint[];
  loading: boolean;
}

export const ResidualChart: React.FC<ResidualChartProps> = ({ data, loading }) => {
  const rows = useMemo(() => data.map((d) => ({ ...d, timeLabel: formatLondon(d.startTime) })), [data]);
  if (rows.length === 0) return null;

  return (
    <div aria-busy={loading} className={`bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6 transition-opacity ${loading ? 'opacity-50' : ''}`}>
      <div className="mb-2">
        <h2 className="text-base font-semibold text-white">Procurement residuals (forecast − actual)</h2>
        <p className="text-xs text-slate-400">
          <span className="text-amber-400 font-medium">Positive bars: forecast above actual, a shortfall the desk must buy back</span>{' '}
          · <span className="text-blue-400 font-medium">Negative bars: surplus</span>
        </p>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="timeLabel" stroke="#64748b" fontSize={11} tickLine={false} interval="preserveStartEnd" minTickGap={50} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={(v: number) => `${formatMw(v)} MW`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
              formatter={(val: unknown) => [`${formatMw(Number(val))} MW`, Number(val) > 0 ? 'Shortfall (over-forecast)' : 'Surplus (under-forecast)']}
            />
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1.5} />
            <Bar dataKey="error_mw" isAnimationActive={false}>
              {rows.map((entry) => (
                <Cell key={entry.startTime} fill={(entry.error_mw ?? 0) > 0 ? '#f59e0b' : '#3b82f6'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
