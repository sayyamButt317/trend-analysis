create extension if not exists "pgcrypto";

create table if not exists public.competitorsanalysis (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid references public.prompts (id) on delete set null,
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
    company_name text,
    region text,
    created_at timestamptz not null default now()
);

create index if not exists idx_competitorsanalysis_prompt_id
    on public.competitorsanalysis (prompt_id);
create index if not exists idx_competitorsanalysis_created_at
    on public.competitorsanalysis (created_at desc);
create index if not exists idx_competitorsanalysis_status
    on public.competitorsanalysis (status);
create index if not exists idx_competitorsanalysis_agent_type
    on public.competitorsanalysis (agent_type);
create index if not exists idx_competitorsanalysis_company_name
    on public.competitorsanalysis (company_name);

alter table public.competitorsanalysis enable row level security;

drop policy if exists "competitorsanalysis_anon_insert" on public.competitorsanalysis;
drop policy if exists "competitorsanalysis_anon_select" on public.competitorsanalysis;
drop policy if exists "competitorsanalysis_anon_delete" on public.competitorsanalysis;
drop policy if exists "competitorsanalysis_service_all" on public.competitorsanalysis;

create policy "competitorsanalysis_anon_insert"
    on public.competitorsanalysis for insert to anon, authenticated
    with check (true);

create policy "competitorsanalysis_anon_select"
    on public.competitorsanalysis for select to anon, authenticated
    using (true);

create policy "competitorsanalysis_anon_delete"
    on public.competitorsanalysis for delete to anon, authenticated
    using (true);

do $$
begin
    if exists (
        select 1
        from information_schema.table_constraints
        where table_schema = 'public'
          and table_name = 'reports'
          and constraint_name = 'reports_analysis_id_fkey'
    ) then
        alter table public.reports drop constraint reports_analysis_id_fkey;
    end if;
end $$;

comment on table public.competitorsanalysis is
    'Competitor-analysis agent results (SUPABASE_TABLE_COMPETITORSANALYSIS). Company DNA lives in public.analysis.';
