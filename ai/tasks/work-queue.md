# Task — Refactoring et robustification du système de Job Processing

## 1. Objectif

Refactoriser le système actuel de traitement des jobs afin de disposer d'un moteur de traitement :

* persistant ;
* asynchrone ;
* robuste ;
* résilient aux erreurs ;
* configurable ;
* observable ;
* compatible avec plusieurs workers ;
* compatible avec le système de quotas ;
* capable de reprendre un traitement après un redémarrage ;
* optimisé pour les traitements vidéo et IA ;
* optimisé pour limiter les coûts et les téléchargements inutiles.

La V1 doit continuer à fonctionner **sans Redis, Celery ou RabbitMQ**.

Architecture cible :

```text
React
  ↓
FastAPI
  ↓
JobManager
  ↓
Supabase
  ↓
asyncio.Queue
  ↓
Worker
  ↓
Processing Pipeline
  ↓
S3 / Local Workspace
```

---

# 2. Principe général de stockage

Vireel ne conserve pas actuellement les vidéos utilisateur comme des entités métier permanentes.

Il n'est donc pas nécessaire de créer une table `videos` ni d'ajouter :

```text
project_id
video_id
```

dans `jobs`.

Les sources vidéo sont gérées comme des **assets temporaires de traitement**.

Les fichiers générés par Vireel constituent, eux, des outputs persistants.

Il faut donc distinguer trois niveaux de stockage :

```text
SOURCE TEMPORAIRE
        ↓
WORKSPACE LOCAL
        ↓
OUTPUT PERMANENT
```

---

# 3. Architecture de stockage des vidéos

## 3.1 Source temporaire

Lorsqu'une vidéo doit être traitée, elle doit être téléchargée/importée puis stockée temporairement dans S3.

Exemple :

```text
S3
└── temp-sources/
    └── {user_id}/
        └── {source_id}/
            └── source.mp4
```

Cette source temporaire doit être conservée pendant une durée configurable.

Exemple :

```env
TEMP_SOURCE_RETENTION_HOURS=48
```

L'objectif est de pouvoir réutiliser la vidéo lors :

* d'un retry ;
* d'un redémarrage du worker ;
* d'un nouveau traitement ;
* d'une génération de plusieurs outputs à partir de la même source.

---

# 4. Pourquoi conserver les sources YouTube temporairement

Pour une vidéo YouTube :

```text
YouTube
   ↓
Download
   ↓
S3 temporary source
   ↓
traitement local
```

Si un worker échoue pendant le traitement :

```text
Worker crash
    ↓
reprise
    ↓
S3 temporary source
    ↓
download local
    ↓
reprise
```

Le système ne doit pas automatiquement retélécharger la vidéo depuis YouTube.

Ceci est particulièrement important pour éviter :

* les problèmes anti-bot ;
* les problèmes de cookies ;
* les limitations YouTube ;
* les téléchargements inutiles ;
* la consommation de bande passante ;
* les temps de traitement supplémentaires.

---

# 5. Réutilisation d'une même source

La source temporaire ne doit pas être obligatoirement liée à un `job_id`.

Éviter :

```text
temp-sources/{user_id}/{job_id}/source.mp4
```

car plusieurs jobs peuvent utiliser la même vidéo.

Préférer :

```text
temp-sources/{user_id}/{source_id}/source.mp4
```

ou une clé déterministe basée sur la source.

Exemple :

```text
temp-sources/
└── user-123/
    └── source-abc/
        └── source.mp4
```

Cela permet :

```text
                    SOURCE
                       │
                       ▼
               S3 TEMP SOURCE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       captions      reels      highlights
```

Une même vidéo peut donc être réutilisée pour plusieurs traitements.

---

# 6. SourceResolver

Créer un composant responsable de la résolution des sources :

```text
SourceResolver
```

Responsabilité :

```text
resolve_source()
```

Logique :

```text
1. Vérifier si une source temporaire existe
          │
          ├── OUI
          │    ↓
          │  utiliser la source existante
          │
          └── NON
               ↓
2. Télécharger/importer la source
               ↓
3. Valider le fichier
               ↓
4. Calculer les métadonnées
               ↓
5. Stocker dans S3 temporaire
               ↓
6. Retourner la référence S3
```

Le `SourceResolver` doit supporter notamment :

```text
YouTube
Local Upload
Dropbox
S3
```

---

# 7. Métadonnées de source

Pour la V1, il n'est pas nécessaire de créer une table `source_assets`.

Les informations nécessaires peuvent être stockées dans `job_data`.

Exemple :

```json
{
  "source": {
    "type": "youtube",
    "url": "https://youtube.com/watch?v=xxx",
    "storage_key": "temp-sources/user-123/source-abc/source.mp4",
    "checksum": "sha256:...",
    "file_size": 1250000000,
    "duration": 3600,
    "mime_type": "video/mp4",
    "expires_at": "2026-08-11T12:00:00Z"
  }
}
```

Pour une source S3 :

```json
{
  "source": {
    "type": "s3",
    "storage_key": "temp-sources/user-123/source-abc/source.mp4"
  }
}
```

Ne jamais stocker la vidéo elle-même dans Supabase.

---

# 8. Workspace local

S3 est utilisé comme stockage temporaire et permanent.

Cependant, les traitements lourds doivent être effectués localement sur le VPS.

Chaque job doit disposer de son propre workspace :

```text
/workspace/{job_id}/
```

Exemple :

```text
/workspace/job-uuid/
├── source.mp4
├── audio.wav
├── transcript.json
├── clips/
├── captions/
├── frames/
└── output.mp4
```

Le traitement doit suivre :

```text
S3 temporary source
        ↓
download local
        ↓
/workspace/{job_id}
        ↓
FFmpeg / Faster-Whisper / MediaPipe / YOLO
        ↓
output
        ↓
S3
```

Ne pas utiliser S3 comme filesystem de travail pour les opérations FFmpeg/IA.

---

# 9. Nettoyage du workspace

À la fin du traitement :

```text
COMPLETED
FAILED
CANCELLED
```

le workspace local doit être supprimé.

Configuration :

```env
TEMP_FILE_RETENTION_MINUTES=15
```

Prévoir également un processus de cleanup pour les workspaces abandonnés après un crash.

---

# 10. Nettoyage des sources S3 temporaires

Les sources temporaires doivent être automatiquement supprimées après leur durée de conservation.

Configuration :

```env
TEMP_SOURCE_RETENTION_HOURS=48
```

La suppression doit être réalisée à deux niveaux :

### Application

Un mécanisme périodique doit supprimer les sources expirées.

### S3 Lifecycle

Configurer également une règle S3 Lifecycle :

```text
temp-sources/*
        ↓
expiration
        ↓
durée configurée
```

Le lifecycle S3 constitue la sécurité supplémentaire en cas de :

* crash du worker ;
* crash de l'application ;
* problème du cron ;
* redémarrage du VPS ;
* erreur applicative.

---

# 11. Modèle de données `jobs`

Créer une table Supabase :

```text
jobs
```

Structure recommandée :

```text
jobs
├── id UUID PK
├── user_id UUID NOT NULL
├── type VARCHAR NOT NULL
├── status VARCHAR NOT NULL
├── priority INTEGER
├── progress INTEGER
├── current_step VARCHAR
├── job_data JSONB
├── result_data JSONB nullable
├── error_code VARCHAR nullable
├── error_message TEXT nullable
├── attempt_count INTEGER
├── max_attempts INTEGER
├── reserved_quota NUMERIC
├── created_at TIMESTAMP
├── started_at TIMESTAMP nullable
├── completed_at TIMESTAMP nullable
└── updated_at TIMESTAMP
```

Ne pas ajouter :

```text
project_id
video_id
```

s'il n'existe aucune entité métier correspondante.

---

# 12. `job_data`

`job_data` contient les informations nécessaires à l'exécution du job.

Exemple :

```json
{
  "source": {
    "type": "youtube",
    "url": "https://youtube.com/...",
    "storage_key": "temp-sources/user-123/source-abc/source.mp4"
  },
  "options": {
    "language": "fr",
    "format": "9:16"
  }
}
```

Ne pas stocker :

* vidéo ;
* audio ;
* données binaires ;
* gros fichiers ;
* gros transcripts.

---

# 13. `result_data`

Les outputs générés sont stockés dans S3.

`result_data` contient uniquement les références vers ces fichiers.

Exemple :

```json
{
  "assets": [
    {
      "type": "reel",
      "storage_key": "users/user-123/reels/reel-001.mp4"
    },
    {
      "type": "thumbnail",
      "storage_key": "users/user-123/thumbnails/reel-001.jpg"
    }
  ]
}
```

---

# 14. Stockage S3

Organisation recommandée :

```text
users/{user_id}/
├── reels/
├── captions/
├── subtitles/
├── highlights/
└── thumbnails/
```

Les sources temporaires sont séparées :

```text
temp-sources/{user_id}/{source_id}/
```

Ne jamais mélanger les sources temporaires et les outputs permanents.

---

# 15. Machine à états

États :

```text
QUEUED
PROCESSING
RETRY_PENDING
COMPLETED
FAILED
CANCELLED
```

Transitions autorisées :

```text
QUEUED
  ↓
PROCESSING
  ↓
COMPLETED

PROCESSING
  ↓
RETRY_PENDING
  ↓
PROCESSING

PROCESSING
  ↓
FAILED

QUEUED
  ↓
CANCELLED

PROCESSING
  ↓
CANCELLED
```

Les transitions doivent être centralisées.

---

# 16. JobManager

Créer :

```text
JobManager
```

avec notamment :

```text
create_job()
enqueue_job()
start_job()
update_progress()
update_step()
complete_job()
fail_job()
retry_job()
cancel_job()
get_job()
recover_stale_jobs()
```

Le JobManager est responsable de la cohérence de l'état du job.

---

# 17. Queue

Conserver pour la V1 :

```python
asyncio.Queue()
```

La queue contient uniquement :

```text
job_id
```

Exemple :

```text
job-001
job-002
job-003
```

Ne jamais mettre de fichiers ou données volumineuses dans la queue.

---

# 18. API / Worker

L'API ne doit jamais exécuter directement les traitements vidéo lourds.

```text
React
 ↓
FastAPI
 ↓
JobManager
 ↓
Supabase
 ↓
asyncio.Queue
 ↓
Worker
 ↓
Pipeline
```

---

# 19. Workers

Configuration :

```env
WORKER_COUNT=1
MAX_CONCURRENT_JOBS_PER_WORKER=2
```

`WORKER_COUNT` correspond au nombre de workers/processus.

`MAX_CONCURRENT_JOBS_PER_WORKER` correspond au nombre maximal de traitements simultanés par worker.

La configuration doit être adaptée aux ressources CPU/RAM/GPU du VPS.

---

# 20. Pipelines

Créer :

```text
ReelProcessingPipeline
CaptionProcessingPipeline
HighlightProcessingPipeline
```

et éventuellement :

```text
SubtitleProcessingPipeline
TranslationProcessingPipeline
```

Privilégier la composition plutôt qu'une hiérarchie d'héritage complexe.

---

# 21. ReelProcessingPipeline

Étapes possibles :

```text
1. resolve source
2. download source depuis S3 vers workspace
3. transcription
4. analyse transcript
5. détection moments clés
6. sélection segments
7. détection visage/sujet
8. cadrage
9. découpage
10. captions
11. rendering
12. upload S3
13. sauvegarde résultat
```

---

# 22. CaptionProcessingPipeline

Étapes :

```text
1. resolve source
2. download depuis S3
3. transcription
4. nettoyage transcript
5. traduction éventuelle
6. génération VTT/SRT
7. rendering éventuel
8. upload S3
9. sauvegarde résultat
```

---

# 23. HighlightProcessingPipeline

Étapes :

```text
1. resolve source
2. récupération depuis S3
3. transcription
4. analyse du transcript
5. identification des faits/moments importants
6. sélection des segments
7. génération du résumé
8. génération de la vidéo récapitulative
9. rendering
10. upload S3
11. sauvegarde résultat
```

---

# 24. Transcription AssemblyAI / Faster-Whisper

AssemblyAI est le provider principal.

Faster-Whisper est le fallback local.

Flux :

```text
AssemblyAI
   ↓
retry 1
   ↓
retry 2
   ↓
retry final
   ↓
FAILED persisté
   ↓
Faster-Whisper
```

Avant le fallback :

1. toutes les tentatives doivent être terminées ;
2. le statut doit être persisté ;
3. l'erreur doit être enregistrée ;
4. le fallback doit être enregistré.

Conserver :

```text
transcription_provider
assemblyai_attempts
fallback_used
fallback_reason
```

---

# 25. MediaPipe / YOLOv8

MediaPipe est prioritaire.

YOLOv8 est utilisé uniquement lorsque MediaPipe :

* échoue ;
* produit une confiance insuffisante ;
* ne trouve aucun sujet exploitable ;
* ne supporte pas correctement la scène ;
* ne permet pas d'obtenir le résultat attendu.

Conserver :

```text
detector_used
fallback_used
fallback_reason
```

---

# 26. Retry

Configuration :

```env
DEFAULT_MAX_JOB_ATTEMPTS=3
```

Retry uniquement pour les erreurs récupérables.

Exemples :

```text
HTTP 429
HTTP 500
timeout
provider unavailable
temporary S3 error
```

Pas de retry inutile pour :

```text
invalid video
invalid URL
unsupported format
corrupted input
quota exceeded
```

Utiliser un backoff progressif.

---

# 27. Reprise d'un job

Lorsqu'un worker démarre ou redémarre :

```text
1. rechercher les jobs PROCESSING/RETRY_PENDING
2. identifier les jobs stale
3. déterminer s'ils sont récupérables
4. réinjecter les jobs appropriés dans la queue
5. utiliser la source S3 temporaire existante
6. éviter de redémarrer inutilement le téléchargement depuis YouTube
```

Si la source temporaire existe encore :

```text
S3 temporary source
        ↓
workspace local
        ↓
reprise
```

Si elle a expiré :

```text
source absente
        ↓
retéléchargement
```

---

# 28. Jobs abandonnés

Configuration :

```env
JOB_STALE_TIMEOUT_MINUTES=30
```

Un job `PROCESSING` trop ancien doit être détecté.

Le système doit :

```text
détecter
 ↓
logger
 ↓
retry si possible
 ↓
sinon FAILED
```

---

# 29. Logs

Créer :

```text
job_logs
├── id UUID
├── job_id UUID
├── level VARCHAR
├── message TEXT
├── metadata JSONB nullable
└── created_at TIMESTAMP
```

Les logs doivent notamment enregistrer :

```text
source resolution
download
transcription
retry
fallback
detection
rendering
upload
errors
```

Ne jamais enregistrer :

* API keys ;
* tokens ;
* credentials ;
* URLs signées S3 complètes si elles contiennent des credentials/signatures.

---

# 30. Catalogue des jobs

Centraliser :

```text
TRANSCRIBE
GENERATE_SUBTITLES
TRANSLATE
DETECT_HIGHLIGHTS
GENERATE_REELS
GENERATE_HIGHLIGHT_VIDEO
RENDER_VIDEO
GENERATE_THUMBNAIL
```

---

# 31. Quotas

Flux :

```text
requête
 ↓
validation
 ↓
réservation quota
 ↓
création job
 ↓
traitement
 ↓
SUCCESS → consommation définitive
FAILED → libération
CANCELLED → libération
```

La réservation doit être atomique.

---

# 32. Coûts

Mesurer notamment :

```text
video_duration
processing_duration
cpu_time
gpu_time
transcription_provider
ai_model
input_tokens
output_tokens
external_api_cost
compute_cost
estimated_total_cost
```

Créer éventuellement :

```text
job_costs
```

Ces données serviront à calibrer les quotas et les abonnements Vireel.

---

# 33. Limites

Configuration :

```env
MAX_VIDEO_DURATION_SECONDS=
MAX_FILE_SIZE_MB=
MAX_CONCURRENT_JOBS_PER_USER=
MAX_STORAGE_PER_USER_MB=
MAX_JOBS_PER_MINUTE=
```

Ajouter également :

```env
TEMP_SOURCE_RETENTION_HOURS=48
TEMP_FILE_RETENTION_MINUTES=15
```

---

# 34. Notifications

Événements :

```text
JOB_COMPLETED
JOB_FAILED
```

Le traitement ne doit pas dépendre du succès d'une notification.

Pour la V1, les notifications in-app peuvent être persistées dans Supabase.

---

# 35. API de statut

Conserver :

```text
GET /api/status/{job_id}
```

Réponse :

```json
{
  "id": "uuid",
  "type": "GENERATE_REELS",
  "status": "PROCESSING",
  "progress": 70,
  "current_step": "AUTO_REFRAMING",
  "created_at": "...",
  "updated_at": "...",
  "result": null,
  "error": null
}
```

Vérifier systématiquement :

```text
job.user_id == authenticated_user.id
```

---

# 36. S3 Lifecycle

Configurer une règle S3 Lifecycle dédiée :

```text
temp-sources/*
```

avec expiration correspondant à :

```env
TEMP_SOURCE_RETENTION_HOURS
```

Cette règle doit être considérée comme une protection supplémentaire et non comme le seul mécanisme de cleanup.

---

# 37. Tests

Tester :

### Jobs

```text
create
enqueue
start
progress
complete
fail
retry
cancel
```

### Sources

```text
YouTube → download → S3
S3 source existante → réutilisation
source expirée → nouveau téléchargement
source réutilisée par plusieurs jobs
```

### AssemblyAI

```text
success
retry
failure
fallback Faster-Whisper
```

### Vision

```text
MediaPipe success
MediaPipe failure
YOLO fallback
```

### Quotas

```text
reservation
success
failure
libération
concurrence
```

### Worker

```text
restart
stale jobs
cleanup
concurrency
```

### Sécurité

```text
user A cannot access user B jobs
```

---

# 38. Contraintes

Ne pas :

* introduire Redis ;
* introduire Celery ;
* introduire RabbitMQ ;
* créer une table `videos` sans besoin métier ;
* ajouter `project_id` ou `video_id` sans besoin métier ;
* stocker les vidéos dans Supabase ;
* stocker les gros fichiers dans `job_data` ;
* stocker les fichiers binaires dans Supabase ;
* stocker les vidéos en RAM ;
* utiliser `jobs{}` comme source de vérité ;
* exécuter les traitements lourds dans FastAPI ;
* télécharger à nouveau une vidéo YouTube lorsqu'une copie temporaire valide existe dans S3 ;
* utiliser S3 comme filesystem de travail pour FFmpeg/IA ;
* lancer Faster-Whisper avant l'échec définitif d'AssemblyAI ;
* lancer YOLO systématiquement ;
* consommer le quota avant le succès ;
* stocker des credentials ou URLs signées complètes dans les logs.

---

# 39. Critères d'acceptation

* [ ] Les jobs sont persistés dans Supabase.
* [ ] `jobs{}` n'est plus la source de vérité.
* [ ] Il n'existe pas de dépendance inutile à `project_id` ou `video_id`.
* [ ] Les sources sont décrites dans `job_data`.
* [ ] Les sources importées sont temporairement stockées dans S3.
* [ ] Les sources YouTube sont téléchargées une seule fois lorsqu'une copie valide existe.
* [ ] Une source S3 existante peut être réutilisée par plusieurs jobs.
* [ ] La durée de conservation des sources temporaires est configurable.
* [ ] S3 Lifecycle supprime automatiquement les sources expirées.
* [ ] Les vidéos sont téléchargées localement avant traitement.
* [ ] Chaque job possède son propre workspace.
* [ ] Les workspaces sont nettoyés.
* [ ] Les résultats finaux sont stockés dans S3.
* [ ] `result_data` contient uniquement les métadonnées/références des outputs.
* [ ] La queue contient uniquement des `job_id`.
* [ ] Le nombre de workers est configurable.
* [ ] La concurrence par worker est configurable.
* [ ] Les pipelines Reel/Captions/Highlights sont structurés.
* [ ] Les retries sont implémentés.
* [ ] AssemblyAI → Faster-Whisper possède un fallback contrôlé.
* [ ] MediaPipe → YOLOv8 possède un fallback contrôlé.
* [ ] Les jobs stale sont récupérés après redémarrage.
* [ ] Les logs sont persistés.
* [ ] Les quotas sont réservés puis consommés/libérés.
* [ ] Les coûts sont mesurables.
* [ ] Les limites sont configurables.
* [ ] Les notifications sont découplées.
* [ ] Les tests couvrent les scénarios critiques.
* [ ] Le système ne nécessite ni Redis ni Celery pour la V1.
