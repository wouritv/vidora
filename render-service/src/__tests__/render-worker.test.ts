import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RenderParams } from "../render-worker.js";
import type { RenderJob } from "../server.js";

const { mkdirSyncMock } = vi.hoisted(() => ({ mkdirSyncMock: vi.fn() }));
const { selectCompositionMock, renderMediaMock } = vi.hoisted(() => ({
  selectCompositionMock: vi.fn(),
  renderMediaMock: vi.fn(),
}));
const { getBundleLocationMock } = vi.hoisted(() => ({
  getBundleLocationMock: vi.fn(() => "/fake/bundle/location"),
}));
const { renderJobsMock } = vi.hoisted(() => ({
  renderJobsMock: new Map<string, unknown>(),
}));

vi.mock("node:fs", () => ({ default: { mkdirSync: mkdirSyncMock } }));

vi.mock("@remotion/renderer", () => ({
  selectComposition: selectCompositionMock,
  renderMedia: renderMediaMock,
}));

vi.mock("../bundle.js", () => ({
  initBundle: vi.fn(),
  getBundleLocation: getBundleLocationMock,
}));

vi.mock("../server.js", () => ({ renderJobs: renderJobsMock }));

const { executeRender } = await import("../render-worker.js");
const { renderJobs } = await import("../server.js");

const SAMPLE_JOB_ID = "550e8400-e29b-41d4-a716-446655440000";

function baseParams(overrides: Partial<RenderParams> = {}): RenderParams {
  return {
    renderId: "render-1",
    jobId: SAMPLE_JOB_ID,
    clipIndex: 0,
    props: {
      videoUrl: "http://localhost:3100/output/job1/clip.mp4",
      durationInFrames: 100,
      fps: 30,
      width: 1080,
      height: 1920,
      subtitles: null,
      hook: null,
      effects: null,
    },
    ...overrides,
  };
}

function seedJob(renderId: string, overrides: Partial<RenderJob> = {}): RenderJob {
  const job: RenderJob = {
    renderId,
    jobId: SAMPLE_JOB_ID,
    clipIndex: 0,
    status: "queued",
    progress: 0,
    ...overrides,
  };
  renderJobs.set(renderId, job);
  return job;
}

describe("executeRender", () => {
  beforeEach(() => {
    renderJobs.clear();
    mkdirSyncMock.mockReset();
    selectCompositionMock.mockReset();
    renderMediaMock.mockReset();
    getBundleLocationMock.mockClear();
    process.env.OUTPUT_DIR = "/tmp/render-worker-test-output";
  });

  afterEach(() => {
    delete process.env.OUTPUT_DIR;
  });

  it("returns early and logs an error when the render job is not in the map", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await executeRender(baseParams({ renderId: "missing-job" }));

    expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining("missing-job"));
    expect(selectCompositionMock).not.toHaveBeenCalled();
    expect(renderMediaMock).not.toHaveBeenCalled();

    errorSpy.mockRestore();
  });

  it("marks the job as errored when jobId is not well-formed (path traversal guard)", async () => {
    seedJob("render-1");

    await executeRender(baseParams({ jobId: "../../etc" }));

    const job = renderJobs.get("render-1") as RenderJob;
    expect(job.status).toBe("error");
    expect(job.error).toMatch(/Invalid jobId/);
    expect(selectCompositionMock).not.toHaveBeenCalled();
    expect(mkdirSyncMock).not.toHaveBeenCalled();
  });

  it("renders successfully, tracks progress and records the output url", async () => {
    seedJob("render-1", { clipIndex: 2 });
    selectCompositionMock.mockResolvedValue({ id: "ShortVideo" });
    renderMediaMock.mockImplementation(
      async ({ onProgress }: { onProgress: (arg: { progress: number }) => void }) => {
        onProgress({ progress: 0.5 });
        onProgress({ progress: 1 });
      }
    );

    await executeRender(baseParams({ clipIndex: 2 }));

    const job = renderJobs.get("render-1") as RenderJob;
    expect(job.status).toBe("done");
    expect(job.progress).toBe(100);
    expect(job.outputUrl).toContain(SAMPLE_JOB_ID);
    expect(job.outputUrl).toContain("remotion_2_");

    expect(mkdirSyncMock).toHaveBeenCalledWith(
      expect.stringContaining(SAMPLE_JOB_ID),
      { recursive: true }
    );
    expect(getBundleLocationMock).toHaveBeenCalledTimes(1);
    expect(selectCompositionMock).toHaveBeenCalledWith(
      expect.objectContaining({ serveUrl: "/fake/bundle/location", id: "ShortVideo" })
    );
    expect(renderMediaMock).toHaveBeenCalledWith(
      expect.objectContaining({ serveUrl: "/fake/bundle/location", codec: "h264" })
    );
  });

  it("marks the job as errored when renderMedia rejects", async () => {
    seedJob("render-1");
    selectCompositionMock.mockResolvedValue({ id: "ShortVideo" });
    renderMediaMock.mockRejectedValue(new Error("boom"));

    await executeRender(baseParams());

    const job = renderJobs.get("render-1") as RenderJob;
    expect(job.status).toBe("error");
    expect(job.error).toBe("boom");
  });

  it("marks the job as errored with a stringified error when the thrown value isn't an Error", async () => {
    seedJob("render-1");
    selectCompositionMock.mockRejectedValue("weird failure");

    await executeRender(baseParams());

    const job = renderJobs.get("render-1") as RenderJob;
    expect(job.status).toBe("error");
    expect(job.error).toBe("weird failure");
  });
});
