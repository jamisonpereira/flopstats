import Link from "next/link";
import { notFound } from "next/navigation";
import { TYPES, matchLabels, mmss, type Guess, type Item, type Supa } from "@/lib/review";

type WithPlayer = { players?: { display_name: string } | { display_name: string }[] | null };
import { signedClipUrl, userClient } from "@/lib/supabase";
import { changeType, confirmFlop, linkEventPlayer, linkMatch, rejectFlop, setPlayer, setSync } from "../actions";
import Shortcuts from "../Shortcuts";

export const dynamic = "force-dynamic";

export default async function ItemPage({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = await params;
  const sb = await userClient();
  let item: Item | null = null;
  let incidentId: number | null = null;
  if (itemId.startsWith("inc-")) {
    incidentId = Number(itemId.slice(4));
  } else {
    const { data } = await sb.from("review_items").select("id, kind, subject_type, subject_id, payload, status").eq("id", Number(itemId)).maybeSingle();
    if (!data) notFound();
    item = data as Item;
    if (item.subject_type === "incident") incidentId = item.subject_id;
  }
  const nav = await neighbours(sb, item?.id ?? null);
  return (
    <main>
      <Shortcuts />
      <p className="nav">
        <Link href="/review">← queue</Link>
        {nav.prev && <Link href={`/review/${nav.prev}`} data-key="k">prev (k)</Link>}
        {nav.next && <Link href={`/review/${nav.next}`} data-key="j">next (j)</Link>}
      </p>
      {item && <h1>{item.kind} #{item.id}{item.status !== "open" && ` (${item.status})`}</h1>}
      {incidentId != null && (await IncidentView({ sb, incidentId, item }))}
      {item?.kind === "match_link" && <MatchLinkView item={item} />}
      {item?.kind === "video_sync" && <VideoSyncView item={item} />}
      {item?.kind === "player_link" && <PlayerLinkView item={item} />}
    </main>
  );
}

async function neighbours(sb: Supa, id: number | null) {
  if (id == null) return { prev: null, next: null };
  const [p, n] = await Promise.all([
    sb.from("review_items").select("id").eq("status", "open").lt("id", id).order("id", { ascending: false }).limit(1),
    sb.from("review_items").select("id").eq("status", "open").gt("id", id).order("id").limit(1),
  ]);
  return { prev: p.data?.[0]?.id ?? null, next: n.data?.[0]?.id ?? null };
}

function Hidden({ item, incidentId }: { item: Item | null; incidentId?: number | null }) {
  return (
    <>
      {item && <input type="hidden" name="item_id" value={item.id} />}
      {incidentId != null && <input type="hidden" name="incident_id" value={incidentId} />}
    </>
  );
}

async function IncidentView({ sb, incidentId, item }: { sb: Supa; incidentId: number; item: Item | null }) {
  const { data: inc } = await sb.from("incidents").select("*").eq("id", incidentId).maybeSingle();
  if (!inc) notFound();
  const [{ data: clip }, { data: players }, labels] = await Promise.all([
    sb.from("clips").select("path").eq("incident_id", incidentId).maybeSingle(),
    sb.from("incident_players").select("role, player_id, team_id, confidence, guesses, players(display_name)").eq("incident_id", incidentId),
    matchLabels(sb, [inc.match_id]),
  ]);
  const flopper = (players ?? []).find((p) => p.role === "flopper");
  const teamId = flopper?.team_id ?? inc.team_id;
  const { data: lineup } = teamId
    ? await sb.from("match_lineups").select("player_id, shirt_number, players(display_name)").eq("match_id", inc.match_id).eq("team_id", teamId).order("shirt_number")
    : { data: [] };
  const url = await signedClipUrl(clip?.path);
  const attrs = (inc.attrs ?? {}) as Record<string, unknown>;
  const name = (p: WithPlayer | null | undefined) => (Array.isArray(p?.players) ? p.players[0]?.display_name : p?.players?.display_name);
  const guesses = (flopper?.guesses ?? []) as Guess[];
  return (
    <section>
      <p className="muted">{labels.get(inc.match_id)} · {inc.game_minute ?? "?"}:{String(inc.game_second ?? 0).padStart(2, "0")} · video {mmss(inc.video_start_s)}</p>
      {url ? <video src={url} controls autoPlay muted playsInline className="clip" /> : <p className="error">No clip.</p>}
      <dl className="facts">
        <dt>AI verdict</dt><dd>{inc.type} · {Math.round(inc.confidence * 100)}% · {inc.status}</dd>
        <dt>Ref</dt><dd>{inc.ref_decision ?? "?"}</dd>
        <dt>Flopper</dt><dd>{flopper?.player_id ? name(flopper) : "unknown"}{flopper ? ` (${Math.round((flopper.confidence ?? 0) * 100)}%)` : ""}</dd>
        {Object.entries(attrs).map(([k, v]) => (<><dt key={k}>{k}</dt><dd key={`${k}-v`}>{String(v)}</dd></>))}
      </dl>
      <form className="actions">
        <Hidden item={item} incidentId={incidentId} />
        <textarea name="reason" placeholder="Reason (optional)" rows={2} />
        <div className="row">
          <button formAction={confirmFlop} data-key="y" className="ok">✓ Confirm (y)</button>
          <button formAction={rejectFlop} data-key="n" className="no">✗ Not a flop (n)</button>
        </div>
        <div className="row">
          {TYPES.map((t, i) => (
            <button key={t} formAction={changeType.bind(null, t)} data-key={String(i + 1)}>{t} ({i + 1})</button>
          ))}
        </div>
        <h3>Who is it?</h3>
        <div className="row">
          {guesses.map((g) => (
            <button key={`g${g.player_id}`} formAction={setPlayer.bind(null, Number(g.player_id))}>#{g.shirt_number ?? "?"} {g.name}</button>
          ))}
        </div>
        <details>
          <summary>Whole lineup</summary>
          <div className="row">
            {((lineup ?? []) as ({ player_id: number; shirt_number: number | null } & WithPlayer)[]).map((p) => (
              <button key={`l${p.player_id}`} formAction={setPlayer.bind(null, Number(p.player_id))}>#{p.shirt_number ?? "?"} {name(p)}</button>
            ))}
          </div>
        </details>
      </form>
    </section>
  );
}

function MatchLinkView({ item }: { item: Item }) {
  const p = item.payload ?? {};
  return (
    <section>
      <p>Footballia: <a href={p.url} target="_blank" rel="noreferrer">{p.home} v {p.away} ({p.date})</a></p>
      <form className="actions">
        <Hidden item={item} />
        <input type="hidden" name="listing_id" value={item.subject_id ?? ""} />
        <textarea name="reason" placeholder="Reason (optional)" rows={2} />
        <div className="row">
          {(p.guesses ?? []).map((g: Guess) => (
            <button key={g.match_id} formAction={linkMatch.bind(null, Number(g.match_id))}>
              {g.home} v {g.away} ({g.date}) · {Math.round((g.confidence ?? 0) * 100)}%
            </button>
          ))}
          <button formAction={linkMatch.bind(null, null)} className="no" data-key="n">✗ None of these (n)</button>
        </div>
      </form>
    </section>
  );
}

function VideoSyncView({ item }: { item: Item }) {
  const p = item.payload ?? {};
  return (
    <section>
      <p>The clock couldn&apos;t be read. Open <a href={p.url} target="_blank" rel="noreferrer">the match video</a> and note the video
        time (mm:ss) where each half kicks off.</p>
      <form className="actions" action={setSync}>
        <Hidden item={item} />
        <input type="hidden" name="video_id" value={item.subject_id ?? ""} />
        <label>Kickoff <input name="kickoff" placeholder="1:12" pattern="\d+:[0-5]\d" required /></label>
        <label>Second half <input name="second_half" placeholder="48:56" pattern="\d+:[0-5]\d" required /></label>
        <textarea name="reason" placeholder="Reason (optional)" rows={2} />
        <button type="submit" className="ok">Save offsets</button>
      </form>
    </section>
  );
}

function PlayerLinkView({ item }: { item: Item }) {
  const p = item.payload ?? {};
  return (
    <section>
      <p>Event player &quot;{p.name ?? "?"}&quot; (API id {p.api_player_id ?? "none"}) could not be linked.</p>
      <form className="actions">
        <Hidden item={item} />
        <input type="hidden" name="event_id" value={item.subject_id ?? ""} />
        <div className="row">
          {(p.guesses ?? []).map((g: Guess) => (
            <button key={g.player_id} formAction={linkEventPlayer.bind(null, Number(g.player_id))}>{g.name} ({g.score})</button>
          ))}
          <button formAction={linkEventPlayer.bind(null, null)} className="no" data-key="n">✗ Leave unlinked (n)</button>
        </div>
      </form>
    </section>
  );
}
