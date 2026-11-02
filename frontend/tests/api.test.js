import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "../src/services/api.js";
import { ADMIN, json, mockBackend, noContent } from "./helpers.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends the session cookie and no API key header", async () => {
    const fetchMock = mockBackend({ "GET /auth/me": () => json(200, ADMIN) });

    await expect(api.currentUser()).resolves.toEqual(ADMIN);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/auth/me");
    expect(options.credentials).toBe("include");
    expect(JSON.stringify(options.headers ?? {})).not.toMatch(/api-key/i);
  });

  it("posts login credentials as JSON", async () => {
    const fetchMock = mockBackend({ "POST /auth/login": () => json(200, { user: ADMIN }) });

    await expect(api.login("roadmind-admin", "Correct-Horse-42!")).resolves.toEqual({ user: ADMIN });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({
      username_or_email: "roadmind-admin",
      password: "Correct-Horse-42!"
    });
  });

  it("returns null for 204 responses without parsing a body", async () => {
    mockBackend({ "POST /auth/logout": () => noContent() });

    await expect(api.logout()).resolves.toBeNull();
  });

  it("preserves the backend error detail and status", async () => {
    mockBackend({ "POST /auth/login": () => json(401, { detail: "Invalid username/email or password" }) });

    const error = await api.login("x", "y").catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
    expect(error.isUnauthorized).toBe(true);
    expect(error.message).toBe("Invalid username/email or password");
  });

  it("summarizes validation error lists", async () => {
    mockBackend({ "POST /auth/login": () => json(422, { detail: [{ msg: "Field required" }] }) });

    const error = await api.login("", "").catch((caught) => caught);

    expect(error.status).toBe(422);
    expect(error.message).toBe("Field required");
  });

  it("falls back to the status when the error body is not JSON", async () => {
    mockBackend({ "GET /intersections": () => new Response("upstream down", { status: 502 }) });

    const error = await api.intersections().catch((caught) => caught);

    expect(error.status).toBe(502);
    expect(error.message).toBe("Request failed with 502");
  });

  it("reports network failures as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await api.currentUser().catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.isNetworkError).toBe(true);
    expect(error.message).toContain("Cannot reach the RoadMind backend");
  });
});
