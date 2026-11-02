const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Browser requests authenticate with the backend's HttpOnly session cookie.
// The cookie is never readable from JavaScript, and nothing credential-like is
// kept in localStorage, sessionStorage or the bundle.
export class ApiError extends Error {
  constructor(message, status, { path = "" } = {}) {
    super(message);
    this.name = "ApiError";
    // 0 means the request never got an HTTP response (network/CORS failure).
    this.status = status;
    this.path = path;
  }

  get isNetworkError() {
    return this.status === 0;
  }

  get isUnauthorized() {
    return this.status === 401;
  }

  get isForbidden() {
    return this.status === 403;
  }
}

async function errorMessage(response) {
  const fallback = `Request failed with ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg).filter(Boolean).join("; ") || fallback;
    }
    return fallback;
  } catch {
    // Keep the HTTP status message when the body is not JSON.
    return fallback;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include"
    });
  } catch {
    throw new ApiError(`Cannot reach the RoadMind backend at ${API_BASE_URL}`, 0, { path });
  }

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status, { path });
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return null;
  }
  return response.json();
}

export const api = {
  baseUrl: API_BASE_URL,
  login: (usernameOrEmail, password) =>
    request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username_or_email: usernameOrEmail, password })
    }),
  currentUser: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  summary: (intersectionId) => {
    const suffix =
      typeof intersectionId === "string" && intersectionId
        ? `?intersection_id=${encodeURIComponent(intersectionId)}`
        : "";
    return request(`/dashboard/summary${suffix}`);
  },
  intersections: () => request("/intersections"),
  createIntersection: (payload) =>
    request("/intersections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  createObservation: (payload) =>
    request("/traffic/observations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  optimize: (payload) =>
    request("/signals/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
  }),
  trainPrediction: () => request("/predictions/train", { method: "POST" }),
  jobStatus: (jobId) => request(`/jobs/${encodeURIComponent(jobId)}`),
  predict: (payload) =>
    request("/predictions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  createEmergency: (payload) =>
    request("/emergencies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  clearIntersectionPriority: (intersectionId) =>
    request(`/emergencies/clear-active?intersection_id=${encodeURIComponent(intersectionId)}`, { method: "POST" }),
  clearEmergency: (eventId) => request(`/emergencies/${eventId}/clear`, { method: "POST" }),
  createCorridor: (emergencyId, intersectionIds, avgSpeedKmh) =>
    request(`/emergencies/${encodeURIComponent(emergencyId)}/corridor?avg_speed_kmh=${encodeURIComponent(avgSpeedKmh)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(intersectionIds)
    }),
  detectImage: (file, intersectionId, persistObservation = false) => {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams();
    if (intersectionId) params.set("intersection_id", intersectionId);
    params.set("persist_observation", String(persistObservation));
    const suffix = `?${params.toString()}`;
    return request(`/detections/image${suffix}`, {
      method: "POST",
      body: form
    });
  }
};
