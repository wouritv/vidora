-- Remove legacy standalone captions table after migrating captions workflow into reels customization.
-- This migration is intentionally scoped to the old ia_caption storage only.

drop table if exists public.ia_caption cascade;

