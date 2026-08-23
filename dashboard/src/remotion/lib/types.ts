import { z } from "zod";

// --- Word-level caption ---
export interface CaptionWord {
  text: string;
  startMs: number;
  endMs: number;
  color?: string;
  lineId?: string;
  lineEmoji?: string;
  linePositionX?: number;
  linePositionY?: number;
  lineFontSize?: number;
  lineFontFamily?: string;
  lineFontColor?: string;
  lineHighlightColor?: string;
  lineAnimation?: SubtitleAnimation;
  lineBold?: boolean;
  lineItalic?: boolean;
  lineBorderColor?: string;
  lineBorderWidth?: number;
  lineBgColor?: string;
  lineBgOpacity?: number;
  lineTextShadowColor?: string;
  lineShadowBlur?: number;
  lineShadowOffsetX?: number;
  lineShadowOffsetY?: number;
  lineTextCase?: "none" | "uppercase" | "lowercase";
}

// --- Subtitle config ---
export type SubtitleAnimation =
  | "none"
  | "active-color"
  | "word-highlight"
  | "pop"
  | "karaoke"
  | "fade-in-out"
  | "zoom-in-out"
  | "slide-in-out"
  | "rotate-in-out"
  | "emoticon";

export interface SubtitleStyle {
  positionX: number;
  positionY: number;
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  borderColor: string;
  borderWidth: number;
  textShadowColor: string;
  shadowBlur: number;
  shadowOffsetX: number;
  shadowOffsetY: number;
  bgColor: string;
  bgOpacity: number;
  textCase: "none" | "uppercase" | "lowercase";
  bold: boolean;
  italic: boolean;
  wordsPerLine: number;
  animation: SubtitleAnimation;
}

export interface SubtitleConfig {
  captions: CaptionWord[];
  style: SubtitleStyle;
}

// --- Hook config ---
export type HookPosition = "top" | "center" | "bottom";
export type HookSize = "S" | "M" | "L";
export type HookEntrance = "spring" | "fade" | "slide-up" | "none";

export interface HookConfig {
  text: string;
  position: HookPosition;
  size: HookSize;
  entranceAnimation: HookEntrance;
  displayDurationSec: number;
}

// --- Effects config ---
export interface EffectSegment {
  startSec: number;
  endSec: number;
  zoom: number;
  zoomCenterX: number;
  zoomCenterY: number;
  brightness: number;
  contrast: number;
  saturate: number;
}

export interface EffectsConfig {
  segments: EffectSegment[];
}

// --- Main composition props ---
export interface ShortVideoProps {
  videoUrl: string;
  durationInFrames: number;
  fps: number;
  width: number;
  height: number;
  subtitles: SubtitleConfig | null;
  hook: HookConfig | null;
  effects: EffectsConfig | null;
}

// --- Zod schemas for validation (used by render service) ---
export const captionWordSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  color: z.string().optional(),
  lineId: z.string().optional(),
  lineEmoji: z.string().optional(),
  linePositionX: z.number().optional(),
  linePositionY: z.number().optional(),
  lineFontSize: z.number().optional(),
  lineFontFamily: z.string().optional(),
  lineFontColor: z.string().optional(),
  lineHighlightColor: z.string().optional(),
  lineAnimation: z.enum([
    "none",
    "active-color",
    "word-highlight",
    "pop",
    "karaoke",
    "fade-in-out",
    "zoom-in-out",
    "slide-in-out",
    "rotate-in-out",
    "emoticon",
  ]).optional(),
  lineBold: z.boolean().optional(),
  lineItalic: z.boolean().optional(),
  lineBorderColor: z.string().optional(),
  lineBorderWidth: z.number().optional(),
  lineBgColor: z.string().optional(),
  lineBgOpacity: z.number().optional(),
  lineTextShadowColor: z.string().optional(),
  lineShadowBlur: z.number().optional(),
  lineShadowOffsetX: z.number().optional(),
  lineShadowOffsetY: z.number().optional(),
  lineTextCase: z.enum(["none", "uppercase", "lowercase"]).optional(),
});

export const subtitleStyleSchema = z.object({
  positionX: z.number().min(0).max(100),
  positionY: z.number().min(0).max(100),
  fontFamily: z.string(),
  fontSize: z.number(),
  fontColor: z.string(),
  highlightColor: z.string(),
  borderColor: z.string(),
  borderWidth: z.number(),
  textShadowColor: z.string(),
  shadowBlur: z.number(),
  shadowOffsetX: z.number(),
  shadowOffsetY: z.number(),
  bgColor: z.string(),
  bgOpacity: z.number().min(0).max(1),
  textCase: z.enum(["none", "uppercase", "lowercase"]),
  bold: z.boolean(),
  italic: z.boolean(),
  wordsPerLine: z.number().int().min(2).max(8),
  animation: z.enum([
    "none",
    "active-color",
    "word-highlight",
    "pop",
    "karaoke",
    "fade-in-out",
    "zoom-in-out",
    "slide-in-out",
    "rotate-in-out",
    "emoticon",
  ]),
});

export const subtitleConfigSchema = z.object({
  captions: z.array(captionWordSchema),
  style: subtitleStyleSchema,
});

export const hookConfigSchema = z.object({
  text: z.string(),
  position: z.enum(["top", "center", "bottom"]),
  size: z.enum(["S", "M", "L"]),
  entranceAnimation: z.enum(["spring", "fade", "slide-up", "none"]),
  displayDurationSec: z.number().positive(),
});

export const effectSegmentSchema = z.object({
  startSec: z.number().min(0),
  endSec: z.number().positive(),
  zoom: z.number().min(0.5).max(3),
  zoomCenterX: z.number().min(0).max(1),
  zoomCenterY: z.number().min(0).max(1),
  brightness: z.number().min(0).max(3),
  contrast: z.number().min(0).max(3),
  saturate: z.number().min(0).max(3),
});

export const effectsConfigSchema = z.object({
  segments: z.array(effectSegmentSchema),
});

export const shortVideoPropsSchema = z.object({
  videoUrl: z.string(),
  durationInFrames: z.number().int().positive(),
  fps: z.number().positive(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  subtitles: subtitleConfigSchema.nullable(),
  hook: hookConfigSchema.nullable(),
  effects: effectsConfigSchema.nullable(),
});
