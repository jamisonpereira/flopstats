import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { onSameHost } from "@/lib/paths";

export const config = { matcher: ["/review/:path*", "/review"], runtime: "nodejs" };

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (list) => {
        list.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });
  const { data: { user } } = await supabase.auth.getUser();
  const redirectTo = (path: string) => {
    const r = NextResponse.redirect(onSameHost(request, path));
    response.cookies.getAll().forEach((c) => r.cookies.set(c));  // keep any refreshed session
    return r;
  };
  if (!user) {
    return redirectTo(`/login?next=${encodeURIComponent(request.nextUrl.pathname + request.nextUrl.search)}`);
  }
  const { data: isAdmin } = await supabase.rpc("is_admin");
  if (!isAdmin) return redirectTo("/login?error=not_admin");
  return response;
}
