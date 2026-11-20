import { execSync } from "node:child_process";
import path from "node:path";

/** URL and keys of the local Supabase stack (demo keys printed by `supabase status`). */
export function localSupabaseEnv(): Record<string, string> {
  const out = execSync("supabase status -o env", { cwd: path.resolve(__dirname, "../.."), encoding: "utf8" });
  const vars: Record<string, string> = {};
  for (const line of out.split("\n")) {
    const m = line.match(/^([A-Z_]+)="?([^"]*)"?$/);
    if (m) vars[m[1]] = m[2];
  }
  const url = vars.API_URL ?? "";
  if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(url)) throw new Error("e2e must target the local Supabase stack");
  return {
    SUPABASE_URL: url,
    SUPABASE_ANON_KEY: vars.ANON_KEY ?? vars.PUBLISHABLE_KEY ?? "",
    SUPABASE_SERVICE_KEY: vars.SERVICE_ROLE_KEY ?? vars.SECRET_KEY ?? "",
    DATABASE_URL: vars.DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
  };
}
