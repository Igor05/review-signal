const BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const response = await fetch(BASE + path, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.detail || `Request failed (${response.status})`);
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),

  listProjects: () => request("/api/projects"),

  createProject: (name, businessType) =>
    request("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, business_type: businessType }),
    }),

  deleteProject: (id) => request(`/api/projects/${id}`, { method: "DELETE" }),

  getProject: (id) => request(`/api/projects/${id}`),

  uploadFile: (id, file, source) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source", source || "");
    return request(`/api/projects/${id}/upload`, { method: "POST", body: form });
  },

  pasteReviews: (id, text, source) =>
    request(`/api/projects/${id}/paste`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source }),
    }),

  clearReviews: (id) => request(`/api/projects/${id}/reviews`, { method: "DELETE" }),

  startAnalysis: (id) => request(`/api/projects/${id}/analyze`, { method: "POST" }),

  runStatus: (runId) => request(`/api/runs/${runId}`),

  getReport: (id, runId) =>
    request(`/api/projects/${id}/report${runId ? `?run_id=${runId}` : ""}`),

  getSummary: (id, runId) =>
    request(`/api/projects/${id}/summary${runId ? `?run_id=${runId}` : ""}`, {
      method: "POST",
    }),

  themeReviews: (themeId) => request(`/api/themes/${themeId}/reviews`),
};
