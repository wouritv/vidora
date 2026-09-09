import http from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { Express } from "express";

const { executeRenderMock } = vi.hoisted(() => ({ executeRenderMock: vi.fn() }));
vi.mock("../render-worker.js", () => ({ executeRender: executeRenderMock }));
vi.mock("../bundle.js", () => ({ initBundle: vi.fn(), getBundleLocation: vi.fn() }));

const TEST_API_KEY = "test-internal-api-key";

let app: Express;
let renderJobs: Map<string, unknown>;
let requireLoopback: typeof import("../server.js").requireLoopback;
let requireInternalApiKey: typeof import("../server.js").requireInternalApiKey;
let httpServer: http.Server;
let baseUrl: string;

beforeAll(async () => {
  // Must be set before ../server.js is (dynamically) imported: it exits the
  // process at module load time if this is missing.
  process.env.RENDER_SERVICE_API_KEY = TEST_API_KEY;

  const serverModule = await import("../server.js");
  app = serverModule.app;
  renderJobs = serverModule.renderJobs;
  requireLoopback = serverModule.requireLoopback;
  requireInternalApiKey = serverModule.requireInternalApiKey;

  await new Promise<void>((resolve) => {
    httpServer = http.createServer(app).listen(0, "127.0.0.1", () => {
      const address = httpServer.address() as AddressInfo;
      baseUrl = `http://127.0.0.1:${address.port}`;
      resolve();
    });
  });
});

afterAll(async () => {
  await new Promise<void>((resolve) => httpServer.close(() => resolve()));
});

function fakeRes() {
  const res = {
    statusCode: 0,
    body: undefined as unknown,
    status(code: number) {
      res.statusCode = code;
      return res;
    },
    json(payload: unknown) {
      res.body = payload;
      return res;
    },
  };
  return res;
}

describe("requireInternalApiKey", () => {
  it("rejects requests missing/with a wrong key", () => {
    const req = { header: () => undefined } as unknown as Parameters<typeof requireInternalApiKey>[0];
    const res = fakeRes();
    const next = vi.fn();

    requireInternalApiKey(req, res as never, next);

    expect(next).not.toHaveBeenCalled();
    expect(res.statusCode).toBe(401);
    expect(res.body).toEqual({ error: "Unauthorized" });
  });

  it("calls next() when the correct key is provided", () => {
    const req = { header: () => TEST_API_KEY } as unknown as Parameters<typeof requireInternalApiKey>[0];
    const res = fakeRes();
    const next = vi.fn();

    requireInternalApiKey(req, res as never, next);

    expect(next).toHaveBeenCalledTimes(1);
    expect(res.statusCode).toBe(0);
  });
});

describe("requireLoopback", () => {
  it.each(["127.0.0.1", "::1", "::ffff:127.0.0.1"])(
    "allows loopback address %s through",
    (remoteAddress) => {
      const req = { socket: { remoteAddress } } as unknown as Parameters<typeof requireLoopback>[0];
      const res = fakeRes();
      const next = vi.fn();

      requireLoopback(req, res as never, next);

      expect(next).toHaveBeenCalledTimes(1);
      expect(res.statusCode).toBe(0);
    }
  );

  it("rejects a non-loopback remote address (SSRF/exposure guard)", () => {
    const req = { socket: { remoteAddress: "10.0.0.5" } } as unknown as Parameters<typeof requireLoopback>[0];
    const res = fakeRes();
    const next = vi.fn();

    requireLoopback(req, res as never, next);

    expect(next).not.toHaveBeenCalled();
    expect(res.statusCode).toBe(403);
    expect(res.body).toEqual({ error: "Forbidden" });
  });

  it("rejects when the remote address is missing entirely", () => {
    const req = { socket: {} } as unknown as Parameters<typeof requireLoopback>[0];
    const res = fakeRes();
    const next = vi.fn();

    requireLoopback(req, res as never, next);

    expect(res.statusCode).toBe(403);
  });
});

describe("GET /health", () => {
  it("responds ok without requiring auth", async () => {
    const res = await fetch(`${baseUrl}/health`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });
});

describe("GET /output/*", () => {
  it("passes the loopback gate for a local request (not a 403)", async () => {
    const res = await fetch(`${baseUrl}/output/does-not-exist.mp4`);
    expect(res.status).not.toBe(403);
  });
});

describe("POST /render", () => {
  beforeAll(() => {
    renderJobs.clear();
  });

  it("rejects requests without the internal API key", async () => {
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
  });

  it("rejects a malformed body with validation details", async () => {
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-internal-api-key": TEST_API_KEY,
      },
      body: JSON.stringify({ jobId: "not-an-id", clipIndex: -1, props: {} }),
    });
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.error).toBe("Invalid request body");
    expect(Array.isArray(body.details)).toBe(true);
    expect(body.details.length).toBeGreaterThan(0);
  });

  it("rejects a well-formed body whose videoUrl isn't an internal /videos/ reference (SSRF guard)", async () => {
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-internal-api-key": TEST_API_KEY,
      },
      body: JSON.stringify({
        jobId: "550e8400-e29b-41d4-a716-446655440000",
        clipIndex: 0,
        props: {
          videoUrl: "https://attacker.example/video.mp4",
          durationInFrames: 100,
          fps: 30,
          width: 1080,
          height: 1920,
        },
      }),
    });
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.error).toMatch(/internal \/videos\//);
    expect(executeRenderMock).not.toHaveBeenCalled();
  });

  it("queues a valid render request and hands it to executeRender", async () => {
    executeRenderMock.mockResolvedValue(undefined);

    const jobId = "550e8400-e29b-41d4-a716-446655440000";
    const res = await fetch(`${baseUrl}/render`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-internal-api-key": TEST_API_KEY,
      },
      body: JSON.stringify({
        jobId,
        clipIndex: 3,
        props: {
          videoUrl: `/videos/${jobId}/clip.mp4`,
          durationInFrames: 100,
          fps: 30,
          width: 1080,
          height: 1920,
        },
      }),
    });
    const body = await res.json();

    expect(res.status).toBe(202);
    expect(body.status).toBe("queued");
    expect(typeof body.renderId).toBe("string");

    expect(renderJobs.get(body.renderId)).toMatchObject({
      renderId: body.renderId,
      jobId,
      clipIndex: 3,
      status: "queued",
      progress: 0,
    });

    expect(executeRenderMock).toHaveBeenCalledWith(
      expect.objectContaining({
        renderId: body.renderId,
        jobId,
        clipIndex: 3,
        props: expect.objectContaining({
          videoUrl: expect.stringContaining(`/output/${jobId}/clip.mp4`),
          subtitles: null,
          hook: null,
          effects: null,
        }),
      })
    );
  });
});

describe("GET /render/:renderId", () => {
  it("rejects requests without the internal API key", async () => {
    const res = await fetch(`${baseUrl}/render/whatever`);
    expect(res.status).toBe(401);
  });

  it("returns 404 for an unknown renderId", async () => {
    const res = await fetch(`${baseUrl}/render/does-not-exist`, {
      headers: { "x-internal-api-key": TEST_API_KEY },
    });
    expect(res.status).toBe(404);
  });

  it("returns the current job status for a known renderId", async () => {
    renderJobs.set("render-xyz", {
      renderId: "render-xyz",
      jobId: "job-1",
      clipIndex: 0,
      status: "done",
      progress: 100,
      outputUrl: "/output/job-1/clip.mp4",
    });

    const res = await fetch(`${baseUrl}/render/render-xyz`, {
      headers: { "x-internal-api-key": TEST_API_KEY },
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({
      renderId: "render-xyz",
      status: "done",
      progress: 100,
      outputUrl: "/output/job-1/clip.mp4",
    });
  });
});
