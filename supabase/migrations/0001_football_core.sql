-- Football core schema (stage 1, Task 2).
-- Every table: identity id, created_at, updated_at (kept current by a trigger).
-- Foreign keys are ON DELETE RESTRICT, except rows that belong to a match (CASCADE).
-- RLS is enabled everywhere with no policies: only the service role (which bypasses RLS)
-- can read or write until stage 2 adds public read policies.

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := pg_catalog.now();
  return new;
end;
$$;

-- Reference data ----------------------------------------------------------------------

create table public.countries (
  id bigint generated always as identity primary key,
  name text not null,
  code text,
  flag_source_url text,
  flag_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.leagues (
  id bigint generated always as identity primary key,
  name text not null,
  country_id bigint references public.countries (id) on delete restrict,
  type text,
  logo_source_url text,
  logo_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index leagues_country_id_idx on public.leagues (country_id);

create table public.seasons (
  id bigint generated always as identity primary key,
  league_id bigint not null references public.leagues (id) on delete restrict,
  year int not null,
  start_date date,
  end_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (league_id, year)
);

create table public.venues (
  id bigint generated always as identity primary key,
  name text not null,
  city text,
  country_id bigint references public.countries (id) on delete restrict,
  capacity int,
  surface text,
  image_source_url text,
  image_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index venues_country_id_idx on public.venues (country_id);

create table public.teams (
  id bigint generated always as identity primary key,
  name text not null,
  code text,
  country_id bigint references public.countries (id) on delete restrict,
  venue_id bigint references public.venues (id) on delete restrict,
  logo_source_url text,
  logo_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index teams_country_id_idx on public.teams (country_id);
create index teams_venue_id_idx on public.teams (venue_id);

create table public.team_seasons (
  id bigint generated always as identity primary key,
  team_id bigint not null references public.teams (id) on delete restrict,
  season_id bigint not null references public.seasons (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (team_id, season_id)
);
create index team_seasons_season_id_idx on public.team_seasons (season_id);

create table public.players (
  id bigint generated always as identity primary key,
  first_name text,
  last_name text,
  display_name text not null,
  birth_date date,
  nationality_country_id bigint references public.countries (id) on delete restrict,
  photo_source_url text,
  photo_path text,
  photo_is_placeholder boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index players_nationality_country_id_idx on public.players (nationality_country_id);

create table public.player_team_seasons (
  id bigint generated always as identity primary key,
  player_id bigint not null references public.players (id) on delete restrict,
  team_id bigint not null references public.teams (id) on delete restrict,
  season_id bigint not null references public.seasons (id) on delete restrict,
  shirt_number smallint,
  position text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (player_id, team_id, season_id)
);
create index player_team_seasons_team_season_idx on public.player_team_seasons (team_id, season_id);
create index player_team_seasons_season_id_idx on public.player_team_seasons (season_id);

create table public.coaches (
  id bigint generated always as identity primary key,
  name text not null,
  nationality_country_id bigint references public.countries (id) on delete restrict,
  photo_source_url text,
  photo_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index coaches_nationality_country_id_idx on public.coaches (nationality_country_id);

create table public.referees (
  id bigint generated always as identity primary key,
  name text not null unique,
  nationality_country_id bigint references public.countries (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index referees_nationality_country_id_idx on public.referees (nationality_country_id);

-- Matches and their child rows -------------------------------------------------------

create table public.matches (
  id bigint generated always as identity primary key,
  season_id bigint not null references public.seasons (id) on delete restrict,
  home_team_id bigint not null references public.teams (id) on delete restrict,
  away_team_id bigint not null references public.teams (id) on delete restrict,
  kickoff_at timestamptz not null,
  venue_id bigint references public.venues (id) on delete restrict,
  referee_id bigint references public.referees (id) on delete restrict,
  home_coach_id bigint references public.coaches (id) on delete restrict,
  away_coach_id bigint references public.coaches (id) on delete restrict,
  round text,
  status text,
  goals_home smallint,
  goals_away smallint,
  attendance int,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (home_team_id <> away_team_id)
);
create index matches_season_id_idx on public.matches (season_id);
create index matches_home_team_id_idx on public.matches (home_team_id);
create index matches_away_team_id_idx on public.matches (away_team_id);
create index matches_kickoff_at_idx on public.matches (kickoff_at);
create index matches_venue_id_idx on public.matches (venue_id);
create index matches_referee_id_idx on public.matches (referee_id);
create index matches_home_coach_id_idx on public.matches (home_coach_id);
create index matches_away_coach_id_idx on public.matches (away_coach_id);

create table public.match_lineups (
  id bigint generated always as identity primary key,
  match_id bigint not null references public.matches (id) on delete cascade,
  player_id bigint not null references public.players (id) on delete restrict,
  team_id bigint not null references public.teams (id) on delete restrict,
  is_starter boolean not null default false,
  shirt_number smallint,
  position text,
  minutes_played smallint,
  fouls_drawn smallint,
  fouls_committed smallint,
  yellow_cards smallint,
  red_cards smallint,
  penalties_won smallint,
  penalties_committed smallint,
  penalties_scored smallint,
  penalties_missed smallint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (match_id, player_id)
);
create index match_lineups_player_id_idx on public.match_lineups (player_id);
create index match_lineups_team_id_idx on public.match_lineups (team_id);

create table public.match_events (
  id bigint generated always as identity primary key,
  match_id bigint not null references public.matches (id) on delete cascade,
  team_id bigint not null references public.teams (id) on delete restrict,
  player_id bigint references public.players (id) on delete restrict,
  assist_player_id bigint references public.players (id) on delete restrict,
  minute smallint,
  extra_minute smallint,
  type text not null,
  detail text,
  comments text,
  source_hash text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index match_events_match_id_idx on public.match_events (match_id);
create index match_events_team_id_idx on public.match_events (team_id);
create index match_events_player_id_idx on public.match_events (player_id);
create index match_events_assist_player_id_idx on public.match_events (assist_player_id);

-- Linking and review -----------------------------------------------------------------

create table public.external_refs (
  id bigint generated always as identity primary key,
  entity_type text not null,
  entity_id bigint,  -- polymorphic (no FK); null while unlinked
  source text not null,
  source_id text not null,
  confidence real,
  status text not null check (status in ('linked', 'needs_review', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (entity_type, source, source_id)
);
create index external_refs_entity_idx on public.external_refs (entity_type, entity_id);

create table public.review_items (
  id bigint generated always as identity primary key,
  kind text not null
    check (kind in ('match_link', 'video_sync', 'player_link', 'flop_verdict', 'flop_player')),
  subject_type text not null,
  subject_id bigint,  -- polymorphic (no FK)
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'open',
  resolution jsonb,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index review_items_open_idx on public.review_items (kind, created_at) where status = 'open';
create index review_items_subject_idx on public.review_items (subject_type, subject_id);

-- updated_at triggers and RLS on every table ----------------------------------------

do $$
declare
  t text;
begin
  foreach t in array array[
    'countries', 'leagues', 'seasons', 'venues', 'teams', 'team_seasons', 'players',
    'player_team_seasons', 'coaches', 'referees', 'matches', 'match_lineups',
    'match_events', 'external_refs', 'review_items'
  ] loop
    execute format(
      'create trigger set_updated_at before update on public.%I '
      'for each row execute function public.set_updated_at()', t);
    execute format('alter table public.%I enable row level security', t);
  end loop;
end;
$$;
