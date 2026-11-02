import { vi } from "vitest";

export const API = "http://localhost:8000/api/v1";

export const ADMIN = {
  id: "8f6c1a52-0000-4000-8000-000000000001",
  username: "roadmind-admin",
  email: "roadmind-admin@example.com",
  role: "admin",
  is_active: true
};

export const SUMMARY = {
  intersections: 1,
  active_emergencies: 0,
  latest_density: null,
  latest_vehicle_count: null,
  signal_plans: [],
  observations: [],
  emergencies: [],
  predictions: [],
  metadata: {}
};

export const INTERSECTIONS = [{ id: "int-1", name: "Central Avenue Junction" }];

export function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

export function noContent() {
  return new Response(null, { status: 204 });
}

export const unauthorized = () => json(401, { detail: "Not authenticated" });

/**
 * Install a fetch mock driven by a route table of `"METHOD /path"` keys.
 * Each value is a Response factory or an array of factories consumed in order
 * (the last one repeats). Unmatched routes fail the test loudly.
 */
export function mockBackend(routes) {
  const queues = Object.fromEntries(
    Object.entries(routes).map(([key, value]) => [key, Array.isArray(value) ? [...value] : [value]])
  );
  const fetchMock = vi.fn(async (url, options = {}) => {
    const method = (options.method ?? "GET").toUpperCase();
    const path = new URL(url).pathname.replace("/api/v1", "");
    const key = `${method} ${path}`;
    const queue = queues[key];
    if (!queue) throw new Error(`Unexpected request: ${key}`);
    const next = queue.length > 1 ? queue.shift() : queue[0];
    return next(options);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function callsTo(fetchMock, method, path) {
  return fetchMock.mock.calls.filter(
    ([url, options = {}]) =>
      (options.method ?? "GET").toUpperCase() === method && new URL(url).pathname === `/api/v1${path}`
  );
}
