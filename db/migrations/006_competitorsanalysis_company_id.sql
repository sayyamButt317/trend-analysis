-- Link competitor-analysis runs to an external company record
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/006_competitorsanalysis_company_id.sql

alter table public.competitorsanalysis
    add column if not exists company_id text;

create index if not exists idx_competitorsanalysis_company_id
    on public.competitorsanalysis (company_id)
    where company_id is not null;

comment on column public.competitorsanalysis.company_id is
    'External company identifier supplied by the client for competitor analysis lookups.';
