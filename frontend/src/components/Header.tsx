import React from 'react';
import { Download, Sliders, ShieldCheck, AlertCircle } from 'lucide-react';
import { getExportUrl } from '../services/api';

interface HeaderProps {
  viewMode: 'month' | 'day';
  setViewMode: (mode: 'month' | 'day') => void;
  decisionDate: string;
  setDecisionDate: (d: string) => void;
  cutoff: string;
  setCutoff: (c: string) => void;
  coveragePct: number;
  pairedCount: number;
  totalCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  viewMode,
  setViewMode,
  decisionDate,
  setDecisionDate,
  cutoff,
  setCutoff,
  coveragePct,
  pairedCount,
  totalCount,
}) => {
  const deliveryDate = React.useMemo(() => {
    if (!decisionDate) return '';
    const d = new Date(decisionDate);
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  }, [decisionDate]);

  const isLeakageProne = cutoff === '11:00';

  const exportUrl = React.useMemo(() => {
    if (viewMode === 'day' && decisionDate) {
      return getExportUrl(`${deliveryDate}T00:00:00Z`, `${deliveryDate}T23:30:00Z`, cutoff);
    }
    return getExportUrl('2026-01-02T00:00:00Z', '2026-02-01T23:30:00Z', cutoff);
  }, [viewMode, decisionDate, deliveryDate, cutoff]);

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Brand & Market Context */}
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              UK Wind Horizon Evaluation
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Elexon BMRS
            </span>
            {isLeakageProne ? (
              <span className="px-2.5 py-0.5 text-xs font-medium rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                Leakage Risk (11:00 Stale Pre-Brexit)
              </span>
            ) : (
              <span className="px-2.5 py-0.5 text-xs font-medium rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                Anti-Leakage Active ({cutoff} London)
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Day-Ahead Wholesale Procurement Analysis • January 2026 Decisions (Delivery: 02 Jan – 01 Feb 2026)
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Mode Switcher */}
          <div className="flex bg-slate-800 rounded-lg p-1 border border-slate-700 text-xs">
            <button
              onClick={() => setViewMode('month')}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                viewMode === 'month' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Full Month (1,488 SPs)
            </button>
            <button
              onClick={() => setViewMode('day')}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                viewMode === 'day' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Single Day (48 SPs)
            </button>
          </div>

          {/* Single Day Filter */}
          {viewMode === 'day' && (
            <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
              <span className="text-slate-400 px-2 font-medium">Decision:</span>
              <input
                type="date"
                min="2026-01-01"
                max="2026-01-31"
                value={decisionDate}
                onChange={(e) => setDecisionDate(e.target.value)}
                className="bg-slate-900 text-white rounded px-2 py-1 border border-slate-700 outline-none focus:border-sky-500"
              />
              <span className="text-slate-500 px-1">→</span>
              <span className="text-slate-400 font-medium">Delivery:</span>
              <span className="text-sky-400 font-semibold px-1.5">{deliveryDate}</span>
            </div>
          )}

          {/* Cutoff Selector */}
          <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
            <Sliders className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-1" />
            <span className="text-slate-400 px-1 font-medium">Gate:</span>
            <select
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
              className="bg-slate-900 text-white rounded px-2 py-1 border border-slate-700 outline-none focus:border-sky-500"
            >
              <option value="09:20">09:20 UK (EPEX Spot)</option>
              <option value="09:50">09:50 UK (N2EX)</option>
              <option value="11:00">11:00 UK (Historical/Stale)</option>
            </select>
          </div>

          {/* Coverage Badge */}
          <div className="text-xs px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            Coverage:{' '}
            <span className="text-emerald-400 font-semibold">{coveragePct}%</span>{' '}
            <span className="text-slate-500">
              ({pairedCount}/{totalCount})
            </span>
          </div>

          {/* CSV Export Button */}
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