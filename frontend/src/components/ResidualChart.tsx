import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  Cell,
} from 'recharts';
import type { TimeSeriesPoint } from '../types/api';

interface ResidualChartProps {
  data: TimeSeriesPoint[];
  loading: boolean;
}

export const ResidualChart: React.FC<ResidualChartProps> = ({ data, loading }) => {
  if (loading) return null;

  const formattedData = data.map((d) => ({
    ...d,
    timeLabel: new Date(d.startTime).toLocaleTimeString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
  }));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-base font-semibold text-white">
            Procurement Residuals (Forecast − Actual)
          </h2>
          <p className="text-xs text-slate-400">
            <span className="text-amber-400 font-medium">Positive Bars = Generation Deficit (Thermal Buy Trigger)</span>{' '}
            • <span className="text-blue-400 font-medium">Negative Bars = Generation Surplus</span>
          </p>
        </div>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={formattedData} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${v} MW`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(val: any) => [
                `${Number(val).toLocaleString()} MW`,
                Number(val) > 0 ? 'Deficit (Shortfall)' : 'Surplus',
              ]}
            />
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1.5} />
            <Bar dataKey="error_mw" isAnimationActive={false}>
              {formattedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={(entry.error_mw ?? 0) > 0 ? '#f59e0b' : '#3b82f6'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};