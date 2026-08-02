import { describe, expect, it } from "vitest";
import { buildRenderOutputLocation, buildRenderStatusResponse, resolveRenderVideoUrl } from "../render-utils";

describe("render-utils", () => {
  it("resolveRenderVideoUrl leaves unrelated urls unchanged", () => {
    expect(resolveRenderVideoUrl("https://example.com/a.mp4", 3100)).toBe("https://example.com/a.mp4");
  });

  it("resolveRenderVideoUrl maps /videos paths to renderer output endpoint", () => {
    expect(resolveRenderVideoUrl("/videos/job1/clip.mp4", 3100)).toBe("http://localhost:3100/output/job1/clip.mp4");
  });

  it("buildRenderStatusResponse omits undefined optional fields", () => {
    expect(buildRenderStatusResponse({ renderId: "r1", status: "queued", progress: 0 })).toEqual({ renderId: "r1", status: "queued", progress: 0 });
  });

  it("buildRenderOutputLocation creates the expected filename", () => {
    expect(buildRenderOutputLocation("/output", "job1", 3, 123456)).toBe("/output/job1/remotion_3_123456.mp4");
  });
});


