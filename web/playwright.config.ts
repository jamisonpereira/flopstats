import { defineConfig } from "@playwright/test";
import { localSupabaseEnv } from "./tests/local-env";

// E2E runs against the LOCAL Supabase stack only (`supabase start`), never the hosted project.
const env = localSupabaseEnv();
const PORT = 3100;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}/login`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { ...env, SITE_URL: `http://127.0.0.1:${PORT}` },
  },
});
