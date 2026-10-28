import React from 'react';
import { AlertTriangle, Download, ShieldCheck, Sliders, Zap } from 'lucide-react';
import { getExportUrl } from '../services/api';
import type { KPIResponse } from '../types/api';
import { DECISION_MAX, DECISION_MIN, deliveryDateFor, isValidDecisionDate, windowFor } from '../lib/dates';
import type { ViewMode } from '../lib/dates';
import { GATES, gateFor } from '../lib/gates';
import { DASH, formatMaeChange, formatPct } from '../lib/format';

interface HeaderProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  decisionDate: string;
  onDecisionDateChange: (date: string) => void;
  cutoff: string;
  onCutoffChange: (cutoff: string) => void;
  showDebiased: boolean;
  onToggleDebiased: () => void;
  metrics: KPIResponse | null;
  /** Forecast issue time (London clock) actually used by most periods in view. */
  runLabel: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  viewMode,
  onViewModeChange,
  decisionDate,
  onDecisionDateChange,
  cutoff,
  onCutoffChange,
  showDebiased,
  onToggleDebiased,
  metrics,
  runLabel,
}) => {
  const gate = gateFor(cutoff);
  const deliveryDate = isValidDecisionDate(decisionDate) ? deliveryDateFor(decisionDate) : DASH;
  const { dateFrom, dateTo } = windowFor(viewMode, decisionDate);
  const exportUrl = getExportUrl(dateFrom, dateTo, cutoff);

  const improvement = metrics?.debiased_improvement_pct ?? null;
  const debiasedPeriods = metrics?.debiased_periods ?? 0;
  const debiasAvailable = improvement !== null && debiasedPeriods > 0;
  const debiasLabel = !debiasAvailable
    ? 'Bias adjustment unavailable'
    : `${showDebiased ? 'Bias-adjusted ON' : 'Show bias-adjusted'} (${formatMaeChange(improvement)})`;
  const debiasHint = debiasAvailable
    ? `Subtracts the trailing 7-day mean error (delivery days D-8 to D-2, all known at gate closure). Measured on the ${debiasedPeriods.toLocaleString('en-GB')} periods with enough history.`
    : 'Not enough finalised history for this selection.';

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">UK Wind Forecast Evaluation</h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Elexon BMRS
            </span>
            <span
              title={gate.description}
              className={`px-2.5 py-0.5 text-xs font-medium rounded border flex items-center gap-1 ${
                gate.legacy
                  ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              }`}
            >
              {gate.legacy ? <AlertTriangle className="w-3.5 h-3.5" /> : <ShieldCheck className="w-3.5 h-3.5" />}
              {gate.legacy ? 'Legacy gate' : 'Gate locked'} {cutoff} UK · forecast run {runLabel ?? DASH} UK on D-1
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Day-ahead wholesale procurement analysis · decisions made 1–31 Jan 2026 (delivery 2 Jan – 1 Feb 2026)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex bg-slate-800 rounded-lg p-1 border border-slate-700 text-xs" role="group" aria-label="View mode">
            {(['month', 'day'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                aria-pressed={viewMode === mode}
                className={`px-3 py-1 rounded font-medium transition-colors ${
                  viewMode === mode ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {mode === 'month' ? 'Full month' : 'Single day'}
              </button>
            ))}
          </div>

          {viewMode === 'day' && (
            <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
              <span className="text-slate-400 px-2 font-medium">Decision:</span>
              <input
                type="date"
                aria-label="Decision date"
                min={DECISION_MIN}
                max={DECISION_MAX}
                value={decisionDate}
                onChange={(e) => {
                  if (isValidDecisionDate(e.target.value)) onDecisionDateChange(e.target.value);
                }}
                className="bg-slate-900 text-white rounded px-2 py-1 border border-slate-700 outline-none focus:border-sky-500"
              />
              <span className="text-slate-500 px-1">→</span>
              <span className="text-slate-400 font-medium">Delivery:</span>
              <span className="text-sky-400 font-semibold px-1.5">{deliveryDate}</span>
            </div>
          )}

          <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
            <Sliders className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-1" />
            <span className="text-slate-400 px-1 font-medium">Gate:</span>
            <select
              aria-label="Gate closure"
              title={gate.description}
              value={cutoff}
              onChange={(e) => onCutoffChange(e.target.value)}
              className="bg-slate-900 text-white rounded px-2 py-1 border border-slate-700 outline-none focus:border-sky-500"
            >
              {GATES.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={onToggleDebiased}
            disabled={!debiasAvailable}
            aria-pressed={showDebiased}
            title={debiasHint}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              showDebiased && debiasAvailable
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            {debiasLabel}
          </button>

          <div className="text-xs px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            Coverage:{' '}
            <span className="text-emerald-400 font-semibold">{metrics ? formatPct(metrics.coverage_pct, 1) : DASH}</span>{' '}
            <span className="text-slate-500">
              ({metrics ? `${metrics.paired_periods.toLocaleString('en-GB')}/${metrics.total_periods.toLocaleString('en-GB')}` : DASH})
            </span>
          </div>

          <a
            href={exportUrl}
            download
            className="flex items-center gap-1.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium px-3 py-2 rounded-lg transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </a>
        </div>
      </div>
    </header>
  );
};
