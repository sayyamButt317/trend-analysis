-- Competitor analysis: user input (prompts) + API results (analysis)
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/001_prompts_analysis.sql

create extension if not exists "pgcrypto";

create table if not exists public.prompts (
    id uuid primary key default gen_random_uuid(),
    agent_type text not null default 'competitor',
    company_data text not null,
    region text not null,
    company_name text,
    competitors jsonb not null default '[]'::jsonb,
    request_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.analysis (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid not null references public.prompts (id) on delete cascade,
    agent_type text not null default 'competitor',
    status text not null default 'failed',
    success boolean not null default false,
    error text,
    summary text,
    result jsonb not null default '{}'::jsonb,
    competitor_count integer not null default 0,
    post_count integer not null default 0,
    duration_sec numeric(10, 3),
    platform text,
    created_at timestamptz not null default now()
);

create index if not exists idx_prompts_created_at on public.prompts (created_at desc);
create index if not exists idx_prompts_agent_type on public.prompts (agent_type);
create index if not exists idx_analysis_prompt_id on public.analysis (prompt_id);
create index if not exists idx_analysis_created_at on public.analysis (created_at desc);
create index if not exists idx_analysis_status on public.analysis (status);

alter table public.prompts enable row level security;
alter table public.analysis enable row level security;

drop policy if exists "prompts_anon_insert" on public.prompts;
drop policy if exists "prompts_anon_select" on public.prompts;
drop policy if exists "analysis_anon_insert" on public.analysis;
drop policy if exists "analysis_anon_select" on public.analysis;

create policy "prompts_anon_insert"
    on public.prompts for insert to anon, authenticated
    with check (true);

create policy "prompts_anon_select"
    on public.prompts for select to anon, authenticated
    using (true);

create policy "analysis_anon_insert"
    on public.analysis for insert to anon, authenticated
    with check (true);

create policy "analysis_anon_select"
    on public.analysis for select to anon, authenticated
    using (true);
