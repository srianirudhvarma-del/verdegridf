import { apiGet, apiPatch, apiPost } from './api';

export function getServerCluster() {
  return apiGet('/powerprune/servers');
}

// The real backend's consolidation pass is a bulk operation (it acts on
// every real IDLE_CANDIDATE host, not one id at a time -- see
// powerprune/power.py's dwell state machine), unlike the old mock's
// per-server performConsolidation(id). The "Harvest" button now triggers
// the real bulk pass.
export function consolidateIdleServers() {
  return apiPost('/powerprune/consolidate');
}

export function getWorkloadClassification(workloadId) {
  return apiGet(`/powerprune/workloads/${encodeURIComponent(workloadId)}/classification`);
}

export function setWorkloadClassification(workloadId, classification, maxDelayMinutes) {
  return apiPatch(`/powerprune/workloads/${encodeURIComponent(workloadId)}/classification`, {
    classification,
    maxDelayMinutes: maxDelayMinutes ?? null,
  });
}
