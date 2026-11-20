const BASE = "http://flopstats.invalid";

/** Only same-site relative paths may be redirect targets ("/\evil.com" and friends are not). */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || /[\\\u0000-\u001f\u007f]/.test(next)) return "/review";
  try {
    const url = new URL(next, BASE);
    if (url.origin !== BASE) return "/review";
    return url.pathname + url.search;
  } catch {
    return "/review";
  }
}

/** Absolute URL on the host the browser actually used (dev servers report "localhost"
 *  even when the browser came in on 127.0.0.1, and cookies are per host). */
export function onSameHost(request: Request, path: string): URL {
  const url = new URL(request.url);
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  if (host) url.host = host;
  return new URL(path, url.origin);
}
