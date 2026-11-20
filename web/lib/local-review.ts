/** Skip login for the review screen: only under `next dev` and only with REVIEW_LOCAL=1 set.
 *  Then the server uses the service key instead of the reviewer's session. A production build
 *  (NODE_ENV=production) never takes this path. Run it with `npm run review:local`, which binds
 *  the dev server to 127.0.0.1 so no one else on the network can reach it. */
export function localReviewBypass(env: Record<string, string | undefined> = process.env): boolean {
  return env.NODE_ENV === "development" && env.REVIEW_LOCAL === "1";
}
