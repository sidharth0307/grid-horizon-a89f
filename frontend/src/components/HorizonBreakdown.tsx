import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { HorizonBreakdownItem } from '../types/api';

interface HorizonBreakdownProps {
  breakdown: HorizonBreakdownItem[];
  loading: boolean;
}

export const HorizonBreakdown: React.FC<HorizonBreakdownProps> = ({ breakdown, loading }) => {
  if (loading || breakdown.length === 0) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-8">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-white">
          Forecast Error vs. Lead-Time Horizon
        </h2>
        <p className="text-xs text-slate-400">
          MAE and Bias as a function of elapsed hours between gate closure (D-1 09:20) and delivery (D)
        </p>
      </div>

      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={breakdown} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="horizon_bucket" stroke="#64748b" fontSize={11} tickLine={false} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={(v) => `${v} MW`} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" />
            <Bar dataKey="mae_mw" name="Mean Absolute Error (MW)" fill="#38bdf8" isAnimationActive={false} />
            <Bar dataKey="bias_mw" name="Directional Bias (MW)" fill="#f59e0b" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};