const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      // Keep the HTTP status message when the body is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
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
    request(`/emergencies/clear-active?intersection_id=${intersectionId}`, { method: "POST" }),
  clearEmergency: (eventId) => request(`/emergencies/${eventId}/clear`, { method: "POST" }),
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
