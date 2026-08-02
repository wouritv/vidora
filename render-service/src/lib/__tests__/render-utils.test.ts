import { describe, expect, it } from "vitest";
import {
  buildRenderOutputLocation,
  buildRenderStatusResponse,
  resolveRenderVideoUrl,
} from "../render-utils";

describe("resolveRenderVideoUrl", () => {
  it("returns the original url when it does not match /videos/...", () => {
    expect(resolveRenderVideoUrl("https://example.com/video.mp4", 3100)).toBe(
      "https://example.com/video.mp4"
    );
  });

  it("rewrites /videos/... urls to the renderer output server", () => {
    expect(
      resolveRenderVideoUrl("/videos/job123/clip.mp4", 3100)
    ).toBe("http://localhost:3100/output/job123/clip.mp4");
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
    const result = buildRenderOutputLocation("/output", "job123", 2, 1712345678901);
    expect(result).toContain("job123");
    expect(result).toContain("remotion_2_1712345678901.mp4");
  });
});

