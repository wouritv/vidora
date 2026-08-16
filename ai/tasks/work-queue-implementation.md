# Work Queue Refactor - Vision et Actions

## Vision d'ensemble

Objectif: passer d'une queue volatile en memoire (`jobs` + `asyncio.Queue`) a une orchestration persistante basee sur Supabase, sans casser les flux existants reels/captions.

Principes appliques:
1. **Source of truth des jobs en base** (`jobs`, `job_logs`) pour survivre aux redemarrages.
2. **Compatibilite progressive**: garder le runtime local pour l'execution (`cmd`, `env`) tout en persistants les etats.
3. **Operations de cycle de vie explicites**: `create_job()`, `enqueue_job()`, `start_job()`, `update_progress()`, `complete_job()`, `fail_job()`, `cancel_job()`.
4. **Worker scaling configurable** via variable d'environnement.
5. **Pipelines metier** pour structurer les etapes reels/captions.
6. **Retry automatique** pour les jobs reels en echec.

---

## Changements implementes

### 1) Schema Supabase pour jobs et logs
- Ajout migration: `supabase/migrations/20260809_create_jobs_tables.sql`
- Nouvelles tables:
  - `public.jobs`
  - `public.job_logs`
- Inclut:
  - indexes (`status`, `queue_name`, `user_id`)
  - trigger `updated_at`
  - policies RLS de base (select/insert/update owner)

### 2) Couche data jobs dans `supabase_request.py`
Ajout des helpers:
- `create_job_record()`
- `update_job_record()`
- `get_job_record()`
- `append_job_log()`
- `list_job_logs()`
- `list_recoverable_jobs()`

Nouvelles variables env prises en charge:
- `SUPABASE_JOBS_TABLE` (defaut `jobs`)
- `SUPABASE_JOB_LOGS_TABLE` (defaut `job_logs`)

### 3) Gestionnaire central des jobs
Nouveau fichier: `job_manager.py`

Contenu:
- catalogue `JobType`:
  - `TRANSCRIBE`, `GENERATE_SUBTITLES`, `TRANSLATE`, `DETECT_HIGHLIGHTS`, `GENERATE_REELS`, `GENERATE_HIGHLIGHT_VIDEO`, `RENDER_VIDEO`, `GENERATE_THUMBNAIL`
- classe `JobManager` avec operations:
  - `create_job()`
  - `enqueue_job()`
  - `start_job()`
  - `update_progress()`
  - `complete_job()`
  - `fail_job()`
  - `retry_job()`
  - `cancel_job()`
  - `get_job_view()`
  - `schedule_retry_after()`

### 4) Pipelines metier
Nouveau fichier: `pipelines.py`
- `Pipeline` (base)
- `ReelProcessingPipeline`
- `CaptionProcessingPipeline`

Ces classes centralisent la progression metier par etape.

### 5) Integration queue reels dans `app.py`
- Ajout `reel_job_manager = JobManager(queue_name="reels")`
- Ajout config workers:
  - `QUEUE_WORKER_COUNT`
  - `REEL_JOB_MAX_ATTEMPTS`
  - `REEL_JOB_RETRY_DELAY_SECONDS`
- `process_queue()` accepte un `worker_name` et plusieurs workers sont demarres via `lifespan`.
- `process_endpoint`:
  - cree un job persiste Supabase
  - reserve quota (`reserved_quota=1.0`)
  - enfile le job
- `run_job`:
  - start/update progress via pipeline
  - complete/fail en base
  - retry automatique planifie en cas d'echec non terminal
- `/api/status/{job_id}`:
  - lit prioritairement l'etat depuis Supabase (`JobManager.get_job_view`)
  - conserve le fallback local si besoin

### 6) Integration jobs captions (`ia_captions.py`)
- Ajout `caption_job_manager = JobManager(queue_name="captions")`
- `captions/analyze` et `captions/render`:
  - creation job en base
  - start/progress/fail/complete en base
- `captions/upload` stocke `user_id` dans la session pour rattacher les jobs.

### 7) Retry AssemblyAI avant fallback local
Fichier modifie: `main.py`
- `transcribe_video()` fait des retries AssemblyAI avant bascule vers faster-whisper.
- Variables env:
  - `ASSEMBLY_RETRY_ATTEMPTS` (defaut `2`)
  - `ASSEMBLY_RETRY_DELAY_SECONDS` (defaut `2`)

---

## Validation effectuee

Compilation Python validee:
- `app.py`
- `ia_captions.py`
- `supabase_request.py`
- `job_manager.py`
- `pipelines.py`
- `main.py`

Commandes executees:

```zsh
python3 -m py_compile /Volumes/SSD_DEV/projects/web/saasvideo/app.py /Volumes/SSD_DEV/projects/web/saasvideo/ia_captions.py /Volumes/SSD_DEV/projects/web/saasvideo/supabase_request.py /Volumes/SSD_DEV/projects/web/saasvideo/job_manager.py /Volumes/SSD_DEV/projects/web/saasvideo/pipelines.py
python3 -m py_compile /Volumes/SSD_DEV/projects/web/saasvideo/main.py
```

---

## Ce qui reste a faire (phase 2)

1. **Recovery startup**
   - relire `jobs` en statut `queued|processing|retry_wait` et reenqueuer automatiquement.

2. **Notifications utilisateur**
   - email/push sur `completed`/`failed`.

3. **Quotas completement transactionnels**
   - `reserve -> consume/release` avec verrous atomiques.

4. **Mesures de couts fines**
   - CPU/GPU time, tokens, provider/model, cout estime/reel dans `job_data`/`result_data`.

5. **Nettoyage standardise des artefacts temporaires**
   - retention configurable 15 min sur les dossiers temporaires operationnels.

6. **Maj statut avant fallback MediaPipe -> YOLO**
   - tracer explicitement en base les echec/transition de detecteur dans le pipeline reels.

---

## Variables d'environnement recommandees

```env
# Queue/workers
MAX_CONCURRENT_JOBS=5
QUEUE_WORKER_COUNT=1
REEL_JOB_MAX_ATTEMPTS=2
REEL_JOB_RETRY_DELAY_SECONDS=15

# Supabase jobs
SUPABASE_JOBS_TABLE=jobs
SUPABASE_JOB_LOGS_TABLE=job_logs

# Transcription retries
ASSEMBLY_RETRY_ATTEMPTS=2
ASSEMBLY_RETRY_DELAY_SECONDS=2
```

---

## Notes de migration

1. Appliquer la migration SQL `20260809_create_jobs_tables.sql` dans Supabase.
2. Redemarrer l'API.
3. Verifier `POST /api/process` puis `GET /api/status/{job_id}`.
4. Verifier creation de lignes dans `jobs` et `job_logs`.

