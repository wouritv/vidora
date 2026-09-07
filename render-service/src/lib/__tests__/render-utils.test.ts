import { describe, expect, it } from "vitest";
import {
  buildRenderOutputLocation,
  buildRenderStatusResponse,
  resolveRenderVideoUrl,
} from "../render-utils";

const SAMPLE_JOB_ID = "550e8400-e29b-41d4-a716-446655440000";

describe("resolveRenderVideoUrl", () => {
  it("rejects (returns null for) urls that are not internal /videos/... references, to prevent SSRF", () => {
    expect(resolveRenderVideoUrl("https://example.com/video.mp4", 3100)).toBeNull();
    expect(resolveRenderVideoUrl("http://169.254.169.254/latest/meta-data/", 3100)).toBeNull();
  });

  it("rewrites /videos/... urls to the renderer output server", () => {
    expect(
      resolveRenderVideoUrl(`/videos/${SAMPLE_JOB_ID}/clip.mp4`, 3100)
    ).toBe(`http://localhost:3100/output/${SAMPLE_JOB_ID}/clip.mp4`);
  });

  it("rejects a /videos/... url whose jobId or filename is not well-formed", () => {
    expect(resolveRenderVideoUrl("/videos/../../etc/clip.mp4", 3100)).toBeNull();
    expect(resolveRenderVideoUrl(`/videos/${SAMPLE_JOB_ID}/../secret.mp4`, 3100)).toBeNull();
  });
});

describe("buildRenderStatusResponse", () => {
  it("always includes renderId and status", () => {
    expect(
      buildRenderStatusResponse({ renderId: "r1", status: "queued", progress: 0 })
    ).toEqual({ renderId: "r1", status: "queued", progress: 0 });
  });

  it("includes optional fields only when present", () => {
    expect(
      buildRenderStatusResponse({
        renderId: "r2",
        status: "done",
        progress: 100,
        outputUrl: "/output/job1/file.mp4",
        error: "boom",
      })
    ).toEqual({
      renderId: "r2",
      status: "done",
      progress: 100,
      outputUrl: "/output/job1/file.mp4",
      error: "boom",
    });
  });
});

describe("buildRenderOutputLocation", () => {
  it("builds a deterministic job-specific output path", () => {
    const result = buildRenderOutputLocation("/output", SAMPLE_JOB_ID, 2, 1712345678901);
    expect(result).toContain(SAMPLE_JOB_ID);
    expect(result).toContain("remotion_2_1712345678901.mp4");
  });

  it("rejects a jobId that would escape outputDir (path traversal)", () => {
    expect(() => buildRenderOutputLocation("/output", "../../etc", 2, 1712345678901)).toThrow();
  });
});

