// src/services/api.js -- Phase 9: the real HTTP integration layer,
// re-introduced after being "removed earlier as dead code" per project
// docs. Every module's *Api.js file in this directory is a thin wrapper
// over these three functions, calling the real FastAPI backend at
// /api/* (proxied to the backend by vite.config.js in dev).

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = body.detail ? `: ${body.detail}` : '';
    } catch {
      // response body wasn't JSON -- ignore, use the status text alone
    }
    throw new Error(`${options?.method || 'GET'} ${path} failed (${res.status})${detail}`);
  }
  return res.json();
}

export function apiGet(path) {
  return request(path);
}

export function apiPost(path, body) {
  return request(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function apiPatch(path, body) {
  return request(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
