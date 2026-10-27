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
  showDebiased: boolean;
}

export const HorizonChart: React.FC<HorizonChartProps> = ({ data, loading, showDebiased }) => {
  if (loading) {
    return (
      <div className="h-80 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center text-slate-500">
        Loading settlement series...
      </div>
    );
  }

  const formattedData = data.map((d) => {
    const delivery = new Date(d.startTime);
    const pub = d.publishTime ? new Date(d.publishTime) : null;
    return {
      ...d,
      timeLabel: delivery.toLocaleTimeString('en-GB', {
        timeZone: 'Europe/London',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
      publishLabel: pub
        ? pub.toLocaleTimeString('en-GB', {
            timeZone: 'Europe/London',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })
        : '—',
    };
  });

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">
            Wind Generation: Actual Outturn vs. Day-Ahead Forecast
          </h2>
          <p className="text-xs text-slate-400">
            Timestamps formatted in Europe/London time • Forecasts locked strictly at gate closure
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
              minTickGap={50}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(val: unknown, name: unknown, item: { payload?: { horizon_h?: number; publishLabel?: string } }) => {
                const numericVal = Number(val);
                const strName = String(name);
                if (strName === 'Day-Ahead Forecast') {
                  const leadTime = item?.payload?.horizon_h ? `${item.payload.horizon_h.toFixed(1)}h lead` : '';
                  const pub = item?.payload?.publishLabel ? `Issued: ${item.payload.publishLabel} UK` : '';
                  const extra = [pub, leadTime].filter(Boolean).join(', ');
                  return [`${numericVal.toLocaleString()} MW (${extra})`, strName];
                }
                return [`${numericVal.toLocaleString()} MW`, strName];
              }}
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
            {showDebiased && (
              <Line
                type="monotone"
                dataKey="bias_adjusted_mw"
                name="Bias-Adjusted Forecast (7d walk-forward)"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};