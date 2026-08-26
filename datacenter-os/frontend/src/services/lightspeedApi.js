import { apiGet, apiPost } from './api';

export function getNetworkTraffic() {
  return apiGet('/lightspeed/network');
}

export function optimizeNetwork() {
  return apiPost('/lightspeed/optimize');
}

export function injectTrafficSpike() {
  return apiPost('/lightspeed/inject-spike');
}
