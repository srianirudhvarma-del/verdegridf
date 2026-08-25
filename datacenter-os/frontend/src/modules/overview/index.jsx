import React, { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getSnapshot as getIdle } from '../../data/mock/serverCluster';
import { getSnapshot as getWater } from '../../data/mock/waterFlow';
import { getSnapshot as getNetwork } from '../../data/mock/networkTraffic';
import { getSnapshot as getThermal } from '../../data/mock/thermalSensors';
import ModuleHeader from '../../components/shared/ModuleHeader';
import { Bot, AlertTriangle } from 'lucide-react';

const MODULE_RELEVANCE = {
  "Reduce electricity costs": ["idlehunter", "carbonclock"],
  "Prevent cooling failures / downtime": ["thermaltrace", "waterwatch"],
  "Carbon reporting / ESG compliance": ["carbonclock"],
  "Improve visibility into what's happening": ["idlehunter", "thermaltrace", "waterwatch", "lightspeed"],
  "Automate manual monitoring tasks": ["idlehunter", "lightspeed"],
  "Meet regulatory requirements": ["carbonclock", "waterwatch"],
};

function useRecommendedModules() {
  return useMemo(() => {
    try {
      const raw = localStorage.getItem('greencore_facility_profile');
      if (!raw) return new Set();
      const profile = JSON.parse(raw);
      const goals = profile.goals || [];
      const recommended = new Set();
      goals.forEach(goal => (MODULE_RELEVANCE[goal] || []).forEach(m => recommended.add(m)));
      return recommended;
    } catch { return new Set(); }
  }, []);
}

// ─── Module card definitions ──────────────────────────────────────────────

function ModuleCards({ onNavigate, zombieCount, energySaved, wue, leaks, globalCarbonIntensity, isDeferralActive, maxInlet, hotspotsCount, maxUtil, recommended }) {

  const ALL_CARDS = [
    {
      id: 'idlehunter',
      label: '01. IdleHunter',
      color: 'text-accent-gold',
      content: (
        <div className="space-y-4">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Unused Servers</div>
            <div className={`text-4xl font-mono ${zombieCount > 5 ? 'text-accent-red' : 'text-white'}`}>{zombieCount}</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Energy Saved</div>
            <div className="text-accent-green text-xl font-mono">{(energySaved/1000).toFixed(2)} MWh</div>
          </div>
        </div>
      ),
    },
    {
      id: 'waterwatch',
      label: '02. WaterWatch',
      color: 'text-[#00E5FF]',
      content: (
        <div className="space-y-4">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Water Usage</div>
            <div className={`text-4xl font-mono ${wue > 2.0 ? 'text-accent-red' : 'text-white'}`}>{wue.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Leak Status</div>
            <div className={`text-xl font-mono ${leaks > 0 ? 'text-accent-red' : 'text-gray-400'}`}>{leaks > 0 ? 'LEAK FOUND' : 'Normal'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'carbonclock',
      label: '03. CarbonClock',
      color: 'text-accent-green',
      extraClass: isDeferralActive ? 'border-alert-orange/50 shadow-[0_0_15px_rgba(255,165,0,0.2)]' : '',
      content: (
        <div className="space-y-4">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Carbon Output</div>
            <div className={`text-4xl font-mono ${isDeferralActive ? 'text-alert-orange' : 'text-white'}`}>
              {Math.round(globalCarbonIntensity)} <span className="text-xs text-gray-400">g/kWh</span>
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Background Tasks</div>
            {isDeferralActive ? (
              <div className="text-alert-orange font-mono text-[11px] uppercase tracking-wider bg-alert-orange/10 inline-block px-1 rounded">Paused for Energy</div>
            ) : (
              <div className="text-accent-green font-mono text-[11px] uppercase tracking-wider">Running Normal</div>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'thermaltrace',
      label: '04. ThermalTrace',
      color: 'text-accent-red',
      content: (
        <div className="space-y-4">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Hottest Server</div>
            <div className={`text-4xl font-mono ${maxInlet > 32 ? 'text-accent-red' : 'text-white'}`}>{maxInlet.toFixed(1)}°C</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Cooling Status</div>
            <div className={`text-xl font-mono ${hotspotsCount > 0 ? 'text-accent-red' : 'text-accent-green/80'}`}>{hotspotsCount > 0 ? 'Hot Air Found' : 'Good'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'lightspeed',
      label: '05. LightSpeed',
      color: 'text-accent-violet',
      content: (
        <div className="space-y-4">
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Internet Traffic</div>
            <div className={`text-4xl font-mono ${maxUtil > 80 ? 'text-alert-orange' : 'text-white'}`}>{maxUtil.toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-gray-400 text-[10px] uppercase tracking-widest mb-1 opacity-80">Traffic Status</div>
            <div className="text-accent-violet/80 font-mono text-[11px] uppercase tracking-wider">Flowing Normal</div>
          </div>
        </div>
      ),
    },
  ];

  const recCards = ALL_CARDS.filter(c => recommended.has(c.id));
  const otherCards = ALL_CARDS.filter(c => !recommended.has(c.id));
  const hasProfile = recommended.size > 0;

  const CardEl = ({ card }) => (
    <div
      onClick={() => onNavigate(card.id)}
      className={`glass-panel group p-6 rounded-2xl cursor-pointer hover:bg-white/[0.05] transition-all duration-500 ${card.extraClass || ''}`}
    >
      <div className={`${card.color} font-bold mb-6 uppercase tracking-wider text-xs opacity-70`}>{card.label}</div>
      {card.content}
    </div>
  );

  if (!hasProfile) {
    // No profile: show all equally
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
        {ALL_CARDS.map(card => <CardEl key={card.id} card={card} />)}
      </div>
    );
  }

  return (
    <div className="mb-8 space-y-6">
      {recCards.length > 0 && (
        <>
          <h2 className="text-base font-semibold" style={{ color: '#f0b429' }}>Recommended for your facility</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {recCards.map(card => <CardEl key={card.id} card={card} />)}
          </div>
        </>
      )}
      {otherCards.length > 0 && (
        <>
          <h2 className="text-sm font-medium text-gray-500 mt-4">All monitoring modules</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {otherCards.map(card => <CardEl key={card.id} card={card} />)}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Main Overview ────────────────────────────────────────────────────────

export default function Overview({ onNavigate, globalCarbonIntensity, setGlobalCarbonIntensity, isDeferralActive, setIsDeferralActive }) {
  const recommended = useRecommendedModules();
  const [stamp, setStamp] = useState(0);

  useEffect(() => {
    const i = setInterval(() => {
      setStamp(Date.now());
      if (globalCarbonIntensity < 400 && !isDeferralActive) {
        setGlobalCarbonIntensity(prev => Math.max(150, prev + (Math.random() - 0.5) * 5));
      }
    }, 2000);
    return () => clearInterval(i);
  }, [globalCarbonIntensity, isDeferralActive]);

  useEffect(() => {
    if (globalCarbonIntensity > 450 && !isDeferralActive) setIsDeferralActive(true);
    else if (globalCarbonIntensity < 400 && isDeferralActive) setIsDeferralActive(false);
  }, [globalCarbonIntensity, isDeferralActive]);

  const idleData = getIdle();
  const waterData = getWater();
  const networkData = getNetwork();
  const thermalData = getThermal();

  const zombieCount = idleData.servers.filter(s => s.state === 'zombie').length;
  const wue = waterData.wue;
  const leaks = waterData.anomalies.length;
  const maxInlet = Math.max(...thermalData.grid.flat().map(c => c.inlet_temp));
  const hotspotsCount = thermalData.grid.flat().filter(c => c.inlet_temp > 32).length;
  const maxUtil = Math.max(...networkData.links.map(l => l.utilization_pct));

  const [energySaved, setEnergySaved] = useState(14022.45);
  const [co2Avoided, setCo2Avoided] = useState(250.31);

  useEffect(() => {
    const iv = setInterval(() => {
      setEnergySaved(prev => prev + (zombieCount * 200 * 0.0001));
      setCo2Avoided(prev => prev + 0.01);
    }, 1000);
    return () => clearInterval(iv);
  }, [zombieCount]);

  const handleSimulateSpike = () => setGlobalCarbonIntensity(480);
  const handleReturnNormal = () => setGlobalCarbonIntensity(245);

  return (
    <div className="animate-in fade-in duration-500 space-y-6">
      <div className="flex items-center justify-between">
        <ModuleHeader title="Dashboard" subtitle="Simple overview of your datacenter features." />
        <div className="flex space-x-2">
          <button onClick={handleReturnNormal} className="bg-white/5 border border-white/10 px-4 py-2 rounded-lg text-sm hover:bg-white/10">
            Reset Carbon
          </button>
          <button onClick={handleSimulateSpike} className="bg-alert-orange text-black px-4 py-2 rounded-lg text-sm font-semibold hover:bg-alert-orange/90 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4" />
            <span>Simulate Carbon Spike</span>
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isDeferralActive && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-alert-orange/10 border border-alert-orange/30 p-4 rounded-xl flex items-start space-x-4"
          >
            <div className="p-2 bg-alert-orange/20 rounded-full">
              <Bot className="w-6 h-6 text-alert-orange" />
            </div>
            <div>
              <h3 className="text-alert-orange font-bold text-lg mb-1">MODE: CARBON DEFERRAL ACTIVE</h3>
              <p className="text-gray-300 text-sm">
                <strong>AI Agent:</strong> "Carbon output has exceeded 450 g/kWh. I am deferring background analytics to optimize for the green energy window."
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Module cards — personalized order */}
      <ModuleCards
        onNavigate={onNavigate}
        zombieCount={zombieCount}
        energySaved={energySaved}
        wue={wue}
        leaks={leaks}
        globalCarbonIntensity={globalCarbonIntensity}
        isDeferralActive={isDeferralActive}
        maxInlet={maxInlet}
        hotspotsCount={hotspotsCount}
        maxUtil={maxUtil}
        recommended={recommended}
      />

      {/* Background jobs */}
      <div className="bg-card-bg/30 backdrop-blur-md rounded-xl border border-white/5 p-6 mb-8">
        <h3 className="text-white font-medium mb-4">Background Data Jobs</h3>
        <div className="space-y-4">
          <div className={`transition-all duration-500 ${isDeferralActive ? 'opacity-30 grayscale' : 'opacity-100'}`}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-300">Daily Log Backup</span>
              <span className="text-gray-400">{isDeferralActive ? 'Paused' : '45%'}</span>
            </div>
            <div className="h-2 bg-black/50 rounded-full overflow-hidden">
              <motion.div className="h-full bg-accent-blue" animate={{ width: isDeferralActive ? '45%' : ['45%', '100%'] }} transition={{ duration: 10, repeat: isDeferralActive ? 0 : Infinity }} />
            </div>
          </div>
          <div className={`transition-all duration-500 ${isDeferralActive ? 'opacity-30 grayscale' : 'opacity-100'}`}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-300">Analytics Number Crunching</span>
              <span className="text-gray-400">{isDeferralActive ? 'Paused' : '82%'}</span>
            </div>
            <div className="h-2 bg-black/50 rounded-full overflow-hidden">
              <motion.div className="h-full bg-accent-blue" animate={{ width: isDeferralActive ? '82%' : ['82%', '100%'] }} transition={{ duration: 5, repeat: isDeferralActive ? 0 : Infinity }} />
            </div>
          </div>
        </div>
      </div>

      <div className="glass-panel group rounded-[24px] p-8 flex flex-col md:flex-row justify-between items-center relative overflow-hidden">
        <div className="p-4 w-full relative z-10 transition-transform hover:scale-105 duration-700">
          <div className="text-gray-400 text-xs font-bold tracking-widest mb-2 opacity-80 uppercase">Total Energy Saved</div>
          <div className="text-5xl lg:text-7xl font-mono text-white">
            {energySaved.toFixed(1)} <span className="text-lg lg:text-xl text-accent-green ml-2">kWh</span>
          </div>
        </div>
        <div className="p-4 w-full relative z-10 transition-transform hover:scale-105 duration-700 text-right">
          <div className="text-gray-400 text-xs font-bold tracking-widest mb-2 opacity-80 uppercase">Total CO₂ Saved</div>
          <div className="text-5xl lg:text-7xl font-mono text-white">
            {co2Avoided.toFixed(2)} <span className="text-lg lg:text-xl text-accent-cyan ml-2">kg</span>
          </div>
        </div>
      </div>
    </div>
  );
}
