import { apiGet, apiPost } from './api';

export function getThermalSnapshot() {
  return apiGet('/thermaltrace/snapshot');
}

// MUST HAVE #22's supervised approval queue.
export function getPendingActions() {
  return apiGet('/thermaltrace/actions');
}

export function approveAction(actionId, operatorId = 'operator') {
  return apiPost(`/thermaltrace/actions/${encodeURIComponent(actionId)}/approve`, { operatorId });
}

export function rejectAction(actionId, operatorId = 'operator') {
  return apiPost(`/thermaltrace/actions/${encodeURIComponent(actionId)}/reject`, { operatorId });
}
