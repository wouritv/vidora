-- Cache reusable transcripts/translations and keep style edit history versions.

create extension if not exists pgcrypto;

create table if not exists public.transcriptions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id text not null,
    clip_index integer not null default 0,
    source_type text,
    source_value text,
    transcript_provider text,
    transcript_language text,
    transcript_text text,
    transcript_payload jsonb not null default '{}'::jsonb,
    translations_cache jsonb not null default '{}'::jsonb,
    billing_details jsonb not null default '{}'::jsonb,
    constraint transcriptions_user_job_clip_unique unique (user_id, job_id, clip_index)
);

create index if not exists idx_transcriptions_user_created
    on public.transcriptions(user_id, created_at desc);

create index if not exists idx_transcriptions_job_clip
    on public.transcriptions(job_id, clip_index);

create or replace function public.set_transcriptions_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_transcriptions_updated_at on public.transcriptions;
create trigger trg_set_transcriptions_updated_at
before update on public.transcriptions
for each row
execute function public.set_transcriptions_updated_at();

alter table public.transcriptions enable row level security;

drop policy if exists transcriptions_select_own on public.transcriptions;
create policy transcriptions_select_own
on public.transcriptions
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists transcriptions_insert_own on public.transcriptions;
create policy transcriptions_insert_own
on public.transcriptions
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists transcriptions_update_own on public.transcriptions;
create policy transcriptions_update_own
on public.transcriptions
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create table if not exists public.style_edit_versions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id text not null,
    clip_index integer not null default 0,
    version_number integer not null,
    operation_type text not null default 'subtitle_style',
    source_video_url text,
    output_video_url text,
    style_config jsonb not null default '{}'::jsonb,
    billing_details jsonb not null default '{}'::jsonb
);

create index if not exists idx_style_versions_user_created
    on public.style_edit_versions(user_id, created_at desc);

create index if not exists idx_style_versions_job_clip_version
    on public.style_edit_versions(job_id, clip_index, version_number desc);

alter table public.style_edit_versions enable row level security;

drop policy if exists style_versions_select_own on public.style_edit_versions;
create policy style_versions_select_own
on public.style_edit_versions
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists style_versions_insert_own on public.style_edit_versions;
create policy style_versions_insert_own
on public.style_edit_versions
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists style_versions_delete_own on public.style_edit_versions;
create policy style_versions_delete_own
on public.style_edit_versions
for delete
to authenticated
using (user_id = auth.uid());

alter table if exists public.reels
    add column if not exists billing_details jsonb not null default '{}'::jsonb,
    add column if not exists total_cost_usd numeric(14, 6) not null default 0;

alter table if exists public.captions
    add column if not exists billing_details jsonb not null default '{}'::jsonb,
    add column if not exists total_cost_usd numeric(14, 6) not null default 0;

