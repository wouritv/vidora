let measureCanvas: HTMLCanvasElement | null = null;

function getMeasureContext(): CanvasRenderingContext2D | null {
  if (typeof document === "undefined") return null;
  if (!measureCanvas) {
    measureCanvas = document.createElement("canvas");
  }
  try {
    return measureCanvas.getContext("2d");
  } catch {
    return null;
  }
}

// Used only when a 2D canvas context isn't available (e.g. jsdom in unit
// tests, which doesn't implement measureText without the optional `canvas`
// native module). Deliberately generous so line-fit checks stay conservative.
const FALLBACK_CHAR_WIDTH_RATIO = 0.62;

/**
 * Pixel width of `text` rendered at `fontSize`/`bold` in `fontStack`, using
 * the same Canvas 2D measureText() available both in the browser (preview)
 * and inside Remotion's Chromium-based renderer (final export) -- this is
 * what makes line-wrap predictions font-accurate instead of an estimate
 * based on character count.
 */
export function measureTextWidth(
  text: string,
  fontStack: string,
  fontSize: number,
  bold: boolean
): number {
  const ctx = getMeasureContext();
  if (!ctx) {
    return text.length * fontSize * FALLBACK_CHAR_WIDTH_RATIO;
  }
  ctx.font = `${bold ? 700 : 500} ${fontSize}px ${fontStack}`;
  return ctx.measureText(text).width;
}
