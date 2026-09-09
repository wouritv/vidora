import express from "express";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";
import { pathToFileURL } from "node:url";
import { initBundle } from "./bundle.js";
import { executeRender } from "./render-worker.js";
import { buildRenderStatusResponse, resolveRenderVideoUrl } from "./lib/render-utils.js";

// --- Render status types ---

export type RenderStatus = "queued" | "rendering" | "done" | "error";

export interface RenderJob {
  renderId: string;
  jobId: string;
  clipIndex: number;
  status: RenderStatus;
  progress: number;
  outputUrl?: string;
  error?: string;
}

// In-memory render job map
export const renderJobs = new Map<string, RenderJob>();

// --- Request validation schema ---

// Security: reasonable hard caps so a single request cannot demand an
// arbitrarily long/large render (CPU/memory/disk exhaustion DoS).
const MAX_DURATION_IN_FRAMES = 36000; // 20 min at 30fps
const MAX_DIMENSION = 4096;

const renderRequestSchema = z.object({
  jobId: z.string().regex(/^[0-9a-fA-F-]{8,64}$/, "Invalid jobId"),
  clipIndex: z.number().int().min(0),
  props: z.object({
    videoUrl: z.string(),
    durationInFrames: z.number().int().positive().max(MAX_DURATION_IN_FRAMES),
    fps: z.number().positive().max(240),
    width: z.number().int().positive().max(MAX_DIMENSION),
    height: z.number().int().positive().max(MAX_DIMENSION),
    subtitles: z.any().nullable().optional(),
    hook: z.any().nullable().optional(),
    effects: z.any().nullable().optional(),
  }),
});

// --- Express app ---

export const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = parseInt(process.env.PORT || "3100", 10);
const OUTPUT_DIR = process.env.OUTPUT_DIR || "/output";

// Security: this service has no user-level auth model of its own -- it is
// meant to be called only by the trusted backend over the internal Docker
// network. Require a shared internal API key so that exposing this port
// (accidentally, or for local debugging) doesn't hand out unauthenticated
// render/SSRF/DoS capability to anyone who can reach it. Refuses to start
// without a configured key so this protection can't be silently skipped.
const INTERNAL_API_KEY = process.env.RENDER_SERVICE_API_KEY;
if (!INTERNAL_API_KEY) {
  console.error(
    "[render-service] RENDER_SERVICE_API_KEY is not set. Refusing to start: " +
      "this service must never accept unauthenticated render requests."
  );
  process.exit(1);
}

export function requireInternalApiKey(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
): void {
  const provided = req.header("x-internal-api-key");
  if (provided !== INTERNAL_API_KEY) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  next();
}

// Remotion's headless Chromium fetches /output/* from *inside this same
// container* via http://localhost:<port>/... (see resolveRenderVideoUrl) --
// it cannot attach the internal API key header, so /output is instead
// restricted to loopback callers only rather than key-gated.
export function requireLoopback(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
): void {
  const ip = req.socket.remoteAddress || "";
  if (ip === "127.0.0.1" || ip === "::1" || ip === "::ffff:127.0.0.1") {
    next();
    return;
  }
  res.status(403).json({ error: "Forbidden" });
}

// Health check (no secrets exposed; safe to leave unauthenticated for
// container orchestration liveness checks).
app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

// Serve video files from the shared output volume so Remotion can access them via HTTP
app.use("/output", requireLoopback, express.static(OUTPUT_DIR));

// Submit a render job
app.post("/render", requireInternalApiKey, (req, res) => {
  const parsed = renderRequestSchema.safeParse(req.body);

  if (!parsed.success) {
    res.status(400).json({
      error: "Invalid request body",
      details: parsed.error.issues,
    });
    return;
  }

  const { jobId, clipIndex, props } = parsed.data;
  const renderId = uuidv4();

  const job: RenderJob = {
    renderId,
    jobId,
    clipIndex,
    status: "queued",
    progress: 0,
  };

  renderJobs.set(renderId, job);

  console.log(
    `[render] Queued render ${renderId} for job=${jobId} clip=${clipIndex}`
  );

  // Resolve video URL: convert frontend/backend URLs to renderer's own static server.
  // The renderer serves /output/* from the shared Docker volume.
  //
  // Security: reject anything that isn't a recognized internal
  // /videos/<jobId>/<file> reference instead of passing an arbitrary
  // caller-supplied URL through to Remotion's headless Chromium (SSRF).
  const resolvedVideoUrl = resolveRenderVideoUrl(props.videoUrl, PORT);
  if (!resolvedVideoUrl) {
    res.status(400).json({ error: "videoUrl must be an internal /videos/<jobId>/<file> reference" });
    return;
  }

  // Fire and forget - render runs in background
  executeRender({
    renderId,
    jobId,
    clipIndex,
    props: {
      videoUrl: resolvedVideoUrl,
      durationInFrames: props.durationInFrames,
      fps: props.fps,
      width: props.width,
      height: props.height,
      subtitles: props.subtitles ?? null,
      hook: props.hook ?? null,
      effects: props.effects ?? null,
    },
  }).catch((err) => {
    console.error(`[render] Unhandled error for ${renderId}:`, err);
    const existingJob = renderJobs.get(renderId);
    if (existingJob) {
      existingJob.status = "error";
      existingJob.error =
        err instanceof Error ? err.message : "Unknown error";
    }
  });

  res.status(202).json({ renderId, status: "queued" });
});

// Get render status
app.get("/render/:renderId", requireInternalApiKey, (req, res) => {
  const renderId = String(req.params.renderId);
  const job = renderJobs.get(renderId);

  if (!job) {
    res.status(404).json({ error: "Render not found" });
    return;
  }

  res.json(buildRenderStatusResponse(job));
});

// --- Start server ---

async function main() {
  console.log("[render-service] Initializing Remotion bundle...");
  await initBundle();
  console.log("[render-service] Bundle ready.");

  app.listen(PORT, () => {
    console.log(`[render-service] Listening on port ${PORT}`);
  });
}

// Only auto-start when this file is executed directly (e.g. `tsx src/server.ts`
// or `node dist/server.js`), not when imported as a module -- mirrors Python's
// `if __name__ == "__main__":` idiom so tests can import `app` without booting
// a real server or bundling Remotion.
const isMainModule = process.argv[1]
  ? import.meta.url === pathToFileURL(process.argv[1]).href
  : false;

if (isMainModule) {
  main().catch((err) => {
    console.error("[render-service] Fatal error during startup:", err);
    process.exit(1);
  });
}
