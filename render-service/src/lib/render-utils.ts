import path from "node:path";

export interface RenderJobLike {
  renderId: string;
  status: string;
  progress: number;
  outputUrl?: string;
  error?: string;
}

/**
 * Resolve a videoUrl into the renderer's own local static server, or return
 * null if it isn't a recognized internal `/videos/<jobId>/<file>` reference.
 *
 * Security: videoUrl is fully attacker-controlled input (it flows from the
 * public /api/process, /api/edit, etc. endpoints all the way down to this
 * service). Previously any URL that didn't match the internal pattern was
 * passed through unchanged to Remotion's headless Chromium, letting a caller
 * point it at cloud metadata endpoints or internal-only services (SSRF).
 * Returning null forces callers to reject the request instead of rendering
 * with an unvalidated external URL.
 */
export function resolveRenderVideoUrl(videoUrl: string, port: number): string | null {
  const videoPathMatch = videoUrl.match(/^\/videos\/([^/]+)\/([^/]+)$/);
  if (!videoPathMatch) return null;
  const [, jobId, file] = videoPathMatch;
  if (!isSafeJobId(jobId) || !isSafeFilename(file)) return null;
  return `http://localhost:${port}/output/${jobId}/${file}`;
}

const JOB_ID_PATTERN = /^[0-9a-fA-F-]{8,64}$/;
const SAFE_FILENAME_PATTERN = /^[A-Za-z0-9._-]{1,255}$/;

export function isSafeJobId(jobId: string): boolean {
  return JOB_ID_PATTERN.test(jobId);
}

export function isSafeFilename(name: string): boolean {
  return SAFE_FILENAME_PATTERN.test(name) && name !== "." && name !== "..";
}

export function buildRenderStatusResponse(job: RenderJobLike): Record<string, unknown> {
  const response: Record<string, unknown> = {
    renderId: job.renderId,
    status: job.status,
  };

  if (job.progress !== undefined) {
    response.progress = job.progress;
  }
  if (job.outputUrl) {
    response.outputUrl = job.outputUrl;
  }
  if (job.error) {
    response.error = job.error;
  }

  return response;
}

export function buildRenderOutputLocation(
  outputDir: string,
  jobId: string,
  clipIndex: number,
  timestamp: number
): string {
  if (!isSafeJobId(jobId)) {
    // Security: jobId is client-controlled; without this check a value like
    // "../../etc" would let path.join() escape outputDir entirely.
    throw new Error(`Invalid jobId: ${jobId}`);
  }
  const resolved = path.join(outputDir, jobId, `remotion_${clipIndex}_${timestamp}.mp4`);
  const resolvedOutputDir = path.resolve(outputDir);
  if (!path.resolve(resolved).startsWith(resolvedOutputDir + path.sep)) {
    throw new Error("Resolved render output path escapes outputDir");
  }
  return resolved;
}

