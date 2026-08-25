import React, { useState, useRef } from 'react';
import { ArrowRight, ArrowLeft, Check } from 'lucide-react';
import AIAgent from '../components/shared/AIAgent';
import { EQUIPMENT_CATALOG } from '../data/equipmentCatalog';

// ─── Catalog summary for AI context ──────────────────────────────────────

const EQUIPMENT_CATALOG_SUMMARY = {
  servers: Object.keys(EQUIPMENT_CATALOG.servers),
  cooling: Object.keys(EQUIPMENT_CATALOG.cooling),
  network: Object.keys(EQUIPMENT_CATALOG.network),
};

const STEP_TOPICS = [
  'Facility Overview',
  'Server Infrastructure',
  'Cooling Infrastructure',
  'Network Infrastructure',
  'Goals & Budget',
];

const SUGGESTED_QUESTIONS = [
  ["What rack count fits my electricity bill?", "Does facility size affect which modules I need?", "What's a typical bill for a 50-rack facility?"],
  ["What if I have mixed server vendors?", "Do I need IPMI cards for older servers?", "Which server type gives the most monitoring data?"],
  ["What if my CRAC units aren't networked?", "Is BACnet required for WaterWatch to work?", "Can I still monitor cooling without smart units?"],
  ["How do I check if my switches support SNMP?", "What's the difference between SNMP and gNMI?", "Can I use LightSpeed with unmanaged switches?"],
  ["Which goal gives fastest ROI?", "What budget do you recommend for my setup?", "Should I go recommendations-only or automated?"],
];

// ─── Step config ──────────────────────────────────────────────────────────

const STEPS = [
  { id: 'facility', title: "Tell us about your facility" },
  { id: 'servers', title: "What servers are you running?" },
  { id: 'cooling', title: "How is your facility cooled?" },
  { id: 'network', title: "What network gear are you running?" },
  { id: 'goals', title: "What matters most to you?" },
];

const INITIAL_PROFILE = {
  facility_name: '', rack_count: '', electricity_bill: '',
  server_vendors: [], server_count: '',
  cooling_equipment: [], cooling_connectivity: '',
  switch_vendors: [], snmp_support: '',
  goals: [], budget: '', automation_preference: '',
};

// ─── Primitive components ─────────────────────────────────────────────────

function SelectCard({ options, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-3">
      {options.map(opt => {
        const sel = value === opt;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className="px-5 py-3 rounded-xl text-sm transition-all duration-200 text-left"
            style={{
              border: `1.5px solid ${sel ? '#f0b429' : '#1e2a45'}`,
              background: sel ? 'rgba(240,180,41,0.08)' : '#0f1629',
              color: sel ? '#f0b429' : '#94a3b8',
              fontWeight: sel ? 600 : 400,
            }}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function ToggleCard({ options, value = [], onChange, maxSelect }) {
  const toggle = (opt) => {
    if (value.includes(opt)) {
      onChange(value.filter(v => v !== opt));
    } else {
      if (maxSelect && value.length >= maxSelect) return;
      onChange([...value, opt]);
    }
  };
  return (
    <div className="flex flex-col gap-2.5">
      {options.map(opt => {
        const sel = value.includes(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className="flex items-center gap-3 px-4 py-3.5 rounded-xl text-sm text-left transition-all duration-200"
            style={{
              border: `1.5px solid ${sel ? '#f0b429' : '#1e2a45'}`,
              background: sel ? 'rgba(240,180,41,0.06)' : '#0f1629',
              color: sel ? '#fff' : '#94a3b8',
            }}
          >
            <div
              className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0"
              style={{ background: sel ? '#f0b429' : 'transparent', border: `1.5px solid ${sel ? '#f0b429' : '#475569'}` }}
            >
              {sel && <Check size={10} strokeWidth={3} color="#000" />}
            </div>
            {opt}
          </button>
        );
      })}
      {maxSelect && <p className="text-xs text-gray-500 mt-1">Pick up to {maxSelect}</p>}
    </div>
  );
}

function TextInput({ placeholder, value, onChange }) {
  return (
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full text-white text-sm placeholder-gray-600 outline-none"
      style={{
        background: '#0f1629',
        border: '1.5px solid #1e2a45',
        borderRadius: 10,
        padding: '12px 16px',
        transition: 'border-color 0.2s',
      }}
      onFocus={e => (e.target.style.borderColor = '#f0b429')}
      onBlur={e => (e.target.style.borderColor = '#1e2a45')}
    />
  );
}

// ─── Per-step form content ─────────────────────────────────────────────────

function StepFacility({ profile, update }) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-300">Facility name</label>
        <TextInput placeholder="e.g. Mumbai Edge DC — Rack Room B" value={profile.facility_name} onChange={v => update('facility_name', v)} />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">How many server racks?</label>
        <SelectCard options={['1–10', '10–50', '50–200', '200+']} value={profile.rack_count} onChange={v => update('rack_count', v)} />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">What is your monthly electricity bill?</label>
        <SelectCard options={['Under ₹1L', '₹1–5L', '₹5–20L', '₹20L+']} value={profile.electricity_bill} onChange={v => update('electricity_bill', v)} />
      </div>
    </div>
  );
}

function StepServers({ profile, update }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Server vendors present <span className="text-xs text-gray-500">(select all that apply)</span></label>
        <ToggleCard
          options={['Dell PowerEdge (iDRAC)', 'HPE ProLiant (iLO)', 'Cisco UCS', 'Supermicro', 'Whitebox / Custom built', 'Virtual machines only (no bare metal)', "Don't know"]}
          value={profile.server_vendors}
          onChange={v => update('server_vendors', v)}
        />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Approximate server count</label>
        <SelectCard options={['Under 20', '20–100', '100–500', '500+']} value={profile.server_count} onChange={v => update('server_count', v)} />
      </div>
    </div>
  );
}

function StepCooling({ profile, update }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Cooling equipment present <span className="text-xs text-gray-500">(select all that apply)</span></label>
        <ToggleCard
          options={['Liebert / Vertiv CRAC units', 'Schneider Electric CRAC units', 'Airedale CRAH units', 'In-row cooling units', 'Chiller plant', 'Basic split AC units', "Don't know / Not sure"]}
          value={profile.cooling_equipment}
          onChange={v => update('cooling_equipment', v)}
        />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Do your cooling units have network connectivity?</label>
        <SelectCard options={['Yes — BACnet or Modbus', 'Yes — proprietary web interface', 'No — manual only', "Don't know"]} value={profile.cooling_connectivity} onChange={v => update('cooling_connectivity', v)} />
      </div>
    </div>
  );
}

function StepNetwork({ profile, update }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Switch vendors <span className="text-xs text-gray-500">(select all that apply)</span></label>
        <ToggleCard
          options={['Cisco Catalyst / Nexus', 'Arista', 'Juniper', 'HPE / Aruba', 'Unmanaged switches only', "Don't know"]}
          value={profile.switch_vendors}
          onChange={v => update('switch_vendors', v)}
        />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Do your switches support SNMP?</label>
        <SelectCard options={['Yes', 'No', "Don't know"]} value={profile.snmp_support} onChange={v => update('snmp_support', v)} />
      </div>
    </div>
  );
}

function StepGoals({ profile, update }) {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Primary goals <span className="text-xs text-gray-500">(pick up to 3)</span></label>
        <ToggleCard
          options={['Reduce electricity costs', 'Prevent cooling failures / downtime', 'Carbon reporting / ESG compliance', "Improve visibility into what's happening", 'Automate manual monitoring tasks', 'Meet regulatory requirements']}
          value={profile.goals}
          onChange={v => update('goals', v)}
          maxSelect={3}
        />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Deployment budget for monitoring hardware</label>
        <SelectCard options={['Under ₹50,000', '₹50,000 – ₹2,00,000', '₹2,00,000 – ₹10,00,000', '₹10,00,000+', 'Not sure yet']} value={profile.budget} onChange={v => update('budget', v)} />
      </div>
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-300">Automation preference</label>
        <SelectCard options={['Recommendations only — I decide what to do', 'Semi-automated — alert me before acting', 'Fully automated — take action automatically']} value={profile.automation_preference} onChange={v => update('automation_preference', v)} />
      </div>
    </div>
  );
}

const STEP_COMPONENTS = [StepFacility, StepServers, StepCooling, StepNetwork, StepGoals];

// ─── Validation ────────────────────────────────────────────────────────────

function isStepValid(step, profile) {
  switch (step) {
    case 0: return profile.facility_name.trim().length > 0 && !!profile.rack_count && !!profile.electricity_bill;
    case 1: return profile.server_vendors.length > 0 && !!profile.server_count;
    case 2: return profile.cooling_equipment.length > 0 && !!profile.cooling_connectivity;
    case 3: return profile.switch_vendors.length > 0 && !!profile.snmp_support;
    case 4: return profile.goals.length > 0 && !!profile.budget && !!profile.automation_preference;
    default: return false;
  }
}

// ─── AI Summary panel (step 5 complete) ───────────────────────────────────

function AISummaryPanel({ profile, onConfirm }) {
  const summaryPrompt = `Based on everything the user has selected, give a 3-sentence summary of: (1) what their biggest efficiency opportunity is, (2) what the first thing they should do is, and (3) what annual savings they can realistically expect. Be specific to their choices.

User's profile:
${JSON.stringify(profile, null, 2)}`;

  return (
    <div
      className="rounded-2xl p-6 mb-6"
      style={{ background: '#0d1526', border: '1.5px solid #f0b429' }}
    >
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
        <span className="text-sm font-bold text-yellow-400 uppercase tracking-widest">AI Deployment Summary</span>
      </div>
      <AIAgent
        systemPrompt="You are GreenCore's intelligent deployment advisor. Be concise — 3 sentences maximum."
        context={profile}
        suggestedQuestions={[]}
        compact={false}
        initialMessage={summaryPrompt}
      />
      <button
        onClick={onConfirm}
        className="mt-6 w-full py-4 rounded-xl text-base font-bold flex items-center justify-center gap-3 transition-all hover:scale-[1.01]"
        style={{ background: '#f0b429', color: '#000' }}
      >
        Generate My Deployment Plan <ArrowRight size={18} />
      </button>
    </div>
  );
}

// ─── Step progress indicator ───────────────────────────────────────────────

function StepIndicator({ current, total }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-10">
      {Array.from({ length: total }, (_, i) => (
        <React.Fragment key={i}>
          <div
            className="flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold transition-all duration-300"
            style={{
              background: i < current ? '#10b981' : i === current ? '#f0b429' : 'transparent',
              border: `2px solid ${i < current ? '#10b981' : i === current ? '#f0b429' : '#1e2a45'}`,
              color: i < current || i === current ? '#000' : '#475569',
            }}
          >
            {i < current ? <Check size={14} strokeWidth={3} /> : i + 1}
          </div>
          {i < total - 1 && (
            <div
              className="h-px w-8"
              style={{ background: i < current ? '#10b981' : '#1e2a45', transition: 'background 0.4s' }}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ─── Main Onboarding component ─────────────────────────────────────────────

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState(INITIAL_PROFILE);
  const [showSummary, setShowSummary] = useState(false);
  const [slideDir, setSlideDir] = useState(1); // 1=forward -1=back
  const [animating, setAnimating] = useState(false);

  const update = (key, value) => setProfile(prev => ({ ...prev, [key]: value }));
  const valid = isStepValid(step, profile);
  const isLast = step === STEPS.length - 1;
  const StepComponent = STEP_COMPONENTS[step];

  const navigate = (dir) => {
    if (animating) return;
    setSlideDir(dir);
    setAnimating(true);
    setTimeout(() => setAnimating(false), 350);
    if (dir === 1) {
      if (!valid) return;
      if (isLast) { setShowSummary(true); return; }
      setStep(s => s + 1);
    } else {
      if (showSummary) { setShowSummary(false); return; }
      if (step > 0) setStep(s => s - 1);
    }
  };

  const handleConfirm = () => {
    const final = { ...profile, completed_at: Date.now() };
    localStorage.setItem('greencore_facility_profile', JSON.stringify(final));
    onComplete(final);
  };

  // Build AI system prompt
  const wizardSystemPrompt = `You are GreenCore's intelligent deployment advisor. You are helping a datacenter operator configure their monitoring platform.

Current wizard step: ${step + 1} of 5
Step topic: ${STEP_TOPICS[step]}

What the user has selected so far:
${JSON.stringify(profile, null, 2)}

Equipment catalog summary:
${JSON.stringify(EQUIPMENT_CATALOG_SUMMARY, null, 2)}

Your role:
- Answer questions about hardware choices
- If the user says they cannot decide on something, choose for them and explain why
- Make recommendations based on their budget, facility size, and goals selected so far
- When making a choice for the user, emit a JSON block like: {"action":"selectOption","field":"fieldName","value":"optionValue"}
- Be concise — 2-4 sentences max per response
- Always explain the ROI implication of choices
- Never recommend hardware above their stated budget tier`;

  const handleSelectOption = (field, value) => {
    if (Array.isArray(profile[field])) {
      if (!profile[field].includes(value)) {
        update(field, [...profile[field], value]);
      }
    } else {
      update(field, value);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8" style={{ background: '#0a0e1a' }}>
      {/* Background glows */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[60%] rounded-full" style={{ background: 'rgba(240,180,41,0.04)', filter: 'blur(120px)' }} />
        <div className="absolute bottom-[-20%] left-[-10%] w-[40%] h-[50%] rounded-full" style={{ background: 'rgba(16,185,129,0.04)', filter: 'blur(100px)' }} />
      </div>

      <div className="w-full max-w-[680px] relative z-10">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="flex items-center justify-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: '#f0b429', boxShadow: '0 0 20px rgba(240,180,41,0.4)' }}>
              <div className="w-4 h-4 border-2 border-black rounded-sm" />
            </div>
            <span className="text-2xl font-bold text-white tracking-tight">DatacenterOS</span>
          </div>
          <p className="text-white text-xl font-light mt-3">Let's build your deployment plan</p>
          <p className="text-gray-500 text-sm mt-1">Step {step + 1} of {STEPS.length}</p>
        </div>

        {/* Step progress indicator */}
        <StepIndicator current={step} total={STEPS.length} />

        {/* Card */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{ background: '#0f1629', border: '1px solid #1e2a45', padding: 48 }}
        >
          {/* Slide wrapper */}
          <div
            style={{
              transform: animating ? `translateX(${slideDir * -20}px)` : 'translateX(0)',
              opacity: animating ? 0 : 1,
              transition: 'transform 0.3s ease, opacity 0.3s ease',
            }}
          >
            <h2 className="text-2xl font-bold text-white mb-2">{STEPS[step].title}</h2>
            <div className="h-px mb-8" style={{ background: '#1e2a45' }} />

            {showSummary ? (
              <AISummaryPanel profile={profile} onConfirm={handleConfirm} />
            ) : (
              <>
                <StepComponent profile={profile} update={update} />

                {/* AI Advisor inline */}
                <div className="mt-8">
                  <AIAgent
                    systemPrompt={wizardSystemPrompt}
                    context={profile}
                    suggestedQuestions={SUGGESTED_QUESTIONS[step]}
                    compact={false}
                    onSelectOption={handleSelectOption}
                  />
                </div>

                {/* Navigation */}
                <div className="flex justify-between items-center mt-8 pt-6" style={{ borderTop: '1px solid #1e2a45' }}>
                  <button
                    onClick={() => navigate(-1)}
                    disabled={step === 0 && !showSummary}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ border: '1.5px solid #1e2a45' }}
                  >
                    <ArrowLeft size={16} /> Back
                  </button>
                  <button
                    onClick={() => navigate(1)}
                    disabled={!valid}
                    className="flex items-center gap-2 px-8 rounded-xl text-sm font-bold transition-all hover:scale-[1.02] disabled:cursor-not-allowed"
                    style={{
                      height: 48,
                      background: valid ? '#f0b429' : '#1e2a45',
                      color: valid ? '#000' : '#64748b',
                      boxShadow: valid ? '0 0 20px rgba(240,180,41,0.2)' : 'none',
                    }}
                  >
                    {isLast ? 'Review AI Summary' : 'Continue'} {!isLast && <ArrowRight size={16} />}
                  </button>
                </div>
              </>
            )}

            {showSummary && (
              <button
                onClick={() => navigate(-1)}
                className="mt-4 w-full py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-white transition-colors"
                style={{ border: '1.5px solid #1e2a45' }}
              >
                <ArrowLeft size={14} className="inline mr-2" /> Back to Step 5
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">
          Your answers are stored locally — no data leaves your browser until you choose to sync.
        </p>
      </div>
    </div>
  );
}
