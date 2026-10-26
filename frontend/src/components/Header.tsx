import React from 'react';
import { Download, Sliders, ShieldCheck } from 'lucide-react';
import { getExportUrl } from '../services/api';

interface HeaderProps {
  decisionDate: string;
  setDecisionDate: (d: string) => void;
  cutoff: string;
  setCutoff: (c: string) => void;
  coveragePct: number;
  pairedCount: number;
  totalCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  decisionDate,
  setDecisionDate,
  cutoff,
  setCutoff,
  coveragePct,
  pairedCount,
  totalCount,
}) => {
  // Compute delivery date (D = Decision Day + 1)
  const deliveryDate = React.useMemo(() => {
    if (!decisionDate) return '';
    const d = new Date(decisionDate);
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  }, [decisionDate]);

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Brand & Market Context */}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white tracking-tight">
              UK Wind Horizon Evaluation
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Elexon BMRS
            </span>
            <span className="px-2.5 py-0.5 text-xs font-medium rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              Anti-Leakage Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Day-Ahead Wholesale Procurement Analysis • January 2026 Decisions
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Decision Date Filter */}
          <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
            <span className="text-slate-400 px-2 font-medium">Decision (D-1):</span>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={decisionDate}
              onChange={(e) => setDecisionDate(e.target.value)}
              className="bg-slate-900 text-white rounded px-2 py-1 border border-slate-700 outline-none focus:border-sky-500"
            />
            <span className="text-slate-500 px-2">→</span>
            <span className="text-slate-400 font-medium">Delivery (D):</span>
            <span className="text-sky-400 font-semibold px-2">{deliveryDate || 'All Jan'}</span>
          </div>

          {/* Gate Closure Cutoff Picker */}
          <div className="flex items-center bg-slate-800 rounded-lg p-1.5 border border-slate-700 text-xs">
            <Sliders className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-1" />
            <span className="text-slate-400 px-1 font-medium">Gate Cutoff:</span>
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
            href={getExportUrl(
              decisionDate ? `${deliveryDate}T00:00:00Z` : undefined,
              decisionDate ? `${deliveryDate}T23:30:00Z` : undefined,
              cutoff
            )}
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