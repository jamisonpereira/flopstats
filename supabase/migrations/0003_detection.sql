-- Detection schema (stage 1, Task 8): videos, runs, windows, candidates, verifications,
-- incidents and their players, clips, and Jamison's reviews.
-- A run's working rows (windows, candidates, verifications, incidents and their children)
-- cascade from the run. Reviews are labelled data and RESTRICT, so a reviewed run can't be
-- deleted by accident. cost_ledger keeps its rows (RESTRICT) and gains its run FK here.
-- RLS on everywhere with no policies (service role only).

create table public.videos (
  id bigint generated always as identity primary key,
  match_id bigint references public.matches (id) on delete restrict,  -- null until linked
  source text not null,
  source_url text not null,
  duration_s real,
  kickoff_offset_s real,
  second_half_offset_s real,
  sync_status text not null default 'pending' check (sync_status in ('pending', 'ok', 'needs_review')),
  local_path text,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source, source_url)
);
create index videos_match_id_idx on public.videos (match_id);

create table public.detection_runs (
  id bigint generated always as identity primary key,
  name text not null unique,
  config jsonb not null,  -- window length/step, thresholds, review cap, padding, models, prompt versions
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.windows (
  id bigint generated always as identity primary key,
  run_id bigint not null references public.detection_runs (id) on delete cascade,
  video_id bigint not null references public.videos (id) on delete restrict,
  start_s real not null,
  end_s real not null,
  score real,
  prior real,
  final_score real,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (run_id, video_id, start_s),
  check (end_s > start_s)
);
create index windows_video_id_idx on public.windows (video_id);

create table public.candidates (
  id bigint generated always as identity primary key,
  run_id bigint not null references public.detection_runs (id) on delete cascade,
  video_id bigint not null references public.videos (id) on delete restrict,
  start_s real not null,
  end_s real not null,
  final_score real,
  status text not null default 'pending' check (status in ('pending', 'verified', 'rejected')),
  segment_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_s > start_s)
);
create index candidates_run_video_idx on public.candidates (run_id, video_id, start_s);
create index candidates_video_id_idx on public.candidates (video_id);

create table public.verifications (
  id bigint generated always as identity primary key,
  candidate_id bigint not null references public.candidates (id) on delete cascade,
  model text not null,
  answers jsonb not null default '{}'::jsonb,
  confidence real,
  usd numeric(10, 4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (candidate_id, model)
);

create table public.incidents (
  id bigint generated always as identity primary key,
  run_id bigint not null references public.detection_runs (id) on delete cascade,
  match_id bigint not null references public.matches (id) on delete restrict,
  video_id bigint not null references public.videos (id) on delete restrict,
  candidate_id bigint references public.candidates (id) on delete set null,
  type text not null check (type in ('dive', 'exaggeration', 'feigned_injury', 'time_wasting')),
  video_start_s real not null,
  video_end_s real not null,
  game_minute smallint,
  game_second smallint,
  team_id bigint references public.teams (id) on delete restrict,  -- the flopper's team
  confidence real,
  status text not null check (status in ('confirmed', 'review', 'rejected', 'ai_judged')),
  -- time_on_ground_s, rolls, fake_pain, clutched_part, contact_part, contact_level,
  -- miracle_recovery, recovery_trigger, pitch_x, pitch_y, pitch_conf
  attrs jsonb not null default '{}'::jsonb,
  ref_decision text check (ref_decision in ('none', 'foul', 'yellow', 'red', 'penalty')),
  ref_penalized_team_id bigint references public.teams (id) on delete restrict,
  consequence jsonb,
  sim_score real,
  dedupe_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (run_id, video_id, dedupe_key),
  check (video_end_s >= video_start_s)
);
create index incidents_match_id_idx on public.incidents (match_id);
create index incidents_video_id_idx on public.incidents (video_id);
create index incidents_candidate_id_idx on public.incidents (candidate_id);
create index incidents_team_id_idx on public.incidents (team_id);
create index incidents_ref_penalized_team_id_idx on public.incidents (ref_penalized_team_id);
create index incidents_run_status_idx on public.incidents (run_id, status);

create table public.incident_players (
  id bigint generated always as identity primary key,
  incident_id bigint not null references public.incidents (id) on delete cascade,
  player_id bigint references public.players (id) on delete restrict,  -- null = "who is this?"
  team_id bigint not null references public.teams (id) on delete restrict,
  role text not null check (role in ('flopper', 'alleged_fouler', 'other')),
  confidence real,
  guesses jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index incident_players_incident_id_idx on public.incident_players (incident_id);
create index incident_players_player_id_idx on public.incident_players (player_id);
create index incident_players_team_id_idx on public.incident_players (team_id);

create table public.clips (
  id bigint generated always as identity primary key,
  incident_id bigint not null unique references public.incidents (id) on delete cascade,
  path text not null,
  duration_s real,
  bytes bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.reviews (
  id bigint generated always as identity primary key,
  incident_id bigint references public.incidents (id) on delete restrict,
  item_id bigint references public.review_items (id) on delete restrict,
  decision text not null check (decision in ('confirm', 'reject', 'change_type', 'set_player')),
  value jsonb,
  reason text,
  at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index reviews_incident_id_idx on public.reviews (incident_id);
create index reviews_item_id_idx on public.reviews (item_id);

-- cost_ledger.run_id was created in 0002 before detection_runs existed.
alter table public.cost_ledger
  add constraint cost_ledger_run_id_fkey foreign key (run_id)
  references public.detection_runs (id) on delete restrict;

do $$
declare
  t text;
begin
  foreach t in array array[
    'videos', 'detection_runs', 'windows', 'candidates', 'verifications', 'incidents',
    'incident_players', 'clips', 'reviews'
  ] loop
    execute format(
      'create trigger set_updated_at before update on public.%I '
      'for each row execute function public.set_updated_at()', t);
    execute format('alter table public.%I enable row level security', t);
  end loop;
end;
$$;
