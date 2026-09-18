import { apiGet, apiPost } from './api';

export function getWaterFlows() {
  return apiGet('/coolsense/flows');
}

export function getWaterAnomalies() {
  return apiGet('/coolsense/anomaly');
}

export function declareMaintenanceWindow(loopId, startIso, endIso, operatorId = 'operator') {
  return apiPost('/coolsense/maintenance-mode', { loopId, start: startIso, end: endIso, operatorId });
}

export function getMaintenanceStatus(loopId) {
  return apiGet(`/coolsense/maintenance-mode/${encodeURIComponent(loopId)}`);
}
