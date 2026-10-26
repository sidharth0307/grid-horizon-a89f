import React from 'react';
import type { KPIResponse } from '../types/api';
import { AlertTriangle, TrendingUp, Compass, ShieldAlert } from 'lucide-react';

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
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 relative overflow-hidden">
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
              (+{metrics.skill_score_pct}% vs persist)
            </span>
          )}
        </div>
      </div>

      {/* 2. Systematic Directional Bias */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 relative overflow-hidden">
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
            ? 'Shortfall Risk (Over-forecast)'
            : 'Surplus Tendency (Under-forecast)'}
        </div>
      </div>

      {/* 3. P90 Forward Safety Margin */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>P90 Reserve Buffer</span>
          <ShieldAlert className="w-4 h-4 text-red-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">
            {metrics.p90_error_mw?.toLocaleString() ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          Thermal hedge buffer (covers 90% deficit scenarios)
        </div>
      </div>

      {/* 4. Peak Observed Deficit */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Max Single-Period Deficit</span>
          <AlertTriangle className="w-4 h-4 text-orange-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-orange-400">
            {metrics.max_shortfall_risk_mw?.toLocaleString() ?? '—'}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          Root Mean Square (RMSE):{' '}
          <span className="text-slate-300 font-semibold">{metrics.rmse_mw ?? '—'} MW</span>
        </div>
      </div>
    </div>
  );
};