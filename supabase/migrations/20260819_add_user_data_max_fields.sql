-- Add explicit user maxima for credits/storage.

alter table if exists public.user_data
    add column if not exists credit_max numeric(14, 2) not null default 0,
    add column if not exists stockage_max numeric(14, 6) not null default 0;

-- Backfill existing rows from current balances to preserve current UX ratio semantics.
update public.user_data
set
    credit_max = greatest(coalesce(credit_max, 0), coalesce(credit, 0)),
    stockage_max = greatest(coalesce(stockage_max, 0), coalesce(stockage, 0))
where
    credit_max = 0
    or stockage_max = 0;

