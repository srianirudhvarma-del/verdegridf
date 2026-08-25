import React, { useState, useMemo } from 'react';
import Navigation from './components/shared/Navigation';
import AIAgent from './components/shared/AIAgent';
import Onboarding from './pages/Onboarding';
import DeploymentPlan from './pages/DeploymentPlan';
import HardwareGuide from './pages/HardwareGuide';
import Overview from './modules/overview';
import IdleHunter from './modules/idlehunter';
import WaterWatch from './modules/waterwatch';
import CarbonClock from './modules/carbonclock';
import ThermalTrace from './modules/thermaltrace';
import LightSpeed from './modules/lightspeed';
import { getSnapshot as getIdle } from './data/mock/serverCluster';
import { getSnapshot as getWater } from './data/mock/waterFlow';
import { getSnapshot as getNetwork } from './data/mock/networkTraffic';
import { getSnapshot as getThermal } from './data/mock/thermalSensors';
import './index.css';

// ─── Facility profile helper ──────────────────────────────────────────────

function getProfile() {
  try { return JSON.parse(localStorage.getItem('greencore_facility_profile') || '{}'); }
  catch { return {}; }
}

function hasProfile() {
  try { return !!localStorage.getItem('greencore_facility_profile'); }
  catch { return false; }
}

// ─── Per-module dashboard AI prompts ─────────────────────────────────────

const MODULE_SUGGESTED_QUESTIONS = {
  idlehunter:   ["How much am I wasting on zombie servers?", "Which servers should I consolidate first?", "What's my projected savings this month?"],
  waterwatch:   ["Is my WUE reading dangerous?", "Which cooling unit is most inefficient?", "What does this leak alert mean?"],
  carbonclock:  ["When is the next clean grid window?", "Which jobs should I defer right now?", "How much CO2 have I saved this session?"],
  thermaltrace: ["Is this hotspot dangerous?", "Which rack needs attention most urgently?", "What caused this temperature spike?"],
  lightspeed:   ["Which link is about to become a bottleneck?", "Should I reroute this traffic manually?", "What does 87% utilization mean for latency?"],
  overview:     ["What are my biggest savings opportunities?", "Which module should I focus on first?", "How is my facility performing overall?"],
};

function getDashboardSystemPrompt(activeModule, facilityProfile) {
  let moduleData = {};
  try {
    switch (activeModule) {
      case 'idlehunter': { const d = getIdle(); moduleData = { zombie_count: d.servers.filter(s => s.state === 'zombie').length, total_servers: d.servers.length, avg_cpu: (d.servers.reduce((a, b) => a + b.cpu_util, 0) / d.servers.length).toFixed(1) }; break; }
      case 'waterwatch': { const d = getWater(); moduleData = { wue: d.wue?.toFixed(2), total_flow: Math.round(d.totalFlow), anomalies: d.anomalies.length, unit_count: d.units?.length }; break; }
      case 'thermaltrace': { const d = getThermal(); const flat = d.grid.flat(); moduleData = { max_inlet_temp: Math.max(...flat.map(c => c.inlet_temp)).toFixed(1), avg_inlet_temp: (flat.reduce((a, c) => a + c.inlet_temp, 0) / flat.length).toFixed(1), hotspots: flat.filter(c => c.inlet_temp > 32).length }; break; }
      case 'lightspeed': { const d = getNetwork(); moduleData = { max_utilization: Math.max(...d.links.map(l => l.utilization_pct)).toFixed(1), bottleneck_links: d.links.filter(l => l.utilization_pct > 80).length, total_links: d.links.length }; break; }
      default: moduleData = {};
    }
  } catch {}

  return `You are GreenCore's datacenter intelligence assistant. You have full context of this facility's monitoring data.

Facility: ${facilityProfile?.facility_name || 'Unknown'}
Active module: ${activeModule}
Current module data: ${JSON.stringify(moduleData, null, 2)}

Facility profile: ${JSON.stringify(facilityProfile, null, 2)}

Your role:
- Answer questions about what the data means
- Explain alerts in plain language
- Suggest specific actions to take
- Calculate savings opportunities
- Be conversational but precise
- Always ground answers in the actual numbers shown in the current module data

AGENTIC CAPABILITIES:
You can interpret trends and anomalies.
You can calculate projections based on current readings.
If asked "what should I do about X", give a specific 3-step action plan.
If asked about hardware, mention the Hardware Setup Guide for relevant devices.`;
}

// ─── App ──────────────────────────────────────────────────────────────────

function App() {
  const [activeTab, setActiveTab] = useState(hasProfile() ? 'overview' : 'onboarding');
  const [globalCarbonIntensity, setGlobalCarbonIntensity] = useState(245);
  const [isDeferralActive, setIsDeferralActive] = useState(false);

  const facilityProfile = useMemo(() => getProfile(), [activeTab]);

  const handleOnboardingComplete = () => setActiveTab('plan');
  const handleReconfigure = () => {
    try { localStorage.removeItem('greencore_facility_profile'); } catch {}
    setActiveTab('onboarding');
  };

  const dashboardSystemPrompt = useMemo(
    () => getDashboardSystemPrompt(activeTab, facilityProfile),
    [activeTab, facilityProfile]
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'onboarding': return <Onboarding onComplete={handleOnboardingComplete} />;
      case 'plan': return <DeploymentPlan onNavigateDashboard={() => setActiveTab('overview')} onReconfigure={handleReconfigure} />;
      case 'hardware-guide': return <HardwareGuide />;
      case 'idlehunter': return <IdleHunter />;
      case 'waterwatch': return <WaterWatch />;
      case 'carbonclock': return <CarbonClock />;
      case 'thermaltrace': return <ThermalTrace />;
      case 'lightspeed': return <LightSpeed isDeferralActive={isDeferralActive} />;
      case 'overview':
      default:
        return (
          <Overview
            onNavigate={setActiveTab}
            globalCarbonIntensity={globalCarbonIntensity}
            setGlobalCarbonIntensity={setGlobalCarbonIntensity}
            isDeferralActive={isDeferralActive}
            setIsDeferralActive={setIsDeferralActive}
          />
        );
    }
  };

  // Full-screen pages (no sidebar)
  if (activeTab === 'onboarding' || activeTab === 'plan') {
    return renderContent();
  }

  return (
    <div className="min-h-screen bg-background text-textMain flex font-sans selection:bg-accent-green selection:text-black transition-colors duration-500">
      <Navigation
        active={activeTab}
        onNavigate={setActiveTab}
        onReconfigure={handleReconfigure}
      />

      <main className="flex-1 lg:ml-64 min-h-screen relative overflow-x-hidden pb-32 lg:pb-8">
        <div className="fixed top-[-10%] right-[-10%] w-[50%] h-[50%] bg-accent-violet/5 blur-[120px] rounded-full pointer-events-none" />
        <div className="fixed bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-accent-green/5 blur-[100px] rounded-full pointer-events-none" />

        <div className="max-w-[1400px] mx-auto w-full p-8 relative z-10">
          {renderContent()}
        </div>
      </main>

      {/* Floating AI assistant — visible on all dashboard pages */}
      <AIAgent
        key={activeTab} // remount when switching modules so suggested questions refresh
        systemPrompt={dashboardSystemPrompt}
        context={facilityProfile}
        suggestedQuestions={MODULE_SUGGESTED_QUESTIONS[activeTab] || MODULE_SUGGESTED_QUESTIONS.overview}
        compact={true}
      />
    </div>
  );
}

export default App;
