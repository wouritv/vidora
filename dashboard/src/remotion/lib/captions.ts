import type { CaptionWord } from "./types";

export interface CaptionBlock {
  words: CaptionWord[];
  startMs: number;
  endMs: number;
  text: string;
}

export interface CaptionGroupingOptions {
  maxChars?: number;
  maxDurationMs?: number;
  maxWords?: number;
}

/**
 * Groups word-level captions into display blocks.
 * Same logic as Vireel' generate_srt: max chars per block, max duration per block.
 */
export function groupCaptionsIntoBlocks(
  captions: CaptionWord[],
  options: CaptionGroupingOptions = {}
): CaptionBlock[] {
  const maxChars = options.maxChars ?? 20;
  const maxDurationMs = options.maxDurationMs ?? 2000;
  const maxWords = options.maxWords ?? 4;
  const blocks: CaptionBlock[] = [];
  let currentWords: CaptionWord[] = [];
  let blockStartMs = 0;

  for (const word of captions) {
    if (currentWords.length === 0) {
      currentWords.push(word);
      blockStartMs = word.startMs;
      continue;
    }

    const currentTextLen = currentWords.reduce(
      (sum, w) => sum + w.text.length + 1,
      0
    );
    const duration = word.endMs - blockStartMs;

    if (
      currentWords.length >= maxWords ||
      currentTextLen + word.text.length > maxChars ||
      duration > maxDurationMs
    ) {
      // Finalize current block
      const lastWord = currentWords[currentWords.length - 1];
      blocks.push({
        words: [...currentWords],
        startMs: blockStartMs,
        endMs: lastWord.endMs,
        text: currentWords.map((w) => w.text).join(" "),
      });

      currentWords = [word];
      blockStartMs = word.startMs;
    } else {
      currentWords.push(word);
    }
  }

  // Final block
  if (currentWords.length > 0) {
    const lastWord = currentWords[currentWords.length - 1];
    blocks.push({
      words: [...currentWords],
      startMs: blockStartMs,
      endMs: lastWord.endMs,
      text: currentWords.map((w) => w.text).join(" "),
    });
  }

  return blocks;
}

/**
 * Find the active word at a given time in milliseconds.
 */
export function getActiveWordIndex(
  words: CaptionWord[],
  timeMs: number
): number {
  for (let i = 0; i < words.length; i++) {
    if (timeMs >= words[i].startMs && timeMs < words[i].endMs) {
      return i;
    }
  }
  return -1;
}
