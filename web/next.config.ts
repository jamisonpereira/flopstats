import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Keys live in the repo-root .env (shared with the pipeline). Values already in the
// environment win, so tests and hosting can override them.
loadEnvConfig(path.resolve(process.cwd(), ".."));

const nextConfig: NextConfig = {};
export default nextConfig;
