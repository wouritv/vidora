import time
import cv2
import scenedetect
import subprocess
import argparse
import re
import sys
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from ultralytics import YOLO
import torch
import os
import numpy as np
from tqdm import tqdm
import yt_dlp
import mediapipe as mp
# import whisper (replaced by faster_whisper inside function)
from google import genai
from dotenv import load_dotenv
import json

import shutil
import tempfile
import uuid
import wave




import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='google.protobuf')

# Load environment variables
load_dotenv()

# Security: hard ceilings on ffmpeg/ffprobe subprocess calls so a
# pathological input can't hang a worker indefinitely (audit finding H13).
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))

# --- Constants ---
ASPECT_RATIO = 9 / 16
MIN_CLIP_DURATION_SECONDS = 30
MAX_CLIP_DURATIONS_SECOND = 90
EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
EXPORT_AUDIO_BITRATE = os.environ.get("VIREEL_EXPORT_AUDIO_BITRATE", "192k")

REEL_PROMPT = """
You are a senior short-form video editor and viral content strategist.

Your task is to analyze the ENTIRE video transcript and its word-level timestamps and identify the strongest short-form video moments for TikTok, Instagram Reels, and YouTube Shorts.

Your goal is NOT to simply select interesting sentences.

You must identify complete, self-contained moments that have strong potential to retain attention, generate curiosity, emotion, discussion, or shares.

Select between 3 and 25 clips, depending on how many genuinely strong moments exist.

Do NOT create clips just to reach the maximum number.

==================================================
1. CLIP DURATION
==================================================

Each selected clip MUST be between:

MIN_DURATION: {min_clip_duration_seconds} seconds
MAX_DURATION: {max_clip_duration_seconds} seconds

Duration is inclusive.

A clip shorter than MIN_DURATION or longer than MAX_DURATION is invalid.

==================================================
2. TIMESTAMP CONTRACT — STRICT
==================================================

All timestamps MUST be absolute seconds from the beginning of the video.

They must be directly usable with FFmpeg.

Example:

- start: 12.350
- end: 37.900

STRICT RULES:

- start and end must be numbers.
- Use decimal seconds only.
- Maximum 3 decimal places.
- Do NOT use timestamps such as 00:12, 00:12.350, 1:02:15, etc.
- 0 <= start < end <= VIDEO_DURATION_SECONDS.
- end - start MUST be between MIN_DURATION and MAX_DURATION inclusive.

VIDEO_DURATION_SECONDS:
{video_duration}

==================================================
3. WORD-LEVEL TIMESTAMPS
==================================================

Use the provided word-level timestamps to determine precise clip boundaries.

WORDS_JSON contains:

{
  "w": "word",
  "s": start_time_in_seconds,
  "e": end_time_in_seconds
}

Never cut:

- in the middle of a word;
- in the middle of a sentence when avoidable;
- in the middle of a meaningful thought;
- immediately before an important payoff.

Prefer boundaries near:

- natural pauses;
- sentence boundaries;
- changes of thought;
- silence;
- speaker transitions.

When appropriate, include approximately 0.2–0.4 seconds before the beginning of the hook and 0.2–0.4 seconds after the final payoff.

However, NEVER violate the maximum clip duration to achieve this.

If the clip is already close to the maximum duration, prioritize the complete narrative moment over the padding.

==================================================
4. WHAT MAKES A STRONG CLIP
==================================================

Prioritize moments with one or more of the following characteristics:

A. STRONG HOOK
- Immediately creates curiosity.
- Starts with a surprising statement, question, claim, revelation, or strong opinion.
- Makes the viewer want to know what happens next.

B. SURPRISE / REVELATION
- Unexpected information.
- A major discovery.
- A twist.
- Something that changes the viewer's understanding of the situation.

C. EMOTION
- Genuine emotional moment.
- Personal experience.
- Vulnerability.
- Excitement.
- Frustration.
- Fear.
- Humor.
- Inspiration.

Only use emotions that are actually present in the transcript.

D. CONTROVERSY / DEBATE
- Strong opinion.
- Interesting disagreement.
- A controversial statement.
- A situation where viewers may disagree about who is right.

Do not manufacture controversy.

E. VALUE / INSIGHT
- Useful advice.
- Practical information.
- A lesson.
- A mistake and its consequence.
- A useful explanation.
- A surprising fact.

F. STORYTELLING
- A compelling personal story.
- A conflict.
- A problem followed by a consequence.
- A meaningful turning point.
- A suspenseful sequence.

G. HUMOR
- Genuine funny moment.
- Unexpected reaction.
- Funny story or punchline.

Do not artificially make a neutral statement humorous.

==================================================
5. SELF-CONTAINED CLIPS
==================================================

Every clip should make sense when watched independently from the original video.

Whenever possible, the clip should contain:

1. A hook or immediate context;
2. The development of the idea/story;
3. A payoff, revelation, punchline, conclusion, or meaningful ending.

Avoid clips that:

- begin in the middle of an unexplained conversation;
- require several minutes of previous context;
- end before the key point;
- contain only setup without payoff;
- contain only a conclusion without sufficient context.

If a strong moment requires a small amount of context, include the minimum necessary context while respecting the duration limits.

==================================================
6. HOOK QUALITY
==================================================

The beginning of the selected clip is extremely important.

Prefer clips where the first few seconds naturally create curiosity.

Examples of strong opening patterns:

- "I never expected this to happen..."
- "The biggest mistake I made was..."
- "Nobody warned me about this..."
- "I realized something was seriously wrong when..."
- "Here's what happened..."
- "I was completely wrong about..."
- "This changed everything for me..."

These are examples only.

Do NOT fabricate these statements.

The actual hook must come from the transcript.

Do not rewrite the spoken content inside the video merely to create a stronger hook.

==================================================
7. PAYOFF
==================================================

Whenever possible, the clip should end immediately after a meaningful payoff.

A payoff can be:

- a revelation;
- an answer;
- a punchline;
- a surprising conclusion;
- a strong opinion;
- a useful lesson;
- an emotional realization;
- a meaningful question.

Do not end the clip immediately before the payoff.

Do not unnecessarily include long silence or unrelated speech after the payoff.

==================================================
8. AVOID WEAK CONTENT
==================================================

Do NOT select:

- generic introductions;
- greetings;
- "welcome to my channel";
- generic outros;
- calls to subscribe that contain no useful content;
- sponsorship segments;
- promotional content without a strong standalone hook;
- repetitive statements;
- filler;
- long explanations with no clear payoff;
- incomplete thoughts;
- technical setup that is not interesting by itself.

A sponsorship or promotional segment may only be selected if it independently contains a genuinely strong viral moment.

==================================================
9. CLIP DIVERSITY
==================================================

Avoid selecting multiple clips that communicate essentially the same idea.

When several strong moments exist:

- prefer different topics;
- prefer different emotional angles;
- prefer different hooks;
- prefer different sections of the video.

The final selection should represent the strongest variety of content available.

Avoid excessive overlap between clips.

Two clips may overlap only when the overlapping section is necessary and both clips have clearly different standalone value.

==================================================
10. PERFORMANCE RANKING
==================================================

Rank clips from strongest predicted performance to weakest.

Consider:

1. Strength of the first seconds;
2. Curiosity;
3. Emotional impact;
4. Clarity;
5. Payoff;
6. Shareability;
7. Comment potential;
8. Relevance to short-form audiences;
9. Ability to stand alone;
10. Originality.

Do not assume that the longest or most emotional clip is automatically the best.

==================================================
11. LANGUAGE
==================================================

The generated metadata must use the SAME LANGUAGE as the video transcript.

Do not translate the metadata into another language.

The following fields MUST be written in the same language as the transcript:

- video_description_for_tiktok
- video_description_for_instagram
- video_title_for_youtube_short
- viral_hook_text

Keep the meaning faithful to the selected clip.

==================================================
12. TIKTOK DESCRIPTION
==================================================

Write a concise TikTok-oriented description designed to encourage:

- curiosity;
- viewing;
- comments;
- engagement.

The description should be natural for the actual content.

Do NOT force a generic CTA into every description.

Only include a CTA when it naturally fits the content.

If a CTA is appropriate, it should be specific to the video.

For example, when relevant:

- ask viewers what they would do;
- ask them to share their experience;
- ask them to choose between two options;
- invite them to comment on the dilemma.

Do NOT automatically use:

"Follow me and comment X and I'll send you the workflow."

That CTA should only be used if the video itself genuinely discusses a workflow, resource, or topic where such an offer makes sense.

==================================================
13. INSTAGRAM DESCRIPTION
==================================================

Write a concise Instagram-oriented description.

Optimize for:

- readability;
- curiosity;
- comments;
- shares;
- saves;
- relevance to the content.

Use a natural CTA when appropriate.

Do not force generic engagement bait.

==================================================
14. YOUTUBE SHORT TITLE
==================================================

Create a compelling YouTube Shorts title.

Maximum length:

100 characters.

The title should:

- create curiosity;
- accurately represent the clip;
- avoid misleading clickbait;
- highlight the most interesting aspect of the moment.

Do not use unnecessary hashtags in the title.

==================================================
15. VIRAL HOOK TEXT
==================================================

Generate a SHORT text overlay that could be displayed at the beginning of the clip.

Maximum:

10 words.

It MUST be written in the SAME LANGUAGE as the video transcript.

The overlay should:

- reinforce the video's hook;
- create curiosity;
- be easy to read quickly;
- accurately represent the selected moment.

Examples:

- "I should have seen the warning signs"
- "This changed everything"
- "I made one huge mistake"
- "Nobody warned me about this"
- "The truth came out"

These are examples only.

Do NOT invent information.

Do NOT simply copy a long sentence from the transcript.

==================================================
16. TRANSCRIPT FIDELITY
==================================================

The selected timestamps must correspond to actual content in the transcript.

Never select a clip because you assume something interesting happens there.

Never invent:

- events;
- facts;
- opinions;
- dialogue;
- reactions;
- conclusions.

The generated descriptions, title, and hook text must also remain faithful to the selected clip.

==================================================
17. ENTIRE VIDEO ANALYSIS
==================================================

Read and analyze the ENTIRE transcript before selecting clips.

Do not stop after finding the first strong moment.

Consider the entire video and compare all candidate moments before producing the final ranking.

==================================================
18. STRICT EXCLUSIONS
==================================================

Do not select:

- clips shorter than {min_clip_duration_seconds} seconds;
- clips longer than {max_clip_duration_seconds} seconds;
- clips outside the video duration;
- clips with invalid timestamps;
- clips that cut words;
- clips that contain no meaningful standalone content;
- duplicate or nearly identical moments unless absolutely necessary.

==================================================
19. OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

No markdown.

No comments.

No explanations.

No text outside the JSON.

The JSON must exactly follow this structure:

{
  "shorts": [
    {
      "start": 12.340,
      "end": 37.900,
      "video_description_for_tiktok": "...",
      "video_description_for_instagram": "...",
      "video_title_for_youtube_short": "...",
      "viral_hook_text": "..."
    }
  ]
}

==================================================
20. FINAL VALIDATION BEFORE OUTPUT
==================================================

Before returning the JSON, silently validate every clip.

For EACH clip verify:

- start is a number;
- end is a number;
- start < end;
- start >= 0;
- end <= VIDEO_DURATION_SECONDS;
- duration >= {min_clip_duration_seconds};
- duration <= {max_clip_duration_seconds};
- maximum 3 decimal places;
- boundaries do not cut words;
- clip contains a meaningful standalone moment;
- clip has a hook or sufficiently strong opening;
- clip has a meaningful payoff whenever possible;
- descriptions match the selected clip;
- title is <= 100 characters;
- viral_hook_text is <= 10 words;
- metadata language matches the transcript language.

If a candidate fails any requirement, replace it with a better candidate or remove it.

Do NOT invent a clip simply to maintain the requested number.

==================================================
VIDEO INFORMATION
==================================================

VIDEO_DURATION_SECONDS:
{video_duration}

TRANSCRIPT_TEXT:
{transcript_text}

WORDS_JSON:
{words_json}

MIN_CLIP_DURATION_SECONDS:
{min_clip_duration_seconds}

MAX_CLIP_DURATION_SECONDS:
{max_clip_duration_seconds}
"""

# Load the YOLO model once (Keep for backup or scene analysis if needed)
model = YOLO('yolov8n.pt')

# --- MediaPipe Setup (Tasks API) ---
# mediapipe 0.10.30+ removed the legacy mp.solutions API this file used to
# use (mp.solutions.face_detection / mp.solutions.face_mesh) -- ported to
# the newer mediapipe.tasks.python.vision API, which -- unlike Solutions --
# needs its model files fetched explicitly rather than bundling them.
_MEDIAPIPE_MODELS_DIR = os.environ.get(
    "MEDIAPIPE_MODELS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediapipe_models"),
)
# Official Google-hosted model URLs (storage.googleapis.com/mediapipe-models),
# the same ones the mediapipe Tasks API documentation points to -- fixed,
# hardcoded targets, not derived from any user/request input.
_FACE_DETECTOR_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
_FACE_LANDMARKER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"


def _ensure_mediapipe_model(url: str, filename: str) -> str:
    """Downloads a MediaPipe Tasks model file to a local cache dir on first
    use, mirroring the YOLO('yolov8n.pt') auto-download pattern just above.
    Returns the local file path."""
    os.makedirs(_MEDIAPIPE_MODELS_DIR, exist_ok=True)
    local_path = os.path.join(_MEDIAPIPE_MODELS_DIR, filename)
    if not os.path.exists(local_path):
        import urllib.request
        print(f"⬇️  Downloading MediaPipe model {filename}...")
        urllib.request.urlretrieve(url, local_path)
    return local_path


_mp_vision = mp.tasks.vision
_mp_base_options = mp.tasks.BaseOptions

# Lightweight BlazeFace detector (short-range model = old model_selection=0)
# for per-frame face candidate boxes used to drive smart-crop scoring.
face_detection = _mp_vision.FaceDetector.create_from_options(
    _mp_vision.FaceDetectorOptions(
        base_options=_mp_base_options(
            model_asset_path=_ensure_mediapipe_model(_FACE_DETECTOR_MODEL_URL, "blaze_face_short_range.tflite")
        ),
        running_mode=_mp_vision.RunningMode.IMAGE,
        min_detection_confidence=0.5,
    )
)

# Resolved once here (download-if-missing is a no-op after the first call);
# _track_mouth_signals below still builds a fresh FaceLandmarker per call,
# same as the old `with mp_face_mesh.FaceMesh(...)` pattern, since
# num_faces varies per call with the number of tracked faces in that scene.
_FACE_LANDMARKER_MODEL_PATH = _ensure_mediapipe_model(_FACE_LANDMARKER_MODEL_URL, "face_landmarker.task")

# Scene analysis thresholds
MIN_FACE_AREA_RATIO = 0.01
IOU_MATCH_THRESHOLD = 0.3
MIN_SAMPLES_PER_SCENE = 3
MAX_SAMPLES_PER_SCENE = 15
MIN_ACTIVE_CORRELATION = 0.25

SEPARATOR_THICKNESS_RATIO = 0.0025
SEPARATOR_MIN_PX = 2
SEPARATOR_MAX_PX = 8
SEPARATOR_COLOR_BGR = (0, 0, 0)

# MediaPipe FaceMesh mouth landmarks
MOUTH_TOP = 13
MOUTH_BOTTOM = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308

class SmoothedCameraman:
    """
    Handles smooth camera movement.
    Simplified Logic: "Heavy Tripod"
    Only moves if the subject leaves the center safe zone.
    Moves slowly and linearly.
    """
    def __init__(self, output_width, output_height, video_width, video_height):
        self.output_width = output_width
        self.output_height = output_height
        self.video_width = video_width
        self.video_height = video_height
        
        # Initial State
        self.current_center_x = video_width / 2
        self.target_center_x = video_width / 2
        
        # Calculate crop dimensions once
        self.crop_height = video_height
        self.crop_width = int(self.crop_height * ASPECT_RATIO)
        if self.crop_width > video_width:
             self.crop_width = video_width
             self.crop_height = int(self.crop_width / ASPECT_RATIO)
             
        # Safe Zone: 20% of the video width
        # As long as the target is within this zone relative to current center, DO NOT MOVE.
        self.safe_zone_radius = self.crop_width * 0.25

    def update_target(self, face_box):
        """Updates the target center based on detected face/person."""
        if face_box:
            x, _, w, _ = face_box
            self.target_center_x = x + w / 2

    def _advance_camera(self, diff):
        """Move current_center_x toward target if outside the safe zone."""
        if abs(diff) <= self.safe_zone_radius:
            return
        direction = 1 if diff > 0 else -1
        speed = 15.0 if abs(diff) > self.crop_width * 0.5 else 3.0
        self.current_center_x += direction * speed
        new_diff = self.target_center_x - self.current_center_x
        overshot = (direction == 1 and new_diff < 0) or (direction == -1 and new_diff > 0)
        if overshot:
            self.current_center_x = self.target_center_x

    def _clamp_center(self):
        """Keep current_center_x within valid crop bounds."""
        half_crop = self.crop_width / 2
        self.current_center_x = max(half_crop, min(self.video_width - half_crop, self.current_center_x))

    def get_crop_box(self, force_snap=False):
        """Returns (x1, y1, x2, y2) crop box for the current frame."""
        if force_snap:
            self.current_center_x = self.target_center_x
        else:
            self._advance_camera(self.target_center_x - self.current_center_x)
        self._clamp_center()
        half_crop = self.crop_width / 2
        x1 = max(0, int(self.current_center_x - half_crop))
        x2 = min(self.video_width, int(self.current_center_x + half_crop))
        return x1, 0, x2, self.video_height

class SpeakerTracker:
    """
    Tracks speakers over time to prevent rapid switching and handle temporary obstructions.
    """
    def __init__(self, stabilization_frames=15, cooldown_frames=30):
        self.active_speaker_id = None
        self.speaker_scores = {}  # {id: score}
        self.last_seen = {}       # {id: frame_number}
        self.locked_counter = 0   # How long we've been locked on current speaker
        
        # Hyperparameters
        self.stabilization_threshold = stabilization_frames # Frames needed to confirm a new speaker
        self.switch_cooldown = cooldown_frames              # Minimum frames before switching again
        self.last_switch_frame = -1000
        
        # ID tracking
        self.next_id = 0
        self.known_faces = [] # [{'id': 0, 'center': x, 'last_frame': 123}]

    def _find_best_match_id(self, center_x, frame_number, width):
        best_match_id = -1
        min_dist = width * 0.15
        for known_face in self.known_faces:
            if frame_number - known_face['last_frame'] > 30:
                continue
            dist = abs(center_x - known_face['center'])
            if dist < min_dist:
                min_dist = dist
                best_match_id = known_face['id']
        return best_match_id

    def _allocate_face_id(self, best_match_id):
        if best_match_id != -1:
            return best_match_id
        allocated = self.next_id
        self.next_id += 1
        return allocated

    def _upsert_known_face(self, face_id, center_x, frame_number):
        self.known_faces = [known_face for known_face in self.known_faces if known_face['id'] != face_id]
        self.known_faces.append({'id': face_id, 'center': center_x, 'last_frame': frame_number})

    def _build_current_candidates(self, face_candidates, frame_number, width):
        current_candidates = []
        for face in face_candidates:
            x, _, w, _ = face['box']
            center_x = x + w / 2
            match_id = self._find_best_match_id(center_x, frame_number, width)
            face_id = self._allocate_face_id(match_id)
            self._upsert_known_face(face_id, center_x, frame_number)
            current_candidates.append({'id': face_id, 'box': face['box'], 'score': face['score']})
        return current_candidates

    def _decay_scores(self):
        for pid in tuple(self.speaker_scores.keys()):
            self.speaker_scores[pid] *= 0.85
            if self.speaker_scores[pid] < 0.1:
                del self.speaker_scores[pid]

    def _accumulate_scores(self, current_candidates, width):
        for candidate in current_candidates:
            pid = candidate['id']
            raw_score = candidate['score'] / (width * width * 0.05)
            self.speaker_scores[pid] = self.speaker_scores.get(pid, 0) + raw_score

    def _pick_best_candidate(self, current_candidates):
        best_candidate = None
        max_score = -1.0
        for candidate in current_candidates:
            pid = candidate['id']
            total_score = self.speaker_scores.get(pid, 0)
            if pid == self.active_speaker_id:
                total_score *= 3.0
            if total_score > max_score:
                max_score = total_score
                best_candidate = candidate
        return best_candidate

    def _find_active_candidate(self, current_candidates):
        return next((cand for cand in current_candidates if cand['id'] == self.active_speaker_id), None)

    def _can_switch_now(self, frame_number):
        return (frame_number - self.last_switch_frame) >= self.switch_cooldown

    def get_target(self, face_candidates, frame_number, width):
        """Decides which face to focus on."""
        current_candidates = self._build_current_candidates(face_candidates, frame_number, width)
        self._decay_scores()
        self._accumulate_scores(current_candidates, width)

        if not current_candidates:
            return None

        best_candidate = self._pick_best_candidate(current_candidates)
        if not best_candidate:
            return None

        target_id = best_candidate['id']
        if target_id == self.active_speaker_id:
            self.locked_counter += 1
            return best_candidate['box']

        if not self._can_switch_now(frame_number):
            old_candidate = self._find_active_candidate(current_candidates)
            if old_candidate:
                return old_candidate['box']

        self.active_speaker_id = target_id
        self.last_switch_frame = frame_number
        self.locked_counter = 0
        return best_candidate['box']

def detect_face_candidates(frame):
    """
    Returns list of all detected faces using lightweight FaceDetection.
    """
    height, width, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    results = face_detection.detect(mp_image)

    candidates = []

    if not results.detections:
        return candidates

    for detection in results.detections:
        # Tasks API's BoundingBox is already in absolute pixels (unlike
        # Solutions' relative_bounding_box, which needed *width/*height).
        bbox = detection.bounding_box
        x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

        # Filter invalid / tiny detections (noise, logos, artifacts).
        if w <= 0 or h <= 0:
            continue
        if (w * h) < (width * height * MIN_FACE_AREA_RATIO):
            continue

        candidates.append({
            'box': [x, y, w, h],
            'score': w * h  # Area as score
        })

    return candidates

def detect_person_yolo(frame):
    """
    Fallback: Detect largest person using YOLO when face detection fails.
    Returns [x, y, w, h] of the person's 'upper body' approximation.
    """
    # Use the globally loaded model
    results = model(frame, verbose=False, classes=[0]) # class 0 is person
    
    if not results:
        return None
        
    best_box = None
    max_area = 0
    
    for result in results:
        boxes = result.boxes
        for box in boxes:
            x1, y1, x2, y2 = [int(i) for i in box.xyxy[0]]
            w = x2 - x1
            h = y2 - y1
            area = w * h
            
            if area > max_area:
                max_area = area
                # Focus on the top 40% of the person (head/chest) for framing
                # This approximates where the face is if we can't detect it directly
                face_h = int(h * 0.4)
                best_box = [x1, y1, w, face_h]
                
    return best_box

def _build_blurred_background(frame, output_width, output_height):
    orig_h, orig_w = frame.shape[:2]
    bg_scale = output_height / orig_h
    bg_w = int(orig_w * bg_scale)
    bg_resized = cv2.resize(frame, (bg_w, output_height))
    start_x = max(0, (bg_w - output_width) // 2)
    background = bg_resized[:, start_x:start_x + output_width]
    if background.shape[1] != output_width:
        background = cv2.resize(background, (output_width, output_height))
    return cv2.GaussianBlur(background, (51, 51), 0)


def create_general_frame(frame, output_width, output_height):
    """Create blurred-background layout with centered full-width foreground."""
    orig_h, orig_w = frame.shape[:2]
    background = _build_blurred_background(frame, output_width, output_height)
    scale = output_width / orig_w
    fg_h = int(orig_h * scale)
    foreground = cv2.resize(frame, (output_width, fg_h))
    y_offset = (output_height - fg_h) // 2
    final_frame = background.copy()
    final_frame[y_offset:y_offset + fg_h, :] = foreground
    return final_frame


def _iou(box_a, box_b):
    """Intersection-over-Union for two boxes [x, y, w, h]."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax + aw, bx + bw)
    inter_y2 = min(ay + ah, by + bh)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    if inter_area == 0:
        return 0.0

    union_area = aw * ah + bw * bh - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def _build_scene_sample_indices(start_f, end_f, fps):
    step = max(1, int(fps * 0.3))
    max_samples = max(1, int(MAX_SAMPLES_PER_SCENE))
    min_samples = max(1, min(int(MIN_SAMPLES_PER_SCENE), max_samples))

    indices = list(range(start_f, end_f, step))[:max_samples]
    if not indices:
        return [start_f]

    # Ensure a minimum number of sample frames when scene span allows it.
    existing = set(indices)
    candidate = start_f
    while len(indices) < min_samples and candidate < end_f:
        if candidate not in existing:
            indices.append(candidate)
            existing.add(candidate)
        candidate += 1

    indices.sort()
    return indices[:max_samples]


def _update_tracked_faces(tracked_faces, candidates):
    for candidate in candidates:
        matched_face = next(
            (face for face in tracked_faces if _iou(candidate['box'], face['box']) >= IOU_MATCH_THRESHOLD),
            None,
        )
        if matched_face:
            matched_face['box'] = candidate['box']
            matched_face['seen'] += 1
        else:
            tracked_faces.append({'box': candidate['box'], 'seen': 1})


def count_distinct_faces_in_scene(cap, start_f, end_f, fps):
    """Estimate distinct faces in a scene with sequential reads and IoU matching."""
    frame_indices = _build_scene_sample_indices(start_f, end_f, fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

    tracked_faces = []
    counts_per_frame = []
    target_set = set(frame_indices)
    current_f = start_f
    last_wanted = frame_indices[-1]

    while current_f <= last_wanted:
        ret, frame = cap.read()
        if not ret:
            break
        if current_f in target_set:
            candidates = detect_face_candidates(frame)
            counts_per_frame.append(len(candidates))
            _update_tracked_faces(tracked_faces, candidates)
        current_f += 1

    min_seen = 2 if len(frame_indices) > 2 else 1
    distinct_faces = [face for face in tracked_faces if face['seen'] >= min_seen]
    distinct_faces.sort(key=lambda face: face['box'][0])
    tracked_boxes = [face['box'] for face in distinct_faces]
    return len(distinct_faces), len(frame_indices), counts_per_frame, tracked_boxes


def _smooth_strategies(strategies):
    """Smooth isolated strategy flips to reduce one-scene flicker."""
    if len(strategies) < 3:
        return strategies

    smoothed = strategies.copy()
    for i in range(1, len(strategies) - 1):
        prev_s = strategies[i - 1]
        curr_s = strategies[i]
        next_s = strategies[i + 1]
        if prev_s == next_s and curr_s != prev_s:
            smoothed[i] = prev_s

    return smoothed

def _classify_scene_strategy(distinct_count):
    if distinct_count == 0:
        return 'GENERAL'
    if distinct_count == 1:
        return 'TRACK'
    if 2 <= distinct_count <= 4:
        return 'MULTI_SPEAKER'
    return 'GENERAL'


def analyze_scenes_strategy(video_path, scenes):
    """
    Analyzes each scene to determine if it should be TRACK (single person),
    MULTI_SPEAKER (2-4 people) or GENERAL (crowd/b-roll/wide shot).

    Retourne (strategies, tracked_boxes_per_scene).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ['TRACK'] * len(scenes), [[] for _ in scenes]

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    raw_strategies = []
    tracked_boxes_per_scene = []

    for start, end in tqdm(scenes, desc="   Analyzing Scenes"):
        start_f = start.frame_num
        end_f = end.frame_num

        # Garde-fou scènes très courtes (< ~0.5s)
        if end_f - start_f < max(3, int(fps * 0.5)):
            raw_strategies.append('TRACK')
            tracked_boxes_per_scene.append([])
            continue

        distinct_count, n_samples, _, tracked_boxes = (
            count_distinct_faces_in_scene(cap, start_f, end_f, fps)
        )

        if n_samples == 0:
            raw_strategies.append('GENERAL')
            tracked_boxes_per_scene.append([])
            continue

        strategy = _classify_scene_strategy(distinct_count)

        raw_strategies.append(strategy)
        tracked_boxes_per_scene.append(tracked_boxes)

    cap.release()

    strategies = _smooth_strategies(raw_strategies)

    # Si le lissage a changé une scène vers une stratégie != MULTI_SPEAKER,
    # les tracked_boxes associées ne sont plus pertinentes.
    for i, (raw, smoothed) in enumerate(zip(raw_strategies, strategies)):
        if raw != smoothed and smoothed != 'MULTI_SPEAKER':
            tracked_boxes_per_scene[i] = []

    return strategies, tracked_boxes_per_scene


# ============================================================
# RAFFINEMENT PAR ACTIVITÉ DE PAROLE (audio + mouvement des lèvres)
# ============================================================

def _extract_audio_rms(video_path, target_fps):
    """
    Extrait la piste audio via ffmpeg (mono 16kHz WAV), puis calcule une
    énergie RMS par fenêtre alignée approximativement sur les frames vidéo.

    Retourne un np.array, ou None si pas d'audio exploitable.
    """
    # Security/correctness: use a unique path per call rather than a fixed
    # shared /tmp filename -- concurrent jobs calling this at the same time
    # would otherwise race on the same file (one job's ffmpeg write
    # clobbering another job's still-unread WAV) (audit finding P2-8).
    fd, wav_path = tempfile.mkstemp(prefix="_scene_audio_", suffix=".wav")
    os.close(fd)
    try:
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", "-ac", "1", "-ar", "16000",
                    "-f", "wav", wav_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return None

        try:
            with wave.open(wav_path, "rb") as wf:
                sr = wf.getframerate()
                n_samples = wf.getnframes()
                raw = wf.readframes(n_samples)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        except Exception:
            return None

        if samples.size == 0:
            return None
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass

    samples_per_video_frame = max(1, int(sr / target_fps))
    rms_per_frame = []
    for i in range(0, samples.size, samples_per_video_frame):
        window = samples[i:i + samples_per_video_frame]
        if window.size == 0:
            continue
        rms_per_frame.append(np.sqrt(np.mean(window ** 2)))

    return np.array(rms_per_frame)


def _mouth_aspect_ratio(landmarks, w, h):
    """Ratio ouverture verticale / largeur de bouche (MAR)."""
    top = landmarks[MOUTH_TOP]
    bottom = landmarks[MOUTH_BOTTOM]
    left = landmarks[MOUTH_LEFT]
    right = landmarks[MOUTH_RIGHT]

    vert = np.hypot((top.x - bottom.x) * w, (top.y - bottom.y) * h)
    horiz = np.hypot((left.x - right.x) * w, (left.y - right.y) * h)

    return vert / horiz if horiz > 0 else 0.0


def _landmarks_to_box(landmarks, w, h):
    xs = [lm.x * w for lm in landmarks]
    ys = [lm.y * h for lm in landmarks]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def _best_matching_face_id(box, tracked_boxes_template):
    best_id, best_iou = None, 0.0
    for i, ref_box in enumerate(tracked_boxes_template):
        iou = _iou(box, ref_box)
        if iou > best_iou:
            best_iou, best_id = iou, i
    if best_id is None or best_iou < 0.15:
        return None
    return best_id


def _interpolate_signal_nans(arr):
    if np.all(np.isnan(arr)):
        return arr
    nans = np.isnan(arr)
    if nans.any():
        arr[nans] = np.interp(np.flatnonzero(nans), np.flatnonzero(~nans), arr[~nans])
    return arr


def _track_mouth_signals(cap, start_f, end_f, tracked_boxes_template):
    """
    Relit la scène séquentiellement avec FaceMesh, et pour chaque visage
    suivi (matché par IoU avec la box de référence), accumule un signal
    temporel d'ouverture de bouche (MAR).

    Retourne un dict {face_id: np.array(mar_signal_par_frame)}.
    """
    signals = {i: [] for i in range(len(tracked_boxes_template))}

    with _mp_vision.FaceLandmarker.create_from_options(
        _mp_vision.FaceLandmarkerOptions(
            base_options=_mp_base_options(model_asset_path=_FACE_LANDMARKER_MODEL_PATH),
            running_mode=_mp_vision.RunningMode.VIDEO,
            num_faces=max(1, len(tracked_boxes_template)),
            min_face_detection_confidence=0.5,
        )
    ) as face_mesh:

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        current_f = start_f

        while current_f < end_f:
            ret, frame = cap.read()
            if not ret:
                break

            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            # VIDEO mode needs strictly increasing timestamps within this
            # detector instance's lifetime -- absolute video time doesn't
            # matter here (nothing else reads it), just monotonicity.
            results = face_mesh.detect_for_video(mp_image, current_f - start_f)

            frame_values = {i: np.nan for i in signals}

            if results.face_landmarks:
                for face_landmarks in results.face_landmarks:
                    box = _landmarks_to_box(face_landmarks, w, h)
                    best_id = _best_matching_face_id(box, tracked_boxes_template)
                    if best_id is not None:
                        frame_values[best_id] = _mouth_aspect_ratio(face_landmarks, w, h)

            for i in signals:
                signals[i].append(frame_values[i])

            current_f += 1

    for i in signals:
        arr = np.array(signals[i], dtype=np.float32)
        signals[i] = _interpolate_signal_nans(arr)

    return signals


def _count_active_speakers(audio_seg, mouth_signals, min_len):
    active_speakers = 0
    audio_std = np.std(audio_seg)
    if audio_std == 0:
        return 0

    for signal in mouth_signals.values():
        sig = signal[:min_len]
        if np.all(np.isnan(sig)) or np.std(sig) == 0:
            continue
        corr = np.corrcoef(sig, audio_seg)[0, 1]
        if not np.isnan(corr) and corr >= MIN_ACTIVE_CORRELATION:
            active_speakers += 1
    return active_speakers


def refine_multi_speaker_scenes(video_path, scenes, strategies, tracked_boxes_per_scene):
    """
    Affine les scènes classées MULTI_SPEAKER en vérifiant, via corrélation
    mouvement des lèvres <-> énergie audio, combien de personnes VISIBLES
    parlent réellement.

    - 1 seul visage corrélé à l'audio -> TRACK
    - 2+ visages corrélés -> reste MULTI_SPEAKER
    - Pas d'audio exploitable -> décision initiale conservée (fallback sûr)

    Retourne la liste de stratégies raffinée.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return strategies

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    refined = strategies.copy()
    audio_rms_full = _extract_audio_rms(video_path, fps)
    if audio_rms_full is None or audio_rms_full.size < 3:
        cap.release()
        return refined

    for idx, (start, end) in enumerate(tqdm(scenes, desc="   Refining MULTI_SPEAKER scenes")):
        if strategies[idx] != 'MULTI_SPEAKER':
            continue

        tracked_boxes = tracked_boxes_per_scene[idx]
        if len(tracked_boxes) < 2:
            continue

        start_f = start.frame_num
        end_f = end.frame_num
        # Align audio to the current scene to correlate the correct time range.
        audio_rms = audio_rms_full[start_f:end_f]
        if audio_rms.size < 3:
            continue

        mouth_signals = _track_mouth_signals(cap, start_f, end_f, tracked_boxes)

        min_len = min(audio_rms.size, min(len(s) for s in mouth_signals.values()))
        if min_len < 3:
            continue
        audio_seg = audio_rms[:min_len]

        active_speakers = _count_active_speakers(audio_seg, mouth_signals, min_len)

        if active_speakers == 1:
            refined[idx] = 'TRACK'
        # active_speakers == 0 ou >= 2 -> on garde la décision initiale

    cap.release()
    return refined


# ============================================================
# RENDU DU SPLIT-SCREEN 50/50 (MULTI_SPEAKER)
# ============================================================

def _compute_separator_thickness(output_height):
    """
    Épaisseur de la bande de séparation, proportionnelle à la hauteur de
    sortie, bornée entre SEPARATOR_MIN_PX et SEPARATOR_MAX_PX, forcée paire
    pour un centrage pixel-parfait.
    """
    raw = output_height * SEPARATOR_THICKNESS_RATIO
    thickness = int(round(raw))
    thickness = max(SEPARATOR_MIN_PX, min(SEPARATOR_MAX_PX, thickness))

    if thickness % 2 != 0:
        thickness += 1

    return thickness


def _crop_centered_on_face(frame, face_box, target_w, target_h):
    """
    Recadre le frame source autour du visage donné pour remplir exactement
    (target_w x target_h), en conservant le ratio d'aspect cible (crop,
    pas de déformation), centré sur le visage.
    """
    src_h, src_w, _ = frame.shape
    fx, fy, fw, fh = face_box
    face_cx = fx + fw / 2
    face_cy = fy + fh / 2

    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if target_ratio > src_ratio:
        crop_w = src_w
        crop_h = int(crop_w / target_ratio)
    else:
        crop_h = src_h
        crop_w = int(crop_h * target_ratio)

    crop_w = min(crop_w, src_w)
    crop_h = min(crop_h, src_h)

    x1 = int(face_cx - crop_w / 2)
    y1 = int(face_cy - crop_h / 2)

    x1 = max(0, min(x1, src_w - crop_w))
    y1 = max(0, min(y1, src_h - crop_h))

    cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
    resized = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    return resized


def render_multi_speaker_frame(frame, tracked_boxes, output_width, output_height):
    """
    Compose un frame en split-screen VERTICAL 50/50 (top/bottom).

    - Toujours exactement 50% en haut / 50% en bas.
    - Bande de séparation fine et noire, épaisseur proportionnelle à la
      résolution de sortie.
    - Si 3-4 visages détectés : garde les 2 avec la plus grande aire.
    """
    src_h, src_w, _ = frame.shape

    separator_px = _compute_separator_thickness(output_height)

    if len(tracked_boxes) > 2:
        boxes_sorted_by_area = sorted(
            tracked_boxes, key=lambda b: b[2] * b[3], reverse=True
        )[:2]
        boxes = sorted(boxes_sorted_by_area, key=lambda b: b[0])
    elif len(tracked_boxes) == 2:
        boxes = tracked_boxes
    else:
        boxes = [[0, 0, src_w, src_h], [0, 0, src_w, src_h]]

    half_h = (output_height - separator_px) // 2
    top_h = half_h
    bottom_h = output_height - separator_px - top_h

    canvas = np.zeros((output_height, output_width, 3), dtype=np.uint8)

    for slot_idx, box in enumerate(boxes[:2]):
        slot_h = top_h if slot_idx == 0 else bottom_h
        crop = _crop_centered_on_face(frame, box, output_width, slot_h)
        y_offset = 0 if slot_idx == 0 else (top_h + separator_px)
        canvas[y_offset:y_offset + slot_h, 0:output_width] = crop

    sep_start = top_h
    sep_end = top_h + separator_px
    canvas[sep_start:sep_end, 0:output_width] = SEPARATOR_COLOR_BGR

    return canvas

def detect_scenes(video_path):
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video=video)
    scene_list = scene_manager.get_scene_list()
    fps = video.frame_rate
    return scene_list, fps

def get_video_resolution(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video file {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height


def sanitize_filename(filename):
    """Remove invalid characters from filename."""
    filename = re.sub(r'[<>:"/\\|?*#]', '', filename)
    filename = filename.replace(' ', '_')
    return filename[:100]


def _looks_like_netscape_cookies(content):
    """Best-effort validation for yt-dlp cookiefile format."""
    if not content:
        return False

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return False

    if lines[0].lower().startswith('# netscape http cookie file'):
        return True

    for line in lines:
        if line.startswith('#'):
            continue
        # Netscape cookie rows are tab-separated with at least 7 fields.
        if len(line.split('\t')) >= 7:
            return True

    return False


def _resolve_cookiefile_from_env():
    """Resolve YOUTUBE_COOKIES as either an existing file path or inline cookie content."""
    cookies_env = os.environ.get("YOUTUBE_COOKIES")
    if not cookies_env:
        print("⚠️ YOUTUBE_COOKIES env var not found.")
        return None

    cookies_env = cookies_env.strip()
    if not cookies_env or cookies_env == '...':
        print("⚠️ YOUTUBE_COOKIES is empty/placeholder. Continuing without cookies.")
        return None

    # Support path mode to avoid multiline .env parsing issues.
    if os.path.isfile(cookies_env):
        try:
            with open(cookies_env, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
            if not _looks_like_netscape_cookies(file_content):
                print(f"⚠️ YOUTUBE_COOKIES path exists but is not Netscape format: {cookies_env}")
                return None
            print(f"🍪 Using YouTube cookies file from path: {cookies_env}")
            return cookies_env
        except Exception as e:
            print(f"⚠️ Failed to read YOUTUBE_COOKIES file '{cookies_env}': {e}")
            return None

    # Inline mode: decode escaped newlines/tabs from .env style strings.
    normalized = cookies_env.replace('\\n', '\n').replace('\\t', '\t').strip()

    # Add header when user pasted only cookie rows.
    if 'Netscape HTTP Cookie File' not in normalized and '\t' in normalized:
        normalized = "# Netscape HTTP Cookie File\n" + normalized

    if not _looks_like_netscape_cookies(normalized):
        print("⚠️ YOUTUBE_COOKIES is not valid Netscape cookie content. Continuing without cookies.")
        return None

    cookies_path = '/app/cookies.txt'
    try:
        with open(cookies_path, 'w', encoding='utf-8') as f:
            f.write(normalized)
        print(f"🍪 Wrote cookies file for yt-dlp: {cookies_path} ({os.path.getsize(cookies_path)} bytes)")
        return cookies_path
    except Exception as e:
        print(f"⚠️ Failed to write cookies file: {e}")
        return None

def _build_ytdlp_opts(use_cookies: bool, job_cookies_path, proxy_session_id):
    """Construit les options yt-dlp selon la stratégie (avec/sans cookies)."""
    proxy_url = os.getenv('YOUTUBE_PROXY')
    if proxy_url and proxy_session_id:
        # Ajoute un identifiant de session au username pour garder la même IP
        # de sortie tout le long du job (extraction + téléchargement).
        # Sans ça, DataImpulse peut changer d'IP entre les deux requêtes,
        # ce qui fait rejeter l'URL signée par YouTube (HTTP 403).
        scheme, rest = proxy_url.split('://', 1)
        userpass, hostport = rest.split('@', 1)
        user, password = userpass.split(':', 1)
        proxy_url = f"{scheme}://{user}__sessid.{proxy_session_id}:{password}@{hostport}"

    return {
        'quiet': False,
        'verbose': True,
        'no_warnings': False,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'nocheckcertificate': True,
        'cachedir': False,
        'cookiefile': job_cookies_path if use_cookies else None,
        'proxy': proxy_url or None,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'] if not use_cookies else ['mweb', 'web'],
                'player_skip': ['webpage', 'configs'],
                'formats': ['missing_pot'],
            },
            # Sonar false positive (S5332): "pot-provider" only resolves on the
            # internal Docker Compose network (see docker-compose.yml),
            # never exposed publicly -- TLS on that internal hop isn't the
            # control that matters here.
            'youtubepot-bgutilhttp': {'base_url': 'http://pot-provider:4416'}  # NOSONAR
        },
        # Pas de 'http_headers' custom ici : yt-dlp applique automatiquement
        # les en-têtes cohérents avec le client choisi (android/ios/web...).
        # Un User-Agent forcé en dur entre en conflit avec l'URL signée
        # par YouTube pour un client précis (ex: c=IOS) et cause un 403.
    }


def _make_job_cookies_copy():
    """
    Copie isolee des cookies pour ce job precis. Evite que plusieurs
    telechargements concurrents ecrivent en meme temps dans le meme fichier
    cookies.txt, ce qui corrompt le fichier et fait invalider la session
    par YouTube ("cookies no longer valid").
    """
    master_cookies_path = os.getenv('YOUTUBE_COOKIES')
    if not master_cookies_path or not os.path.exists(master_cookies_path):
        return None
    fd, job_cookies_path = tempfile.mkstemp(suffix='.txt', prefix='ytcookies_')
    os.close(fd)
    shutil.copy(master_cookies_path, job_cookies_path)
    return job_cookies_path


def _extract_info_with_fallback(url, job_cookies_path, proxy_session_id):
    """
    Tente l'extraction sans cookies (android/ios, valide avec le proxy),
    puis avec cookies en fallback (mweb/web + PO Token) si necessaire.
    Retourne (info, opts_utilisees) ou leve la derniere erreur rencontree.
    """
    last_error = None
    for use_cookies in (False, True):
        opts = _build_ytdlp_opts(use_cookies, job_cookies_path, proxy_session_id)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info, opts
        except Exception as e:
            last_error = e
            print(f"WARNING Echec avec use_cookies={use_cookies}: {e}")
    raise last_error


def _print_download_failure(error):
    """Affiche le message d'erreur utilisateur en cas d'echec total."""
    print("YOUTUBE DOWNLOAD ERROR", file=sys.stderr)
    error_msg = f"""

FATAL ERROR: YOUTUBE DOWNLOAD FAILED

REASON: YouTube has blocked the download request (Error 429/Unavailable).
        This is likely a temporary IP ban on this server.

SOLUTION FOR USER
---------------------------------------------------------------------
1. Download the video manually to your computer.
2. Use the 'Upload Video' tab in this app to process it.
---------------------------------------------------------------------

Technical Details: {str(error)}
    """
    print(error_msg, file=sys.stdout)
    print(error_msg, file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    time.sleep(0.5)


def _locate_downloaded_file(output_dir, sanitized_title):
    """Retrouve le fichier telecharge, meme si l'extension differe de .mp4."""
    downloaded_file = os.path.join(output_dir, f'{sanitized_title}.mp4')
    if os.path.exists(downloaded_file):
        return downloaded_file
    for f in os.listdir(output_dir):
        if f.startswith(sanitized_title) and f.endswith('.mp4'):
            return os.path.join(output_dir, f)
    return downloaded_file


def _run_download(url, output_dir, sanitized_title, base_opts):
    """Lance le telechargement effectif avec le format H.264 prioritaire."""
    output_template = os.path.join(output_dir, f'{sanitized_title}.%(ext)s')
    expected_file = os.path.join(output_dir, f'{sanitized_title}.mp4')
    if os.path.exists(expected_file):
        os.remove(expected_file)
        print("Removed existing file to re-download with H.264 codec")

    ydl_opts = {
        **base_opts,
        'format': (
            '18/22/'
            'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/'
            'bestvideo[vcodec^=avc1]+bestaudio/'
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/'
            'bestvideo+bestaudio/'
            'best[ext=mp4]/'
            'best'
        ),
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'overwrites': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return _locate_downloaded_file(output_dir, sanitized_title)


def download_youtube_video(url, output_dir="."):
    """
    Downloads a YouTube video using yt-dlp.
    Returns the path to the downloaded video and the video title.
    """
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print("Downloading video from YouTube...")
    step_start_time = time.time()

    job_cookies_path = _make_job_cookies_copy()
    # ID de session unique pour ce job — garantit la même IP de sortie
    # proxy pour toutes les requêtes (extraction + téléchargement).
    proxy_session_id = uuid.uuid4().hex[:12]

    try:
        try:
            info, base_opts = _extract_info_with_fallback(url, job_cookies_path, proxy_session_id)
        except Exception as e:
            _print_download_failure(e)
            raise

        video_title = info.get('title', 'youtube_video')
        sanitized_title = sanitize_filename(video_title)

        downloaded_file = _run_download(url, output_dir, sanitized_title, base_opts)

        step_end_time = time.time()
        print(f"Video downloaded in {step_end_time - step_start_time:.2f}s: {downloaded_file}")

        return downloaded_file, sanitized_title

    finally:
        if job_cookies_path and os.path.exists(job_cookies_path):
            os.remove(job_cookies_path)


def _prepare_temp_paths(final_output_video):
    base_name = os.path.splitext(final_output_video)[0]
    return f"{base_name}_temp_video.mp4", f"{base_name}_temp_audio.aac"


def _cleanup_existing_outputs(*paths):
    for path in paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        except FileNotFoundError:
            continue


def _fallback_single_scene(input_video, fps):
    cap = cv2.VideoCapture(input_video)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    from scenedetect import FrameTimecode
    return [(FrameTimecode(0, fps), FrameTimecode(total_frames, fps))]


def _compute_output_dimensions(original_height):
    output_height = original_height
    output_width = int(output_height * ASPECT_RATIO)
    if output_width % 2 != 0:
        output_width += 1
    return output_width, output_height


def _build_scene_boundaries(scenes):
    return [(start.frame_num, end.frame_num) for start, end in scenes]


def _advance_scene_index(frame_number, current_scene_index, scene_boundaries):
    if current_scene_index >= len(scene_boundaries):
        return current_scene_index
    _, end_f = scene_boundaries[current_scene_index]
    if frame_number >= end_f and current_scene_index < len(scene_boundaries) - 1:
        return current_scene_index + 1
    return current_scene_index


def _render_track_frame(frame, frame_number, scene_boundaries, speaker_tracker, cameraman, output_width, output_height, original_width):
    if frame_number % 2 == 0:
        candidates = detect_face_candidates(frame)
        target_box = speaker_tracker.get_target(candidates, frame_number, original_width)
        if target_box:
            cameraman.update_target(target_box)
        else:
            person_box = detect_person_yolo(frame)
            if person_box:
                cameraman.update_target(person_box)

    is_scene_start = frame_number == scene_boundaries[0] if len(scene_boundaries) == 1 else False
    x1, y1, x2, y2 = cameraman.get_crop_box(force_snap=is_scene_start)
    if y2 > y1 and x2 > x1:
        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (output_width, output_height))
    return cv2.resize(frame, (output_width, output_height))


def _render_multi_speaker_frame_live(frame, frame_number, cameraman, scene_boxes, output_width, output_height):
    if frame_number % 2 == 0:
        live_candidates = detect_face_candidates(frame)
        if len(live_candidates) >= 2:
            cameraman._ms_live_boxes = sorted([candidate['box'] for candidate in live_candidates], key=lambda b: b[0])
    live_boxes = getattr(cameraman, '_ms_live_boxes', None)
    render_boxes = live_boxes if live_boxes else scene_boxes
    return render_multi_speaker_frame(frame, render_boxes, output_width, output_height)


def _reset_cameraman(cameraman, original_width):
    cameraman.current_center_x = original_width / 2
    cameraman.target_center_x = original_width / 2


def _render_frame_by_strategy(
    frame,
    frame_number,
    current_scene_index,
    scene_boundaries,
    scene_strategies,
    cameraman,
    speaker_tracker,
    output_width,
    output_height,
    original_width,
):
    strategy = scene_strategies[current_scene_index] if current_scene_index < len(scene_strategies) else 'TRACK'

    if strategy == 'GENERAL':
        _reset_cameraman(cameraman, original_width)
        return create_general_frame(frame, output_width, output_height)

    # Split-screen (2 speakers) is intentionally disabled for now.
    # Keep this block commented to allow easy reactivation later.
    # if strategy == 'MULTI_SPEAKER':
    #     scene_boxes = tracked_boxes_per_scene[current_scene_index] if current_scene_index < len(tracked_boxes_per_scene) else []
    #     _reset_cameraman(cameraman, original_width)
    #     return _render_multi_speaker_frame_live(frame, frame_number, cameraman, scene_boxes, output_width, output_height)

    scene_range = scene_boundaries[current_scene_index] if current_scene_index < len(scene_boundaries) else (0, 0)
    is_scene_start = frame_number == scene_range[0]
    if frame_number % 2 == 0:
        candidates = detect_face_candidates(frame)
        target_box = speaker_tracker.get_target(candidates, frame_number, original_width)
        if target_box:
            cameraman.update_target(target_box)
        else:
            person_box = detect_person_yolo(frame)
            if person_box:
                cameraman.update_target(person_box)
    x1, y1, x2, y2 = cameraman.get_crop_box(force_snap=is_scene_start)
    if y2 > y1 and x2 > x1:
        return cv2.resize(frame[y1:y2, x1:x2], (output_width, output_height))
    return cv2.resize(frame, (output_width, output_height))


def _process_frames_to_temp_video(
    input_video,
    temp_video_output,
    fps,
    output_width,
    output_height,
    scene_boundaries,
    scene_strategies,
    cameraman,
    speaker_tracker,
    original_width,
):
    command = [
        'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{output_width}x{output_height}', '-pix_fmt', 'bgr24',
        '-r', str(fps), '-i', '-', '-c:v', 'libx264',
        '-preset', EXPORT_VIDEO_PRESET, '-crf', EXPORT_VIDEO_CRF,
        '-pix_fmt', 'yuv420p', '-an', temp_video_output
    ]
    ffmpeg_process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    cap = cv2.VideoCapture(input_video)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_number = 0
    current_scene_index = 0

    with tqdm(total=total_frames, desc="   Processing", file=sys.stdout) as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            current_scene_index = _advance_scene_index(frame_number, current_scene_index, scene_boundaries)
            output_frame = _render_frame_by_strategy(
                frame,
                frame_number,
                current_scene_index,
                scene_boundaries,
                scene_strategies,
                cameraman,
                speaker_tracker,
                output_width,
                output_height,
                original_width,
            )
            ffmpeg_process.stdin.write(output_frame.tobytes())
            frame_number += 1
            pbar.update(1)

    ffmpeg_process.stdin.close()
    stderr_output = ffmpeg_process.stderr.read().decode()
    try:
        ffmpeg_process.wait(timeout=FFMPEG_STEP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # Note: the outer job watchdog (REEL_JOB_MAX_PROCESSING_SECONDS in
        # app.py) also bounds this whole pipeline's total runtime; this is
        # a local safety net for the final flush specifically hanging.
        ffmpeg_process.kill()
        ffmpeg_process.wait()
    cap.release()
    return ffmpeg_process.returncode, stderr_output


def _extract_audio_track(input_video, temp_audio_output):
    audio_extract_command = ['ffmpeg', '-y', '-i', input_video, '-vn', '-acodec', 'copy', temp_audio_output]
    try:
        subprocess.run(
            audio_extract_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("\n   ❌ Audio extraction failed (maybe no audio?). Proceeding without audio.")
        return False


def _merge_video_and_audio(temp_video_output, temp_audio_output, final_output_video):
    if os.path.exists(temp_audio_output):
        merge_command = [
            'ffmpeg', '-y', '-i', temp_video_output, '-i', temp_audio_output,
            '-c:v', 'copy', '-c:a', 'copy', final_output_video
        ]
    else:
        merge_command = ['ffmpeg', '-y', '-i', temp_video_output, '-c:v', 'copy', final_output_video]

    try:
        subprocess.run(
            merge_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
        )
        print(f"   ✅ Clip saved to {final_output_video}")
        return True
    except subprocess.TimeoutExpired:
        print(f"\n   ❌ Final merge timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s.")
        return False
    except subprocess.CalledProcessError as exc:
        print("\n   ❌ Final merge failed.")
        print("   Stderr:", exc.stderr.decode())
        return False


def process_video_to_vertical(input_video, final_output_video):
    """Convert horizontal video to vertical using scene strategies and tracking."""
    temp_video_output, temp_audio_output = _prepare_temp_paths(final_output_video)
    _cleanup_existing_outputs(temp_video_output, temp_audio_output, final_output_video)

    print(f"🎬 Processing clip: {input_video}")
    print("   Step 1: Detecting scenes...")
    scenes, fps = detect_scenes(input_video)
    if not scenes:
        print("   ❌ No scenes were detected. Using full video as one scene.")
        scenes = _fallback_single_scene(input_video, fps)
    print(f"   ✅ Found {len(scenes)} scenes.")

    print("\n   🧠 Step 2: Preparing Active Tracking...")
    original_width, original_height = get_video_resolution(input_video)
    output_width, output_height = _compute_output_dimensions(original_height)
    cameraman = SmoothedCameraman(output_width, output_height, original_width, original_height)

    print("\n   🤖 Step 3: Analyzing Scenes for Strategy (Single vs Group)...")
    scene_strategies, tracked_boxes_per_scene = analyze_scenes_strategy(input_video, scenes)
    scene_strategies = refine_multi_speaker_scenes(input_video, scenes, scene_strategies, tracked_boxes_per_scene)
    scene_strategies = ['TRACK' if strategy == 'MULTI_SPEAKER' else strategy for strategy in scene_strategies]

    print("\n   ✂️ Step 4: Processing video frames...")
    scene_boundaries = _build_scene_boundaries(scenes)
    speaker_tracker = SpeakerTracker(cooldown_frames=30)
    return_code, stderr_output = _process_frames_to_temp_video(
        input_video,
        temp_video_output,
        fps,
        output_width,
        output_height,
        scene_boundaries,
        scene_strategies,
        cameraman,
        speaker_tracker,
        original_width,
    )

    if return_code != 0:
        print("\n   ❌ FFmpeg frame processing failed.")
        print("   Stderr:", stderr_output)
        return False

    print("\n   🔊 Step 5: Extracting audio...")
    _extract_audio_track(input_video, temp_audio_output)

    print("\n   ✨ Step 6: Merging...")
    success = _merge_video_and_audio(temp_video_output, temp_audio_output, final_output_video)
    _cleanup_existing_outputs(temp_video_output, temp_audio_output)
    return success

def _build_segments_from_word_list(words, language="unknown"):
    """
    Convert a flat list of word dicts into whisper-like segments.
    Expected word item shape: {'word': str, 'start': float, 'end': float, 'probability': float}
    """
    transcript_segments = []
    full_text_parts = []

    current_words = []
    seg_start = None
    seg_end = None

    for w in words:
        w_text = (w.get("word") or "").strip()
        w_start = float(w.get("start", 0.0))
        w_end = float(w.get("end", w_start))

        if not w_text:
            continue

        if seg_start is None:
            seg_start = w_start
        seg_end = w_end

        current_words.append({
            "word": w_text,
            "start": w_start,
            "end": w_end,
            "probability": float(w.get("probability", 1.0))
        })

        full_text_parts.append(w_text)

        # Sentence-ish split for compatibility
        if w_text.endswith((".", "!", "?")):
            seg_text = " ".join(item["word"] for item in current_words).strip()
            transcript_segments.append({
                "text": seg_text,
                "start": seg_start,
                "end": seg_end,
                "words": current_words
            })
            print(f"   [{seg_start:.2f}s -> {seg_end:.2f}s] {seg_text}")
            current_words = []
            seg_start = None
            seg_end = None

    if current_words:
        seg_text = " ".join(item["word"] for item in current_words).strip()
        s = seg_start if seg_start is not None else 0.0
        e = seg_end if seg_end is not None else s
        transcript_segments.append({
            "text": seg_text,
            "start": s,
            "end": e,
            "words": current_words
        })
        print(f"   [{s:.2f}s -> {e:.2f}s] {seg_text}")

    full_text = " ".join(full_text_parts).strip()
    return {
        "text": full_text,
        "segments": transcript_segments,
        "language": language or "unknown"
    }


def _transcribe_with_assemblyai(video_path):
    print("🛰️  Transcribing with AssemblyAI (remote API)...")

    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is missing.")

    import assemblyai as aai

    aai.settings.api_key = api_key

    timeout_seconds = int(os.getenv("ASSEMBLYAI_TIMEOUT_SECONDS", "600"))

    # Use new speech_models parameter (list-based)
    config = aai.TranscriptionConfig(
        punctuate=True,
        format_text=True,
        speech_models=["universal-3-5-pro", "universal-2"]
    )

    transcriber = aai.Transcriber(config=config)

    start_time = time.time()
    transcript = transcriber.transcribe(video_path)
    elapsed = time.time() - start_time

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

    print(f"✅ AssemblyAI done in {elapsed:.2f}s")
    if elapsed > timeout_seconds:
        print(f"⚠️ Processing time exceeded hint ({timeout_seconds}s), but completed successfully.")

    lang = transcript.language_code or os.getenv("ASSEMBLYAI_DEFAULT_LANGUAGE", "unknown")
    print(f"   Detected language: {lang}")

    words = []
    for w in (transcript.words or []):
        words.append({
            "word": (w.text or "").strip(),
            "start": float(w.start or 0) / 1000.0,  # ms -> s
            "end": float(w.end or 0) / 1000.0,      # ms -> s
            "probability": 1.0
        })

    result = _build_segments_from_word_list(words, language=lang)
    result["meta"] = {
        "provider": "assemblyai",
        "audio_seconds": result["segments"][-1]["end"] if result["segments"] else 0.0,
    }
    return result


def _transcribe_with_faster_whisper(video_path):
    print("🎙️  Transcribing with Faster-Whisper (local fallback)...")

    from faster_whisper import WhisperModel

    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments, info = model.transcribe(
        video_path,
        word_timestamps=True,
        beam_size=1
    )

    print(f"   Detected language '{info.language}' with probability {info.language_probability:.2f}")

    transcript_segments = []
    full_text = ""

    for segment in segments:
        print(f"   [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

        seg_dict = {
            "text": segment.text,
            "start": segment.start,
            "end": segment.end,
            "words": []
        }

        if segment.words:
            for word in segment.words:
                seg_dict["words"].append({
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability
                })

        transcript_segments.append(seg_dict)
        full_text += segment.text + " "

    return {
        "text": full_text.strip(),
        "segments": transcript_segments,
        "language": info.language,
        "meta": {
            "provider": "faster_whisper",
            "audio_seconds": transcript_segments[-1]["end"] if transcript_segments else 0.0,
        },
    }


def _load_transcriber_settings():
    provider = os.getenv("TRANSCRIBER_PROVIDER", "hybrid").strip().lower()
    fallback = os.getenv("TRANSCRIBER_FALLBACK", "faster_whisper").strip().lower()
    assembly_retry_attempts = max(1, int(os.getenv("ASSEMBLY_RETRY_ATTEMPTS", "2")))
    assembly_retry_delay_seconds = max(0.0, float(os.getenv("ASSEMBLY_RETRY_DELAY_SECONDS", "2")))
    return provider, fallback, assembly_retry_attempts, assembly_retry_delay_seconds


def _run_assemblyai_attempts(video_path, retry_attempts, retry_delay_seconds):
    last_error = None
    for attempt in range(1, retry_attempts + 1):
        try:
            return _transcribe_with_assemblyai(video_path), None
        except Exception as exc:
            last_error = exc
            print(f"⚠️ AssemblyAI failed (attempt {attempt}/{retry_attempts}): {exc}")
            if attempt < retry_attempts and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)
    return None, last_error


def transcribe_video(video_path):
    """
    Hybrid transcription entrypoint.
    TRANSCRIBER_PROVIDER: assemblyai | faster_whisper | hybrid
    TRANSCRIBER_FALLBACK: faster_whisper | none
    """
    provider, fallback, assembly_retry_attempts, assembly_retry_delay_seconds = _load_transcriber_settings()

    print(f"🎛️  Transcriber provider: {provider}")

    if provider == "assemblyai":
        result, last_error = _run_assemblyai_attempts(
            video_path,
            assembly_retry_attempts,
            assembly_retry_delay_seconds,
        )
        if result is not None:
            return result
        raise RuntimeError(f"AssemblyAI transcription failed after {assembly_retry_attempts} attempts: {last_error}")

    if provider == "faster_whisper":
        return _transcribe_with_faster_whisper(video_path)

    # Hybrid: retry AssemblyAI first, then fallback local if enabled.
    result, last_error = _run_assemblyai_attempts(
        video_path,
        assembly_retry_attempts,
        assembly_retry_delay_seconds,
    )
    if result is not None:
        return result

    if fallback == "faster_whisper":
        print("↩️ Falling back to Faster-Whisper...")
        return _transcribe_with_faster_whisper(video_path)

    raise RuntimeError(f"Transcription failed and fallback disabled. Root cause: {last_error}")

def _extract_error_message(exc):
    """Return a lowercase best-effort error string for provider routing."""
    try:
        return str(exc).lower()
    except Exception:
        return ""


def _is_quota_or_rate_limit_error(exc):
    msg = _extract_error_message(exc)
    return (
        "resource_exhausted" in msg
        or "quota exceeded" in msg
        or "rate limit" in msg
        or "429" in msg
        or "limit: 0" in msg
        or "too many requests" in msg
    )


def _strip_json_markdown(text):
    if not text:
        return text
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _build_words_payload(transcript_result):
    words = []
    for segment in transcript_result.get("segments", []):
        for word in segment.get("words", []):
            words.append({
                "w": word.get("word", ""),
                "s": word.get("start", 0.0),
                "e": word.get("end", 0.0),
            })
    return words


# _build_analysis_prompt fills REEL_PROMPT in with a targeted regex
# substitution instead of str.format() -- REEL_PROMPT is meant to be
# hand-edited (it gets tuned/rewritten directly in this file over time),
# and .format() treats EVERY '{' in the template as the start of a
# placeholder. A prompt edit that pastes in a JSON example -- exactly the
# kind of thing a prompt like this tends to grow, and exactly what broke it
# last time (KeyError: '\n  "w"', from the WORDS_JSON example block) --
# silently breaks every call unless each literal brace is manually doubled
# to '{{'/'}}', which is an easy, unobvious mistake to make and to miss in
# review. Matching only these 5 known names means any other '{...}'
# anywhere in the template is just text, never a trap.
_PROMPT_PLACEHOLDER_NAMES = (
    "video_duration",
    "transcript_text",
    "words_json",
    "max_clip_duration_seconds",
    "min_clip_duration_seconds",
)
_PROMPT_PLACEHOLDER_RE = re.compile(
    "{(" + "|".join(re.escape(name) for name in _PROMPT_PLACEHOLDER_NAMES) + ")}"
)


def _build_analysis_prompt(transcript_result, video_duration):
    words = _build_words_payload(transcript_result)
    values = {
        "video_duration": str(video_duration),
        "transcript_text": json.dumps(transcript_result.get("text", "")),
        "words_json": json.dumps(words),
        "max_clip_duration_seconds": str(MAX_CLIP_DURATIONS_SECOND),
        "min_clip_duration_seconds": str(MIN_CLIP_DURATION_SECONDS),
    }
    return _PROMPT_PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], REEL_PROMPT)


def _get_viral_clips_with_gemini(transcript_result, video_duration):
    """Analyze with Google Gemini."""
    print("🤖 Gemini Analysis...")

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found.")

    from google import genai
    client = genai.Client(api_key=api_key)

    print(f"   Model: {model_name}")

    prompt = _build_analysis_prompt(transcript_result, video_duration)

    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )

    cost_analysis = None
    try:
        usage = response.usage_metadata
        if usage:
            # Keep prices configurable via env to avoid stale hardcoded values.
            input_price_per_million = float(os.getenv("GEMINI_INPUT_PRICE_PER_MILLION", "0.075"))
            output_price_per_million = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_MILLION", "0.30"))

            prompt_tokens = usage.prompt_token_count or 0
            output_tokens = usage.candidates_token_count or 0

            input_cost = (prompt_tokens / 1_000_000) * input_price_per_million
            output_cost = (output_tokens / 1_000_000) * output_price_per_million
            total_cost = input_cost + output_cost

            cost_analysis = {
                "input_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "input_cost": input_cost,
                "output_cost": output_cost,
                "total_cost": total_cost,
                "model": model_name,
                "provider": "gemini",
            }

            print(f"💰 Token Usage ({model_name}):")
            print(f"   - Input: {prompt_tokens} (${input_cost:.6f})")
            print(f"   - Output: {output_tokens} (${output_cost:.6f})")
            print(f"   - Total: ${total_cost:.6f}")
    except Exception as e:
        print(f"⚠️ Could not calculate Gemini cost: {e}")

    text = _strip_json_markdown(response.text)
    result_json = json.loads(text)

    if cost_analysis:
        result_json["cost_analysis"] = cost_analysis

    return result_json


def _get_viral_clips_with_openai(transcript_result, video_duration):
    """Analyze with OpenAI."""
    print("🤖 OpenAI Analysis...")

    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY not found or still placeholder.")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print(f"   Model: {model_name}")

    prompt = _build_analysis_prompt(transcript_result, video_duration)

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a short-form video editing expert."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    text = _strip_json_markdown(response.choices[0].message.content)
    result_json = json.loads(text)

    try:
        usage = response.usage
        # Keep prices configurable via env.
        input_price_per_1k = float(os.getenv("OPENAI_INPUT_PRICE_PER_1K", "0.01"))
        output_price_per_1k = float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1K", "0.03"))

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        input_cost = prompt_tokens * input_price_per_1k / 1000.0
        output_cost = completion_tokens * output_price_per_1k / 1000.0
        total_cost = input_cost + output_cost

        result_json["cost_analysis"] = {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "model": model_name,
            "provider": "openai",
        }

        print(f"💰 Token Usage ({model_name}):")
        print(f"   - Input: {prompt_tokens} (${input_cost:.6f})")
        print(f"   - Output: {completion_tokens} (${output_cost:.6f})")
        print(f"   - Total: ${total_cost:.6f}")
    except Exception as e:
        print(f"⚠️ Could not calculate OpenAI cost: {e}")

    return result_json


def get_viral_clips(transcript_result, video_duration):
    """
    AI_PROVIDER:
      - gemini
      - openai
      - hybrid
    HYBRID behavior:
      - OpenIA first
      - fallback to Gemini when OpenIA fails (especially quota/rate-limit)
    """
    provider = os.getenv("AI_PROVIDER", "hybrid").strip().lower()
    print(f"🎛️  AI Provider: {provider}")

    if provider == "gemini":
        result = _get_viral_clips_with_gemini(transcript_result, video_duration)
        return _normalize_short_durations(result, video_duration)

    if provider == "openai":
        result = _get_viral_clips_with_openai(transcript_result, video_duration)
        return _normalize_short_durations(result, video_duration)

    # Hybrid mode
    print("🔄 Hybrid mode: trying OpenIA first...")
    try:
        result = _get_viral_clips_with_openai(transcript_result, video_duration)
        return _normalize_short_durations(result, video_duration)
    except Exception as e:
        print(f"⚠️ OpenIA failed: {e}")
        if _is_quota_or_rate_limit_error(e):
            print("↩️ OpenIA quota/rate-limit hit, falling back to OpenAI...")
        else:
            print("↩️ OpenIA failed, falling back to OpenAI...")

        try:
            result = _get_viral_clips_with_gemini(transcript_result, video_duration)
            return _normalize_short_durations(result, video_duration)
        except Exception as e2:
            raise RuntimeError(f"Both AI providers failed. OpenIA: {e}; Gemini: {e2}")

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _build_external_costs(transcript, clips_data):
    """Aggregate all external API costs for this job."""
    meta = transcript.get("meta", {})
    provider = meta.get("provider", "unknown")
    audio_seconds = _safe_float(meta.get("audio_seconds", 0.0))

    assembly_used = provider == "assemblyai"
    price_per_hour = _safe_float(os.getenv("ASSEMBLYAI_PRICE_PER_HOUR_USD", "0"))
    assembly_cost = (audio_seconds / 3600.0) * price_per_hour if assembly_used and price_per_hour > 0 else 0.0

    ca = (clips_data or {}).get("cost_analysis") or {}
    llm_cost_usd = _safe_float(ca.get("total_cost", 0.0))

    return {
        "assemblyai": {
            "used": assembly_used,
            "cost_usd": assembly_cost,
            "meta": {"audio_seconds": audio_seconds, "price_per_hour_usd": price_per_hour},
        },
        "llm": {
            "provider": ca.get("provider", "unknown"),
            "model": ca.get("model", "unknown"),
            "cost_usd": llm_cost_usd,
            "meta": ca,
        },
        "total_usd": assembly_cost + llm_cost_usd,
    }


def _clip_duration_bounds():
    return float(MIN_CLIP_DURATION_SECONDS), float(MAX_CLIP_DURATIONS_SECOND)


def _clamp_clip_window(start, end, source_duration):
    start = max(0.0, min(start, source_duration))
    end = max(0.0, min(end, source_duration))
    return start, end


def _normalize_single_short(clip, source_duration, min_clip_duration, max_clip_duration):
    if not isinstance(clip, dict):
        return None

    start = _safe_float(clip.get("start"), 0.0)
    end = _safe_float(clip.get("end"), 0.0)
    start, end = _clamp_clip_window(start, end, source_duration)
    if end <= start:
        return None

    duration = end - start
    if duration < min_clip_duration:
        end = min(source_duration, start + min_clip_duration)
        if (end - start) < min_clip_duration:
            return None

    duration = end - start
    if duration > max_clip_duration:
        end = start + max_clip_duration
        if end > source_duration:
            end = source_duration
            start = max(0.0, end - max_clip_duration)

    if end <= start:
        return None

    clip["start"] = round(start, 3)
    clip["end"] = round(end, 3)
    return clip


def _normalize_short_durations(clips_data, video_duration):
    shorts = clips_data.get("shorts") if isinstance(clips_data, dict) else None
    if not isinstance(shorts, list):
        return clips_data

    source_duration = _safe_float(video_duration, 0.0)
    if source_duration <= 0:
        return clips_data

    min_clip_duration, max_clip_duration = _clip_duration_bounds()

    normalized_shorts = []

    for clip in shorts:
        normalized = _normalize_single_short(
            clip,
            source_duration,
            min_clip_duration,
            max_clip_duration,
        )
        if normalized is not None:
            normalized_shorts.append(normalized)

    clips_data["shorts"] = normalized_shorts
    return clips_data

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AutoCrop-Vertical with Viral Clip Detection.")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-i', '--input', type=str, help="Path to the input video file.")
    input_group.add_argument('-u', '--url', type=str, help="YouTube URL to download and process.")

    parser.add_argument('-o', '--output', type=str, help="Output directory or file (if processing whole video).")
    parser.add_argument('--keep-original', action='store_true', help="Keep the downloaded YouTube video.")
    parser.add_argument('--skip-analysis', action='store_true', help="Skip AI analysis and convert the whole video.")

    args = parser.parse_args()

    script_start_time = time.time()

    def _ensure_dir(path: str) -> str:
        """Create directory if missing and return the same path."""
        if path:
            os.makedirs(path, exist_ok=True)
        return path

    # 1. Get Input Video
    if args.url:
        # For multi-clip runs, treat --output as an OUTPUT DIRECTORY (create it if needed).
        # For whole-video runs (--skip-analysis), --output can be a file path.
        if args.output and not args.skip_analysis:
            output_dir = _ensure_dir(args.output)
        else:
            # If output is a directory, use it; if it's a filename, use its directory; else default "."
            if args.output and os.path.isdir(args.output):
                output_dir = args.output
            elif args.output and not os.path.isdir(args.output):
                output_dir = os.path.dirname(args.output) or "."
            else:
                output_dir = "."

        input_video, video_title = download_youtube_video(args.url, output_dir)
    else:
        input_video = args.input
        video_title = os.path.splitext(os.path.basename(input_video))[0]

        if args.output and not args.skip_analysis:
            # For multi-clip runs, treat --output as an OUTPUT DIRECTORY (create it if needed).
            output_dir = _ensure_dir(args.output)
        else:
            # If output is a directory, use it; if it's a filename, use its directory; else default to input dir.
            if args.output and os.path.isdir(args.output):
                output_dir = args.output
            elif args.output and not os.path.isdir(args.output):
                output_dir = os.path.dirname(args.output) or os.path.dirname(input_video)
            else:
                output_dir = os.path.dirname(input_video)

    if not os.path.exists(input_video):
        print(f"❌ Input file not found: {input_video}")
        exit(1)

    # 2. Decision: Analyze clips or process whole?
    if args.skip_analysis:
        print("⏩ Skipping analysis, processing entire video...")
        output_file = args.output if args.output else os.path.join(output_dir, f"{video_title}_vertical.mp4")
        process_video_to_vertical(input_video, output_file)
    else:
        # 3. Transcribe
        transcript = transcribe_video(input_video)

        # Get duration
        cap = cv2.VideoCapture(input_video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        cap.release()

        # 4. Gemini Analysis
        clips_data = get_viral_clips(transcript, duration)

        if not clips_data or 'shorts' not in clips_data:
            print("❌ Failed to identify clips. Converting whole video as fallback.")
            output_file = os.path.join(output_dir, f"{video_title}_vertical.mp4")
            process_video_to_vertical(input_video, output_file)
        else:
            print(f"🔥 Found {len(clips_data['shorts'])} viral clips!")
            # Aggregate external costs
            clips_data["external_costs"] = _build_external_costs(transcript, clips_data)
            ec = clips_data["external_costs"]
            print("💸 External Costs Summary:")
            print(f"   - AssemblyAI : ${ec['assemblyai']['cost_usd']:.6f}")
            print(f"   - LLM ({ec['llm']['provider']}/{ec['llm']['model']}): ${ec['llm']['cost_usd']:.6f}")
            print(f"   - TOTAL      : ${ec['total_usd']:.6f}")

            # Save metadata
            clips_data['transcript'] = transcript # Save full transcript for subtitles
            metadata_file = os.path.join(output_dir, f"{video_title}_metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(clips_data, f, indent=2)
            print(f"   Saved metadata to {metadata_file}")

            # 5. Process each clip
            for i, clip in enumerate(clips_data['shorts']):
                start = clip['start']
                end = clip['end']
                print(f"\n🎬 Processing Clip {i+1}: {start}s - {end}s")
                print(f"   Title: {clip.get('video_title_for_youtube_short', 'No Title')}")

                # Cut clip
                clip_filename = f"{video_title}_clip_{i+1}.mp4"
                clip_temp_path = os.path.join(output_dir, f"temp_{clip_filename}")
                clip_final_path = os.path.join(output_dir, clip_filename)

                # ffmpeg cut
                # Using re-encoding for precision as requested by strict seconds
                cut_command = [
                    'ffmpeg', '-y',
                    '-ss', str(start),
                    '-to', str(end),
                    '-i', input_video,
                    '-c:v', 'libx264', '-crf', EXPORT_VIDEO_CRF, '-preset', EXPORT_VIDEO_PRESET,
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', EXPORT_AUDIO_BITRATE,
                    clip_temp_path
                ]
                subprocess.run(
                    cut_command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
                )

                # Process vertical
                success = process_video_to_vertical(clip_temp_path, clip_final_path)

                if success:
                    print(f"   ✅ Clip {i+1} ready: {clip_final_path}")

                # Clean up temp cut
                if os.path.exists(clip_temp_path):
                    os.remove(clip_temp_path)

    # Clean up original if requested
    if args.url and not args.keep_original and os.path.exists(input_video):
        os.remove(input_video)
        print("🗑️  Cleaned up downloaded video.")

    total_time = time.time() - script_start_time
    print(f"\n⏱️  Total execution time: {total_time:.2f}s")
