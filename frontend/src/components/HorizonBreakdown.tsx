import React, { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { HorizonBreakdownItem } from '../types/api';
import { formatMw } from '../lib/format';

interface HorizonBreakdownProps {
  breakdown: HorizonBreakdownItem[];
  loading: boolean;
}

/** Two-line axis label: block name, then the average forecast age for that block. */
const BlockTick = ({ x = 0, y = 0, payload }: { x?: number; y?: number; payload?: { value?: string } }) => {
  const [name, lead] = String(payload?.value ?? '').split('|');
  return (
    <g transform={`translate(${x},${y})`}>
      <text dy={14} textAnchor="middle" fill="#94a3b8" fontSize={11}>{name}</text>
      {lead && (
        <text dy={28} textAnchor="middle" fill="#64748b" fontSize={10}>{lead}</text>
      )}
    </g>
  );
};

export const HorizonBreakdown: React.FC<HorizonBreakdownProps> = ({ breakdown, loading }) => {
  const rows = useMemo(
    () =>
      breakdown.map((b) => ({
        ...b,
        axisLabel: b.avg_lead_time_h != null ? `${b.horizon_bucket}|avg forecast age ${Math.round(b.avg_lead_time_h)}h` : b.horizon_bucket,
      })),
    [breakdown],
  );
  if (rows.length === 0) return null;

  return (
    <div aria-busy={loading} className={`bg-slate-900 border border-slate-800 rounded-xl p-5 mb-8 transition-opacity ${loading ? 'opacity-50' : ''}`}>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-white">Forecast error by delivery block</h2>
        <p className="text-xs text-slate-400">
          MAE and net bias by delivery hour (Europe/London). With a fixed gate closure, later blocks use older forecasts, so
          time of day and forecast age move together here and cannot be separated.
        </p>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="axisLabel" interval={0} height={48} tickLine={false} tick={<BlockTick />} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={(v: number) => `${formatMw(v)} MW`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
              formatter={(val: unknown, name: unknown) => [`${formatMw(Number(val))} MW`, String(name)]}
              labelFormatter={(label: unknown) => String(label).split('|')[0]}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" />
            <Bar dataKey="mae_mw" name="Mean absolute error (MW)" fill="#38bdf8" isAnimationActive={false} />
            <Bar dataKey="bias_mw" name="Net bias (MW)" fill="#f59e0b" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
