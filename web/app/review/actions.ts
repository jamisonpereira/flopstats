"use server";

import { redirect } from "next/navigation";
import { TYPES, type Supa } from "@/lib/review";
import { userClient } from "@/lib/supabase";

type Ctx = { sb: Supa; itemId: number | null; incidentId: number | null; reason: string | null };

async function ctx(form: FormData): Promise<Ctx> {
  const num = (k: string) => (form.get(k) ? Number(form.get(k)) : null);
  const reason = String(form.get("reason") ?? "").trim();
  return { sb: await userClient(), itemId: num("item_id"), incidentId: num("incident_id"), reason: reason || null };
}

function check<T>(res: { error: { message: string } | null; data?: T }, what: string): T | undefined {
  if (res.error) throw new Error(`${what}: ${res.error.message}`);
  return res.data;
}

async function record(c: Ctx, decision: string, value: Record<string, unknown>, resolution: Record<string, unknown>) {
  check(await c.sb.from("reviews").insert({ incident_id: c.incidentId, item_id: c.itemId, decision, value, reason: c.reason }), "review");
  if (c.itemId) {
    check(await c.sb.from("review_items").update({ status: "resolved", resolution, resolved_at: new Date().toISOString() })
      .eq("id", c.itemId).eq("status", "open"), "resolve item");
  }
}

/** The next open item after this one, else the queue. */
async function goNext(c: Ctx): Promise<never> {
  const { data } = await c.sb.from("review_items").select("id").eq("status", "open").gt("id", c.itemId ?? 0).order("id").limit(1);
  redirect(data?.[0] ? `/review/${data[0].id}` : "/review");
}

export async function confirmFlop(form: FormData) {
  const c = await ctx(form);
  check(await c.sb.from("incidents").update({ status: "confirmed" }).eq("id", c.incidentId!), "incident");
  await record(c, "confirm", {}, { status: "confirmed" });
  await goNext(c);
}

export async function rejectFlop(form: FormData) {
  const c = await ctx(form);
  check(await c.sb.from("incidents").update({ status: "rejected" }).eq("id", c.incidentId!), "incident");
  await record(c, "reject", {}, { status: "rejected" });
  await goNext(c);
}

export async function changeType(type: string, form: FormData) {
  const c = await ctx(form);
  if (!(TYPES as readonly string[]).includes(type)) throw new Error("unknown flop type");
  check(await c.sb.from("incidents").update({ type, status: "confirmed" }).eq("id", c.incidentId!), "incident");
  await record(c, "change_type", { type }, { status: "confirmed", type });
  await goNext(c);
}

export async function setPlayer(playerId: number, form: FormData) {
  const c = await ctx(form);
  if (!Number.isInteger(playerId) || playerId <= 0) throw new Error("no player chosen");
  check(await c.sb.from("incident_players").update({ player_id: playerId, confidence: 1 })
    .eq("incident_id", c.incidentId!).eq("role", "flopper"), "incident player");
  await record(c, "set_player", { player_id: playerId }, { player_id: playerId });
  await goNext(c);
}

export async function linkMatch(matchId: number | null, form: FormData) {
  const c = await ctx(form);
  const listing = Number(form.get("listing_id"));
  if (matchId) {
    check(await c.sb.from("external_refs").update({ entity_id: matchId, confidence: 1, status: "linked" }).eq("id", listing), "link");
    await record(c, "confirm", { match_id: matchId }, { match_id: matchId });
  } else {
    check(await c.sb.from("external_refs").update({ status: "rejected" }).eq("id", listing), "link");
    await record(c, "reject", {}, { rejected: true });
  }
  await goNext(c);
}

function seconds(mmss: string): number {
  const m = mmss.trim().match(/^(\d+):([0-5]\d)$/);
  if (!m) throw new Error(`expected mm:ss, got ${mmss}`);
  return Number(m[1]) * 60 + Number(m[2]);
}

export async function setSync(form: FormData) {
  const c = await ctx(form);
  const videoId = Number(form.get("video_id"));
  const kickoff = seconds(String(form.get("kickoff")));
  const second = seconds(String(form.get("second_half")));
  if (second <= kickoff) throw new Error("the second half must start after kickoff");
  // The runner picks the resolution up on its next pass ("re-queue"): it resumes after sync.
  check(await c.sb.from("videos").update({ kickoff_offset_s: kickoff, second_half_offset_s: second, sync_status: "ok" }).eq("id", videoId), "video");
  await record(c, "confirm", { kickoff_offset_s: kickoff, second_half_offset_s: second },
    { kickoff_offset_s: kickoff, second_half_offset_s: second });
  await goNext(c);
}

export async function linkEventPlayer(playerId: number | null, form: FormData) {
  const c = await ctx(form);
  const eventId = Number(form.get("event_id"));
  if (playerId) check(await c.sb.from("match_events").update({ player_id: playerId }).eq("id", eventId), "event");
  await record(c, playerId ? "set_player" : "reject", { player_id: playerId }, { player_id: playerId });
  await goNext(c);
}
