import { expect, test } from "@playwright/test";
import { safeNext } from "../lib/paths";

// final review I1: post-login redirects must stay on this site.
test("safeNext only allows same-site paths", () => {
  for (const bad of ["/\\evil.com", "/\\/evil.com", "//evil.com", "https://evil.com", "/\tevil", "\\evil.com", "", null, undefined]) {
    expect(safeNext(bad as string | null | undefined), String(bad)).toBe("/review");
  }
  expect(safeNext("/review/12")).toBe("/review/12");
  expect(safeNext("/review?tab=spot")).toBe("/review?tab=spot");
});
