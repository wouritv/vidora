import path from "node:path";

export interface RenderJobLike {
  renderId: string;
  status: string;
  progress: number;
  outputUrl?: string;
  error?: string;
}

export function resolveRenderVideoUrl(videoUrl: string, port: number): string {
  const videoPathMatch = videoUrl.match(/\/videos\/([^/]+)\/(.+)$/);
  if (!videoPathMatch) return videoUrl;
  return `http://localhost:${port}/output/${videoPathMatch[1]}/${videoPathMatch[2]}`;
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
  return path.join(outputDir, jobId, `remotion_${clipIndex}_${timestamp}.mp4`);
}

