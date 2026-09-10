import * as React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { SubtitleConfig } from "../lib/types";
import { groupCaptionsIntoBlocks, getActiveWordIndex } from "../lib/captions";
import { fitBlocksToLineLimit } from "../lib/lineFit";
import { getFontStack } from "../lib/fonts";
import { getEmojiForWord } from "../lib/emojiMatcher";

interface SubtitlesProps {
  config: SubtitleConfig;
}

// Matches the SubtitleBlock container below: gap and maxWidth used when
// laying out words.
const BLOCK_MAX_WIDTH_RATIO = 0.85;
const BLOCK_WORD_GAP_PX = 14;
const MAX_SUBTITLE_LINES = 2;
const WORD_LETTER_SPACING_EM = 0.02;
const WORD_LINE_HEIGHT = 1.28;

export const Subtitles: React.FC<SubtitlesProps> = ({ config }) => {
  const { fps, width } = useVideoConfig();
  const rawBlocks = groupCaptionsIntoBlocks(config.captions, {
    maxChars: Math.max(10, config.style.wordsPerLine * 7),
    maxWords: config.style.wordsPerLine,
  });
  // The char-count heuristic above is font-agnostic and can underestimate a
  // wide font (e.g. Montserrat Bold), letting a block wrap past
  // MAX_SUBTITLE_LINES with no clipping safety net. Re-split any block that
  // would actually render past the line limit using real measured glyph
  // widths for the selected font.
  const blocks = fitBlocksToLineLimit(rawBlocks, {
    fontStack: getFontStack(config.style.fontFamily),
    fontSize: config.style.fontSize,
    bold: Boolean(config.style.bold),
    maxWidthPx: width * BLOCK_MAX_WIDTH_RATIO,
    gapPx: BLOCK_WORD_GAP_PX,
    maxLines: MAX_SUBTITLE_LINES,
    letterSpacingEm: WORD_LETTER_SPACING_EM,
  });

  return (
    <AbsoluteFill>
      {blocks.map((block) => {
        const startFrame = Math.round((block.startMs / 1000) * fps);
        const durationFrames = Math.max(
          1,
          Math.round(((block.endMs - block.startMs) / 1000) * fps)
        );

        return (
          <Sequence
            key={`${block.startMs}-${block.endMs}-${block.words.length}`}
            from={startFrame}
            durationInFrames={durationFrames}
            layout="none"
          >
            <SubtitleBlock
              block={block}
              config={config}
              blockStartMs={block.startMs}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

interface SubtitleBlockProps {
  block: ReturnType<typeof groupCaptionsIntoBlocks>[number];
  config: SubtitleConfig;
  blockStartMs: number;
}

const SubtitleBlock: React.FC<SubtitleBlockProps> = ({
  block,
  config,
  blockStartMs,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { style } = config;

  // Current time relative to composition start (sequence-relative frame)
  const currentTimeMs = blockStartMs + (frame / fps) * 1000;
  const activeIndex = getActiveWordIndex(block.words, currentTimeMs);

  const fontStack = getFontStack(style.fontFamily);

  // Background box style
  const hasBg = style.bgOpacity > 0;
  const bgStyle: React.CSSProperties = hasBg
    ? {
        backgroundColor: `${style.bgColor}${Math.round(style.bgOpacity * 255)
          .toString(16)
          .padStart(2, "0")}`,
        borderRadius: 8,
        padding: "8px 16px",
      }
    : {};
  
  return (
    <div
      style={{
        position: "absolute",
        left: `${style.positionX}%`,
        top: `${style.positionY}%`,
        transform: "translate(-50%, -50%)",
        display: "flex",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "10px 14px",
          maxWidth: "85%",
          // Safety net matching WordSpan's actual line-height, in case a
          // single word alone is too wide to split further (see lineFit.ts).
          maxHeight: `${Math.round(
            style.fontSize * WORD_LINE_HEIGHT * MAX_SUBTITLE_LINES + 14
          )}px`,
          overflow: "hidden",
          ...bgStyle,
        }}
      >
        {block.words.map((word, i) => (
          <WordSpan
            key={`${word.startMs}-${word.endMs}-${word.text}`}
            word={word.text}
            isActive={i === activeIndex}
            style={style}
            fontStack={fontStack}
            animation={style.animation}
            frame={frame}
            fps={fps}
            wordStartMs={word.startMs}
            blockStartMs={blockStartMs}
          />
        ))}
      </div>
    </div>
  );
};

interface WordSpanProps {
  word: string;
  isActive: boolean;
  style: SubtitleConfig["style"];
  fontStack: string;
  animation: SubtitleConfig["style"]["animation"];
  frame: number;
  fps: number;
  wordStartMs: number;
  blockStartMs: number;
}

const WordSpan: React.FC<WordSpanProps> = ({
  word,
  isActive,
  style,
  fontStack,
  animation,
  frame,
  fps,
  wordStartMs,
  blockStartMs,
}) => {
  const wordStartFrame = Math.round(
    ((wordStartMs - blockStartMs) / 1000) * fps
  );
  const matchedEmoji =
    isActive && animation === "emoticon" ? getEmojiForWord(word) : null;
  const emojiSpring = spring({
    frame: frame - wordStartFrame,
    fps,
    config: { mass: 0.45, stiffness: 260, damping: 14 },
    durationInFrames: 40,
  });
  const emojiScale = interpolate(emojiSpring, [0, 1], [0.75, 1.12]);
  const emojiOpacity = interpolate(emojiSpring, [0, 1], [0, 1]);
  const emojiRise = interpolate(emojiSpring, [0, 1], [10, -6]);
  const wordLife = spring({
    frame: frame - wordStartFrame,
    fps,
    config: { mass: 0.6, stiffness: 220, damping: 18 },
    durationInFrames: 18,
  });

  let transform = "";
  let color = style.fontColor;
  let extraStyle: React.CSSProperties = {};
  let opacity = 1;
  let displayWord = word;
  if (style.textCase === "uppercase") {
    displayWord = word.toUpperCase();
  } else if (style.textCase === "lowercase") {
    displayWord = word.toLowerCase();
  }

  if (isActive) {
    color = style.highlightColor;

    switch (animation) {
      case "pop": {
        const scale = spring({
          frame: frame - wordStartFrame,
          fps,
          config: { mass: 0.5, stiffness: 300, damping: 12 },
          durationInFrames: 10,
        });
        const scaleValue = interpolate(scale, [0, 1], [1, 1.25]);
        transform = `scale(${scaleValue})`;
        break;
      }
      case "karaoke": {
        extraStyle = {
          backgroundColor: style.highlightColor,
          color: style.bgColor || "#000000",
          borderRadius: 4,
          padding: "2px 6px",
        };
        break;
      }
      case "word-highlight": {
        extraStyle = {
          textShadow: `0 0 12px ${style.highlightColor}, 0 0 24px ${style.highlightColor}40`,
        };
        break;
      }
      case "emoticon": {
        const scale = spring({
          frame: frame - wordStartFrame,
          fps,
          config: { mass: 0.5, stiffness: 300, damping: 14 },
          durationInFrames: 8,
        });
        const scaleValue = interpolate(scale, [0, 1], [1, 1.12]);
        transform = `scale(${scaleValue})`;
        break;
      }
      case "fade-in-out": {
        opacity = interpolate(wordLife, [0, 1], [0.3, 1]);
        break;
      }
      case "zoom-in-out": {
        const scaleValue = interpolate(wordLife, [0, 1], [0.88, 1.12]);
        transform = `scale(${scaleValue})`;
        break;
      }
      case "slide-in-out": {
        const slide = interpolate(wordLife, [0, 1], [12, 0]);
        transform = `translateY(${slide}px)`;
        opacity = interpolate(wordLife, [0, 1], [0.4, 1]);
        break;
      }
      case "rotate-in-out": {
        const rot = interpolate(wordLife, [0, 1], [-8, 0]);
        transform = `rotate(${rot}deg)`;
        opacity = interpolate(wordLife, [0, 1], [0.4, 1]);
        break;
      }
      default:
        break;
    }
  }

  // Text stroke via textShadow (CSS paint-order not reliable in Remotion)
  const strokeShadow =
    style.borderWidth > 0
      ? [
          `${style.borderWidth}px 0 0 ${style.borderColor}`,
          `-${style.borderWidth}px 0 0 ${style.borderColor}`,
          `0 ${style.borderWidth}px 0 ${style.borderColor}`,
          `0 -${style.borderWidth}px 0 ${style.borderColor}`,
        ].join(", ")
      : "none";

  return (
    <span
      style={{
        position: "relative",
        display: "inline-block",
      }}
    >
      {matchedEmoji ? (
        <span
          style={{
            position: "absolute",
            left: "50%",
            top: -style.fontSize * 1.15,
            transform: `translateX(-50%) translateY(${emojiRise}px) scale(${emojiScale})`,
            opacity: emojiOpacity,
            fontSize: Math.max(70, style.fontSize * 1.6),
            lineHeight: 1,
            filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
            pointerEvents: "none",
          }}
        >
          {matchedEmoji}
        </span>
      ) : null}
      <span
        style={{
          fontFamily: fontStack,
          fontSize: style.fontSize,
          fontWeight: style.bold ? 700 : 500,
          fontStyle: style.italic ? "italic" : "normal",
          letterSpacing: "0.02em",
          lineHeight: 1.28,
          color: animation === "karaoke" && isActive ? undefined : color,
          textShadow:
            animation === "karaoke"
              ? strokeShadow
              : [
                  strokeShadow,
                  `${style.shadowOffsetX}px ${style.shadowOffsetY}px ${style.shadowBlur}px ${style.textShadowColor}`,
                  extraStyle.textShadow,
                ]
                  .filter(Boolean)
                  .join(", "),
          transform,
          opacity,
          display: "inline-block",
          transition: "none",
          ...extraStyle,
        }}
      >
        {displayWord}
      </span>
    </span>
  );
};
