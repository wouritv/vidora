-- Anonymous stories ("Temoignages"): upload/YouTube video -> transcript ->
-- AI-generated, anonymized written testimonial -> user edits -> copy/publish.
-- The video source and transcript are tracked separately (source_* columns
-- + the existing public.transcriptions table via job_id/clip_index=0); this
-- table only owns the editorial content and its lifecycle.

create extension if not exists pgcrypto;

create table if not exists public.anonymous_stories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    project_id uuid,
    title text,
    source_type text not null check (source_type in ('upload', 'youtube')),
    source_url text,
    source_s3_key text,
    source_duration_seconds integer,
    status text not null default 'draft' check (
        status in ('draft', 'queued', 'processing', 'completed', 'failed', 'cancelled')
    ),
    stage text check (
        stage in ('upload', 'transcription', 'analysis', 'generation', 'finalization')
    ),
    job_id text,
    generated_content jsonb not null default '{}'::jsonb,
    edited_content jsonb not null default '{}'::jsonb,
    final_text text,
    error_code text,
    error_message text,
    billing_details jsonb not null default '{}'::jsonb,
    total_cost_usd numeric(14, 6) not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    deleted_at timestamptz
);

create index if not exists idx_anonymous_stories_user_created
    on public.anonymous_stories (user_id, created_at desc);
create index if not exists idx_anonymous_stories_status
    on public.anonymous_stories (status);
create index if not exists idx_anonymous_stories_job
    on public.anonymous_stories (job_id);
create index if not exists idx_anonymous_stories_deleted
    on public.anonymous_stories (deleted_at);

create or replace function public.set_anonymous_stories_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_anonymous_stories_updated_at on public.anonymous_stories;
create trigger trg_set_anonymous_stories_updated_at
before update on public.anonymous_stories
for each row
execute function public.set_anonymous_stories_updated_at();

alter table public.anonymous_stories enable row level security;

-- Users can only ever read/write their own testimonials (spec section 5.4).
drop policy if exists anonymous_stories_select_own on public.anonymous_stories;
create policy anonymous_stories_select_own
on public.anonymous_stories
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists anonymous_stories_insert_own on public.anonymous_stories;
create policy anonymous_stories_insert_own
on public.anonymous_stories
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists anonymous_stories_update_own on public.anonymous_stories;
create policy anonymous_stories_update_own
on public.anonymous_stories
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists anonymous_stories_delete_own on public.anonymous_stories;
create policy anonymous_stories_delete_own
on public.anonymous_stories
for delete
to authenticated
using (user_id = auth.uid());
