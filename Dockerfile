# syntax=docker/dockerfile:1

# ============================================================
# Stage 1 : builder — installe les dépendances Python
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# Cache mount BuildKit : garde le cache pip entre les builds SANS l'inclure dans l'image
# (nécessite # syntax=docker/dockerfile:1 en haut du fichier, déjà ajouté)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

# ============================================================
# Stage 2 : image finale
# ============================================================
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# yt-dlp toujours à jour (bot-detection YouTube évolue souvent) — volontairement
# séparé du reste pour ne pas invalider tout le cache pip à chaque build
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade --no-cache-dir yt-dlp

# Créer l'utilisateur non-root et les dossiers AVANT de copier le code :
# ainsi, un changement de code n'invalide pas cette étape ni le téléchargement YOLO ci-dessous
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    mkdir -p /app/uploads /app/output /tmp/Ultralytics && \
    chown -R appuser:appuser /app /tmp/Ultralytics

USER appuser

# Pré-télécharger le modèle YOLO : placé AVANT le COPY du code applicatif
# pour que ce layer reste en cache tant que le modèle ne change pas
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copie du code en dernier : c'est le layer qui change le plus souvent,
# le placer en fin de fichier maximise la réutilisation du cache pour tout le reste.
# Security (docker:S6470): copy only what the backend actually needs at
# runtime instead of the whole build context -- a blanket `COPY . .` would
# also bake in anything a developer happens to have sitting locally
# (uncommitted secrets, stray files) that .dockerignore doesn't happen to
# cover. dashboard/, render-service/, remotion/, node_modules/, tests/ and
# the supabase/ CLI migrations are never read by this image at runtime.
# Security (docker:S6504): owned by root, not by the appuser the process
# runs as, and shipped without the write bit -- if an attacker ever gets
# code execution as appuser they can't tamper with the application code
# itself. appuser only needs read (+ traverse for fonts/) access, granted
# via the group bit, never write.
COPY --chown=root:appuser --chmod=750 *.py ./
COPY --chown=root:appuser --chmod=750 fonts/ ./fonts/

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]