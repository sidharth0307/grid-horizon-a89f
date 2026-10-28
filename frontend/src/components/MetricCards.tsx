import React from 'react';
import { BarChart3, Compass, ShieldAlert, TrendingUp } from 'lucide-react';
import type { KPIResponse } from '../types/api';
import { DASH, formatMw, formatPct, formatSignedMw } from '../lib/format';

interface MetricCardsProps {
  metrics: KPIResponse | null;
  loading: boolean;
}

const card = 'bg-slate-900 border border-slate-800 rounded-xl p-4';

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics, loading }) => {
  if (!metrics) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-slate-800/50 rounded-xl border border-slate-800 animate-pulse" />
        ))}
      </div>
    );
  }

  const bias = metrics.mean_bias_mw;
  const overShare = metrics.over_forecast_share_pct;

  return (
    <div
      aria-busy={loading}
      className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6 transition-opacity ${loading ? 'opacity-50' : ''}`}
    >
      <div className={card}>
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Mean Absolute Error (MAE)</span>
          <TrendingUp className="w-4 h-4 text-sky-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">{formatMw(metrics.mae_mw)}</span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          WAPE <span className="text-sky-400 font-semibold">{formatPct(metrics.wape_pct)}</span>
          {metrics.skill_score_pct != null && (
            <span className="text-emerald-400 ml-2">
              {formatPct(metrics.skill_score_pct)} better than 48h persistence
            </span>
          )}
        </div>
      </div>

      <div className={card}>
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Root Mean Square Error (RMSE)</span>
          <BarChart3 className="w-4 h-4 text-purple-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-white">{formatMw(metrics.rmse_mw)}</span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">Penalises large misses more than MAE</div>
      </div>

      <div className={card}>
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Net Bias (forecast − actual)</span>
          <Compass className="w-4 h-4 text-amber-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className={`text-2xl font-bold ${(bias ?? 0) > 0 ? 'text-amber-400' : 'text-blue-400'}`}>
            {formatSignedMw(bias)}
          </span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          {bias === null
            ? DASH
            : bias > 0
              ? 'Over-forecast tendency: shortfall risk'
              : 'Under-forecast tendency: surplus'}
          {overShare != null && (
            <span className="text-slate-300"> · {formatPct(overShare)} of half-hours over-forecast</span>
          )}
        </div>
      </div>

      <div className={card}>
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>P90 Shortfall Buffer</span>
          <ShieldAlert className="w-4 h-4 text-rose-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-rose-400">{formatMw(metrics.p90_error_mw)}</span>
          <span className="text-xs text-slate-400">MW</span>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          90th percentile of shortfall events (forecast above actual)
        </div>
      </div>
    </div>
  );
};
