import { test as base, expect, type Page } from "@playwright/test";

const backend = "http://127.0.0.1:8018/api/v1";

// Each test owns its browser context and only the sessions it creates.
const test = base.extend<{ cleanup: void }>({
  cleanup: [
    async ({ page, request }, runTest) => {
      const sessions = new Set<string>();
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("response", async (response) => {
        if (
          response.url() === `${backend}/sessions` &&
          response.request().method() === "POST" &&
          response.ok()
        ) {
          sessions.add((await response.json()).session_id);
        }
      });
      try {
        await runTest();
      } finally {
        await page.context().setOffline(false);
        for (const id of sessions) {
          const result = await request.delete(`${backend}/sessions/${id}`);
          expect([204, 404]).toContain(result.status());
        }
        expect(errors, "Unhandled browser exceptions").toEqual([]);
      }
    },
    { auto: true },
  ],
});

async function start(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    /Beyond the score/,
  );
  await page
    .getByRole("link", { name: "Enter the studio", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create demo session", exact: true })
    .click();
  const connection = page.getByRole("region", {
    name: "Match connection",
    exact: true,
  });
  await expect(connection).toContainText("Connected to server");
  await expect(
    page.getByRole("button", { name: "Play clip", exact: true }),
  ).toBeEnabled();
  return (await connection.locator("code").innerText()).trim();
}

test("demo journey: real playback, inclusive climax, evidence and bilingual view switching", async ({
  page,
  request,
}, testInfo) => {
  const id = await start(page);
  const clock = page.getByRole("slider", { name: "Match clock", exact: true });
  await expect(clock).toHaveValue("3660");
  await page.getByRole("button", { name: "Play clip", exact: true }).click();
  await expect
    .poll(async () => Number(await clock.inputValue()))
    .toBeGreaterThan(3660);
  await page.getByRole("button", { name: "Pause clip", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Play clip", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Revisit 62:00", exact: true })
    .click();
  await expect(clock).toHaveValue("3720");
  await expect(
    page.getByRole("heading", { name: "A familiar weakness, exposed again." }),
  ).toBeVisible();
  const state = await (await request.get(`${backend}/sessions/${id}`)).json();
  expect(state.state.score).toEqual([1, 1]);

  await expect(clock).toBeEnabled();
  await clock.focus();
  await clock.press("ArrowLeft");
  await expect(clock).toHaveValue("3719");
  await expect(
    page.getByRole("heading", { name: "The next moment is still to come." }),
  ).toBeVisible();
  const before = await (
    await request.get(`${backend}/sessions/${id}/context`)
  ).json();
  expect(before.climax).toBeNull();
  expect(before.preview).toBeNull();
  expect(
    (await (await request.get(`${backend}/sessions/${id}`)).json()).state.score,
  ).toEqual([1, 0]);
  await expect(
    page.locator(".timeline").getByRole("button", { name: /^62:00 Goal/ }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Revisit 62:00", exact: true })
    .click();
  await expect(clock).toHaveValue("3720");
  await expect(
    page.getByRole("button", { name: /^Pass accuracy .*Inspect evidence/ }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: /^Pass accuracy .*Inspect evidence/ })
    .click();
  const trail = page.getByRole("complementary", {
    name: "Evidence trail",
    exact: true,
  });
  await expect(trail.getByRole("status")).toContainText(
    "source actions resolved",
  );
  await trail.getByRole("button", { name: /Pass / }).first().click();
  await expect(page.locator(".evidence-grid")).toContainText("Event ID");
  await page
    .getByRole("button", { name: "Pattern ledger", exact: true })
    .click();
  await page.getByRole("button", { name: /^Matchday 6 / }).click();
  await expect(trail.getByRole("status")).toContainText(
    "4 source actions resolved",
  );
  await expect(trail).toContainText("Historical fixture");
  await expect(clock).toHaveValue("3720");
  await page.getByRole("button", { name: "Fan", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Match metrics", exact: true }),
  ).toHaveCount(0);
  await expect(clock).toHaveValue("3720");
  await page
    .getByRole("combobox", { name: "Language", exact: true })
    .selectOption("es");
  await expect(
    page.getByRole("heading", { name: "Cada acción tiene una historia." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Analista", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Métricas del partido", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("slider", { name: "Reloj del partido", exact: true }),
  ).toHaveValue("3720");
  await testInfo.attach("climax", {
    body: await page.screenshot({ fullPage: false }),
    contentType: "image/png",
  });
});

test("network interruption retains the cut and recovers without duplicate visible actions", async ({
  page,
}) => {
  await start(page);
  const clock = page.getByRole("slider", { name: "Match clock", exact: true });
  const actions = page.locator(".timeline button[aria-pressed]");
  const confirmedActions = await actions.allTextContents();
  const count = confirmedActions.length;
  await page.context().setOffline(true);
  const connection = page.getByRole("region", {
    name: "Match connection",
    exact: true,
  });
  await expect(connection).toContainText("Reconnecting");
  await expect(connection).toContainText("Keeping the last confirmed view");
  await expect(clock).toHaveValue("3660");
  await expect(clock).toBeDisabled();
  await page.context().setOffline(false);
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  await expect(connection).toContainText("Connected to server");
  await expect(clock).toBeEnabled();
  await expect(page.locator(".timeline button[aria-pressed]")).toHaveCount(
    count,
  );
  await expect(clock).toHaveValue("3660");
  expect(await actions.allTextContents()).toEqual(confirmedActions);
});

test("deleted session is terminal and a fresh demo restores the studio", async ({
  page,
  request,
}) => {
  const id = await start(page);
  expect((await request.delete(`${backend}/sessions/${id}`)).status()).toBe(
    204,
  );
  const connection = page.getByRole("region", {
    name: "Match connection",
    exact: true,
  });
  await expect(connection).toContainText("Session closed");
  await expect(connection).toContainText(
    "This temporary session is no longer available",
  );
  await expect(
    page.getByRole("button", { name: "Reconnect", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Create demo session", exact: true })
    .click();
  await expect(connection).toContainText("Connected to server");
  await expect(
    page.getByRole("slider", { name: "Match clock", exact: true }),
  ).toHaveValue("3660");
  expect(await connection.locator("code").innerText()).not.toBe(id);
});

test("homepage assets, responsive navigation and local rehearsal work without a session", async ({
  page,
  isMobile,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("img", { name: "Fictional athletes. A new perspective." }),
  ).toBeVisible();
  expect(
    await page
      .locator("img")
      .evaluateAll((images) =>
        images.every(
          (image) =>
            (image as HTMLImageElement).complete &&
            (image as HTMLImageElement).naturalWidth > 0,
        ),
      ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  if (isMobile) {
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Close navigation", exact: true }),
    ).toHaveAttribute("aria-expanded", "true");
  }
  await page.getByRole("link", { name: "The approach", exact: true }).click();
  await page.getByRole("button", { name: "02 Historian", exact: true }).click();
  await expect(
    page.getByText("Connects the moment to season history.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open local rehearsal", exact: true })
    .click();
  await expect(
    page.getByText("Local rehearsal", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("link", { name: "TactiX home", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    /Beyond the score/,
  );
});
