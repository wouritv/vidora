import os
import json


EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
EXPORT_AUDIO_BITRATE = os.environ.get("VIREEL_EXPORT_AUDIO_BITRATE", "192k")
# Security: hard ceilings on ffmpeg/ffprobe subprocess calls so a
# pathological input can't hang a worker indefinitely (audit finding H13).
FFPROBE_TIMEOUT_SECONDS = int(os.environ.get("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))
_LOCALE_UTF8 = "C.UTF-8"
import re
import subprocess
import time
from google import genai
from google.genai import types

class VideoEditor:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        # Every other Gemini call site in this codebase (thumbnail.py,
        # main.py, app.py's translation endpoint) reads GEMINI_MODEL with no
        # fallback -- this file was the only one guessing a hardcoded model
        # name when the env var is unset, which silently diverges from
        # whatever model is actually configured/working elsewhere.
        self.model_name = os.getenv("GEMINI_MODEL")

    def upload_video(self, video_path):
        """Uploads video to Gemini File API."""
        print(f"📤 Uploading {video_path} to Gemini...")
        
        # Ensure we are passing a path that exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # Using 'file' keyword instead of 'path'
        try:
            file_upload = self.client.files.upload(file=video_path)
        except Exception as e:
            print(f"❌ Gemini Upload Error: {e}")
            raise e
        
        # Wait for processing
        print("⏳ Waiting for video processing by Gemini...")
        while True:
            file_info = self.client.files.get(name=file_upload.name)
            if file_info.state == "ACTIVE":
                print("✅ Video processed and ready.")
                return file_upload
            elif file_info.state == "FAILED":
                raise RuntimeError("Video processing failed by Gemini.")
            time.sleep(2)

    def get_ffmpeg_filter(self, video_file_obj, duration, fps=30, width=None, height=None, transcript=None):
        """Asks Gemini for a raw FFmpeg filter string."""
        if width is None or height is None:
            # Keep prompt usable even if caller didn't pass dimensions.
            width, height = 1080, 1920
        
        transcript_text = json.dumps(transcript) if transcript else "Not available."

        prompt = f"""
        You are an expert FFmpeg video editor. Your task is to generate a complex video filter string to make a short video viral, BUT ONLY apply effects where they make sense contextually.

        Video Duration: {duration} seconds.
        Video FPS: {fps}
        Video Resolution (MUST KEEP EXACT): {width}x{height}
        
        TRANSCRIPT (Context of what is being said):
        {transcript_text}

        Goal: Enhance the video with dynamic zooms, cuts (simulated with punch-ins), and visual effects to increase retention, but DO NOT overdo it. Random effects are bad. Contextual effects are good.

        Instructions:
        1. ANALYZE THE VIDEO AND TRANSCRIPT: Understand the mood, the pacing, and the key moments.
        2. APPLY EFFECTS ONLY WHEN RELEVANT:
           - Use "punch-in" zooms (zoompan) to emphasize key points, jokes, or dramatic moments in the speech.
           - slow zooms to face when the speaker is speaking
           - Use visual effects (contrast, saturation, sharpness) to highlight mood changes or specific segments.
           - If nothing significant is happening, keep it simple. It is BETTER to have no effect than a random/distracting one.
           - Avoid constant motion if the speaker is delivering a serious or steady message.
        3. Create a single valid FFmpeg filter complex string (for the -vf flag).
        4. Use filters like `zoompan`, `eq` (contrast), `hue` (saturation/bw), `unsharp`.
        5. Pacing: Align effects with the rhythm of the speech (from transcript) or visual action.
        6. CRITICAL SYNTAX RULES:
           - DO NOT use comparison operators like `<`, `>`, `<=`, `>=` anywhere. They frequently break FFmpeg expression parsing.
           - USE FFmpeg expression FUNCTIONS instead:
             - `between(x,a,b)`
             - `lt(x,y)`, `lte(x,y)`, `gt(x,y)`, `gte(x,y)`
             - `if(cond,then,else)`
           - Always wrap expression values in single quotes: `z='...'`, `x='...'`, `y='...'`, `enable='...'`.
           
           - FOR `zoompan`: 
             - Prefer `on` (output frame index) to avoid time-variable quirks.
             - Convert seconds to frames using FPS={fps}: `frame = seconds * {fps}`.
             - Use `between(on, startFrame, endFrame)` for segmenting and pacing.
             - Example:
              `zoompan=z='1.1*between(on,0,75)+1.3*between(on,76,150)+1.15*between(on,151,300)+1.2*gte(on,301)'`
             - ALWAYS set zoompan output size to EXACT `{width}x{height}` using `s={width}x{height}`.
             - ALWAYS set `fps={fps}` and `d=1`.
             - DO NOT use `scale`, `crop`, `pad` unless you keep EXACT `{width}x{height}` (no aspect ratio changes).
             
           - FOR `eq`, `hue`, `curves`, `unsharp` (Visual Effects): 
             - **DO NOT** use dynamic expressions for parameter values (e.g. `contrast='1+0.5*t'`).
             - **USE TIMELINE EDITING** via the `enable` option.
             - Create MULTIPLE filter instances for different time ranges.
             - **SYNTAX FOR ENABLE:**
              - **USE** `between(t,start,end)` for clarity and robustness.
              - **USE** single quotes around the enable expression.
              - **Example:** `eq=contrast=1.2:enable='between(t,0,3)'`
              - **Example:** `hue=s=0:enable='between(t,10,12)'`
             - This is much safer and robust than boolean multiplication.
        
        Constraints:
        - Output JSON with a single key: "filter_string".
        - The value must be the RAW filter string ready to be passed to `-vf`.
        - OUTPUT MUST KEEP EXACT RESOLUTION AND ASPECT RATIO: {width}x{height}.
        - Do NOT output 1280x720 or 1080x1080 unless the input is exactly that.
        - IMPORTANT: Do NOT include the `-vf` flag itself, just the filter content.
        - IMPORTANT: Ensure syntax is correct for FFmpeg. 
        
        Output JSON:
        {{
            "filter_string": "..."
        }}
        """

        print("🤖 Asking Gemini for FFmpeg filter...")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[video_file_obj, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        print(f"🔍 DEBUG: Gemini Raw Response:\n{response.text}")

        try:
            # Clean response text (remove potential markdown blocks)
            text = response.text
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            
            if text.endswith("```"):
                text = text[:-3]
                
            text = text.strip()
            
            # Additional cleanup for potential trailing characters outside JSON
            # Find the first '{' and last '}'
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
            
            print(f"🔍 DEBUG: Cleaned JSON Text:\n{text}")
                
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON: {response.text}")
            return None

    def get_effects_config(self, video_file_obj, duration, fps=30, width=None, height=None, transcript=None):
        """Asks Gemini for a structured EffectsConfig JSON for Remotion rendering."""
        if width is None or height is None:
            width, height = 1080, 1920

        transcript_text = json.dumps(transcript) if transcript else "Not available."

        prompt = f"""
        You are an expert video editor analyzing a video and its transcript to generate dynamic visual effects for a Remotion-based renderer.

        Video Duration: {duration} seconds.
        Video FPS: {fps}
        Video Resolution: {width}x{height}

        TRANSCRIPT (Context of what is being said):
        {transcript_text}

        Your task is to produce a structured JSON describing time-based effect segments that cover the FULL video duration.

        Each segment has these fields:
        - "startSec" (number): Start time in seconds.
        - "endSec" (number): End time in seconds.
        - "zoom" (number): Zoom level. 1.0 = no zoom, max 1.5. Use subtle values like 1.05-1.2 for most cases.
        - "zoomCenterX" (number): Horizontal focus point for zoom, 0.0 (left) to 1.0 (right). 0.5 = center.
        - "zoomCenterY" (number): Vertical focus point for zoom, 0.0 (top) to 1.0 (bottom). 0.5 = center.
        - "brightness" (number): Brightness multiplier. 1.0 = normal. Range 0.8-1.2.
        - "contrast" (number): Contrast multiplier. 1.0 = normal. Range 0.8-1.3.
        - "saturate" (number): Saturation multiplier. 1.0 = normal. Range 0.8-1.3.

        Instructions:
        1. ANALYZE the video content and transcript to understand mood, pacing, and key moments.
        2. Apply CONTEXTUAL effects aligned with speech and action:
           - Use slow, subtle zooms toward the speaker's face during speaking moments.
           - Emphasize key moments, punchlines, or dramatic beats with slightly stronger zoom or contrast.
           - Keep transitions smooth — avoid jarring jumps between segments.
           - If nothing significant is happening, keep values at defaults (zoom 1.0, all multipliers 1.0).
        3. Segments MUST cover the entire video duration from 0 to {duration} seconds with no gaps.
        4. Prefer fewer, longer segments with gradual changes over many rapid short segments.
        5. Output ONLY valid JSON, no explanations.

        Output format:
        {{
            "segments": [
                {{
                    "startSec": 0,
                    "endSec": 3.5,
                    "zoom": 1.0,
                    "zoomCenterX": 0.5,
                    "zoomCenterY": 0.5,
                    "brightness": 1.0,
                    "contrast": 1.0,
                    "saturate": 1.0
                }}
            ]
        }}
        """

        print("🤖 Asking Gemini for Remotion effects config...")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[video_file_obj, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        print(f"🔍 DEBUG: Gemini Raw Response:\n{response.text}")

        try:
            # Clean response text (remove potential markdown blocks)
            text = response.text
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]

            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Find the first '{' and last '}'
            start_idx = text.find('{')
            end_idx = text.rfind('}')

            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]

            print(f"🔍 DEBUG: Cleaned JSON Text:\n{text}")

            return json.loads(text)
        except json.JSONDecodeError:
            print(f"❌ Failed to parse effects config JSON: {response.text}")
            return None

    @staticmethod
    def _split_filter_chain(filter_string: str) -> list[str]:
        """Split a -vf filter chain on commas, respecting single-quoted substrings."""
        parts: list[str] = []
        start = 0
        in_quote = False
        for i, ch in enumerate(filter_string):
            if ch == "'":
                in_quote = not in_quote
            elif ch == "," and not in_quote:
                parts.append(filter_string[start:i])
                start = i + 1
        parts.append(filter_string[start:])
        return parts

    @classmethod
    def _enforce_zoompan_output_size(cls, filter_string: str, width: int, height: int) -> str:
        """Force any zoompan filter to output the same geometry as the input clip."""
        parts = cls._split_filter_chain(filter_string)
        out_parts: list[str] = []
        for part in parts:
            if "zoompan=" in part:
                # Force s=WxH inside zoompan options (digitsxdigits only).
                if re.search(r":s=\d+x\d+", part):
                    part = re.sub(r":s=\d+x\d+", f":s={width}x{height}", part)
                else:
                    part = f"{part}:s={width}x{height}"
            out_parts.append(part)
        return ",".join(out_parts)

    @staticmethod
    def _probe_video_dimensions(input_path: str) -> tuple[int, int] | tuple[None, None]:
        try:
            probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', input_path]
            res_out = subprocess.check_output(
                probe_cmd, env={**os.environ, "LANG": _LOCALE_UTF8}, timeout=FFPROBE_TIMEOUT_SECONDS
            ).decode().strip()
            w, h = map(int, res_out.split('x'))
            return w, h
        except Exception as e:
            print(f"⚠️ Could not probe resolution: {e}")
            return None, None

    @staticmethod
    def _prepare_filter_string(filter_string: str, width: int | None, height: int | None) -> str:
        sanitized = VideoEditor._sanitize_filter_string(filter_string)
        if sanitized != filter_string:
            print("🧼 Sanitized AI Filter (converted comparisons to lt/lte/gt/gte functions)")
            print(f"🧼 Before: {filter_string}")
            print(f"🧼 After:  {sanitized}")
            filter_string = sanitized

        if width and height:
            enforced = VideoEditor._enforce_zoompan_output_size(filter_string, width, height)
            if enforced != filter_string:
                print(f"📐 Enforced zoompan output size to {width}x{height}")
                filter_string = enforced
            if "setsar=" not in filter_string:
                filter_string = f"{filter_string},setsar=1"

        return filter_string

    @staticmethod
    def _build_ffmpeg_cmd(input_path: str, output_path: str, filter_string: str) -> list:
        return [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_string,
            '-c:v', 'libx264', '-preset', EXPORT_VIDEO_PRESET, '-crf', EXPORT_VIDEO_CRF,
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', EXPORT_AUDIO_BITRATE,
            output_path
        ]

    @staticmethod
    def _execute_ffmpeg_command(cmd: list) -> None:
        env = os.environ.copy()
        env["LANG"] = _LOCALE_UTF8
        env["LC_ALL"] = _LOCALE_UTF8

        cmd_bytes = []
        for arg in cmd:
            if isinstance(arg, str):
                cmd_bytes.append(arg.encode('utf-8'))
            else:
                cmd_bytes.append(arg)

        try:
            subprocess.run(
                cmd_bytes, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as e:
            print(f"❌ FFmpeg timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s")
            raise e
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg failed: {e}")
            try:
                stderr_text = (e.stderr or b"").decode("utf-8", errors="ignore")
                if stderr_text:
                    print(f"❌ FFmpeg stderr:\n{stderr_text}")
            except Exception:
                pass
            raise e

    @staticmethod
    def _sanitize_filter_string(filter_string: str) -> str:
        """
        Best-effort sanitizer for Gemini-generated FFmpeg expressions.
        Converts comparison operators (t<3, on>=75, etc.) into FFmpeg expr functions (lt(), gte(), ...),
        which are far more reliably parsed across FFmpeg builds.
        """
        s = filter_string

        # Order matters: handle >= / <= before > / <
        patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"(?<!\w)([A-Za-z_]\w*)\s*>=\s*(-?\d+(?:\.\d+)?)"), r"gte(\1,\2)"),
            (re.compile(r"(?<!\w)([A-Za-z_]\w*)\s*<=\s*(-?\d+(?:\.\d+)?)"), r"lte(\1,\2)"),
            (re.compile(r"(?<!\w)([A-Za-z_]\w*)\s*>\s*(-?\d+(?:\.\d+)?)"), r"gt(\1,\2)"),
            (re.compile(r"(?<!\w)([A-Za-z_]\w*)\s*<\s*(-?\d+(?:\.\d+)?)"), r"lt(\1,\2)"),
        ]
        for pat, repl in patterns:
            s = pat.sub(repl, s)

        # Rewrite fragile timeline toggles like enable='1-between(t,a,b)'.
        # FFmpeg can parse this, but AI-generated variants are often brittle.
        s = re.sub(
            r"enable='\s*1\s*-\s*between\(([^)]*)\)\s*'",
            r"enable='not(between(\1))'",
            s,
        )

        # Normalize excessively precise floats that can trigger parser edge cases.
        # Example: fps=30.0000708083 -> fps=30
        def _round_float_token(match: re.Match[str]) -> str:
            raw = match.group(0)
            try:
                value = float(raw)
            except Exception:
                return raw
            rounded = round(value, 3)
            if abs(rounded - round(rounded)) < 1e-6:
                return str(int(round(rounded)))
            return f"{rounded:.3f}".rstrip("0").rstrip(".")

        # Sonar false positive (S8786): no nested/overlapping quantifiers here
        # (\d+ and \d{6,} match disjoint character positions separated by a
        # literal '.') -- not actually susceptible to catastrophic
        # backtracking despite the heuristic flag.
        s = re.sub(r"\d+\.\d{6,}", _round_float_token, s)  # NOSONAR

        return s

    def apply_edits(self, input_path, output_path, filter_data):
        """Executes FFmpeg with the generated filter."""

        if not filter_data or "filter_string" not in filter_data:
            print("⚠️ No filter string found. Copying original.")
            copy_cmd = ['ffmpeg', '-y', '-i', input_path, '-c', 'copy', output_path]
            self._execute_ffmpeg_command(copy_cmd)
            return

        filter_string = filter_data["filter_string"]
        w, h = self._probe_video_dimensions(input_path)
        filter_string = self._prepare_filter_string(filter_string, w, h)
        print(f"🎬 Executing AI Filter: {filter_string}")
        cmd = self._build_ffmpeg_cmd(input_path, output_path, filter_string)
        self._execute_ffmpeg_command(cmd)
