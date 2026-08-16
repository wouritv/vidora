-- Storage tracking + subscription lifecycle controls

alter table if exists public.reels
    add column if not exists reel_size_bytes bigint not null default 0;

alter table if exists public.ia_caption
    add column if not exists caption_size_bytes bigint not null default 0;

alter table if exists public.souscription
    add column if not exists auto_renew boolean not null default true,
    add column if not exists canceled_at timestamptz,
    add column if not exists reactivated_at timestamptz,
    add column if not exists paused_at timestamptz,
    add column if not exists resumed_at timestamptz,
    add column if not exists retention_deadline_at timestamptz,
    add column if not exists account_disabled_at timestamptz;

create index if not exists idx_souscription_user_end_date
    on public.souscription(userid, payment_end_date desc);

create index if not exists idx_souscription_retention_cleanup
    on public.souscription(retention_deadline_at)
    where account_disabled_at is null;

