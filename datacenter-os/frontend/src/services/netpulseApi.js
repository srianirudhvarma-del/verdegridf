import { apiGet, apiPost } from './api';

export function getNetworkTraffic() {
  return apiGet('/netpulse/network');
}

export function optimizeNetwork() {
  return apiPost('/netpulse/optimize');
}

export function injectTrafficSpike() {
  return apiPost('/netpulse/inject-spike');
}
