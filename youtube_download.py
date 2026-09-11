"""YouTube download via yt-dlp: proxy/cookie/PO-Token strategy shared by
every feature that needs to pull a video from a YouTube URL (reels,
anonymous stories, ...).

Moved out of main.py so it can be imported without pulling in that
module's heavy CV/ML stack (torch, ultralytics, mediapipe, cv2,
scenedetect) -- this module only needs yt_dlp and the standard library, so
it's safe to import directly from the FastAPI process (app.py) as well as
from main.py's own reel-cutting CLI pipeline. Keeping it in one place also
means every caller gets the same YouTube-side behavior (mobile clients by
default to dodge the 'web' client's JS/PO-Token challenge, falling back to
cookies + the bgutil PO-Token provider when that's not enough) instead of
each feature reinventing -- and likely under-configuring -- its own
yt-dlp options.
"""

import os
import re
import shutil
import sys
import tempfile
import time
import uuid

import yt_dlp


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
                # Mobile clients (android/ios) don't need the 'web' client's
                # JS challenge/PO-Token, which is what "No supported
                # JavaScript runtime could be found" (deno) is about --
                # using them by default avoids that warning/failure
                # entirely for the common case.
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
