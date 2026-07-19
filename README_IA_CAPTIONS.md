# IA Captions (migration notes)

This repository now exposes an **IA Captions** workflow replacing the old AI Shorts / AI Agent / YouTube Resume flow.

## What changed

- Removed from product flow:
  - AI Shorts UI routing
  - AI Agent UI routing
  - YouTube Resume gallery semantics
- Added:
  - `POST /api/captions/upload`
  - `POST /api/captions/analyze`
  - `POST /api/captions/render`
  - `GET /api/ia-captions`
  - `GET /api/ia-captions/{id}/media-url`
  - `GET /api/ia-captions/{id}/download`
  - `DELETE /api/ia-captions/{id}`
  - `POST /api/ia-captions/{id}/share`
- Legacy endpoints now return `410 Gone` for:
  - `/api/saasshorts/*`
  - `/api/ia-shorts/*`
  - `/api/youtube-resumes/*`

## Database

Run migration:

- `supabase/migrations/20260719_replace_features_with_ia_captions.sql`

It creates `public.ia_caption` and drops deprecated `ia_short` and `youtube_resume`.

## Quick smoke test

Run:

```bash
python3 /Volumes/SSD_DEV/projects/web/saasvideo/verify_ia_captions.py
```

Expected output:

- `ia_captions smoke test: ok`

