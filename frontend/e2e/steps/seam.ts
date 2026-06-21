/**
 * E2E ヘルパ — `window.__aimTest` シームと Canvas クリックのユーティリティ。
 *
 * Canvas は DOM 要素を持たないため、的座標・状態はシーム（getTarget / getState）で読む。
 * クリックはプレイ領域内部座標（800×600）を `game-canvas` の表示矩形へスケールして実座標へ変換し、
 * `page.mouse.click` で撃つ。型は frontend 本体の testSeam / session と同一の最小形を再宣言する
 * （e2e は別 tsconfig で本体を import しないため）。
 */

import { expect, type Page } from "@playwright/test";

/** プレイ領域の内部解像度（GameCanvas の width/height と一致）。 */
export const PLAY_AREA_WIDTH = 800;
export const PLAY_AREA_HEIGHT = 600;

/** シームが返すセッション状態（lib/session SessionState の E2E から見える形）。 */
export interface SeamState {
  readonly status: "idle" | "running" | "finished";
  readonly startedAt: number;
  readonly hits: number;
  readonly totalClicks: number;
  readonly reactionTimes: readonly number[];
  readonly target: { readonly x: number; readonly y: number; readonly radius: number };
}

/** シームが返す的座標。 */
export interface SeamTarget {
  readonly x: number;
  readonly y: number;
  readonly radius: number;
}

/** 現在のセッション状態を取得する。 */
export async function getState(page: Page): Promise<SeamState> {
  return page.evaluate(() => {
    const seam = window.__aimTest;
    if (!seam) {
      throw new Error("__aimTest seam is not installed (VITE_AIM_TEST=1 が必要)");
    }
    return seam.getState() as SeamState;
  });
}

/** 現在の的座標を取得する。 */
export async function getTarget(page: Page): Promise<SeamTarget> {
  return page.evaluate(() => {
    const seam = window.__aimTest;
    if (!seam) {
      throw new Error("__aimTest seam is not installed");
    }
    return seam.getTarget() as SeamTarget;
  });
}

/** シームが取り付くまで待つ（コンテナのマウント後に installTestSeam が走る）。 */
export async function waitForSeam(page: Page): Promise<void> {
  await page.waitForFunction(() => Boolean(window.__aimTest));
}

/**
 * 内部座標 (x, y) を `game-canvas` 上で実クリックする。
 * 表示矩形 ↔ 内部解像度のスケールを GameCanvas と逆変換して実ピクセルへ写す。
 */
export async function clickCanvasAt(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId("game-canvas");
  const box = await canvas.boundingBox();
  if (!box) {
    throw new Error("game-canvas の boundingBox が取得できない");
  }
  const realX = box.x + (x / PLAY_AREA_WIDTH) * box.width;
  const realY = box.y + (y / PLAY_AREA_HEIGHT) * box.height;
  await page.mouse.click(realX, realY);
}

/**
 * 内部座標 (x, y) を `game-canvas` へ **同期的に** クリックする（仮想時計の値を同時に設定）。
 *
 * 終了時刻ちょうど（R-8）など、rAF tick とクリックが同じ時刻で競合する境界では、実マウス
 * クリック（複数往復）だと tick が先に finished にしてしまう。そこで 1 回の evaluate 内で
 * 「__vnow を設定 → canvas へ synthetic click を dispatch」を原子的に行い、rAF より先に
 * React の onClick（registerClick）を走らせる。clock を進めない場合は now を null にする。
 */
export async function clickCanvasSync(
  page: Page,
  x: number,
  y: number,
  now: number | null,
): Promise<void> {
  await page.evaluate(
    ({ ix, iy, w, h, nowMs }) => {
      if (nowMs !== null) {
        (window as unknown as { __vnow: number }).__vnow = nowMs;
      }
      const canvas = document.querySelector<HTMLCanvasElement>('[data-testid="game-canvas"]');
      if (!canvas) {
        throw new Error("game-canvas が見つからない（synthetic click）");
      }
      const rect = canvas.getBoundingClientRect();
      const clientX = rect.left + (ix / w) * rect.width;
      const clientY = rect.top + (iy / h) * rect.height;
      canvas.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX, clientY }));
    },
    { ix: x, iy: y, w: PLAY_AREA_WIDTH, h: PLAY_AREA_HEIGHT, nowMs: now },
  );
}

/** start-button を押してセッションを開始し、running になるまで待つ。 */
export async function startSession(page: Page): Promise<void> {
  await page.getByTestId("start-button").click();
  await expect.poll(async () => (await getState(page)).status).toBe("running");
}

/** 現在の的を「ヒット済み」にする（R-20 の再クリック無視を E2E から再現する test hook）。 */
export async function markTargetHit(page: Page): Promise<void> {
  await page.evaluate(() => {
    window.__aimTest?.markTargetHit();
  });
}

declare global {
  interface Window {
    __aimTest?: {
      getState: () => unknown;
      getTarget: () => unknown;
      setClock: (source: () => number) => void;
      resetClock: () => void;
      markTargetHit: () => void;
    };
  }
}
