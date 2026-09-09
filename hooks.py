import os
import textwrap
import subprocess
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSerif/NotoSerif-Bold.ttf"
FONT_DIR = "fonts"
FONT_PATH = os.path.join(FONT_DIR, "NotoSerif-Bold.ttf")
EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
# Security: hard ceilings on ffmpeg/ffprobe subprocess calls (audit finding H13).
FFPROBE_TIMEOUT_SECONDS = int(os.environ.get("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))

def download_font_if_needed():
    """Downloads a serif font for the hook text if not present."""
    if not os.path.exists(FONT_DIR):
        os.makedirs(FONT_DIR)
    if not os.path.exists(FONT_PATH):
        print(f"⬇️ Downloading font from {FONT_URL}...")
        try:
            # Add user agent to avoid 403s slightly
            req = urllib.request.Request(
                FONT_URL, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(FONT_PATH, 'wb') as out_file:
                out_file.write(response.read())
            print("✅ Font downloaded.")
        except Exception as e:
            print(f"❌ Failed to download font: {e}")

def _load_hook_font(target_width, font_scale):
    # Font Size Calculation (approx 5% of width - tuned to match Noto Serif Bold metrics in browser)
    base_font_size = int(target_width * 0.05)
    font_size = int(base_font_size * font_scale)

    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception as e:
        print(f"⚠️ Warning: Could not load font {FONT_PATH}, using default. Error: {e}")
        font = ImageFont.load_default()

    return font, font_size


def _wrap_paragraph_into_lines(paragraph, font, max_text_width, draw):
    words = paragraph.split()
    lines = []
    current_line = []

    for word in words:
        # Test if adding word fits
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]

        if w <= max_text_width:
            current_line.append(word)
        else:
            # Line full, push current_line and start new
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word too long? Force it.
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(' '.join(current_line))

    return lines


def _wrap_hook_text_lines(text, font, max_text_width):
    # Wrap text logic (Pixel-based)
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    # Handle manual newlines first
    paragraphs = text.split('\n')
    lines = []

    for p in paragraphs:
        if not p.strip():
            lines.append("")
            continue

        lines.extend(_wrap_paragraph_into_lines(p, font, max_text_width, draw))

    return lines


def _measure_hook_lines(lines, font, font_size, line_spacing, padding_x, padding_y, target_width):
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    # Recalculate true width/height
    max_line_width = 0
    text_heights = []

    for line in lines:
        if not line:
            text_heights.append(font_size) # Use font size for empty line height
            continue

        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_line_width = max(max_line_width, w)
        text_heights.append(h)

    # Box dimensions
    # We want the box to fit the text exactly + padding
    # Ensure min width for aesthetic reasons if text is short (at least 30% of target)
    box_width = max(max_line_width + (2 * padding_x), int(target_width * 0.3))

    # Total Text Height: sum(heights) + spacing * (n-1)
    if not text_heights:
         total_text_height = font_size
    else:
         total_text_height = sum(text_heights) + (len(text_heights) - 1) * line_spacing

    box_height = total_text_height + (2 * padding_y)

    return box_width, box_height, text_heights


def _render_hook_box_canvas(box_width, box_height, cornerradius, shadow_offset):
    # Create Final Image with Rounded Corners and Shadow
    # 1. Canvas for Shadow (larger than box)
    canvas_w = box_width + 40
    canvas_h = box_height + 40

    img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 2. Draw Shadow
    shadow_box = [
        (20 + shadow_offset[0], 20 + shadow_offset[1]),
        (20 + box_width + shadow_offset[0], 20 + box_height + shadow_offset[1])
    ]
    draw.rounded_rectangle(shadow_box, radius=cornerradius, fill=(0, 0, 0, 100))

    # 3. Blur Shadow
    img = img.filter(ImageFilter.GaussianBlur(5))

    # 4. Draw White Box (sharper, on top of blurred shadow)
    draw_final = ImageDraw.Draw(img)

    main_box = [
        (20, 20),
        (20 + box_width, 20 + box_height)
    ]
    # Semi-transparent white (240/255 alpha ~ 94% opacity)
    draw_final.rounded_rectangle(main_box, radius=cornerradius, fill=(255, 255, 255, 240))

    return img, draw_final, canvas_w, canvas_h


def _draw_hook_text_lines(draw_final, lines, text_heights, font, font_size, box_width, line_spacing, padding_y):
    # 5. Draw Text
    current_y = 20 + padding_y - 2 # Minor visual adjustment
    for i, line in enumerate(lines):
        if not line:
            current_y += font_size + line_spacing
            continue

        bbox = draw_final.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = text_heights[i] if i < len(text_heights) else bbox[3] - bbox[1]

        # Center X
        x = 20 + (box_width - line_w) // 2

        # Draw Black Text
        draw_final.text((x, current_y), line, font=font, fill="black")

        current_y += line_h + line_spacing


def create_hook_image(text, target_width, output_image_path="hook_overlay.png", font_scale=1.0):
    """
    Generates a white box with black serif text using pixel-based wrapping.
    target_width: The max width the box should occupy (e.g. 85% of video)
    """
    download_font_if_needed()

    # Configuration
    padding_x = 30 # Balanced padding
    padding_y = 25
    line_spacing = 20 # Increased spacing
    cornerradius = 20
    shadow_offset = (5, 5)

    font, font_size = _load_hook_font(target_width, font_scale)

    max_text_width = target_width - (2 * padding_x)
    lines = _wrap_hook_text_lines(text, font, max_text_width)

    box_width, box_height, text_heights = _measure_hook_lines(
        lines, font, font_size, line_spacing, padding_x, padding_y, target_width,
    )

    img, draw_final, canvas_w, canvas_h = _render_hook_box_canvas(box_width, box_height, cornerradius, shadow_offset)

    _draw_hook_text_lines(draw_final, lines, text_heights, font, font_size, box_width, line_spacing, padding_y)

    img.save(output_image_path)
    return output_image_path, canvas_w, canvas_h

def add_hook_to_video(video_path, text, output_path, position="top", font_scale=1.0):
    """
    Overlays text hook onto video.
    position: 'top', 'center', 'bottom'
    font_scale: float multiplier (1.0 = default)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video {video_path} not found")

    # 1. Probe video width to scale text properly
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path]
        res = subprocess.check_output(cmd, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
        # Takes first stream if multiple
        dims = res.split('\n')[0].split('x')
        video_width = int(dims[0])
        video_height = int(dims[1])
    except Exception as e:
        print(f"⚠️ FFprobe failed: {e}. Assuming 1080x1920")
        video_width = 1080
        video_height = 1920
        
    # 2. Generate Image
    # Box check: Don't let it be wider than 90% of screen
    target_box_width = int(video_width * 0.9)
    
    hook_filename = f"temp_hook_{os.path.basename(video_path)}.png"
    # Ensure unique or temp location if needed, but relative is fine for this app structure
    
    try:
        img_path, box_w, box_h = create_hook_image(text, target_box_width, hook_filename, font_scale=font_scale)
        
        # 3. Calculate Overlay Position
        overlay_x = (video_width - box_w) // 2
        
        if position == "center":
            overlay_y = (video_height - box_h) // 2
        elif position == "bottom":
             # Bottom 20% mark (approx)
             overlay_y = int(video_height * 0.70)
        else:
             # Top 20% mark
             overlay_y = int(video_height * 0.20)
        
        # 4. FFmpeg Command
        print(f"🎬 Overlaying hook: '{text}' at {overlay_x},{overlay_y}")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', img_path,
            '-filter_complex', f"[0:v][1:v]overlay={overlay_x}:{overlay_y}",
            '-c:a', 'copy',
            '-c:v', 'libx264', '-preset', EXPORT_VIDEO_PRESET, '-crf', EXPORT_VIDEO_CRF,
            '-pix_fmt', 'yuv420p',
            output_path
        ]
        
        subprocess.run(
            ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
        )
        print(f"✅ Hook added to {output_path}")
        return True

    except subprocess.TimeoutExpired as e:
        print(f"❌ FFmpeg timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s")
        raise e
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error: {e.stderr.decode() if e.stderr else 'Unknown'}")
        raise e
    except Exception as e:
        print(f"❌ Hook Gen Error: {e}")
        raise e
    finally:
        # Cleanup temp image
        if os.path.exists(hook_filename):
            os.remove(hook_filename)
