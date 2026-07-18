import { expect, test } from "@playwright/test";

test("resume evidence opens its PDF source highlight", async ({ page }) => {
  await page.goto("/#/resumes/res2");
  await expect(page.getByRole("heading", { name: "Ananya Subramanian" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Resume page 1" })).toBeVisible();

  await page.getByRole("button", { name: "Show details for Full name" }).click();
  await expect(page.getByText("high", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Locate on PDF" }).first().click();
  await expect(page.getByRole("button", { name: "Show Full Name source" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Highlighted source for Full Name" })).toBeVisible();
  await page.getByRole("button", { name: "All" }).click();
  await expect(page.getByRole("button", { name: /Show Python/ })).toBeVisible();
  await page.getByRole("button", { name: "Focus" }).click();

  const divider = page.getByRole("separator", { name: "Resize resume panels" });
  const before = Number(await divider.getAttribute("aria-valuenow"));
  const box = await divider.boundingBox();
  expect(box).not.toBeNull();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + 50);
    await page.mouse.down();
    await page.mouse.move(box.x + 70, box.y + 50, { steps: 5 });
    await page.mouse.up();
  }
  const after = Number(await divider.getAttribute("aria-valuenow"));
  expect(after).toBeGreaterThan(before);

  await page.screenshot({ path: "test-results/resume-provenance.png", fullPage: true });
});

test("candidate chat returns a routed answer with linked sources", async ({ page }) => {
  await page.goto("/#/jds/backend_dev");
  await expect(page.getByRole("heading", { name: "Candidate pool" })).toBeVisible();
  await page.getByRole("tab", { name: "Chat" }).click();
  await page.getByRole("textbox", { name: "Message candidate chat" }).fill("How many candidates have CGPA above 8?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText(/2 candidates matched/)).toBeVisible();
  await expect(page.getByText("structured", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Rohit Verma" }).click();
  await expect(page).toHaveURL(/#\/resumes\/sample2$/);
  await expect(page.getByRole("heading", { name: "Rohit Verma" })).toBeVisible();
});

test("JD workspace keeps description and chat left of the candidate pool", async ({ page }) => {
  await page.goto("/#/jds/backend_dev");
  await expect(page.getByRole("heading", { name: "Backend Developer" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Candidate pool" })).toBeVisible();
  await expect(page.getByText("Required skills", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Chat" }).click();
  await expect(page.getByRole("textbox", { name: "Message candidate chat" })).toBeVisible();
  await page.getByRole("tab", { name: "Description" }).click();
  await expect(page.getByText("Preferred skills", { exact: true })).toBeVisible();
});

test("mobile resume detail has no body-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#/resumes/res2");
  await expect(page.getByRole("heading", { name: "Ananya Subramanian" })).toBeVisible();
  const sizes = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.clientWidth);
});
