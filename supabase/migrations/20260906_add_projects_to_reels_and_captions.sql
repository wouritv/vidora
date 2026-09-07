-- Add project_id and truthfulness_score to reels, and project_id to captions

-- Add project_id to reels
alter table public.reels
add column project_id uuid references public.projects(id) on delete cascade;

create index if not exists idx_reels_project on public.reels (project_id);

-- Add truthfulness_score to reels
alter table public.reels
add column truthfulness_score integer check (truthfulness_score >= 0 and truthfulness_score <= 100);

-- Add project_id to captions
alter table public.captions
add column project_id uuid references public.projects(id) on delete cascade;

create index if not exists idx_captions_project on public.captions (project_id);

