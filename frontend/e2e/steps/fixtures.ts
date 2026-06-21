/**
 * playwright-bdd の共有フィクスチャ（@e2e）。
 *
 * `createBdd` が返す Given/When/Then で全ステップを定義する。各ステップは:
 * - DOM 操作・検証は `page.getByTestId(...)`（start-button / summary-* / 等）。
 * - Canvas の的は DOM が無いため `window.__aimTest`（getState / getTarget）で読み取り、
 *   座標は `game-canvas` の表示矩形へスケールして `mouse.click` する。
 * - 時間は Playwright の `page.clock`（performance.now / rAF / setTimeout を仮想化）で
 *   確定的に進める（rAF 自走を制御し、30 秒経過・終了境界を再現）。
 * - 保存失敗は `page.route('**\/api/sessions', ...)`（abort / 5xx fulfill）で注入する。
 *
 * 既定では `POST /api/sessions` を 201 ＋ ダミー ScoreResponse でスタブし、実 backend を不要にする。
 */

import { expect } from "@playwright/test";
import { test as base } from "playwright-bdd";

/** テスト間で持ち回るシナリオ局所の状態（撃った座標の記録など）。 */
export interface ScenarioWorld {
  /** 直近に撃った的の中心座標（R-20 の「同じ的を再クリック」で使う）。 */
  lastHitCenter?: { readonly x: number; readonly y: number };
}

export const test = base.extend<{ world: ScenarioWorld }>({
  world: async ({}, use) => {
    await use({});
  },
});

export { expect };
