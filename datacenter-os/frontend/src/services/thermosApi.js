import { apiGet, apiPost } from './api';

export function getThermalSnapshot() {
  return apiGet('/thermos/snapshot');
}

// MUST HAVE #22's supervised approval queue.
export function getPendingActions() {
  return apiGet('/thermos/actions');
}

export function approveAction(actionId, operatorId = 'operator') {
  return apiPost(`/thermos/actions/${encodeURIComponent(actionId)}/approve`, { operatorId });
}

export function rejectAction(actionId, operatorId = 'operator') {
  return apiPost(`/thermos/actions/${encodeURIComponent(actionId)}/reject`, { operatorId });
}
