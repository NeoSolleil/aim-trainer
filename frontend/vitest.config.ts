import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest 設定。
 *
 * - 環境は jsdom（components の DOM テスト）。lib の純粋関数テストも jsdom で問題なく動く
 *   （performance.now などブラウザ API も使えるため node 環境より無難）。
 * - Tailwind の Vite プラグインはテストでは読み込まない（CSS 変換不要・依存を減らす）。
 * - @testing-library/jest-dom のマッチャを setup で読み込む。
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Vitest は src/ のユニットテストのみ。E2E（Playwright）とその生成物は対象外。
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e", ".features-gen"],
  },
});
