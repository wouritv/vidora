create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

create table if not exists public.captions (
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

create index if not exists idx_captions_user_created on public.captions (caption_user_id, caption_created_at desc);
create index if not exists idx_captions_status on public.captions (caption_status);
create index if not exists idx_captions_deleted on public.captions (deleted_at);
create index if not exists idx_captions_title_trgm on public.captions using gin (caption_title gin_trgm_ops);
create index if not exists idx_captions_description_trgm on public.captions using gin (caption_description gin_trgm_ops);
create index if not exists idx_captions_job_clip on public.captions (caption_job_id, caption_clip_index);

create or replace function public.set_captions_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.caption_updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_captions_updated_at on public.captions;
create trigger trg_set_captions_updated_at
before update on public.captions
for each row
execute function public.set_captions_updated_at();

alter table public.captions enable row level security;

drop policy if exists captions_select_own on public.captions;
create policy captions_select_own
on public.captions
for select
to authenticated
using (caption_user_id = auth.uid());

drop policy if exists captions_insert_own on public.captions;
create policy captions_insert_own
on public.captions
for insert
to authenticated
with check (caption_user_id = auth.uid());

drop policy if exists captions_update_own on public.captions;
create policy captions_update_own
on public.captions
for update
to authenticated
using (caption_user_id = auth.uid())
with check (caption_user_id = auth.uid());

drop policy if exists captions_delete_own on public.captions;
create policy captions_delete_own
on public.captions
for delete
to authenticated
using (caption_user_id = auth.uid());

