/**
 * tokens — デザイントークンの値（役割ベース）。
 *
 * 生 hex を画面・描画に散らさないための単一情報源。Tailwind（CSS）側は
 * `src/index.css` の `@theme` に同じ値を定義し、Canvas など CSS が効かない
 * 命令的描画層はこの定数を参照する（design スキル: 描画層の色も同じトークン値）。
 *
 * 役割名は固定・値は差し替え可能に保つ（primary / bg / surface / text / muted /
 * 状態色 成功・失敗）。CSS と値がずれないよう、変更時は index.css の @theme も更新する。
 */

/** 役割ベースのカラートークン（hex）。CSS の @theme と一致させる。 */
export const colorTokens = {
  /** 主要ボタン・強調・的の塗り。 */
  primary: "#3b82f6",
  /** 画面背景。 */
  bg: "#0f172a",
  /** パネル・プレイ領域の面。 */
  surface: "#1e293b",
  /** 本文テキスト。 */
  text: "#f1f5f9",
  /** 補助テキスト・HUD のラベル。 */
  muted: "#94a3b8",
  /** 成功状態（保存成功など）。 */
  success: "#22c55e",
  /** 失敗状態（保存失敗通知など）。 */
  danger: "#ef4444",
} as const;

/** トークンのキー型。 */
export type ColorToken = keyof typeof colorTokens;
