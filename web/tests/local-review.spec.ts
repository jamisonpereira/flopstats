import { expect, test } from "@playwright/test";
import { localReviewBypass } from "../lib/local-review";

// Skipping login is only for `npm run review:local` on this machine: dev server plus an explicit opt-in.
test("local review bypass needs both the dev server and REVIEW_LOCAL=1", () => {
  expect(localReviewBypass({ NODE_ENV: "development", REVIEW_LOCAL: "1" })).toBe(true);
  expect(localReviewBypass({ NODE_ENV: "development" })).toBe(false);
  expect(localReviewBypass({ NODE_ENV: "development", REVIEW_LOCAL: "true" })).toBe(false);
  expect(localReviewBypass({ NODE_ENV: "production", REVIEW_LOCAL: "1" })).toBe(false);
  expect(localReviewBypass({ NODE_ENV: "test", REVIEW_LOCAL: "1" })).toBe(false);
  expect(localReviewBypass({ REVIEW_LOCAL: "1" })).toBe(false);
});
