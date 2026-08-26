import { apiGet, apiPost } from './api';

export function getWaterFlows() {
  return apiGet('/waterwatch/flows');
}

export function getWaterAnomalies() {
  return apiGet('/waterwatch/anomaly');
}

export function declareMaintenanceWindow(loopId, startIso, endIso, operatorId = 'operator') {
  return apiPost('/waterwatch/maintenance-mode', { loopId, start: startIso, end: endIso, operatorId });
}

export function getMaintenanceStatus(loopId) {
  return apiGet(`/waterwatch/maintenance-mode/${encodeURIComponent(loopId)}`);
}
