-- Ops schema (stage 1, Task 3): raw API store, job queue / load log, cost ledger, settings.
-- RLS on everywhere with no policies (service role only). Reuses public.set_updated_at().

create table public.api_raw (
  id bigint generated always as identity primary key,
  endpoint text not null,
  params jsonb not null default '{}'::jsonb,
  params_hash text not null unique,  -- hash of endpoint + canonical params
  status_code int not null,
  body jsonb not null,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index api_raw_endpoint_idx on public.api_raw (endpoint);

create table public.jobs (
  id bigint generated always as identity primary key,
  kind text not null,
  key text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'done', 'failed', 'needs_review', 'blocked_budget')),
  attempts int not null default 0,
  last_error text,
  locked_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (kind, key)
);
-- Claimable work: pending jobs, or running jobs whose lease may have expired.
create index jobs_claimable_idx on public.jobs (kind, id)
  where status in ('pending', 'running');

create table public.cost_ledger (
  id bigint generated always as identity primary key,
  run_id bigint,  -- detection_runs arrives in 0003; FK added there
  match_id bigint references public.matches (id) on delete restrict,
  service text not null,
  model text,
  units jsonb not null default '{}'::jsonb,
  usd numeric(10, 4) not null check (usd >= 0),
  idempotency_key text not null unique,
  at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index cost_ledger_run_id_idx on public.cost_ledger (run_id);
create index cost_ledger_match_id_idx on public.cost_ledger (match_id);

create table public.settings (
  key text primary key,
  value jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

do $$
declare
  t text;
begin
  foreach t in array array['api_raw', 'jobs', 'cost_ledger', 'settings'] loop
    execute format(
      'create trigger set_updated_at before update on public.%I '
      'for each row execute function public.set_updated_at()', t);
    execute format('alter table public.%I enable row level security', t);
  end loop;
end;
$$;
