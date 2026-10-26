import React from 'react';
import type { KPIResponse } from '../types/api';
import { TrendingUp, Compass, ShieldAlert, BarChart3 } from 'lucide-react';

interface MetricCardsProps {
  metrics: KPIResponse | null;
  loading: boolean;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics, loading }) => {
  if (loading || !metrics) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-slate-800/50 rounded-xl border border-slate-800 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* 1. MAE & Persistence Baseline */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Mean Absolute Error (MAE)</span>
          <TrendingUp className="w-4 h-4 text-sky-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">
            {metrics.mae_mw?.toLocaleString() ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          WAPE:{' '}
          <span className="text-sky-400 font-semibold">{metrics.wape_pct ?? '—'}%</span>
          {metrics.skill_score_pct !== null && (
            <span className="text-emerald-400 ml-2">
              (+{metrics.skill_score_pct}% vs 48h lag)
            </span>
          )}
        </div>
      </div>

      {/* 2. Dedicated RMSE Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Root Mean Square (RMSE)</span>
          <BarChart3 className="w-4 h-4 text-purple-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">
            {metrics.rmse_mw?.toLocaleString() ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          Quadratic penalty on large forecast deviations
        </div>
      </div>

      {/* 3. Directional Net Bias */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Directional Net Bias</span>
          <Compass className="w-4 h-4 text-amber-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span
            className={`text-2xl font-bold ${
              (metrics.mean_bias_mw ?? 0) > 0 ? 'text-amber-400' : 'text-blue-400'
            }`}
          >
            {(metrics.mean_bias_mw ?? 0) > 0 ? `+${metrics.mean_bias_mw}` : metrics.mean_bias_mw ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          {(metrics.mean_bias_mw ?? 0) > 0
            ? 'Shortfall Risk (Over-forecast tendency)'
            : 'Surplus Tendency (Under-forecast)'}
        </div>
      </div>

      {/* 4. P90 Deficit Reserve Buffer */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>P90 Reserve Buffer (Deficits)</span>
          <ShieldAlert className="w-4 h-4 text-rose-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-rose-400">
            {metrics.p90_error_mw?.toLocaleString() ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          Thermal buffer covering 90% of shortfall events
        </div>
      </div>
    </div>
  );
};