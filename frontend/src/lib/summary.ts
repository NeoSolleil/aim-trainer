/**
 * summary — サマリ算出・表示整形（フレームワーク非依存の純粋関数）。
 *
 * 終了時の結果サマリ（R-9 / R-18 / R-19）をフロントの画面 state から算出・整形する。
 * 算出規則（accuracy = hits ÷ totalClicks 等）は backend domain と概念一致させ、
 * 表示用フォーマット（"62.5%" / "— " / "400 ms"）は frontend の責務として持つ。
 *
 * 未定義（分母 0・ヒット 0）は `null` で表し、表示時に「—」へ整形する。
 */

/** 命中率を算出する。totalClicks が 0 なら未定義（null）。 */
export function computeAccuracy(hits: number, totalClicks: number): number | null {
  if (totalClicks === 0) {
    return null;
  }
  return hits / totalClicks;
}

/** ヒットの平均反応時間（ms）を算出する。ヒットが無ければ未定義（null）。 */
export function computeAvgReactionTime(reactionTimes: readonly number[]): number | null {
  if (reactionTimes.length === 0) {
    return null;
  }
  const total = reactionTimes.reduce((sum, ms) => sum + ms, 0);
  return total / reactionTimes.length;
}

/**
 * 命中率を百分率文字列へ整形する。null は「—」。
 * 小数第1位まで表示し、不要な末尾 0 は出さない（0 → "0%"・0.625 → "62.5%"）。
 */
export function formatAccuracy(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const percent = value * 100;
  const rounded = Math.round(percent * 10) / 10;
  return `${rounded}%`;
}

/** 平均反応時間を「### ms」へ整形する。null は「—」。ms は整数に丸める。 */
export function formatAvg(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${Math.round(value)} ms`;
}
