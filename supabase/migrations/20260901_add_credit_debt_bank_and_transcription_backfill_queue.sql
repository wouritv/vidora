-- Credit debt bank + offline backfill queue for transcription cache.

create table if not exists public.user_credit_bank (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    direction text not null check (direction in ('debt_increase', 'debt_payment')),
    amount numeric(14, 2) not null default 0,
    debt_balance_after numeric(14, 2) not null default 0,
    operation_type text not null default 'operation',
    operation_id text not null default '',
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_user_credit_bank_user_created
    on public.user_credit_bank(user_id, created_at desc);

alter table public.user_credit_bank enable row level security;

drop policy if exists user_credit_bank_select_own on public.user_credit_bank;
create policy user_credit_bank_select_own
on public.user_credit_bank
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists user_credit_bank_insert_own on public.user_credit_bank;
create policy user_credit_bank_insert_own
on public.user_credit_bank
for insert
to authenticated
with check (auth.uid() = user_id);

alter table if exists public.user_data
    add column if not exists credit_debt numeric(14, 2) not null default 0;

update public.user_data
set credit_debt = greatest(coalesce(credit_debt, 0), 0)
where credit_debt is null or credit_debt < 0;

-- Queue rows that still need transcript payload backfill from filesystem metadata.
create table if not exists public.transcription_backfill_queue (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id text not null,
    clip_index integer not null default 0,
    source_table text not null check (source_table in ('reels', 'captions')),
    source_row_id uuid,
    source_video_url text,
    status text not null default 'pending' check (status in ('pending', 'processing', 'done', 'failed')),
    attempts integer not null default 0,
    last_error text,
    unique (source_table, source_row_id)
);

create index if not exists idx_transcription_backfill_status_created
    on public.transcription_backfill_queue(status, created_at asc);

alter table public.transcription_backfill_queue enable row level security;

drop policy if exists transcription_backfill_select_own on public.transcription_backfill_queue;
create policy transcription_backfill_select_own
on public.transcription_backfill_queue
for select
to authenticated
using (auth.uid() = user_id);

insert into public.transcription_backfill_queue (
    user_id,
    job_id,
    clip_index,
    source_table,
    source_row_id,
    source_video_url,
    status
)
select
    r.reel_user_id,
    coalesce(r.reel_job_id, ''),
    coalesce(r.reel_clip_index, 0),
    'reels',
    r.id,
    coalesce(r.reel_url, ''),
    'pending'
from public.reels r
where r.deleted_at is null
on conflict (source_table, source_row_id) do nothing;

insert into public.transcription_backfill_queue (
    user_id,
    job_id,
    clip_index,
    source_table,
    source_row_id,
    source_video_url,
    status
)
select
    c.caption_user_id,
    coalesce(c.caption_job_id, ''),
    coalesce(c.caption_clip_index, 0),
    'captions',
    c.id,
    coalesce(c.caption_url, ''),
    'pending'
from public.captions c
where c.deleted_at is null
on conflict (source_table, source_row_id) do nothing;

