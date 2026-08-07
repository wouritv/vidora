import os
import subprocess
from dataclasses import dataclass


def transcribe_audio(video_path):
    """
    Transcribe audio from a video file using faster-whisper.
    Returns transcript in the same format as main.py for compatibility.
    """
    from faster_whisper import WhisperModel

    print(f"🎙️  Transcribing audio from: {video_path}")

    # Run on CPU with INT8 quantization for speed
    model = WhisperModel("base", device="cpu", compute_type="int8")

    segments, info = model.transcribe(video_path, word_timestamps=True)

    transcript = {
        "segments": [],
        "language": info.language
    }

    for segment in segments:
        seg_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": []
        }
        if segment.words:
            for word in segment.words:
                seg_data["words"].append({
                    "word": word.word.strip(),
                    "start": word.start,
                    "end": word.end
                })
        transcript["segments"].append(seg_data)

    print(f"✅ Transcription complete. Language: {info.language}")
    return transcript


def generate_srt_from_video(video_path, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """
    Transcribe a video and generate SRT directly.
    Used for dubbed videos that don't have a pre-existing transcript.
    """
    transcript = transcribe_audio(video_path)

    # Get video duration to use as clip_end
    import cv2
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0
    cap.release()

    return generate_srt(
        transcript,
        0,
        duration,
        output_path,
        max_chars=max_chars,
        max_duration=max_duration,
        max_words_per_line=max_words_per_line,
    )


def _extract_words_in_range(transcript, clip_start, clip_end):
    return [
        word_info
        for segment in transcript.get('segments', [])
        for word_info in segment.get('words', [])
        if word_info['end'] > clip_start and word_info['start'] < clip_end
    ]


def _should_flush_block(current_block, block_start, next_word_end, next_word_text, max_chars, max_duration, max_words_per_line):
    if not current_block:
        return False
    current_text_len = sum(len(w['word']) + 1 for w in current_block)
    duration = next_word_end - block_start
    return (
        len(current_block) >= max_words_per_line
        or current_text_len + len(next_word_text) > max_chars
        or duration > max_duration
    )


def _flush_srt_block(current_block, clip_start, block_start, index):
    if not current_block:
        return index, ""
    block_end = current_block[-1]['end'] - clip_start
    text = " ".join(w['word'] for w in current_block).strip()
    return index + 1, format_srt_block(index, block_start, block_end, text)


def generate_srt(transcript, clip_start, clip_end, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """
    Generates an SRT file from the transcript for a specific time range.
    Groups words into short lines suitable for vertical video.
    """
    
    words = _extract_words_in_range(transcript, clip_start, clip_end)

    if not words:
        return False

    srt_content = ""
    index = 1

    current_block = []
    block_start = None

    for word in words:
        # Adjust times relative to clip
        start = max(0, word['start'] - clip_start)
        end = max(0, word['end'] - clip_start)
        
        if not current_block:
            current_block.append(word)
            block_start = start
            continue

        if _should_flush_block(current_block, block_start, end, word['word'], max_chars, max_duration, max_words_per_line):
            index, block_text = _flush_srt_block(current_block, clip_start, block_start, index)
            srt_content += block_text
            current_block = [word]
            block_start = start
        else:
            current_block.append(word)

    # Final block
    if current_block:
        _, block_text = _flush_srt_block(current_block, clip_start, block_start, index)
        srt_content += block_text

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)
        
    return True

def format_srt_block(index, start, end, text):
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
    return f"{index}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n"

def hex_to_ass_color(hex_color, opacity=1.0):
    """Convert #RRGGBB to ASS &HAABBGGRR format. opacity: 0.0=transparent, 1.0=opaque"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    alpha = round((1.0 - opacity) * 255)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _normalize_subtitle_text_case(srt_path, text_case):
    mode = (text_case or "none").lower()
    if mode not in {"uppercase", "lowercase"}:
        return

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        normalized = []
        for line in lines:
            stripped = line.strip()
            if stripped and '-->' not in line and not stripped.isdigit():
                normalized.append(line.upper() if mode == "uppercase" else line.lower())
            else:
                normalized.append(line)

        with open(srt_path, 'w', encoding='utf-8') as f:
            f.writelines(normalized)
    except Exception:
        return


@dataclass
class SubtitleStyleOptions:
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    text_shadow_color: str = "#000000"
    shadow_blur: int = 6
    shadow_offset_x: int = 0
    shadow_offset_y: int = 2
    bold: bool = True
    italic: bool = False
    text_case: str = "none"


def burn_subtitles(video_path, srt_path, output_path, alignment=2, fontsize=16, style_options=None):
    """
    Burns subtitles into the video using FFmpeg.
    Supports two modes:
    - Outline mode (bg_opacity=0): Text with colored outline/border
    - Box mode (bg_opacity>0): Text with semi-transparent background box
    """
    style = style_options or SubtitleStyleOptions()

    # Position mapping
    ass_alignment = 2
    align_lower = str(alignment).lower()
    if align_lower == 'top':
        ass_alignment = 6
    elif align_lower == 'middle':
        ass_alignment = 10
    elif align_lower == 'bottom':
        ass_alignment = 2

    # Font size scaling for ASS virtual resolution (PlayResY=288 default)
    # For vertical 1080x1920 video, we need larger text for readability
    final_fontsize = int(fontsize * 0.85)
    if final_fontsize < 10:
        final_fontsize = 10

    _normalize_subtitle_text_case(srt_path, style.text_case)

    # Path handling for FFmpeg filter syntax
    safe_srt_path = srt_path.replace('\\', '/').replace(':', '\\:')

    # Convert colors to ASS format and build style
    primary_colour = hex_to_ass_color(style.font_color, 1.0)
    shadow_colour = hex_to_ass_color(style.text_shadow_color, 1.0)
    _ = (style.shadow_offset_x, style.shadow_offset_y)  # Kept for API compatibility; ASS shadow offset is limited.

    if style.bg_opacity > 0:
        # Box mode: opaque background box
        border_style = 3
        outline_colour = hex_to_ass_color(style.bg_color, style.bg_opacity)
        outline_width = 1
    else:
        # Outline mode: text border/outline
        border_style = 1
        outline_colour = hex_to_ass_color(style.border_color, 1.0)
        outline_width = max(1, style.border_width)

    back_colour = hex_to_ass_color("#000000", 0.0)

    style_string = (
        f"Alignment={ass_alignment},"
        f"Fontname={style.font_name},"
        f"Fontsize={final_fontsize},"
        f"PrimaryColour={primary_colour},"
        f"OutlineColour={outline_colour},"
        f"BackColour={back_colour},"
        f"BorderStyle={border_style},"
        f"Outline={outline_width},"
        f"Shadow={max(0, int(style.shadow_blur))},"
        f"ShadowColour={shadow_colour},"
        f"MarginV=25,"
        f"Bold={1 if style.bold else 0},"
        f"Italic={1 if style.italic else 0}"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"subtitles='{safe_srt_path}':force_style='{style_string}'",
        '-c:a', 'copy',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        output_path
    ]

    print(f"🎬 Burning subtitles: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(f"❌ FFmpeg Subtitle Error: {result.stderr.decode()}")
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode()}")

    return True

