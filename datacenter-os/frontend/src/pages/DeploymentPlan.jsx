import React, { useMemo } from 'react';
import { generateDeploymentPlan } from '../logic/configurator';
import {
  CheckCircle2, AlertCircle, Clock, LayoutDashboard,
  Terminal, Droplet, Thermometer, Activity, Leaf,
  Map, RefreshCcw, ArrowRight, ShoppingCart
} from 'lucide-react';

const MODULE_ICONS = {
  CarbonClock: Leaf,
  IDLEhunter: Terminal,
  WaterWatch: Droplet,
  ThermalTrace: Thermometer,
  LightSpeed: Activity,
  PowerWatch: LayoutDashboard,
};

const STATUS_CONFIG = {
  active_now: {
    dot: 'bg-green-500',
    badge: 'bg-green-500/10 text-green-400 border border-green-500/30',
  },
  needs_setup: {
    dot: 'bg-yellow-500',
    badge: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30',
  },
  phase1_hardware: {
    dot: 'bg-[#f0b429]',
    badge: 'bg-[#f0b429]/10 text-[#f0b429] border border-[#f0b429]/30',
  },
  phase2_hardware: {
    dot: 'bg-orange-500',
    badge: 'bg-orange-500/10 text-orange-400 border border-orange-500/30',
  },
  check: {
    dot: 'bg-blue-400',
    badge: 'bg-blue-500/10 text-blue-400 border border-blue-500/30',
  },
};

function fmt(num) {
  return '₹' + num.toLocaleString('en-IN');
}

// ─── Summary card ─────────────────────────────────────────────────────────────

function SummaryCard({ label, value, color }) {
  return (
    <div className="rounded-xl p-5 border border-[#1e2a45]" style={{ background: '#0f1629' }}>
      <div className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-3">{label}</div>
      <div className={`text-2xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}

// ─── Module status card ───────────────────────────────────────────────────────

function ModuleCard({ moduleName, statusObj }) {
  const Icon = MODULE_ICONS[moduleName] || LayoutDashboard;
  const cfg = STATUS_CONFIG[statusObj?.status] || STATUS_CONFIG.check;

  return (
    <div className="rounded-xl p-5 border border-[#1e2a45] flex flex-col gap-3" style={{ background: '#0f1629' }}>
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${cfg.dot} shadow-[0_0_6px_currentColor]`} />
        <Icon size={16} className="text-gray-400" />
        <span className="text-sm font-semibold text-white">{moduleName}</span>
      </div>
      <span className={`text-xs px-2.5 py-1 rounded-full w-fit font-medium ${cfg.badge}`}>
        {statusObj?.label || 'Unknown'}
      </span>
      {statusObj?.note && (
        <p className="text-xs text-gray-500 leading-relaxed">{statusObj.note}</p>
      )}
    </div>
  );
}

// ─── Phase card ───────────────────────────────────────────────────────────────

function PhaseCard({ phase }) {
  return (
    <div className="rounded-2xl border border-[#1e2a45] overflow-hidden" style={{ background: '#0f1629' }}>
      {/* Phase header */}
      <div className="flex items-center justify-between p-6 border-b border-[#1e2a45]">
        <div>
          <div className="text-xs font-mono text-[#f0b429] uppercase tracking-widest mb-1">
            Phase {phase.phase_number}
          </div>
          <h3 className="text-lg font-bold text-white">{phase.title}</h3>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-bold text-white">{fmt(phase.total_cost)}</div>
          <div className="text-xs text-gray-500">total hardware cost</div>
        </div>
      </div>

      {/* Hardware table */}
      {phase.hardware_items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2a45]">
                {['Item', 'Qty', 'Unit Cost', 'Total', 'Where to Buy', 'Unlocks'].map(h => (
                  <th
                    key={h}
                    className="text-left px-6 py-3 text-xs font-mono text-gray-500 uppercase tracking-widest"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e2a45]">
              {phase.hardware_items.map((item, i) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-4">
                    <div className="font-medium text-white">{item.name}</div>
                    <div className="text-xs text-gray-500 mt-1">{item.why_this_first}</div>
                  </td>
                  <td className="px-6 py-4 text-gray-300 font-mono">{item.quantity}</td>
                  <td className="px-6 py-4 text-gray-300 font-mono">{fmt(item.unit_cost)}</td>
                  <td className="px-6 py-4 font-mono font-bold text-white">{fmt(item.total_cost)}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      <ShoppingCart size={12} className="text-gray-500" />
                      <span className="text-gray-400 text-xs">{item.where_to_buy}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs bg-green-500/10 text-green-400 border border-green-500/20 px-2.5 py-1 rounded-full">
                      {item.what_it_unlocks}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Phase footer */}
      <div className="flex items-center justify-between px-6 py-4 bg-white/[0.02] border-t border-[#1e2a45]">
        <div className="text-sm text-gray-400">
          Projected additional savings:{' '}
          <span className="text-green-400 font-mono font-bold">{fmt(phase.projected_savings_per_year)}/year</span>
        </div>
        {phase.payback_weeks > 0 && (
          <div className="text-sm text-gray-400">
            Payback from this phase:{' '}
            <span className="text-[#f0b429] font-mono font-bold">{phase.payback_weeks} weeks</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Roadmap item ─────────────────────────────────────────────────────────────

function RoadmapItem({ item, index, total }) {
  return (
    <div className="flex gap-5">
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-full bg-[#f0b429]/20 border border-[#f0b429]/40 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-[#f0b429]">{index + 1}</span>
        </div>
        {index < total - 1 && <div className="w-px flex-1 bg-[#1e2a45] mt-2" />}
      </div>
      <div className="pb-8">
        <div className="text-xs font-mono text-[#f0b429] uppercase tracking-widest mb-1">{item.when}</div>
        <h4 className="text-base font-semibold text-white mb-1">{item.title}</h4>
        <p className="text-sm text-gray-400 leading-relaxed">{item.description}</p>
      </div>
    </div>
  );
}

// ─── Main DeploymentPlan component ───────────────────────────────────────────

export default function DeploymentPlan({ onNavigateDashboard, onReconfigure }) {
  const profile = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('greencore_facility_profile') || '{}');
    } catch {
      return {};
    }
  }, []);

  const plan = useMemo(() => generateDeploymentPlan(profile), [profile]);

  const activeCount = plan.summary.modules_active_now.length;

  return (
    <div
      className="min-h-screen px-4 py-10"
      style={{ background: '#0a0e1a', fontFamily: 'Inter, sans-serif' }}
    >
      {/* BG glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[60%] bg-[#f0b429]/4 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[40%] h-[50%] bg-green-500/4 blur-[100px] rounded-full" />
      </div>

      <div className="max-w-6xl mx-auto relative z-10 space-y-10">

        {/* ── Top header ─────────────────────────────────────────────────────── */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Map size={20} className="text-[#f0b429]" />
            <h1 className="text-3xl font-bold text-white">Your GreenCore Deployment Plan</h1>
          </div>
          <p className="text-gray-400">{plan.facility_name}</p>
        </div>

        {/* ── Summary cards ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard
            label="Modules Active Now"
            value={activeCount}
            color="text-green-400"
          />
          <SummaryCard
            label="Phase 1 Hardware Cost"
            value={fmt(plan.summary.phase1_cost)}
            color="text-white"
          />
          <SummaryCard
            label="Estimated Annual Savings"
            value={fmt(plan.summary.estimated_annual_savings)}
            color="text-green-400"
          />
          <SummaryCard
            label="Payback Period"
            value={plan.summary.payback_weeks > 0 ? `${plan.summary.payback_weeks} weeks` : '< 1 week'}
            color="text-[#f0b429]"
          />
        </div>

        {/* ── Module status grid ─────────────────────────────────────────────── */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-5">Module Status</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(plan.module_statuses).map(([mod, status]) => (
              <ModuleCard key={mod} moduleName={mod} statusObj={status} />
            ))}
          </div>
        </section>

        {/* ── Phase cards ────────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-5">Deployment Phases</h2>
          <div className="space-y-6">
            {plan.phases.map(phase => (
              <PhaseCard key={phase.phase_number} phase={phase} />
            ))}
          </div>
        </section>

        {/* ── Architecture note ──────────────────────────────────────────────── */}
        <section>
          <div className="rounded-2xl p-6 border border-[#1e2a45]" style={{ background: '#0f1629' }}>
            <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-[#f0b429]" />
              How GreenCore deploys
            </h2>
            <p className="text-sm text-gray-400 leading-relaxed">{plan.architecture_note}</p>
          </div>
        </section>

        {/* ── Roadmap ────────────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-6">Implementation Roadmap</h2>
          <div className="rounded-2xl p-8 border border-[#1e2a45]" style={{ background: '#0f1629' }}>
            {plan.roadmap.map((item, i) => (
              <RoadmapItem key={i} item={item} index={i} total={plan.roadmap.length} />
            ))}
          </div>
        </section>

        {/* ── Bottom buttons ─────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4">
          <button
            onClick={onNavigateDashboard}
            className="flex items-center justify-center gap-2 px-8 py-3 rounded-xl text-sm font-bold bg-[#f0b429] text-black hover:bg-[#f0b429]/90 shadow-[0_0_20px_rgba(240,180,41,0.25)] hover:scale-[1.02] transition-all"
          >
            View Live Dashboard
            <ArrowRight size={16} />
          </button>
          <button
            onClick={onReconfigure}
            className="flex items-center justify-center gap-2 px-8 py-3 rounded-xl text-sm font-medium border border-[#1e2a45] text-gray-400 hover:text-white hover:border-gray-500 transition-all"
          >
            <RefreshCcw size={14} />
            Reconfigure
          </button>
        </div>
      </div>
    </div>
  );
}
