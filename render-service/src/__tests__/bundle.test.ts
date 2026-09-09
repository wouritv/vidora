import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { bundleMock } = vi.hoisted(() => ({ bundleMock: vi.fn() }));

vi.mock("@remotion/bundler", () => ({ bundle: bundleMock }));

describe("bundle", () => {
  const ORIGINAL_REMOTION_BUNDLE_PATH = process.env.REMOTION_BUNDLE_PATH;

  beforeEach(() => {
    vi.resetModules();
    bundleMock.mockReset();
  });

  afterEach(() => {
    if (ORIGINAL_REMOTION_BUNDLE_PATH === undefined) {
      delete process.env.REMOTION_BUNDLE_PATH;
    } else {
      process.env.REMOTION_BUNDLE_PATH = ORIGINAL_REMOTION_BUNDLE_PATH;
    }
  });

  it("getBundleLocation throws before initBundle has ever been called", async () => {
    const { getBundleLocation } = await import("../bundle.js");
    expect(() => getBundleLocation()).toThrow(/Bundle not initialized/);
  });

  it("initBundle resolves the entry point relative to REMOTION_BUNDLE_PATH when set", async () => {
    process.env.REMOTION_BUNDLE_PATH = "/custom/remotion";
    bundleMock.mockResolvedValue("/tmp/fake-bundle-custom");

    const { initBundle, getBundleLocation } = await import("../bundle.js");
    await initBundle();

    expect(bundleMock).toHaveBeenCalledTimes(1);
    const callArgs = bundleMock.mock.calls[0][0];
    expect(callArgs.entryPoint).toBe(path.join("/custom/remotion", "src", "index.ts"));
    expect(getBundleLocation()).toBe("/tmp/fake-bundle-custom");
  });

  it("falls back to a default ../../remotion path when REMOTION_BUNDLE_PATH is unset", async () => {
    delete process.env.REMOTION_BUNDLE_PATH;
    bundleMock.mockResolvedValue("/tmp/fake-bundle-default");

    const { initBundle, getBundleLocation } = await import("../bundle.js");
    await initBundle();

    const callArgs = bundleMock.mock.calls[0][0];
    expect(callArgs.entryPoint.endsWith(path.join("remotion", "src", "index.ts"))).toBe(true);
    expect(getBundleLocation()).toBe("/tmp/fake-bundle-default");
  });

  it("caches the bundle location across multiple getBundleLocation calls", async () => {
    bundleMock.mockResolvedValue("/tmp/fake-bundle-cached");

    const { initBundle, getBundleLocation } = await import("../bundle.js");
    await initBundle();

    expect(getBundleLocation()).toBe("/tmp/fake-bundle-cached");
    expect(getBundleLocation()).toBe("/tmp/fake-bundle-cached");
    expect(bundleMock).toHaveBeenCalledTimes(1);
  });

  it("only logs bundling progress on multiples of 10 percent", async () => {
    bundleMock.mockImplementation(
      async ({ onProgress }: { onProgress: (progress: number) => void }) => {
        onProgress(5);
        onProgress(10);
        onProgress(23);
        onProgress(100);
        return "/tmp/fake-bundle-progress";
      }
    );
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);

    const { initBundle } = await import("../bundle.js");
    await initBundle();

    const progressLogs = logSpy.mock.calls
      .map(([msg]) => msg)
      .filter((msg): msg is string => typeof msg === "string" && msg.includes("Progress:"));

    expect(progressLogs).toEqual(["[bundle] Progress: 10%", "[bundle] Progress: 100%"]);

    logSpy.mockRestore();
  });
});
