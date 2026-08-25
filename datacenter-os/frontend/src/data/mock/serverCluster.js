import { createMockGenerator } from './generator';

// 50 internal server objects
const initServers = Array.from({ length: 50 }, (_, i) => {
  const isZombie = Math.random() < 0.15; // ~7-10 servers
  return {
    id: `S-${(i + 1).toString().padStart(3, '0')}`,
    rack: `rack${Math.floor(i / 10) + 1}`,
    cpu_util: isZombie ? Math.random() * 10 : 30 + Math.random() * 60,
    ram_util: isZombie ? Math.random() * 15 : 40 + Math.random() * 50,
    watts_idle: 200,
    watts_active: 400,
    state: isZombie ? 'zombie' : 'active'
  };
});

function applyServerDrift(servers) {
  return servers.map(s => {
    if (s.state === 'sleep') return s;
    
    // Gaussian-like noise
    const cpuDrift = (Math.random() + Math.random() + Math.random() - 1.5) * 5;
    const ramDrift = (Math.random() + Math.random() + Math.random() - 1.5) * 5;
    
    let newCpu = Math.max(0, Math.min(100, s.cpu_util + cpuDrift));
    let newRam = Math.max(0, Math.min(100, s.ram_util + ramDrift));
    
    // Re-evaluate zombie strictly below 15 CPU and 20 RAM
    // In our algorithm, we evaluate on client side usually, but the mock keeps it consistent
    let newState = s.state;
    if (s.state !== 'zombie' && newCpu < 15 && newRam < 20) {
      newState = 'zombie';
    } else if (s.state === 'zombie' && (newCpu >= 15 || newRam >= 20)) {
      // Force it back down to keep the zombie state if it was a zombie, 
      // or let it wake up occasionally.
      if (Math.random() > 0.1) {
        newCpu = Math.min(14, newCpu);
        newRam = Math.min(19, newRam);
      } else {
        newState = 'active';
      }
    }
    
    return { ...s, cpu_util: newCpu, ram_util: newRam, state: newState };
  });
}

const serverClusterLogic = createMockGenerator(
  { servers: initServers, is_live: false },
  (state) => ({ servers: applyServerDrift(state.servers), is_live: false })
);

export const getSnapshot = () => serverClusterLogic.getSnapshot();
export const subscribe = (callback, intervalMs = 3000) => serverClusterLogic.subscribe(callback, intervalMs);

// Helper exposed for Auto-Consolidate feature mutation
export const performConsolidation = (serverId) => {
  const current = serverClusterLogic.getSnapshot();
  const updated = current.servers.map(s => 
    s.id === serverId ? { ...s, state: 'sleep', cpu_util: 0, ram_util: 0 } : s
  );
  // Pick least loaded active server to migrate load conceptually
  const activeServers = updated.filter(s => s.state === 'active').sort((a,b) => a.cpu_util - b.cpu_util);
  if (activeServers.length > 0) {
     activeServers[0].cpu_util = Math.min(100, activeServers[0].cpu_util + 10);
     activeServers[0].ram_util = Math.min(100, activeServers[0].ram_util + 10);
  }
  serverClusterLogic.forceUpdate({ servers: updated, is_live: false });
}
