import { apiGet, apiPost } from './api';

export function getCarbonIntensity() {
  return apiGet('/gridsync/intensity');
}

export function getSignalInfo() {
  return apiGet('/gridsync/signal-info');
}

export function getJobQueue() {
  return apiGet('/gridsync/jobs');
}

export function deferJob(jobId, hours) {
  return apiPost(`/gridsync/jobs/${encodeURIComponent(jobId)}/defer`, { hours });
}

export function runJobNow(jobId) {
  return apiPost(`/gridsync/jobs/${encodeURIComponent(jobId)}/run`);
}
