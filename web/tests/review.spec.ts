import { expect, test } from "@playwright/test";
import { ADMIN, OUTSIDER, magicLinkPath, query, seed, type Seed } from "./seed";

let s: Seed;
test.beforeEach(async () => {
  s = await seed();
});

test("non-admin is redirected from /review", async ({ page }) => {
  await page.goto("/review");
  await expect(page).toHaveURL(/\/login/);
  await page.goto(await magicLinkPath(OUTSIDER));
  await page.goto("/review");
  await expect(page).toHaveURL(/\/login\?error=not_admin/);
  await expect(page.getByText("not on the review list")).toBeVisible();
});

test("confirm resolves item and sets incident confirmed", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN));
  await expect(page).toHaveURL(/\/review$/);
  await expect(page.getByText("Brentford v Nottingham Forest")).toBeVisible();
  await page.locator(".items").getByRole("link", { name: /flop_verdict/ }).click();
  await expect(page).toHaveURL(new RegExp(`/review/${s.verdictItem}$`));
  await expect(page.locator("video")).toHaveAttribute("src", /token=/);
  await page.getByRole("button", { name: /Confirm/ }).click();
  await expect(page).not.toHaveURL(new RegExp(`/review/${s.verdictItem}$`));
  const [inc] = await query<{ status: string }>("select status from incidents where id = $1", [s.reviewIncident]);
  expect(inc.status).toBe("confirmed");
  const [item] = await query<{ status: string }>("select status from review_items where id = $1", [s.verdictItem]);
  expect(item.status).toBe("resolved");
  const reviews = await query<{ decision: string; item_id: string }>("select decision, item_id from reviews");
  expect(reviews.map((r) => [r.decision, Number(r.item_id)])).toEqual([["confirm", s.verdictItem]]);
});

test("keyboard: n rejects", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, `/review/${s.verdictItem}`));
  await expect(page.getByRole("button", { name: /Confirm/ })).toBeVisible();
  await page.keyboard.press("n");
  await expect(page).not.toHaveURL(new RegExp(`/review/${s.verdictItem}$`));
  const [inc] = await query<{ status: string }>("select status from incidents where id = $1", [s.reviewIncident]);
  expect(inc.status).toBe("rejected");
});

test("set player from lineup guess updates incident_players and closes flop_player item", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, `/review/${s.playerItem}`));
  await page.getByRole("button", { name: /#7 Home Seven/ }).click();
  await expect(page).not.toHaveURL(new RegExp(`/review/${s.playerItem}$`));
  const [p] = await query<{ player_id: number }>("select player_id from incident_players where incident_id = $1 and role = 'flopper'", [s.playerIncident]);
  expect(Number(p.player_id)).toBe(s.homeSeven);
  const [item] = await query<{ status: string }>("select status from review_items where id = $1", [s.playerItem]);
  expect(item.status).toBe("resolved");
  const [r] = await query<{ decision: string }>("select decision from reviews");
  expect(r.decision).toBe("set_player");
});

test("spot check tab shows confirmed incidents only", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, "/review?tab=spot"));
  const rows = page.locator("[data-spot-incident]");
  await expect(rows.first()).toBeVisible();
  const ids = (await rows.evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-spot-incident")))));
  expect(ids.length).toBeGreaterThan(0);
  for (const id of ids) expect(s.confirmedIncidents).toContain(id);
  expect(ids).not.toContain(s.rejectedIncident);
  expect(ids).not.toContain(s.reviewIncident);
});

// --- final review I7/I8 -------------------------------------------------------------------

test("fixing the player on a verdict item leaves the verdict open", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, `/review/${s.verdictItem}`));
  await page.getByText("Whole lineup").click();
  await page.getByRole("button", { name: /#7 Home Seven/ }).click();
  await expect(page.getByText(/still needs a verdict/)).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/review/${s.verdictItem}(\\?.*)?$`));
  const [p] = await query<{ player_id: string }>("select player_id from incident_players where incident_id = $1 and role = 'flopper'", [s.reviewIncident]);
  expect(Number(p.player_id)).toBe(s.homeSeven);  // the fix was saved...
  const [item] = await query<{ status: string }>("select status from review_items where id = $1", [s.verdictItem]);
  expect(item.status).toBe("open");  // ...but the verdict is still owed
  const [inc] = await query<{ status: string }>("select status from incidents where id = $1", [s.reviewIncident]);
  expect(inc.status).toBe("review");
});

test("a verdict key on a who-is-this item doesn't close it", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, `/review/${s.playerItem}`));
  await expect(page.getByRole("button", { name: /#7 Home Seven/ })).toBeVisible();
  await page.keyboard.press("y");
  await expect(page.getByText(/still needs/)).toBeVisible();
  const [item] = await query<{ status: string }>("select status from review_items where id = $1", [s.playerItem]);
  expect(item.status).toBe("open");
});

test("an unknown-team flopper can be named from either lineup", async ({ page }) => {
  await page.goto(await magicLinkPath(ADMIN, `/review/${s.noTeamItem}`));
  await page.getByText("Whole lineup").click();
  await page.getByRole("button", { name: /#11 Away Eleven/ }).click();
  await expect(page).not.toHaveURL(new RegExp(`/review/${s.noTeamItem}$`));
  const rows = await query<{ player_id: string; team_id: string }>("select player_id, team_id from incident_players where incident_id = $1 and role = 'flopper'", [s.noTeamIncident]);
  expect(rows.map((r) => [Number(r.player_id), Number(r.team_id)])).toEqual([[s.awayEleven, s.away]]);
  const [inc] = await query<{ team_id: string }>("select team_id from incidents where id = $1", [s.noTeamIncident]);
  expect(Number(inc.team_id)).toBe(s.away);
  const [item] = await query<{ status: string }>("select status from review_items where id = $1", [s.noTeamItem]);
  expect(item.status).toBe("resolved");
});
