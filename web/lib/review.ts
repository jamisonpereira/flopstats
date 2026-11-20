import "server-only";
import { userClient } from "@/lib/supabase";

export type Supa = Awaited<ReturnType<typeof userClient>>;
export const KINDS = ["flop_verdict", "flop_player", "match_link", "video_sync", "player_link"] as const;
export const TYPES = ["dive", "exaggeration", "feigned_injury", "time_wasting"] as const;

export type Guess = { player_id?: number; match_id?: number; name?: string; shirt_number?: number | null; team_id?: number;
  home?: string; away?: string; date?: string; confidence?: number; score?: number };
export type Payload = { url?: string; home?: string; away?: string; date?: string; type?: string; name?: string;
  api_player_id?: number | null; match_id?: number; guesses?: Guess[] };
export type Item = { id: number; kind: string; subject_type: string; subject_id: number | null; payload: Payload; status: string };

type MatchRow = { id: number; kickoff_at: string; home: { name: string } | null; away: { name: string } | null };

export async function matchLabels(sb: Supa, ids: number[]): Promise<Map<number, string>> {
  const out = new Map<number, string>();
  if (!ids.length) return out;
  const { data } = await sb
    .from("matches")
    .select("id, kickoff_at, home:teams!matches_home_team_id_fkey(name), away:teams!matches_away_team_id_fkey(name)")
    .in("id", ids);
  for (const m of (data ?? []) as unknown as MatchRow[]) {
    out.set(m.id, `${m.home?.name ?? "?"} v ${m.away?.name ?? "?"} (${m.kickoff_at.slice(0, 10)})`);
  }
  return out;
}

/** Which match each review item is about (null when not linked yet). */
export async function itemMatches(sb: Supa, items: Item[]): Promise<Map<number, number | null>> {
  const byIncident = items.filter((i) => i.subject_type === "incident").map((i) => i.subject_id!);
  const byVideo = items.filter((i) => i.subject_type === "video").map((i) => i.subject_id!);
  const inc = byIncident.length ? (await sb.from("incidents").select("id, match_id").in("id", byIncident)).data ?? [] : [];
  const vid = byVideo.length ? (await sb.from("videos").select("id, match_id").in("id", byVideo)).data ?? [] : [];
  const incMap = new Map(inc.map((r) => [r.id as number, r.match_id as number]));
  const vidMap = new Map(vid.map((r) => [r.id as number, r.match_id as number | null]));
  const out = new Map<number, number | null>();
  for (const i of items) {
    if (i.subject_type === "incident") out.set(i.id, incMap.get(i.subject_id!) ?? null);
    else if (i.subject_type === "video") out.set(i.id, vidMap.get(i.subject_id!) ?? null);
    else out.set(i.id, (i.payload?.match_id as number) ?? null);
  }
  return out;
}

/** Deterministic ~10% sample (at least one) of each run's confirmed incidents. */
export function spotSample<T extends { id: number; run_id: number }>(rows: T[]): T[] {
  const byRun = new Map<number, T[]>();
  for (const r of rows) byRun.set(r.run_id, [...(byRun.get(r.run_id) ?? []), r]);
  const hash = (id: number) => Math.imul(id, 2654435761) >>> 0;
  const out: T[] = [];
  for (const list of byRun.values()) {
    const n = Math.max(1, Math.ceil(list.length * 0.1));
    out.push(...[...list].sort((a, b) => hash(a.id) - hash(b.id)).slice(0, n));
  }
  return out.sort((a, b) => a.id - b.id);
}

export function mmss(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null) return "?";
  const s = Math.round(totalSeconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
