import { redirect } from "next/navigation";
import { siteUrl, userClient } from "@/lib/supabase";

async function sendLink(formData: FormData) {
  "use server";
  const email = String(formData.get("email") ?? "").trim();
  const next = String(formData.get("next") ?? "/review");
  const supabase = await userClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${siteUrl()}/auth/callback?next=${encodeURIComponent(next)}`, shouldCreateUser: true },
  });
  redirect(error ? "/login?error=send_failed" : "/login?sent=1");
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  return (
    <main className="narrow">
      <h1>Flopstats review</h1>
      {sp.error === "not_admin" && <p className="error">This email is not on the review list.</p>}
      {sp.error === "send_failed" && <p className="error">Could not send the sign-in link. Try again.</p>}
      {sp.error === "link_invalid" && <p className="error">That sign-in link is invalid or expired.</p>}
      {sp.sent ? (
        <p>Check your email for a sign-in link.</p>
      ) : (
        <form action={sendLink} className="stack">
          <input type="hidden" name="next" value={sp.next ?? "/review"} />
          <label>
            Email <input type="email" name="email" required autoComplete="email" />
          </label>
          <button type="submit">Send sign-in link</button>
        </form>
      )}
    </main>
  );
}
