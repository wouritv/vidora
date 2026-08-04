import { staticFile } from "remotion";

/**
 * CSS @font-face declaration for NotoSerif-Bold (bundled locally).
 */
export const NOTO_SERIF_FONT_FAMILY = "NotoSerif-Bold";

export const notoSerifFontFace = `
@font-face {
  font-family: '${NOTO_SERIF_FONT_FAMILY}';
  src: url('${staticFile("fonts/NotoSerif-Bold.ttf")}') format('truetype');
  font-weight: 700;
  font-style: normal;
}
`;

/**
 * Map of subtitle font families to their CSS-safe names.
 * Google Fonts are loaded via <link> in index.html for browser preview.
 * These match the options available in SubtitleModal.jsx.
 */
export const SUBTITLE_FONTS: Record<string, string> = {
  // 🔥 TikTok / Viral
  "Bebas Neue":    "'Bebas Neue', Impact, sans-serif",
  "Anton":         "'Anton', Impact, sans-serif",
  "Impact":        "Impact, Haettenschweiler, sans-serif",
  "Bangers":       "'Bangers', Impact, sans-serif",
  "Archivo Black": "'Archivo Black', Impact, sans-serif",
  "Lilita One":    "'Lilita One', Impact, sans-serif",
  "Rubik Mono One": "'Rubik Mono One', Impact, sans-serif",
  "Teko":           "'Teko', Impact, sans-serif",
  // 🎉 Fun & Playful
  "Pacifico":         "'Pacifico', cursive",
  "Fredoka":          "'Fredoka', 'Fredoka One', sans-serif",
  "Righteous":        "'Righteous', sans-serif",
  "Boogaloo":         "'Boogaloo', sans-serif",
  "Luckiest Guy":     "'Luckiest Guy', cursive",
  "Baloo 2":          "'Baloo 2', sans-serif",
  "Chewy":            "'Chewy', cursive",
  "Comic Neue":       "'Comic Neue', cursive",
  "Bubblegum Sans":   "'Bubblegum Sans', cursive",
  // 💼 Professional
  "Montserrat":       "'Montserrat', Arial, sans-serif",
  "Poppins":          "'Poppins', Arial, sans-serif",
  "Roboto":           "'Roboto', Arial, sans-serif",
  "Inter":            "'Inter', Arial, sans-serif",
  "Manrope":          "'Manrope', Arial, sans-serif",
  "DM Sans":          "'DM Sans', Arial, sans-serif",
  // ✍️ Handwriting
  "Permanent Marker": "'Permanent Marker', cursive",
  "Caveat":           "'Caveat', cursive",
  "Kalam":            "'Kalam', cursive",
  // 🚀 Exotic / Tech
  "Orbitron":         "'Orbitron', sans-serif",
  "Audiowide":        "'Audiowide', sans-serif",
  "Press Start 2P":   "'Press Start 2P', monospace",
  // 😀 Emoji Friendly
  "Noto Sans":        "'Noto Sans', 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif",
  "Nunito":           "'Nunito', 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif",
  // 📚 Classic
  "Playfair Display": "'Playfair Display', Georgia, serif",
  "Georgia":          "Georgia, 'Times New Roman', serif",
  "Verdana":          "Verdana, Geneva, sans-serif",
  "Arial":            "Arial, Helvetica, sans-serif",
  "Helvetica":        "Helvetica, Arial, sans-serif",
  "Courier New":      "'Courier New', Courier, monospace",
};

export function getFontStack(fontFamily: string): string {
  return SUBTITLE_FONTS[fontFamily] ?? fontFamily;
}
