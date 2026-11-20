import { NextResponse, type NextRequest } from "next/server";
import { userClient } from "@/lib/supabase";
import { onSameHost, safeNext } from "@/lib/paths";

/** Default Supabase magic link (PKCE): exchange ?code= for a session. */
export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const supabase = await userClient();
  const { error } = await supabase.auth.exchangeCodeForSession(url.searchParams.get("code") ?? "");
  return NextResponse.redirect(onSameHost(request, error ? "/login?error=link_invalid" : safeNext(url.searchParams.get("next"))));
}
