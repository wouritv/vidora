import type { CaptionBlock } from "./captions";
import { measureTextWidth } from "./textMeasure";

export interface LineFitOptions {
  fontStack: string;
  fontSize: number;
  bold: boolean;
  maxWidthPx: number;
  gapPx: number;
  maxLines: number;
  letterSpacingEm: number;
}

function wordWidth(word: string, opts: LineFitOptions): number {
  const base = measureTextWidth(word, opts.fontStack, opts.fontSize, opts.bold);
  // measureText() doesn't account for CSS letter-spacing, which the actual
  // renderer applies per character -- add it back so the estimate matches.
  return base + word.length * opts.fontSize * opts.letterSpacingEm;
}

/** Simulates the same flex-wrap behavior as the CSS renderer and returns
 * how many lines `words` would occupy at `maxWidthPx`. */
function countWrappedLines(words: string[], opts: LineFitOptions): number {
  let lines = 1;
  let lineWidth = 0;
  for (const word of words) {
    const w = wordWidth(word, opts);
    const next = lineWidth === 0 ? w : lineWidth + opts.gapPx + w;
    if (next > opts.maxWidthPx && lineWidth > 0) {
      lines += 1;
      lineWidth = w;
    } else {
      lineWidth = next;
    }
  }
  return lines;
}

/**
 * Re-splits caption blocks so none of them wrap past `maxLines` lines when
 * rendered with the real font metrics. Upstream grouping
 * (groupCaptionsIntoBlocks) only estimates block size by character count,
 * which can undercount a wide font (e.g. Montserrat Bold) and let a block
 * silently wrap onto extra lines that overflow the subtitle container.
 */
export function fitBlocksToLineLimit(
  blocks: CaptionBlock[],
  opts: LineFitOptions
): CaptionBlock[] {
  const result: CaptionBlock[] = [];

  for (const block of blocks) {
    let remaining = block.words;
    while (remaining.length > 0) {
      let take = remaining.length;
      while (
        take > 1 &&
        countWrappedLines(
          remaining.slice(0, take).map((w) => w.text),
          opts
        ) > opts.maxLines
      ) {
        take -= 1;
      }
      const chunk = remaining.slice(0, take);
      const lastWord = chunk[chunk.length - 1];
      result.push({
        words: chunk,
        startMs: chunk[0].startMs,
        endMs: lastWord.endMs,
        text: chunk.map((w) => w.text).join(" "),
      });
      remaining = remaining.slice(take);
    }
  }

  return result;
}
