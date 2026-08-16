-- ============================================================
-- Billing tables: user_data, user_data_history
-- Extra columns on jobs for credit tracking
-- ============================================================

-- ----------------------------------------------------------------
-- user_data  (credit balance + storage per user)
-- ----------------------------------------------------------------
create table if not exists public.user_data (
    id          uuid        primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    user_id     uuid        not null references auth.users(id) on delete cascade,
    credit      numeric(14, 2) not null default 0,
    stockage    numeric(14, 6) not null default 0,  -- in GB
    constraint user_data_user_id_unique unique (user_id)
);

create index if not exists idx_user_data_user_id on public.user_data(user_id);

create or replace function public.set_user_data_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_user_data_updated_at on public.user_data;
create trigger trg_user_data_updated_at
before update on public.user_data
for each row execute function public.set_user_data_updated_at();

alter table public.user_data enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_data' and policyname = 'user_data_select_own'
  ) then
    create policy user_data_select_own on public.user_data
      for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_data' and policyname = 'user_data_insert_own'
  ) then
    create policy user_data_insert_own on public.user_data
      for insert with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_data' and policyname = 'user_data_update_own'
  ) then
    create policy user_data_update_own on public.user_data
      for update using (auth.uid() = user_id);
  end if;
end $$;


-- ----------------------------------------------------------------
-- user_data_history  (audit log of credit / storage changes)
-- ----------------------------------------------------------------
create table if not exists public.user_data_history (
    id             uuid        primary key default gen_random_uuid(),
    created_at     timestamptz not null default now(),
    user_id        uuid        not null references auth.users(id) on delete cascade,
    credit         numeric(14, 2) not null default 0,   -- amount of credits involved
    storage        numeric(14, 6) not null default 0,   -- storage GB involved
    operation      text        not null,                -- 'input' | 'output'
    operation_type text        not null,                -- 'subscription' | 'reels' | 'captions' | 'publications' | 'credit_purchase'
    operation_id   text        not null default ''
);

create index if not exists idx_user_data_history_user_created
    on public.user_data_history(user_id, created_at desc);

alter table public.user_data_history enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_data_history' and policyname = 'user_data_history_select_own'
  ) then
    create policy user_data_history_select_own on public.user_data_history
      for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_data_history' and policyname = 'user_data_history_insert_own'
  ) then
    create policy user_data_history_insert_own on public.user_data_history
      for insert with check (auth.uid() = user_id);
  end if;
end $$;


-- ----------------------------------------------------------------
-- Extra billing columns on jobs
-- ----------------------------------------------------------------
alter table public.jobs
    add column if not exists estimated_credit numeric(14, 2) not null default 0,
    add column if not exists actual_credit    numeric(14, 2) not null default 0,
    add column if not exists cost_breakdown   jsonb          not null default '{}'::jsonb;

