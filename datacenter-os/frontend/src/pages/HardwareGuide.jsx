import React, { useState, useMemo } from 'react';
import { SETUP_INSTRUCTIONS, getRelevantInstructions } from '../data/setupInstructions';
import AIAgent from '../components/shared/AIAgent';
import { Check, ChevronDown, ChevronUp, Copy, CheckCheck } from 'lucide-react';

// ─── Difficulty badge ─────────────────────────────────────────────────────

const DIFF_COLORS = {
  Easy:   { bg: 'rgba(16,185,129,0.12)', color: '#10b981', border: 'rgba(16,185,129,0.3)' },
  Medium: { bg: 'rgba(251,191,36,0.12)', color: '#f0b429', border: 'rgba(240,180,41,0.3)' },
  Hard:   { bg: 'rgba(239,68,68,0.12)',  color: '#ef4444', border: 'rgba(239,68,68,0.3)' },
};

function DiffBadge({ level }) {
  const c = DIFF_COLORS[level] || DIFF_COLORS.Easy;
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>
      {level}
    </span>
  );
}

const MODULE_COLORS = {
  IDLEhunter: '#f0b429', WaterWatch: '#00E5FF', ThermalTrace: '#ef4444',
  LightSpeed: '#8B5CF6', CarbonClock: '#10b981', PowerWatch: '#f97316',
};

function ModuleBadge({ module }) {
  const base = module.split(' ')[0];
  const color = MODULE_COLORS[base] || '#94a3b8';
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}>
      {module}
    </span>
  );
}

// ─── Code block with copy button ──────────────────────────────────────────

function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="relative rounded-xl overflow-hidden mt-3" style={{ background: '#060a14', border: '1px solid #1e2a45' }}>
      <button
        onClick={copy}
        className="absolute top-3 right-3 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-all"
        style={{ background: '#1e2a45', color: '#94a3b8' }}
        onMouseEnter={e => e.currentTarget.style.color = '#fff'}
        onMouseLeave={e => e.currentTarget.style.color = '#94a3b8'}
      >
        {copied ? <CheckCheck size={12} color="#10b981" /> : <Copy size={12} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="p-5 pt-4 text-[13px] text-gray-300 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap">
        {code}
      </pre>
    </div>
  );
}

// ─── Verify section (expandable) ─────────────────────────────────────────

function VerifySection({ text }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-xs font-semibold text-green-400 hover:text-green-300 transition-colors"
      >
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        How to verify this step
      </button>
      {open && (
        <div className="mt-2 p-3 rounded-lg text-sm text-gray-400 leading-relaxed"
          style={{ background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.2)' }}>
          {text}
        </div>
      )}
    </div>
  );
}

// ─── Step instruction card ────────────────────────────────────────────────

function StepCard({ step }) {
  return (
    <div className="rounded-xl p-6" style={{ background: '#0f1629', border: '1px solid #1e2a45' }}>
      <div className="flex items-start gap-4">
        <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold text-black mt-0.5"
          style={{ background: '#f0b429' }}>
          {step.step}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-base font-bold text-white mb-2">{step.title}</p>
          <p className="text-sm text-gray-400 leading-relaxed">{step.detail}</p>
          {step.command && <CodeBlock code={step.command} />}
          {step.verify && <VerifySection text={step.verify} />}
        </div>
      </div>
    </div>
  );
}

// ─── Device list item ─────────────────────────────────────────────────────

function DeviceListItem({ name, instruction, isSelected, isRelevant, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 rounded-xl transition-all duration-200"
      style={{
        background: isSelected ? 'rgba(240,180,41,0.08)' : '#0f1629',
        border: `1.5px solid ${isSelected ? '#f0b429' : isRelevant ? 'rgba(240,180,41,0.3)' : '#1e2a45'}`,
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-sm font-semibold text-white leading-snug">{name}</span>
        {isRelevant && !isSelected && (
          <span className="flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded text-yellow-400"
            style={{ background: 'rgba(240,180,41,0.1)', border: '1px solid rgba(240,180,41,0.2)' }}>
            YOUR SETUP
          </span>
        )}
      </div>
      <ModuleBadge module={instruction.module} />
      <div className="flex items-center gap-3 mt-2">
        <span className="text-xs text-gray-500">{instruction.estimated_time}</span>
        <DiffBadge level={instruction.difficulty} />
      </div>
    </button>
  );
}

// ─── Grouped device categories for sidebar list ───────────────────────────

const DEVICE_GROUPS = [
  { label: 'Servers', keys: ['Dell PowerEdge (iDRAC)', 'HPE ProLiant (iLO)', 'Supermicro (IPMI)', 'Whitebox / Custom built', 'Raspberry Pi (psutil agent)'] },
  { label: 'Network', keys: ['Cisco switch (SNMP)', 'ESP32 (network + thermal node)'] },
  { label: 'Cooling & Sensors', keys: ['Liebert/Vertiv CRAC (Modbus)', 'YF-S201 Water Flow Sensor'] },
  { label: 'Power', keys: ['APC UPS (Network Management Card)'] },
];

// ─── Main HardwareGuide page ──────────────────────────────────────────────

export default function HardwareGuide() {
  const facilityProfile = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('greencore_facility_profile') || '{}'); } catch { return {}; }
  }, []);

  const relevantDevices = useMemo(() => new Set(getRelevantInstructions(facilityProfile)), [facilityProfile]);

  // Default to first relevant device or first in list
  const defaultDevice = relevantDevices.size > 0
    ? [...relevantDevices][0]
    : Object.keys(SETUP_INSTRUCTIONS)[0];

  const [selectedDevice, setSelectedDevice] = useState(defaultDevice);
  const instruction = SETUP_INSTRUCTIONS[selectedDevice];

  const hardwareSystemPrompt = instruction ? `You are GreenCore's hardware integration expert.
You are helping a user set up their datacenter monitoring hardware.

Currently viewing setup guide for: ${selectedDevice}
This device enables: ${instruction.module}

User's facility profile:
${JSON.stringify(facilityProfile, null, 2)}

Your role:
- Answer specific technical questions about this hardware integration
- Help troubleshoot if something isn't working
- Explain what each step does in plain language
- Suggest workarounds if the user has a different model or version
- If the user is stuck, walk them through debugging step by step
- Format all commands in code blocks
- Be specific — include actual IP addresses or values from their profile where known` : '';

  const suggestedQuestions = [
    `What if my ${selectedDevice?.split(' ')[0]} is a different model?`,
    "I ran the command but got an error",
    "How do I find my device's IP address?",
    "Is there a simpler alternative to this?",
    "What if I don't have admin access?",
  ];

  return (
    <div className="animate-in fade-in duration-500">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2" style={{ color: '#f0b429' }}>Hardware Setup Guide</h1>
        <p className="text-gray-400 text-sm">Step-by-step integration instructions for your selected hardware</p>
      </div>

      <div className="flex gap-8">
        {/* ── LEFT: Device list (30%) ─────────────────────────────────── */}
        <div className="w-72 flex-shrink-0 space-y-6 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 160px)' }}>

          {/* "Your setup" section */}
          {relevantDevices.size > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-yellow-400 mb-3 px-1">Your Setup</p>
              <div className="space-y-2">
                {[...relevantDevices].filter(k => SETUP_INSTRUCTIONS[k]).map(key => (
                  <DeviceListItem
                    key={key}
                    name={key}
                    instruction={SETUP_INSTRUCTIONS[key]}
                    isSelected={selectedDevice === key}
                    isRelevant={true}
                    onClick={() => setSelectedDevice(key)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* All other integrations */}
          {DEVICE_GROUPS.map(group => {
            const validKeys = group.keys.filter(k => SETUP_INSTRUCTIONS[k] && !relevantDevices.has(k));
            if (!validKeys.length) return null;
            return (
              <div key={group.label}>
                <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3 px-1">{group.label}</p>
                <div className="space-y-2">
                  {validKeys.map(key => (
                    <DeviceListItem
                      key={key}
                      name={key}
                      instruction={SETUP_INSTRUCTIONS[key]}
                      isSelected={selectedDevice === key}
                      isRelevant={false}
                      onClick={() => setSelectedDevice(key)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── RIGHT: Instructions (70%) ──────────────────────────────── */}
        <div className="flex-1 min-w-0 space-y-6 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 160px)' }}>
          {instruction ? (
            <>
              {/* Device header */}
              <div className="rounded-2xl p-6" style={{ background: '#0f1629', border: '1px solid #1e2a45' }}>
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-white mb-2">{selectedDevice}</h2>
                    <div className="flex items-center gap-3 flex-wrap">
                      <ModuleBadge module={instruction.module} />
                      <DiffBadge level={instruction.difficulty} />
                      <span className="text-xs text-gray-500">⏱ {instruction.estimated_time}</span>
                    </div>
                  </div>
                </div>

                {instruction.prerequisites?.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3">Before you start</p>
                    <ul className="space-y-2">
                      {instruction.prerequisites.map((p, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                          <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                            style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)' }}>
                            <Check size={9} color="#10b981" strokeWidth={3} />
                          </div>
                          {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Steps */}
              <div className="space-y-4">
                {instruction.steps.map(step => (
                  <StepCard key={step.step} step={step} />
                ))}
              </div>

              {/* AI Advisor */}
              <div className="mt-6">
                <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3">Ask the AI Integration Expert</p>
                <AIAgent
                  systemPrompt={hardwareSystemPrompt}
                  context={{ selectedDevice, facilityProfile }}
                  suggestedQuestions={suggestedQuestions}
                  compact={false}
                />
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Select a device from the list
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
