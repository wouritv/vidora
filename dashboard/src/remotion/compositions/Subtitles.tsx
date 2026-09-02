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
import { getFontStack } from "../lib/fonts";
import { getEmojiForWord } from "../lib/emojiMatcher";

interface SubtitlesProps {
  config: SubtitleConfig;
}

const ACTIVE_WORD_COLORS = [
  "#FFD93D",
  "#FF6B6B",
  "#6BCB77",
  "#4D96FF",
  "#C77DFF",
];

export const Subtitles: React.FC<SubtitlesProps> = ({ config }) => {
  const { fps } = useVideoConfig();
  const wordsPerLine = Math.min(
    8,
    Math.max(2, Number(config.style.wordsPerLine) || 4)
  );
  const blocks = groupCaptionsIntoBlocks(config.captions, {
    // Keep a single block large enough to naturally wrap on up to two lines.
    maxChars: Math.max(24, wordsPerLine * 16),
    maxWords: wordsPerLine * 2,
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

  const currentTimeMs = blockStartMs + (frame / fps) * 1000;
  const elapsedBlockMs = Math.max(0, currentTimeMs - blockStartMs);
  const flashPulse = interpolate(elapsedBlockMs, [0, 120, 280], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const activeIndex = getActiveWordIndex(block.words, currentTimeMs);
  const blockStyle = style;
  const blockFontFamily = String(style.fontFamily || "Arial");
  const fontStack = getFontStack(blockFontFamily);
  const blockPositionX = blockStyle.positionX;
  const blockPositionY = blockStyle.positionY;
  const blockFontSize = blockStyle.fontSize;
  const blockEmoji = "";

  const hasBg = blockStyle.bgOpacity > 0;
  const bgStyle: React.CSSProperties = hasBg
    ? {
        backgroundColor: `${blockStyle.bgColor}${Math.round(blockStyle.bgOpacity * 255)
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
        left: `${blockPositionX}%`,
        top: `${blockPositionY}%`,
        transform: "translate(-50%, -50%)",
        display: "flex",
        justifyContent: "center",
        width: "100%",
        padding: "0 3.5%",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignContent: "center",
          justifyContent: "center",
          gap: "10px 14px",
          width: "100%",
          maxWidth: "100%",
          maxHeight: `${Math.round(blockFontSize * 2.7)}px`,
          overflow: "hidden",
          boxShadow: flashPulse > 0
            ? `0 0 ${Math.round(26 * flashPulse)}px rgba(16,185,129,${0.45 * flashPulse})`
            : "none",
          border: flashPulse > 0
            ? `1px solid rgba(16,185,129,${0.55 * flashPulse})`
            : "1px solid transparent",
          transition: "box-shadow 120ms linear, border-color 120ms linear",
          ...bgStyle,
        }}
      >
        {blockEmoji ? (
          <span
            style={{
              fontSize: Math.max(42, blockFontSize * 0.95),
              lineHeight: 1,
              marginRight: 6,
              filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
            }}
          >
            {blockEmoji}
          </span>
        ) : null}
        {block.words.map((word, i) => (
          <WordSpan
            key={`${word.startMs}-${word.endMs}-${word.text}-${i}`}
            word={word.text}
            isActive={i === activeIndex}
            style={blockStyle}
            fontSize={blockFontSize}
            fontStack={fontStack}
            animation={blockStyle.animation}
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
  fontSize: number;
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
  fontSize,
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
      case "active-color": {
        const elapsed = Math.max(0, frame - wordStartFrame);
        const colorIndex = Math.floor(elapsed / 2) % ACTIVE_WORD_COLORS.length;
        color = ACTIVE_WORD_COLORS[colorIndex];
        extraStyle = {
          textShadow: `0 0 10px ${color}AA`,
        };
        const scale = spring({
          frame: frame - wordStartFrame,
          fps,
          config: { mass: 0.55, stiffness: 280, damping: 13 },
          durationInFrames: 9,
        });
        const scaleValue = interpolate(scale, [0, 1], [1, 1.16]);
        transform = `scale(${scaleValue})`;
        break;
      }
      case "emoticon": {
        const scale = spring({
          frame: frame - wordStartFrame,
          fps,
          config: { mass: 0.5, stiffness: 300, damping: 14 },
          durationInFrames: 20,
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

  const strokeShadow =
    style.borderWidth > 0
      ? [
          `${style.borderWidth}px 0 0 ${style.borderColor}`,
          `-${style.borderWidth}px 0 0 ${style.borderColor}`,
          `0 ${style.borderWidth}px 0 ${style.borderColor}`,
          `0 -${style.borderWidth}px 0 ${style.borderColor}`,
        ].join(", ")
      : "none";

  const combinedShadow =
    animation === "karaoke"
      ? strokeShadow
      : [
          strokeShadow,
          `${style.shadowOffsetX}px ${style.shadowOffsetY}px ${style.shadowBlur}px ${style.textShadowColor}`,
          extraStyle.textShadow,
        ]
          .filter(Boolean)
          .join(", ");

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
            top: -fontSize * 1.15,
            transform: `translateX(-50%) translateY(${emojiRise}px) scale(${emojiScale})`,
            opacity: emojiOpacity,
            fontSize: Math.max(70, fontSize * 1.6),
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
          fontSize,
          fontWeight: style.bold ? 700 : 500,
          fontStyle: style.italic ? "italic" : "normal",
          letterSpacing: "0.03em",
          lineHeight: 1.34,
          color: animation === "karaoke" && isActive ? undefined : color,
          textShadow: combinedShadow,
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
