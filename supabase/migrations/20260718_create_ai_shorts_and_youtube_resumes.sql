-- Prerequisites:
-- 1) Run as a role that can create tables/policies in your Supabase project.
-- 2) Ensure auth is enabled (auth.users exists).
-- 3) Optional: enable pg_trgm for better text search performance.

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create table if not exists public.ia_short (
    id uuid primary key default gen_random_uuid(),
    reel_url text,
    reel_thumbnail_url text,
    reel_title text,
    reel_description text,
    reel_duration integer,
    reel_created_at timestamptz not null default now(),
    reel_updated_at timestamptz not null default now(),
    reel_user_id uuid not null references auth.users(id) on delete cascade,
    reel_status text not null default 'en_cours' check (reel_status in ('en_cours', 'termine', 'echec')),
    reel_job_id text,
    reel_clip_index integer,
    reel_s3_key text,
    generation_inputs jsonb not null default '{}'::jsonb,
    input_source_type text,
    input_source_value text,
    deleted_at timestamptz
);

create table if not exists public.youtube_resume (
    id uuid primary key default gen_random_uuid(),
    resume_url text,
    resume_thumbnail_url text,
    resume_title text,
    resume_description text,
    resume_duration integer,
    resume_created_at timestamptz not null default now(),
    resume_updated_at timestamptz not null default now(),
    resume_user_id uuid not null references auth.users(id) on delete cascade,
    resume_status text not null default 'en_cours' check (resume_status in ('en_cours', 'termine', 'echec')),
    resume_job_id text,
    resume_clip_index integer,
    resume_s3_key text,
    generation_inputs jsonb not null default '{}'::jsonb,
    input_source_type text,
    input_source_value text,
    deleted_at timestamptz
);

create index if not exists idx_ia_short_user_created on public.ia_short (reel_user_id, reel_created_at desc);
create index if not exists idx_ia_short_status on public.ia_short (reel_status);
create index if not exists idx_ia_short_job on public.ia_short (reel_job_id, reel_clip_index);
create index if not exists idx_ia_short_deleted on public.ia_short (deleted_at);
create index if not exists idx_ia_short_title_trgm on public.ia_short using gin (reel_title gin_trgm_ops);
create index if not exists idx_ia_short_description_trgm on public.ia_short using gin (reel_description gin_trgm_ops);

create index if not exists idx_youtube_resume_user_created on public.youtube_resume (resume_user_id, resume_created_at desc);
create index if not exists idx_youtube_resume_status on public.youtube_resume (resume_status);
create index if not exists idx_youtube_resume_job on public.youtube_resume (resume_job_id, resume_clip_index);
create index if not exists idx_youtube_resume_deleted on public.youtube_resume (deleted_at);
create index if not exists idx_youtube_resume_title_trgm on public.youtube_resume using gin (resume_title gin_trgm_ops);
create index if not exists idx_youtube_resume_description_trgm on public.youtube_resume using gin (resume_description gin_trgm_ops);

create or replace function public.set_ia_short_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.reel_updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_ia_short_updated_at on public.ia_short;
create trigger trg_set_ia_short_updated_at
before update on public.ia_short
for each row
execute function public.set_ia_short_updated_at();

create or replace function public.set_youtube_resume_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.resume_updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_youtube_resume_updated_at on public.youtube_resume;
create trigger trg_set_youtube_resume_updated_at
before update on public.youtube_resume
for each row
execute function public.set_youtube_resume_updated_at();

alter table public.ia_short enable row level security;
alter table public.youtube_resume enable row level security;

-- Users can read only their own rows
 drop policy if exists ia_short_select_own on public.ia_short;
create policy ia_short_select_own
on public.ia_short
for select
to authenticated
using (reel_user_id = auth.uid());

drop policy if exists ia_short_insert_own on public.ia_short;
create policy ia_short_insert_own
on public.ia_short
for insert
to authenticated
with check (reel_user_id = auth.uid());

drop policy if exists ia_short_update_own on public.ia_short;
create policy ia_short_update_own
on public.ia_short
for update
to authenticated
using (reel_user_id = auth.uid())
with check (reel_user_id = auth.uid());

drop policy if exists ia_short_delete_own on public.ia_short;
create policy ia_short_delete_own
on public.ia_short
for delete
to authenticated
using (reel_user_id = auth.uid());

drop policy if exists youtube_resume_select_own on public.youtube_resume;
create policy youtube_resume_select_own
on public.youtube_resume
for select
to authenticated
using (resume_user_id = auth.uid());

drop policy if exists youtube_resume_insert_own on public.youtube_resume;
create policy youtube_resume_insert_own
on public.youtube_resume
for insert
to authenticated
with check (resume_user_id = auth.uid());

drop policy if exists youtube_resume_update_own on public.youtube_resume;
create policy youtube_resume_update_own
on public.youtube_resume
for update
to authenticated
using (resume_user_id = auth.uid())
with check (resume_user_id = auth.uid());

drop policy if exists youtube_resume_delete_own on public.youtube_resume;
create policy youtube_resume_delete_own
on public.youtube_resume
for delete
to authenticated
using (resume_user_id = auth.uid());

