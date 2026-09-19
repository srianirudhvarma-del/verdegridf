import { createMockGenerator } from './generator';

// 8x8 thermal grid
const GRID_SIZE = 8;
const initThermalGrid = [];
for (let r = 0; r < GRID_SIZE; r++) {
  const row = [];
  for (let c = 0; c < GRID_SIZE; c++) {
    // Generate base hotspot around center
    const distToCenter = Math.sqrt(Math.pow(r - 3.5, 2) + Math.pow(c - 3.5, 2));
    const baseInlet = 28 - distToCenter * 1.5 + (Math.random() * 4);
    row.push({
      row: r, col: c,
      inlet_temp: Math.max(18, Math.min(34, baseInlet)),
      outlet_temp: baseInlet + 8 + Math.random() * 12
    });
  }
  initThermalGrid.push(row);
}

function applyThermalDrift(grid) {
  const newGrid = JSON.parse(JSON.stringify(grid));
  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      // Small random drift + spatial regression
      const drift = (Math.random() - 0.5) * 1.5;
      newGrid[r][c].inlet_temp = Math.max(18, Math.min(35, grid[r][c].inlet_temp + drift));
      newGrid[r][c].outlet_temp = newGrid[r][c].inlet_temp + 8 + Math.random() * 12;
    }
  }
  return newGrid;
}

const thermalLogic = createMockGenerator(
  { grid: initThermalGrid, is_live: false },
  (state) => ({ grid: applyThermalDrift(state.grid), is_live: false })
);

export const getSnapshot = () => thermalLogic.getSnapshot();
export const subscribe = (callback, intervalMs = 5000) => thermalLogic.subscribe(callback, intervalMs);
