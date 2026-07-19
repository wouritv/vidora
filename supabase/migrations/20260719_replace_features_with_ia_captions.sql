create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create table if not exists public.ia_caption (
    id uuid primary key default gen_random_uuid(),
    caption_url text,
    caption_thumbnail_url text,
    caption_title text,
    caption_description text,
    caption_duration integer,
    caption_created_at timestamptz not null default now(),
    caption_updated_at timestamptz not null default now(),
    caption_user_id uuid not null references auth.users(id) on delete cascade,
    caption_status text not null default 'en_cours' check (caption_status in ('en_cours', 'termine', 'echec')),
    caption_job_id text,
    caption_clip_index integer,
    caption_s3_key text,
    generation_inputs jsonb not null default '{}'::jsonb,
    input_source_type text,
    input_source_value text,
    deleted_at timestamptz
);

create index if not exists idx_ia_caption_user_created on public.ia_caption (caption_user_id, caption_created_at desc);
create index if not exists idx_ia_caption_status on public.ia_caption (caption_status);
create index if not exists idx_ia_caption_deleted on public.ia_caption (deleted_at);
create index if not exists idx_ia_caption_title_trgm on public.ia_caption using gin (caption_title gin_trgm_ops);
create index if not exists idx_ia_caption_description_trgm on public.ia_caption using gin (caption_description gin_trgm_ops);

create or replace function public.set_ia_caption_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.caption_updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_ia_caption_updated_at on public.ia_caption;
create trigger trg_set_ia_caption_updated_at
before update on public.ia_caption
for each row
execute function public.set_ia_caption_updated_at();

alter table public.ia_caption enable row level security;

drop policy if exists ia_caption_select_own on public.ia_caption;
create policy ia_caption_select_own
on public.ia_caption
for select
to authenticated
using (caption_user_id = auth.uid());

drop policy if exists ia_caption_insert_own on public.ia_caption;
create policy ia_caption_insert_own
on public.ia_caption
for insert
to authenticated
with check (caption_user_id = auth.uid());

drop policy if exists ia_caption_update_own on public.ia_caption;
create policy ia_caption_update_own
on public.ia_caption
for update
to authenticated
using (caption_user_id = auth.uid())
with check (caption_user_id = auth.uid());

drop policy if exists ia_caption_delete_own on public.ia_caption;
create policy ia_caption_delete_own
on public.ia_caption
for delete
to authenticated
using (caption_user_id = auth.uid());

-- Remove deprecated feature tables.
drop table if exists public.ia_short cascade;
drop table if exists public.youtube_resume cascade;

