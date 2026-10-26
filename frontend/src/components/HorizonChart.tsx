import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { TimeSeriesPoint } from '../types/api';

interface HorizonChartProps {
  data: TimeSeriesPoint[];
  loading: boolean;
}

export const HorizonChart: React.FC<HorizonChartProps> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="h-80 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center text-slate-500">
        Loading settlement series...
      </div>
    );
  }

  // Format timestamp for display (e.g. "05 Jan 14:30")
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
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">
            Wind Generation: Actual Outturn vs. Day-Ahead Forecast
          </h2>
          <p className="text-xs text-slate-400">
            National half-hourly volume (MW) locked at gate closure
          </p>
        </div>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formattedData} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
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
              tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(val: any) => [`${Number(val).toLocaleString()} MW`]}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" />
            <Line
              type="monotone"
              dataKey="actual_mw"
              name="Actual Wind Outturn"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="forecast_mw"
              name="Day-Ahead Forecast"
              stroke="#38bdf8"
              strokeWidth={2}
              strokeDasharray="4 2"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};