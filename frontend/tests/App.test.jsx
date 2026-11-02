import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App.jsx";
import { SELECTED_INTERSECTION_KEY } from "../src/components/constants.js";
import {
  ADMIN,
  INTERSECTIONS,
  SUMMARY,
  callsTo,
  json,
  mockBackend,
  noContent,
  unauthorized
} from "./helpers.js";

const PASSWORD = "Correct-Horse-42!";

// With an intersection already selected the dashboard polls only on its timer;
// otherwise the first refresh auto-selects one and immediately refetches.
function preselectIntersection() {
  window.localStorage.setItem(SELECTED_INTERSECTION_KEY, INTERSECTIONS[0].id);
}

const dashboardRoutes = {
  "GET /dashboard/summary": () => json(200, SUMMARY),
  "GET /intersections": () => json(200, INTERSECTIONS)
};

async function findDashboard() {
  return screen.findByRole("heading", { name: "Smart Traffic Optimization" });
}

function topbarStatus() {
  return document.querySelector(".topbar .live-dot").nextElementSibling.textContent;
}

function signIn(identifier = "roadmind-admin", password = PASSWORD) {
  fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: identifier } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("session authentication", () => {
  it("renders the login form when unauthenticated", async () => {
    const fetchMock = mockBackend({ "GET /auth/me": unauthorized });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Sign in to RoadMind" })).toBeTruthy();
    expect(screen.getByLabelText("Username or email")).toBeTruthy();
    expect(screen.getByLabelText("Password").getAttribute("type")).toBe("password");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText("Offline")).toBeNull();
    expect(callsTo(fetchMock, "GET", "/dashboard/summary")).toHaveLength(0);
    expect(callsTo(fetchMock, "GET", "/auth/me")[0][1].credentials).toBe("include");
  });

  it("transitions to the dashboard after a successful login", async () => {
    const fetchMock = mockBackend({
      "GET /auth/me": unauthorized,
      "POST /auth/login": () => json(200, { user: ADMIN }),
      ...dashboardRoutes
    });

    render(<App />);
    await screen.findByLabelText("Username or email");
    signIn();

    await findDashboard();
    expect(screen.getByText("roadmind-admin")).toBeTruthy();
    await waitFor(() => expect(topbarStatus()).toBe("Live"));

    const [, loginOptions] = callsTo(fetchMock, "POST", "/auth/login")[0];
    expect(loginOptions.credentials).toBe("include");
    expect(JSON.parse(loginOptions.body)).toEqual({ username_or_email: "roadmind-admin", password: PASSWORD });
    for (const [, options] of callsTo(fetchMock, "GET", "/dashboard/summary")) {
      expect(options.credentials).toBe("include");
    }

    // Nothing credential-like is persisted in web storage.
    const stored = JSON.stringify({ ...window.localStorage, ...window.sessionStorage });
    expect(stored).not.toContain(PASSWORD);
    expect(stored).not.toMatch(/session|api-key/i);
  });

  it("shows a clear error and clears the password on bad credentials", async () => {
    mockBackend({
      "GET /auth/me": unauthorized,
      "POST /auth/login": () => json(401, { detail: "Invalid username/email or password" })
    });

    render(<App />);
    await screen.findByLabelText("Username or email");
    signIn("roadmind-admin", "wrong-password-1");

    expect((await screen.findByRole("alert")).textContent).toBe("Incorrect username/email or password.");
    expect(screen.getByLabelText("Password").value).toBe("");
    expect(screen.getByLabelText("Username or email").value).toBe("roadmind-admin");
    expect(screen.queryByRole("heading", { name: "Smart Traffic Optimization" })).toBeNull();
  });

  it("restores an existing session on page load without showing the login form", async () => {
    const fetchMock = mockBackend({ "GET /auth/me": () => json(200, ADMIN), ...dashboardRoutes });

    render(<App />);

    await findDashboard();
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(screen.getByText("admin")).toBeTruthy();
    expect(callsTo(fetchMock, "POST", "/auth/login")).toHaveLength(0);
  });

  it("logs out and returns to the login screen", async () => {
    const fetchMock = mockBackend({
      "GET /auth/me": [() => json(200, ADMIN), unauthorized],
      "POST /auth/logout": () => noContent(),
      ...dashboardRoutes
    });

    render(<App />);
    await findDashboard();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in to RoadMind" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe("You have signed out.");
    expect(callsTo(fetchMock, "POST", "/auth/logout")[0][1].credentials).toBe("include");
  });

  it("stays signed in and reports the error when logout cannot reach the backend", async () => {
    mockBackend({
      "GET /auth/me": () => json(200, ADMIN),
      "POST /auth/logout": () => Promise.reject(new TypeError("Failed to fetch")),
      ...dashboardRoutes
    });

    render(<App />);
    await findDashboard();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText(/Sign-out failed: Cannot reach the RoadMind backend/)).toBeTruthy();
    expect(screen.queryByLabelText("Password")).toBeNull();
  });
});

describe("status and error handling", () => {
  it("treats a 401 as signed-out rather than marking the backend Offline", async () => {
    mockBackend({ "GET /auth/me": unauthorized, ...dashboardRoutes });

    render(<App />);

    await screen.findByRole("heading", { name: "Sign in to RoadMind" });
    expect(screen.queryByText("Offline")).toBeNull();
    expect(screen.queryByText(/Cannot reach/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("returns to login once when the session expires during polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    preselectIntersection();
    const fetchMock = mockBackend({
      "GET /auth/me": [() => json(200, ADMIN), unauthorized],
      "GET /dashboard/summary": [() => json(200, SUMMARY), unauthorized],
      "GET /intersections": [() => json(200, INTERSECTIONS), unauthorized]
    });

    render(<App />);
    await findDashboard();
    await waitFor(() => expect(topbarStatus()).toBe("Live"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(await screen.findByRole("heading", { name: "Sign in to RoadMind" })).toBeTruthy();
    expect(screen.getAllByRole("alert").map((node) => node.textContent)).toEqual([
      "Your session has expired. Sign in again."
    ]);
    expect(screen.queryByText("Offline")).toBeNull();

    // Polling stops with the dashboard; no further requests or notifications.
    const summaryCalls = callsTo(fetchMock, "GET", "/dashboard/summary").length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(callsTo(fetchMock, "GET", "/dashboard/summary")).toHaveLength(summaryCalls);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("explains 403 responses using the user's role", async () => {
    mockBackend({
      "GET /auth/me": () => json(200, { ...ADMIN, username: "watcher", role: "viewer" }),
      "POST /signals/optimize": () => json(403, { detail: "Insufficient permissions" }),
      ...dashboardRoutes
    });

    render(<App />);
    await findDashboard();
    await waitFor(() => expect(topbarStatus()).toBe("Live"));
    const optimize = screen.getByRole("button", { name: "Optimize" });
    await waitFor(() => expect(optimize.disabled).toBe(false));
    fireEvent.click(optimize);

    expect(await screen.findByText("Your role (viewer) is not permitted to perform this action.")).toBeTruthy();
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(topbarStatus()).toBe("Live");
  });

  it("shows a connectivity error with retry when the backend is unreachable", async () => {
    let reachable = false;
    mockBackend({
      "GET /auth/me": () => (reachable ? json(200, ADMIN) : Promise.reject(new TypeError("Failed to fetch"))),
      ...dashboardRoutes
    });

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Cannot reach the RoadMind backend at http://localhost:8000/api/v1");

    reachable = true;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await findDashboard();
  });

  it("shows the server error with retry when session restoration returns 5xx", async () => {
    let healthy = false;
    mockBackend({
      "GET /auth/me": () => (healthy ? json(200, ADMIN) : json(503, { detail: "Service Unavailable" })),
      ...dashboardRoutes
    });

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(
      "The RoadMind backend returned a server error (HTTP 503) while checking your session. Try again shortly."
    );
    expect(screen.getByLabelText("Username or email")).toBeTruthy();

    healthy = true;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await findDashboard();
  });

  it("shows an authorization message without retry for 403", async () => {
    mockBackend({ "GET /auth/me": () => json(403, { detail: "Insufficient permissions" }) });

    render(<App />);

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Your account is not permitted to use the RoadMind dashboard. Contact an administrator."
    );
    expect(screen.getByLabelText("Username or email")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.queryByText("Offline")).toBeNull();
  });

  it("returns to the plain login screen when a retry gets 401", async () => {
    let backendUp = false;
    mockBackend({
      "GET /auth/me": () => (backendUp ? unauthorized() : Promise.reject(new TypeError("Failed to fetch")))
    });

    render(<App />);
    await screen.findByRole("alert");

    backendUp = true;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByLabelText("Username or email")).toBeTruthy();
  });

  it("keeps a single notification across repeated failed retries", async () => {
    const fetchMock = mockBackend({ "GET /auth/me": () => json(502, { detail: "Bad Gateway" }) });

    render(<App />);
    const firstAlert = await screen.findByRole("alert");

    for (let attempt = 0; attempt < 3; attempt += 1) {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
      await waitFor(() => expect(screen.getByRole("button", { name: "Retry" }).disabled).toBe(false));
    }

    expect(callsTo(fetchMock, "GET", "/auth/me")).toHaveLength(4);
    expect(screen.getAllByRole("alert")).toEqual([firstAlert]);
    expect(firstAlert.textContent).toContain("HTTP 502");
  });

  it("ignores extra retry clicks while a retry is in flight", async () => {
    let releaseRetry;
    const fetchMock = mockBackend({
      "GET /auth/me": [
        () => Promise.reject(new TypeError("Failed to fetch")),
        () => new Promise((resolve) => (releaseRetry = () => resolve(json(200, ADMIN))))
      ],
      ...dashboardRoutes
    });

    render(<App />);
    await screen.findByRole("alert");

    const retry = screen.getByRole("button", { name: "Retry" });
    fireEvent.click(retry);
    fireEvent.click(retry);
    const pending = await screen.findByRole("button", { name: "Retrying…" });
    expect(pending.disabled).toBe(true);
    fireEvent.click(pending);
    expect(callsTo(fetchMock, "GET", "/auth/me")).toHaveLength(2);

    releaseRetry();
    await findDashboard();
  });

  it("marks the dashboard Offline only when the backend is unreachable", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    preselectIntersection();
    mockBackend({
      "GET /auth/me": () => json(200, ADMIN),
      "GET /dashboard/summary": [() => json(200, SUMMARY), () => Promise.reject(new TypeError("Failed to fetch"))],
      "GET /intersections": () => json(200, INTERSECTIONS)
    });

    render(<App />);
    await findDashboard();
    await waitFor(() => expect(topbarStatus()).toBe("Live"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    await waitFor(() => expect(topbarStatus()).toBe("Offline"));
    const notice = document.querySelector(".notice.error");
    expect(within(notice).getByText(/Cannot reach the RoadMind backend/)).toBeTruthy();
  });
});
