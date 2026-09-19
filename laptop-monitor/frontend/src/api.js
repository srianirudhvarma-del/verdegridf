const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, options) {
  const resp = await fetch(`${BASE_URL}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    throw new Error(`${options?.method || "GET"} ${path} failed: ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  getHosts: () => request("/hosts"),
  getPendingActions: () => request("/actions"),
  approveAction: (id) => request(`/actions/${id}/approve`, { method: "POST", body: JSON.stringify({ operatorId: "dashboard" }) }),
  rejectAction: (id) => request(`/actions/${id}/reject`, { method: "POST", body: JSON.stringify({ operatorId: "dashboard" }) }),
  getGridSync: () => request("/gridsync"),
};
