import { apiGet, apiPost } from './api';

export function getCarbonIntensity() {
  return apiGet('/carbonclock/intensity');
}

export function getSignalInfo() {
  return apiGet('/carbonclock/signal-info');
}

export function getJobQueue() {
  return apiGet('/carbonclock/jobs');
}

export function deferJob(jobId, hours) {
  return apiPost(`/carbonclock/jobs/${encodeURIComponent(jobId)}/defer`, { hours });
}

export function runJobNow(jobId) {
  return apiPost(`/carbonclock/jobs/${encodeURIComponent(jobId)}/run`);
}
