import { describe, expect, it } from "vitest";
import {
  buildRenderOutputLocation,
  buildRenderStatusResponse,
  isSafeFilename,
  isSafeJobId,
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

  it("rejects a url with more path segments than the /videos/<jobId>/<file> shape", () => {
    expect(resolveRenderVideoUrl("/videos/../../etc/clip.mp4", 3100)).toBeNull();
    expect(resolveRenderVideoUrl(`/videos/${SAMPLE_JOB_ID}/../secret.mp4`, 3100)).toBeNull();
  });

  it("rejects a well-formed /videos/<jobId>/<file> url whose jobId isn't safe", () => {
    expect(resolveRenderVideoUrl("/videos/not-a-valid-job-id!/clip.mp4", 3100)).toBeNull();
  });

  it("rejects a well-formed /videos/<jobId>/<file> url whose filename isn't safe", () => {
    expect(resolveRenderVideoUrl(`/videos/${SAMPLE_JOB_ID}/bad*file.mp4`, 3100)).toBeNull();
  });
});

describe("isSafeJobId", () => {
  it("accepts well-formed uuid-like ids", () => {
    expect(isSafeJobId(SAMPLE_JOB_ID)).toBe(true);
    expect(isSafeJobId("abcdef01")).toBe(true);
  });

  it("rejects path traversal, empty, and oversized ids", () => {
    expect(isSafeJobId("../../etc")).toBe(false);
    expect(isSafeJobId("")).toBe(false);
    expect(isSafeJobId("short")).toBe(false);
    expect(isSafeJobId("a".repeat(65))).toBe(false);
  });
});

describe("isSafeFilename", () => {
  it("accepts simple filenames", () => {
    expect(isSafeFilename("clip.mp4")).toBe(true);
    expect(isSafeFilename("remotion_0_1712345678901.mp4")).toBe(true);
  });

  it("rejects path traversal, path separators, and the special . / .. names", () => {
    expect(isSafeFilename("../secret.mp4")).toBe(false);
    expect(isSafeFilename("a/b.mp4")).toBe(false);
    expect(isSafeFilename(".")).toBe(false);
    expect(isSafeFilename("..")).toBe(false);
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

  it("rejects a resolved path that would escape outputDir even with a valid jobId", () => {
    // jobId itself passes isSafeJobId (hex/hyphen only, so it alone can never
    // traverse), but clipIndex is only ever *typed* as a number -- at runtime
    // nothing stops a caller from passing something else. This defense-in-depth
    // check is what would catch that if it ever happened.
    const maliciousClipIndex = "../../../../etc/passwd" as unknown as number;
    expect(() =>
      buildRenderOutputLocation("/output", SAMPLE_JOB_ID, maliciousClipIndex, 1712345678901)
    ).toThrow(/escapes outputDir/);
  });
});

