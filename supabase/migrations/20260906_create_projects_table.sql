-- Create projects table
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create table if not exists public.projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    description text,
    project_type text not null check (project_type in ('reel', 'caption')),
    source_type text not null check (source_type in ('upload', 'youtube', 'url')),
    source_url text,
    source_s3_key text not null,
    source_duration integer,
    source_size bigint not null,
    thumbnail_url text,
    output_count integer not null default 0,
    status text not null default 'processing' check (status in ('processing', 'completed', 'failed', 'cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists idx_projects_user_created on public.projects (user_id, created_at desc);
create index if not exists idx_projects_status on public.projects (status);
create index if not exists idx_projects_type on public.projects (project_type);
create index if not exists idx_projects_name_trgm on public.projects using gin (name gin_trgm_ops);
create index if not exists idx_projects_description_trgm on public.projects using gin (description gin_trgm_ops);

create or replace function public.set_projects_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_projects_updated_at on public.projects;
create trigger trg_set_projects_updated_at
before update on public.projects
for each row
execute function public.set_projects_updated_at();

alter table public.projects enable row level security;

-- Users can read only their own projects
drop policy if exists projects_select_own on public.projects;
create policy projects_select_own
on public.projects
for select
to authenticated
using (user_id = auth.uid());

-- Users can insert only for themselves
drop policy if exists projects_insert_own on public.projects;
create policy projects_insert_own
on public.projects
for insert
to authenticated
with check (user_id = auth.uid());

-- Users can update only their own projects
drop policy if exists projects_update_own on public.projects;
create policy projects_update_own
on public.projects
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

-- Users can delete only their own projects
drop policy if exists projects_delete_own on public.projects;
create policy projects_delete_own
on public.projects
for delete
to authenticated
using (user_id = auth.uid());

