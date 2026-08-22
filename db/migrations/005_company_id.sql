-- Link analyze-company runs to an external company record
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/005_company_id.sql

alter table public.prompts
    add column if not exists company_id text;

alter table public.analysis
    add column if not exists company_id text;

create index if not exists idx_prompts_company_id
    on public.prompts (company_id)
    where company_id is not null;

create index if not exists idx_analysis_company_id
    on public.analysis (company_id)
    where company_id is not null;

comment on column public.prompts.company_id is
    'External company identifier supplied by the client (analyze-company / competitor).';

comment on column public.analysis.company_id is
    'External company identifier copied from the related prompts row.';
