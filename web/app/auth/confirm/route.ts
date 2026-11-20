import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { onSameHost, safeNext } from "@/lib/paths";
import { userClient } from "@/lib/supabase";

/** Sign-in link with a token hash (email template "{{ .SiteURL }}/auth/confirm?token_hash=..."). */
export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const next = safeNext(url.searchParams.get("next"));
  const supabase = await userClient();
  const { error } = await supabase.auth.verifyOtp({
    token_hash: url.searchParams.get("token_hash") ?? "",
    type: (url.searchParams.get("type") ?? "magiclink") as EmailOtpType,
  });
  return NextResponse.redirect(onSameHost(request, error ? "/login?error=link_invalid" : next));
}
