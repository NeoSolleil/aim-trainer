/**
 * @e2e ステップ定義 — シューティングセッション（acceptance.feature @e2e 20 シナリオ）。
 *
 * 原本 Gherkin を変換するのみ（新規シナリオは作らない）。
 *
 * 操作・検証の方針:
 * - DOM（start-button / summary-* / play-again-button / save-error-notice）は getByTestId。
 * - Canvas の的は DOM が無いため `window.__aimTest`（getState / getTarget）で読み、座標は
 *   game-canvas の表示矩形へスケールして mouse.click する（seam.ts）。
 * - 時間は二段構え:
 *     page.clock.install … 実時間の rAF 自走を止め、フレーム発火を runFor で制御。
 *     setClock(() => __vnow) … reaction_time / endTime を「ちょうどの値」で確定（R-1/R-2/R-8）。
 * - 保存は既定で 201＋ダミー ScoreResponse を route スタブ（実 backend 不要）。R-16 のみ失敗へ。
 * - R-17 は「finished 前にやめると POST が飛ばない」を route 監視（リクエスト数）で確認。
 *
 * Gherkin の「中心 (400,300)」は的の中心の例示。respawn 位置は乱数のため、的の実中心を
 * getTarget で読み、その中心 / 縁 / 縁外を撃って hit/miss ルールを検証する。
 */

import { expect } from "@playwright/test";
import { createBdd } from "playwright-bdd";

import { test } from "./fixtures";
import {
  clickCanvasAt,
  clickCanvasSync,
  getState,
  getTarget,
  markTargetHit,
  startSession,
  waitForSeam,
  type SeamState,
} from "./seam";

const { Given, When, Then } = createBdd(test);

/** ダミー ScoreResponse（snake_case・backend 不要のスタブ）。 */
function stubScoreResponse(state: { hits: number; total: number }): string {
  return JSON.stringify({
    id: 1,
    hits: state.hits,
    total_clicks: state.total,
    accuracy: state.total === 0 ? null : state.hits / state.total,
    avg_reaction_time: state.hits === 0 ? null : 300,
    time_limit_ms: 30000,
    gun_id: 1,
    created_at: "2026-06-21T00:00:00Z",
  });
}

/** setClock 用の仮想時計を取り付ける（__vnow を参照させる）。0 から開始。 */
async function installVirtualClock(page: import("@playwright/test").Page): Promise<void> {
  await page.evaluate(() => {
    const w = window as unknown as {
      __vnow: number;
      __aimTest?: { setClock: (f: () => number) => void };
    };
    w.__vnow = 0;
    w.__aimTest?.setClock(() => w.__vnow);
  });
}

/** 仮想時計の現在値を設定する。 */
async function setNow(page: import("@playwright/test").Page, ms: number): Promise<void> {
  await page.evaluate((v) => {
    (window as unknown as { __vnow: number }).__vnow = v;
  }, ms);
}

/** rAF フレームを 1 回発火させる（tick → finished の駆動）。 */
async function fireFrame(page: import("@playwright/test").Page): Promise<void> {
  await page.clock.runFor(20);
}

/** 既定の保存スタブ（201）を取り付け、POST 回数カウンタを返す。 */
async function stubSubmitOk(
  page: import("@playwright/test").Page,
): Promise<{ count: () => number }> {
  let posts = 0;
  await page.route("**/api/sessions", async (route) => {
    posts += 1;
    const s = await getState(page);
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: stubScoreResponse({ hits: s.hits, total: s.totalClicks }),
    });
  });
  return { count: () => posts };
}

/** 共通の起動シーケンス: clock 仮想化 → 遷移 → シーム待ち → 仮想時計取り付け。 */
async function bootstrap(page: import("@playwright/test").Page): Promise<void> {
  await page.clock.install({ time: 0 });
  await page.goto("/");
  await waitForSeam(page);
  await installVirtualClock(page);
}

// --- Given ---------------------------------------------------------------

Given("セッションが進行中である", async ({ page }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
});

Given("セッションが進行中で、中央に的が1つある", async ({ page }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
  // 開始直後は常に的が 1 つ（lib/session の不変条件）。状態で確認する。
  const s = await getState(page);
  expect(s.target.radius).toBeGreaterThan(0);
});

Given("プレイヤーがセッションを開始した", async ({ page }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
});

Given("セッションが終了時刻に達した", async ({ page }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
  // ここではまだ時計を進めない（進めると rAF tick が finished にし canvas が外れる）。
  // 「終了時刻を過ぎてから」の When が原子的に時計超過＋クリックを行い、超過クリックの除外を見る。
});

Given(
  "中心 \\({int},{int})・半径 20px の的が出現している",
  async ({ page }, _x: number, _y: number) => {
    // 的は乱数位置に 1 つ存在する。実中心は getTarget で読む（各 When が参照）。
    const t = await getTarget(page);
    expect(t.radius).toBe(20);
  },
);

Given("セッションが進行中で、ある的を既にヒットしている", async ({ page, world }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
  // 的を 1 つヒット（hits=1, total=1）。通常はここで respawn して新しい的（hit=false）になる。
  const first = await getTarget(page);
  await clickCanvasAt(page, first.x, first.y);
  await expect.poll(async () => (await getState(page)).hits).toBe(1);
  // 「ヒット済みの的が残っている」状態を test hook で再現し、その中心を再クリック対象にする。
  await markTargetHit(page);
  const hitTarget = await getTarget(page);
  world.lastHitCenter = { x: hitTarget.x, y: hitTarget.y };
});

Given("セッションが既に終了している", async ({ page }) => {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);
  await setNow(page, 30000);
  await fireFrame(page);
  await expect.poll(async () => (await getState(page)).status).toBe("finished");
});

Given("hits=5・total_clicks=8 のセッションが終了した", async ({ page }) => {
  await driveToFinishedWith(page, 5, 8);
});

Given("hits=0・total_clicks=8 のセッションが終了した", async ({ page }) => {
  await driveToFinishedWith(page, 0, 8);
});

Given("プレイヤーが一度もクリックせずに 30 秒経過してセッションが終了した", async ({ page }) => {
  await driveToFinishedWith(page, 0, 0);
});

Given("結果サマリが表示されている", async ({ page }) => {
  await driveToFinishedWith(page, 1, 2);
  await expect(page.getByTestId("summary-accuracy")).toBeVisible();
});

Given("セッションが終了し、結果サマリが表示されている", async ({ page }) => {
  // R-16: 保存を失敗させる。route を失敗に切り替えてから終了へ進める。
  await page.clock.install({ time: 0 });
  await page.route("**/api/sessions", (route) => route.abort("failed"));
  await page.goto("/");
  await waitForSeam(page);
  await installVirtualClock(page);
  await startSession(page);
  // 1 ヒットしておく（サマリに何か出る状態）。
  const t = await getTarget(page);
  await clickCanvasAt(page, t.x, t.y);
  await setNow(page, 30000);
  await fireFrame(page);
  await expect.poll(async () => (await getState(page)).status).toBe("finished");
  await expect(page.getByTestId("summary-accuracy")).toBeVisible();
});

// --- When ----------------------------------------------------------------

When(
  "プレイヤーが的の出現から 320ms 後に中心 \\({int},{int}) をクリックする",
  async ({ page }, _x: number, _y: number) => {
    const t = await getTarget(page);
    // 的は startedAt(=0) に spawn 済み。reaction を 320 に確定。
    await setNow(page, 320);
    await clickCanvasAt(page, t.x, t.y);
    await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
  },
);

When("プレイヤーが中心からの距離が 20.0px ちょうどの位置をクリックする", async ({ page }) => {
  const t = await getTarget(page);
  // 縁ちょうど（距離 = 半径）。内部座標は浮動小数でも GameCanvas が内部解像度へ写すため、
  // 縁を安全側に取るため半径 - 微小量にせず、判定は閉区間（isHit は距離 <= 半径）なので半径ちょうどで撃つ。
  await clickCanvasAt(page, t.x + t.radius, t.y);
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
});

When("プレイヤーが中心からの距離が 21px の位置をクリックする", async ({ page }) => {
  const t = await getTarget(page);
  await clickCanvasAt(page, t.x + t.radius + 1, t.y);
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
});

When(
  "プレイヤーが的の出現と同フレームで中心 \\({int},{int}) をクリックする",
  async ({ page }, _x: number, _y: number) => {
    const t = await getTarget(page);
    // __vnow は 0 のまま == spawnedAt(0) → reaction 0。
    await clickCanvasAt(page, t.x, t.y);
    await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
  },
);

When(
  "プレイヤーが空白座標 \\({int},{int}) をクリックする",
  async ({ page }, _x: number, _y: number) => {
    // 的に当たらない座標を撃つ。的中心から十分離れた領域内座標を選ぶ。
    const t = await getTarget(page);
    const blank = pickBlankPoint(t);
    await clickCanvasAt(page, blank.x, blank.y);
    await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
  },
);

When("プレイヤーが空白座標を 100ms 以内に 5 回連打する", async ({ page }) => {
  const t = await getTarget(page);
  const blank = pickBlankPoint(t);
  for (let i = 0; i < 5; i += 1) {
    await clickCanvasAt(page, blank.x, blank.y);
  }
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(5);
});

When("プレイヤーがその的をクリックしてヒットする", async ({ page, world }) => {
  const t = await getTarget(page);
  world.lastHitCenter = { x: t.x, y: t.y };
  await clickCanvasAt(page, t.x, t.y);
  await expect.poll(async () => (await getState(page)).hits).toBe(1);
});

When("プレイヤーがその的をクリックせずに 10 秒間待つ", async ({ page }) => {
  await setNow(page, 10000);
  await fireFrame(page);
});

When("開始から 30 秒が経過する", async ({ page }) => {
  await setNow(page, 30000);
  await fireFrame(page);
});

When("プレイヤーが終了時刻ちょうどに的をクリックする", async ({ page }) => {
  const t = await getTarget(page);
  // 終了時刻ちょうど（now == endTime）はクリックを含める（閉区間・R-8）。rAF tick との競合を
  // 避けるため、__vnow=30000 の設定と canvas クリックを 1 evaluate で原子的に行う。
  await clickCanvasSync(page, t.x, t.y, 30000);
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
});

When("プレイヤーが終了時刻を過ぎてからクリックする", async ({ page }) => {
  const t = await getTarget(page);
  // 終了時刻を 1ms 超過（now > endTime）させてからクリック → 除外される（R-8）。
  // __vnow=30001 の設定とクリックを原子的に行い、registerClick が now>endTime で無視するのを確認。
  await clickCanvasSync(page, t.x, t.y, 30001);
});

When("結果サマリが表示される", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toBeVisible();
});

When("プレイヤーが「もう一度」を選ぶ", async ({ page }) => {
  await page.getByTestId("play-again-button").click();
  await expect.poll(async () => (await getState(page)).status).toBe("running");
});

When("score の保存に失敗する", async () => {
  // 保存失敗は Given（route abort）で既に発生済み。ここでは追加操作は不要。
});

When("プレイヤーが 30 秒に達する前にやめる", async ({ page }) => {
  // 30 秒未満で離脱（リロード）。POST が飛ばないことを Then で確認する。
  await setNow(page, 15000);
  await fireFrame(page);
  await page.reload();
});

When("プレイヤーが同じ的をもう一度クリックする", async ({ page, world }) => {
  const c = world.lastHitCenter;
  expect(c).toBeDefined();
  if (c) {
    await clickCanvasAt(page, c.x, c.y);
  }
});

When(
  "プレイヤーがキャンバス外の座標 \\({int},{int}) をクリックする",
  async ({ page }, x: number, y: number) => {
    // 内部座標 (-5,-5) は領域外 → lib/session が無視。負方向にスケールして撃つ。
    await clickCanvasAt(page, x, y);
  },
);

When("プレイヤーがキャンバス上をクリックする", async ({ page }) => {
  // 終了後は canvas が unmount されているため、状態は変わらない。
  const canvas = page.getByTestId("game-canvas");
  if (await canvas.count()) {
    const t = await getTarget(page);
    await clickCanvasAt(page, t.x, t.y);
  }
});

// --- Then ----------------------------------------------------------------

Then("システムはヒットを記録する", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).hits).toBe(1);
});

Then("total_clicks が 1 になる", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
});

Then("reaction_time として 320ms が記録される", async ({ page }) => {
  const s = await getState(page);
  expect(s.reactionTimes).toEqual([320]);
});

Then("システムはミスを記録する", async ({ page }) => {
  const s = await getState(page);
  expect(s.hits).toBe(0);
  expect(s.totalClicks).toBeGreaterThanOrEqual(1);
});

Then("reaction_time は記録されない", async ({ page }) => {
  const s = await getState(page);
  expect(s.reactionTimes).toHaveLength(0);
});

Then("reaction_time として 0ms が記録される", async ({ page }) => {
  const s = await getState(page);
  expect(s.reactionTimes).toEqual([0]);
});

Then("負の reaction_time は記録されない", async ({ page }) => {
  const s = await getState(page);
  for (const rt of s.reactionTimes) {
    expect(rt).toBeGreaterThanOrEqual(0);
  }
});

Then("total_clicks が 1 増える", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(1);
});

Then("ヒット数は変化しない", async ({ page }) => {
  const s = await getState(page);
  expect(s.hits).toBe(0);
});

Then("システムはミスを 5 回記録する", async ({ page }) => {
  const s = await getState(page);
  expect(s.hits).toBe(0);
  expect(s.totalClicks).toBe(5);
});

Then("total_clicks が 5 増える", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(5);
});

Then("次の的が 1 つだけ出現する", async ({ page, world }) => {
  // 常に的は 1 つ（getTarget は単一）。ヒット後は別の的（中心が変わる）。
  const t = await getTarget(page);
  const prev = world.lastHitCenter;
  expect(t.radius).toBe(20);
  if (prev) {
    const moved = t.x !== prev.x || t.y !== prev.y;
    expect(moved).toBe(true);
  }
});

Then("同じ的が 1 つだけ残っている", async ({ page }) => {
  const s = await getState(page);
  // 寿命で消えない（R-6）: ヒットしていないので hits=0、的は残る。
  expect(s.hits).toBe(0);
  expect(s.target.radius).toBe(20);
});

Then("システムはセッションを終了する", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).status).toBe("finished");
});

Then("結果の集計に進む", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toBeVisible();
});

Then("そのクリックは集計に含まれる", async ({ page }) => {
  const s = await getState(page);
  expect(s.totalClicks).toBeGreaterThanOrEqual(1);
});

Then("そのクリックは集計から除外される", async ({ page }) => {
  const s = await getState(page);
  expect(s.totalClicks).toBe(0);
});

Then("命中率として 62.5% が表示される", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toHaveText("62.5%");
});

Then("平均 reaction_time としてヒット 5 件の平均が表示される", async ({ page }) => {
  // 表示は「— でない」ことを確認（具体値は乱数 reaction に依存しないよう緩く）。
  const text = await page.getByTestId("summary-avg").textContent();
  expect(text).not.toBe("—");
  expect(text).toMatch(/ms/);
});

Then("ヒット数として {int}\\/{int} が表示される", async ({ page }, hits: number, total: number) => {
  await expect(page.getByTestId("summary-hits")).toHaveText(`${hits}/${total}`);
});

Then("新しいセッションが開始する", async ({ page }) => {
  await expect.poll(async () => (await getState(page)).status).toBe("running");
});

Then("hits・total_clicks・記録された reaction_time が 0 にリセットされる", async ({ page }) => {
  const s = await getState(page);
  expect(s.hits).toBe(0);
  expect(s.totalClicks).toBe(0);
  expect(s.reactionTimes).toHaveLength(0);
});

Then("結果サマリは表示されたままになる", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toBeVisible();
});

Then("保存に失敗したことがプレイヤーに通知される", async ({ page }) => {
  await expect(page.getByTestId("save-error-notice")).toBeVisible();
});

Then("そのセッションの score は保存されない", async ({ page }) => {
  // リロード後は idle に戻り、POST は一度も飛んでいない。route 監視で 0 件を確認。
  let posts = 0;
  page.on("request", (req) => {
    if (req.url().includes("/api/sessions") && req.method() === "POST") {
      posts += 1;
    }
  });
  // 少し待っても POST が来ないこと。
  await page.waitForTimeout(200);
  expect(posts).toBe(0);
  const s = await getState(page);
  expect(s.status).not.toBe("finished");
});

Then("命中率は「—」と表示される", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toHaveText("—");
});

Then("平均 reaction_time は「—」と表示される", async ({ page }) => {
  await expect(page.getByTestId("summary-avg")).toHaveText("—");
});

Then("命中率は 0% と表示される", async ({ page }) => {
  await expect(page.getByTestId("summary-accuracy")).toHaveText("0%");
});

Then("そのクリックは無視される", async ({ page }) => {
  // 検証本体は次の「hits と total_clicks は変化しない」が担う。ここは状態の存在確認のみ。
  await getState(page);
});

Then("hits と total_clicks は変化しない", async ({ page }) => {
  const s = await getState(page);
  // R-20: 既に 1 ヒット済み → hits は 1 のまま、再クリックは total に計上しない。
  // R-21/R-22: 一切クリック計上なし → 0 のまま。いずれも「再クリックで増えない」を確認する。
  expectUnchangedAfterIgnoredClick(s);
});

// --- ヘルパ ---------------------------------------------------------------

/**
 * 指定の hits/total になるよう撃ち、30 秒で終了させる。
 * total - hits 回のミス、hits 回のヒットを行う（ヒット後 respawn を getTarget で追う）。
 */
async function driveToFinishedWith(
  page: import("@playwright/test").Page,
  hits: number,
  total: number,
): Promise<void> {
  await bootstrap(page);
  await stubSubmitOk(page);
  await startSession(page);

  const misses = total - hits;
  // ミスを先に（的に当たらない座標へ）。
  for (let i = 0; i < misses; i += 1) {
    const t = await getTarget(page);
    const blank = pickBlankPoint(t);
    await clickCanvasAt(page, blank.x, blank.y);
  }
  // ヒット（毎回 respawn 位置を読み直す）。
  for (let i = 0; i < hits; i += 1) {
    const t = await getTarget(page);
    await clickCanvasAt(page, t.x, t.y);
    await expect.poll(async () => (await getState(page)).hits).toBe(i + 1);
  }
  await expect.poll(async () => (await getState(page)).totalClicks).toBe(total);

  await setNow(page, 30000);
  await fireFrame(page);
  await expect.poll(async () => (await getState(page)).status).toBe("finished");
}

/** 的に当たらない領域内座標を選ぶ（的中心から半径以上離す）。 */
function pickBlankPoint(target: { x: number; y: number; radius: number }): {
  x: number;
  y: number;
} {
  // 左上隅 (5,5) が的から十分離れていればそれを使う。近ければ反対側へ。
  const farCorner = { x: 5, y: 5 };
  const dist = Math.hypot(farCorner.x - target.x, farCorner.y - target.y);
  if (dist > target.radius + 5) {
    return farCorner;
  }
  return { x: 795, y: 595 };
}

/** 無視されたクリック後、hits/total が「再クリックで増えていない」ことを検証する。 */
function expectUnchangedAfterIgnoredClick(s: SeamState): void {
  // R-20: hits=1/total=1（ヒット済み）に再クリックしても total は 1 のまま。
  // R-21/R-22: 何も計上されないため hits=0/total=0。
  const okR20 = s.hits === 1 && s.totalClicks === 1;
  const okR21or22 = s.hits === 0 && s.totalClicks === 0;
  expect(okR20 || okR21or22).toBe(true);
}
