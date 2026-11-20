import fs from "node:fs";
import path from "node:path";
import { Client } from "pg";
import { createClient } from "@supabase/supabase-js";
import { localSupabaseEnv } from "./local-env";

export const ADMIN = "admin@example.com";
export const OUTSIDER = "fan@example.com";
const env = localSupabaseEnv();

export type Seed = { verdictItem: number; playerItem: number; reviewIncident: number; playerIncident: number;
  confirmedIncidents: number[]; rejectedIncident: number; homeSeven: number };

export function admin() {
  return createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_KEY, { auth: { persistSession: false } });
}

export async function seed(): Promise<Seed> {
  const db = new Client({ connectionString: env.DATABASE_URL });
  await db.connect();
  const one = async (sql: string, p: unknown[] = []) => Number((await db.query(sql, p)).rows[0]?.id);
  try {
    const { rows } = await db.query("select tablename from pg_tables where schemaname = 'public'");
    await db.query(`truncate ${rows.map((r) => `public."${r.tablename}"`).join(", ")} restart identity cascade`);
    await db.query("insert into settings (key, value) values ('admin_emails', $1)", [JSON.stringify([ADMIN])]);
    const c = await one("insert into countries (name) values ('England') returning id");
    const lg = await one("insert into leagues (name, country_id) values ('Premier League', $1) returning id", [c]);
    const s = await one("insert into seasons (league_id, year) values ($1, 2024) returning id", [lg]);
    const home = await one("insert into teams (name) values ('Brentford') returning id");
    const away = await one("insert into teams (name) values ('Nottingham Forest') returning id");
    const m = await one("insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values ($1, $2, $3, '2024-12-21 15:00Z') returning id", [s, home, away]);
    const players: Record<string, number> = {};
    for (const [team, num, name] of [[home, 7, "Home Seven"], [home, 9, "Home Nine"], [away, 11, "Away Eleven"]] as const) {
      players[name] = await one("insert into players (display_name) values ($1) returning id", [name]);
      await db.query("insert into match_lineups (match_id, player_id, team_id, is_starter, shirt_number) values ($1, $2, $3, true, $4)", [m, players[name], team, num]);
    }
    const v = await one("insert into videos (match_id, source, source_url, sync_status) values ($1, 'footballia', 'https://footballia.eu/matches/x', 'ok') returning id", [m]);
    const run = await one("insert into detection_runs (name, config) values ('pilot-v1', '{}') returning id");
    const incident = async (status: string, minute: number, key: string) => {
      const id = await one(
        `insert into incidents (run_id, match_id, video_id, type, video_start_s, video_end_s, game_minute, game_second, team_id,
           confidence, status, attrs, ref_decision, dedupe_key)
         values ($1, $2, $3, 'dive', $4, $5, $6, 12, $7, 0.7, $8, '{"fake_pain": 7, "contact_level": "light"}', 'foul', $9) returning id`,
        [run, m, v, minute * 60, minute * 60 + 8, minute, home, status, key]);
      await db.query("insert into clips (incident_id, path, duration_s, bytes) values ($1, $2, 14, 1000)", [id, `clips/${m}/${id}.mp4`]);
      return id;
    };
    const reviewIncident = await incident("review", 12, "a");
    const playerIncident = await incident("confirmed", 30, "b");
    const confirmedIncidents = [playerIncident, await incident("confirmed", 50, "c"), await incident("confirmed", 70, "d")];
    const rejectedIncident = await incident("rejected", 80, "e");
    await db.query("insert into incident_players (incident_id, team_id, role, confidence, player_id) values ($1, $2, 'flopper', 0.9, $3)", [reviewIncident, home, players["Home Nine"]]);
    const guesses = [{ player_id: players["Home Seven"], name: "Home Seven", shirt_number: 7, team_id: home },
                     { player_id: players["Home Nine"], name: "Home Nine", shirt_number: 9, team_id: home }];
    await db.query("insert into incident_players (incident_id, team_id, role, confidence, guesses) values ($1, $2, 'flopper', 0.3, $3)", [playerIncident, home, JSON.stringify(guesses)]);
    const verdictItem = await one("insert into review_items (kind, subject_type, subject_id, payload) values ('flop_verdict', 'incident', $1, '{}') returning id", [reviewIncident]);
    const playerItem = await one("insert into review_items (kind, subject_type, subject_id, payload) values ('flop_player', 'incident', $1, $2) returning id", [playerIncident, JSON.stringify({ team_id: home, guesses })]);

    const sb = admin();
    await sb.storage.createBucket("media", { public: false }).catch(() => undefined);
    const clip = fs.readFileSync(path.resolve(__dirname, "../../pipeline/tests/fixtures/video/tiny.mp4"));
    for (const id of [...confirmedIncidents, reviewIncident, rejectedIncident]) {
      await sb.storage.from("media").upload(`clips/${m}/${id}.mp4`, clip, { contentType: "video/mp4", upsert: true });
    }
    return { verdictItem, playerItem, reviewIncident, playerIncident, confirmedIncidents, rejectedIncident, homeSeven: players["Home Seven"] };
  } finally {
    await db.end();
  }
}

export async function query<T = Record<string, unknown>>(sql: string, p: unknown[] = []): Promise<T[]> {
  const db = new Client({ connectionString: env.DATABASE_URL });
  await db.connect();
  try {
    return (await db.query(sql, p)).rows as T[];
  } finally {
    await db.end();
  }
}

/** A one-time sign-in link for `email`, as Supabase would email it (via the admin API). */
export async function magicLinkPath(email: string, next = "/review"): Promise<string> {
  const sb = admin();
  await sb.auth.admin.createUser({ email, email_confirm: true }).catch(() => undefined);
  const { data, error } = await sb.auth.admin.generateLink({ type: "magiclink", email });
  if (error || !data.properties) throw error ?? new Error("no link");
  return `/auth/confirm?token_hash=${data.properties.hashed_token}&type=magiclink&next=${encodeURIComponent(next)}`;
}
