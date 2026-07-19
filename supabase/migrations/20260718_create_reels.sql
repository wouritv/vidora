-- Prerequisites:
-- 1) Run as a role that can create tables/policies in your Supabase project.
-- 2) Ensure auth is enabled (auth.users exists).
-- 3) Optional: enable pg_trgm for better text search performance.

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create table if not exists public.reels (
    id uuid primary key default gen_random_uuid(),
    reel_url text,
    reel_thumbnail_url text,
    reel_title text,
    reel_description text,
    reel_duration integer,
    reel_created_at timestamptz not null default now(),
    reel_updated_at timestamptz not null default now(),
    reel_user_id uuid not null references auth.users(id) on delete cascade,
    reel_video_id uuid,
    reel_status text not null default 'en_cours' check (reel_status in ('en_cours', 'termine', 'echec')),
    reel_job_id text,
    reel_clip_index integer,
    reel_s3_key text,
    input_source_type text check (input_source_type in ('youtube', 'upload', 's3')),
    input_source_value text,
    deleted_at timestamptz
);

create index if not exists idx_reels_user_created on public.reels (reel_user_id, reel_created_at desc);
create index if not exists idx_reels_status on public.reels (reel_status);
create index if not exists idx_reels_job on public.reels (reel_job_id, reel_clip_index);
create index if not exists idx_reels_deleted on public.reels (deleted_at);
create index if not exists idx_reels_title_trgm on public.reels using gin (reel_title gin_trgm_ops);
create index if not exists idx_reels_description_trgm on public.reels using gin (reel_description gin_trgm_ops);

create or replace function public.set_reel_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.reel_updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_reel_updated_at on public.reels;
create trigger trg_set_reel_updated_at
before update on public.reels
for each row
execute function public.set_reel_updated_at();

alter table public.reels enable row level security;

-- Users can read only their own reels
drop policy if exists reels_select_own on public.reels;
create policy reels_select_own
on public.reels
for select
to authenticated
using (reel_user_id = auth.uid());

-- Users can insert only for themselves
drop policy if exists reels_insert_own on public.reels;
create policy reels_insert_own
on public.reels
for insert
to authenticated
with check (reel_user_id = auth.uid());

-- Users can update only their own rows
drop policy if exists reels_update_own on public.reels;
create policy reels_update_own
on public.reels
for update
to authenticated
using (reel_user_id = auth.uid())
with check (reel_user_id = auth.uid());

-- Users can delete only their own rows
drop policy if exists reels_delete_own on public.reels;
create policy reels_delete_own
on public.reels
for delete
to authenticated
using (reel_user_id = auth.uid());


