/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * E2E テストシーム（window.__aimTest）を有効化するフラグ。"1" のときのみ露出する。
   * 本番ビルドでは未設定のためシームは生えない（lib/testSeam.ts のガード）。
   * 次委譲（@e2e 実行）で Playwright 起動時に "1" を渡す。
   */
  readonly VITE_AIM_TEST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
