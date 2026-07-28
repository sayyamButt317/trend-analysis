
create table if not exists public.reports (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null references public.analysis (id) on delete cascade,
    prompt_id uuid not null references public.prompts (id) on delete cascade,
    agent_type text not null default 'competitor',
    title text not null,
    company_name text,
    region text,
    executive_summary text,
    report jsonb not null default '{}'::jsonb,
    competitor_count integer not null default 0,
    post_count integer not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_reports_analysis_id on public.reports (analysis_id);
create index if not exists idx_reports_prompt_id on public.reports (prompt_id);
create index if not exists idx_reports_created_at on public.reports (created_at desc);
create index if not exists idx_reports_agent_type on public.reports (agent_type);

alter table public.reports enable row level security;

drop policy if exists "reports_anon_insert" on public.reports;
drop policy if exists "reports_anon_select" on public.reports;

create policy "reports_anon_insert"
    on public.reports for insert to anon, authenticated
    with check (true);

create policy "reports_anon_select"
    on public.reports for select to anon, authenticated
    using (true);
