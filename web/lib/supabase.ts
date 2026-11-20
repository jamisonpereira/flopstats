import "server-only";
import { createServerClient } from "@supabase/ssr";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { localReviewBypass } from "@/lib/local-review";

function env(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} is not set`);
  return v;
}

/** The signed-in user's client: every query runs under RLS (admins only, see 0006_review_access.sql).
 *  Local review (see local-review.ts) uses the service key instead, so no login is needed. */
export async function userClient() {
  if (localReviewBypass()) {
    return createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_KEY"), {
      auth: { persistSession: false },
    }) as unknown as Awaited<ReturnType<typeof sessionClient>>;
  }
  return sessionClient();
}

async function sessionClient() {
  const store = await cookies();
  return createServerClient(env("SUPABASE_URL"), env("SUPABASE_ANON_KEY"), {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (list) => {
        try {
          list.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // Server components can't set cookies; the middleware refreshes the session.
        }
      },
    },
  });
}

/** Service-role client, used only on the server to sign clip URLs in the private bucket. */
export function storageClient() {
  return createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_KEY"), { auth: { persistSession: false } }).storage;
}

export async function signedClipUrl(path: string | null | undefined): Promise<string | null> {
  if (!path) return null;
  const { data } = await storageClient().from("media").createSignedUrl(path, 60 * 60);
  return data?.signedUrl ?? null;
}

export function siteUrl(): string {
  return process.env.SITE_URL ?? "http://127.0.0.1:3000";
}
