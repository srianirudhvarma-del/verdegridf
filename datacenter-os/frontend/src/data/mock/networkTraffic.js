import { createMockGenerator } from './generator';

const NODES = Array.from({length: 8}, (_,i) => `Node${i+1}`);
const LINKS = [];
for (let i = 0; i < NODES.length; i++) {
  // Connect to next 2 nodes to create a mesh ring
  LINKS.push({ source: NODES[i], target: NODES[(i+1)%8], capacity_gbps: 100, utilization_pct: 30 + Math.random()*20 });
  LINKS.push({ source: NODES[i], target: NODES[(i+2)%8], capacity_gbps: 100, utilization_pct: 20 + Math.random()*20 });
}

function applyNetworkDrift(links) {
  // Drift
  let newLinks = links.map(l => {
    let drift = (Math.random() - 0.5) * 8;
    return { ...l, utilization_pct: Math.max(10, Math.min(100, l.utilization_pct + drift)) };
  });

  // Random spike
  if (Math.random() < 0.1) {
    const spikeIdx = Math.floor(Math.random() * newLinks.length);
    newLinks[spikeIdx].utilization_pct = 86 + Math.random() * 10;
  }

  // Max-flow heuristic rerouting logic (auto triggers when > 80%)
  const bottleneck = newLinks.find(l => l.utilization_pct > 80);
  if (bottleneck) {
    const excess = bottleneck.utilization_pct - 70;
    bottleneck.utilization_pct = 70; // relieved
    // Distribute proportionally to parallel paths (random other links for mock)
    const otherLinks = newLinks.filter(l => l !== bottleneck);
    for (let i=0; i<3; i++) {
      otherLinks[Math.floor(Math.random() * otherLinks.length)].utilization_pct += (excess / 3);
    }
  }

  return newLinks.map(l => ({...l, utilization_pct: Math.min(100, l.utilization_pct)}));
}

const networkLogic = createMockGenerator(
  { nodes: NODES, links: LINKS, is_live: false },
  (state) => ({ nodes: NODES, links: applyNetworkDrift(state.links), is_live: false })
);

export const getSnapshot = () => networkLogic.getSnapshot();
export const subscribe = (callback, intervalMs = 4000) => networkLogic.subscribe(callback, intervalMs);

export const injectSpike = () => {
  const current = networkLogic.getSnapshot();
  const links = [...current.links];
  const spikeIdx = Math.floor(Math.random() * links.length);
  links[spikeIdx] = { ...links[spikeIdx], utilization_pct: 95 };
  networkLogic.forceUpdate({ ...current, links });
}
