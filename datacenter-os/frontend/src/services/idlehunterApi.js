import { apiGet, apiPatch, apiPost } from './api';

export function getServerCluster() {
  return apiGet('/idlehunter/servers');
}

// The real backend's consolidation pass is a bulk operation (it acts on
// every real IDLE_CANDIDATE host, not one id at a time -- see
// idlehunter/power.py's dwell state machine), unlike the old mock's
// per-server performConsolidation(id). The "Harvest" button now triggers
// the real bulk pass.
export function consolidateIdleServers() {
  return apiPost('/idlehunter/consolidate');
}

export function getWorkloadClassification(workloadId) {
  return apiGet(`/idlehunter/workloads/${encodeURIComponent(workloadId)}/classification`);
}

export function setWorkloadClassification(workloadId, classification, maxDelayMinutes) {
  return apiPatch(`/idlehunter/workloads/${encodeURIComponent(workloadId)}/classification`, {
    classification,
    maxDelayMinutes: maxDelayMinutes ?? null,
  });
}
