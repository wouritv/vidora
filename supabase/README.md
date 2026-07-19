# Supabase Reels Setup

## 1) Apply migration
Run the SQL in `supabase/migrations/20260718_create_reels.sql` in your Supabase SQL Editor.

## 2) Backend environment variables
Add these variables to your backend `.env`:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_REELS_TABLE` (optional, defaults to `reels`)
- `AWS_S3_BUCKET` (already used by the app)
- `AWS_REGION` (already used by the app)

## 3) Frontend requirements
The dashboard sends `X-User-Id` (Supabase auth user id) for reel API calls.
Make sure auth is active in `dashboard/src/state/AuthContext.jsx`.

## 4) Implemented API endpoints
- `GET /api/reels`
- `DELETE /api/reels/{reel_id}`
- `GET /api/reels/{reel_id}/download`
- `POST /api/reels/{reel_id}/share`

## 5) Notes
- Generated clips are automatically persisted into Supabase at the end of `/api/process` jobs.
- Reels are soft-deleted using `deleted_at`.
- Share uses Upload-Post API credentials already configured in Settings.

