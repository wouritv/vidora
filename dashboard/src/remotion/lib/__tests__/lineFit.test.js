import { describe, it, expect } from 'vitest';
import { fitBlocksToLineLimit } from '../lineFit';

function word(text, startMs, endMs) {
    return { text, startMs, endMs };
}

function block(words) {
    return {
        words,
        startMs: words[0].startMs,
        endMs: words[words.length - 1].endMs,
        text: words.map((w) => w.text).join(' '),
    };
}

const BASE_OPTS = {
    fontStack: "'Montserrat', Arial, sans-serif",
    fontSize: 60,
    bold: true,
    gapPx: 14,
    maxLines: 2,
    letterSpacingEm: 0.03,
};

describe('fitBlocksToLineLimit', () => {
    it('leaves a block untouched when it already fits within the line limit', () => {
        const words = [word('hello', 0, 100), word('world', 100, 200)];
        const result = fitBlocksToLineLimit([block(words)], {
            ...BASE_OPTS,
            maxWidthPx: 10_000, // effectively unlimited -> always 1 line
        });
        expect(result).toHaveLength(1);
        expect(result[0].words).toHaveLength(2);
    });

    it('splits a block that would wrap onto a 3rd line into two blocks', () => {
        // Regression test: this is the Montserrat cut-off bug -- a block that
        // upstream char-count grouping considered "fits in 2 lines" could
        // actually be wide enough (at the real, bold, letter-spaced glyph
        // width) to need a 3rd line, which then got clipped by the
        // fixed-height overflow:hidden container instead of ever appearing.
        const words = [
            word('supercalifragilisticexpialidocious', 0, 100),
            word('extraordinarily', 100, 200),
            word('magnificent', 200, 300),
            word('wonderful', 300, 400),
            word('spectacular', 400, 500),
            word('incredible', 500, 600),
        ];
        // Narrow enough that each of these long words roughly fills a line.
        const result = fitBlocksToLineLimit([block(words)], {
            ...BASE_OPTS,
            maxWidthPx: 900,
        });

        expect(result.length).toBeGreaterThan(1);
        // No sub-block should have been split away with zero words.
        result.forEach((b) => expect(b.words.length).toBeGreaterThan(0));
        // Word order and identity must be preserved across the split.
        expect(result.flatMap((b) => b.words.map((w) => w.text))).toEqual(
            words.map((w) => w.text)
        );
    });

    it('derives startMs/endMs from the first/last word of each split chunk', () => {
        const words = [
            word('alpha', 0, 100),
            word('bravo', 100, 200),
            word('charlie', 200, 300),
            word('delta', 300, 400),
        ];
        const result = fitBlocksToLineLimit([block(words)], {
            ...BASE_OPTS,
            maxWidthPx: 1, // force a split after every single word
        });

        result.forEach((b) => {
            expect(b.startMs).toBe(b.words[0].startMs);
            expect(b.endMs).toBe(b.words[b.words.length - 1].endMs);
            expect(b.text).toBe(b.words.map((w) => w.text).join(' '));
        });
    });

    it('never produces an infinite loop for a single word wider than maxWidthPx', () => {
        const words = [word('pneumonoultramicroscopicsilicovolcanoconiosis', 0, 100)];
        const result = fitBlocksToLineLimit([block(words)], {
            ...BASE_OPTS,
            maxWidthPx: 1,
        });
        expect(result).toHaveLength(1);
        expect(result[0].words).toHaveLength(1);
    });

    it('passes through multiple input blocks independently', () => {
        const blockA = block([word('one', 0, 100), word('two', 100, 200)]);
        const blockB = block([word('three', 500, 600), word('four', 600, 700)]);
        const result = fitBlocksToLineLimit([blockA, blockB], {
            ...BASE_OPTS,
            maxWidthPx: 10_000,
        });
        expect(result).toHaveLength(2);
        expect(result[0].text).toBe('one two');
        expect(result[1].text).toBe('three four');
    });
});
