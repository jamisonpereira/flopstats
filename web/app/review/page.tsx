import Link from "next/link";
import { KINDS, itemMatches, matchLabels, spotSample, type Item } from "@/lib/review";
import { userClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Queue({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const sb = await userClient();
  const tab = sp.tab === "spot" ? "spot" : "queue";
  return (
    <main>
      <h1>Review</h1>
      <nav className="tabs">
        <Link href="/review" aria-current={tab === "queue"}>Queue</Link>
        <Link href="/review?tab=spot" aria-current={tab === "spot"}>Spot check</Link>
      </nav>
      {tab === "spot" ? await SpotCheck({ sb }) : await QueueList({ sb, kind: sp.kind })}
    </main>
  );
}

async function QueueList({ sb, kind }: { sb: Awaited<ReturnType<typeof userClient>>; kind?: string }) {
  const { data: all } = await sb.from("review_items").select("id, kind, subject_type, subject_id, payload, status")
    .eq("status", "open").order("id");
  const items = (all ?? []) as Item[];
  const counts = new Map<string, number>(KINDS.map((k) => [k, 0]));
  items.forEach((i) => counts.set(i.kind, (counts.get(i.kind) ?? 0) + 1));
  const shown = kind ? items.filter((i) => i.kind === kind) : items;
  const matchOf = await itemMatches(sb, shown);
  const labels = await matchLabels(sb, [...new Set([...matchOf.values()].filter((m): m is number => m != null))]);
  const groups = new Map<string, Item[]>();
  for (const i of shown) {
    const m = matchOf.get(i.id);
    const label = m != null ? labels.get(m) ?? `match ${m}` : i.payload?.url ? `Unlinked: ${i.payload.url}` : "Unlinked";
    groups.set(label, [...(groups.get(label) ?? []), i]);
  }
  return (
    <>
      <p className="filters">
        <Link href="/review" aria-current={!kind}>all ({items.length})</Link>
        {KINDS.map((k) => (
          <Link key={k} href={`/review?kind=${k}`} aria-current={kind === k}>{k} ({counts.get(k)})</Link>
        ))}
      </p>
      {shown.length === 0 && <p>Nothing to review.</p>}
      {[...groups.entries()].map(([label, list]) => (
        <section key={label}>
          <h2>{label}</h2>
          <ul className="items">
            {list.map((i) => (
              <li key={i.id}>
                <Link href={`/review/${i.id}`}>{i.kind} · #{i.id}{i.payload?.type ? ` · ${i.payload.type}` : ""}</Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

async function SpotCheck({ sb }: { sb: Awaited<ReturnType<typeof userClient>> }) {
  const { data } = await sb.from("incidents").select("id, run_id, match_id, type, confidence, game_minute, game_second, status")
    .eq("status", "confirmed").order("id");
  const sample = spotSample((data ?? []) as { id: number; run_id: number; match_id: number; type: string; confidence: number;
    game_minute: number | null; game_second: number | null; status: string }[]);
  const labels = await matchLabels(sb, [...new Set(sample.map((s) => s.match_id))]);
  return (
    <>
      <p>A 10% sample of each run&apos;s auto-confirmed flops ({sample.length} shown).</p>
      <ul className="items">
        {sample.map((s) => (
          <li key={s.id} data-spot-incident={s.id}>
            <Link href={`/review/inc-${s.id}`}>
              {labels.get(s.match_id)} · {s.game_minute ?? "?"}&apos; · {s.type} · {Math.round(s.confidence * 100)}% · {s.status}
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
