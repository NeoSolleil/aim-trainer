/**
 * Playwright + playwright-bdd の設定（T-10）。
 *
 * Gherkin 原本 `specs/0001-shooting-session/acceptance.feature` を **コピーせず** 参照し、
 * `@e2e` タグのシナリオだけを生成・実行する（`@backend` は pytest-bdd 側で実行）。
 * dev サーバは `VITE_AIM_TEST=1` 付きで起動し、`window.__aimTest` シームを有効化する。
 *
 * 生成物（.features-gen）と report/results は .gitignore / .prettierignore 済み。
 */

import { defineConfig, devices } from "@playwright/test";
import { defineBddConfig } from "playwright-bdd";

const testDir = defineBddConfig({
  // 原本 .feature を直接参照（二重管理しない）。
  features: ["../specs/0001-shooting-session/acceptance.feature"],
  steps: ["e2e/steps/**/*.ts"],
  // .feature がリポジトリ root（frontend の外）にあるため featuresRoot を上げる。
  featuresRoot: "..",
  // @e2e のみ生成（@backend は除外）。
  tags: "@e2e",
  // 生成物の出力先。
  outputDir: ".features-gen",
});

export default defineConfig({
  testDir,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "list" : [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // シームを有効化した dev サーバ。
    command: "npm run dev -- --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    env: { VITE_AIM_TEST: "1" },
    timeout: 120_000,
  },
});
