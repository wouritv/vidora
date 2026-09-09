import { describe, expect, it } from "vitest";
import { buildRenderOutputLocation, buildRenderStatusResponse, resolveRenderVideoUrl } from "../render-utils";

const SAMPLE_JOB_ID = "550e8400-e29b-41d4-a716-446655440000";

describe("render-utils", () => {
  it("resolveRenderVideoUrl rejects unrelated urls (SSRF protection)", () => {
    expect(resolveRenderVideoUrl("https://example.com/a.mp4", 3100)).toBeNull();
  });

  it("resolveRenderVideoUrl maps /videos paths to renderer output endpoint", () => {
    expect(resolveRenderVideoUrl(`/videos/${SAMPLE_JOB_ID}/clip.mp4`, 3100)).toBe(
      `http://localhost:3100/output/${SAMPLE_JOB_ID}/clip.mp4`
    );
  });

  it("buildRenderStatusResponse omits undefined optional fields", () => {
    expect(buildRenderStatusResponse({ renderId: "r1", status: "queued", progress: 0 })).toEqual({ renderId: "r1", status: "queued", progress: 0 });
  });

  it("buildRenderOutputLocation creates the expected filename", () => {
    expect(buildRenderOutputLocation("/output", SAMPLE_JOB_ID, 3, 123456)).toBe(`/output/${SAMPLE_JOB_ID}/remotion_3_123456.mp4`);
  });
});


