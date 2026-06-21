/**
 * time — 単調時計のラッパー。
 *
 * reaction_time の計測には壁時計 `Date.now()` を使わず、単調増加する
 * `performance.now()` を使う（Rule 11）。時刻取得をこの1関数に集約することで、
 * テスト・E2E で時間を差し替え可能なシームにする。
 */

/** 単調時計の現在値（ミリ秒）。`performance.now()` のラッパー。 */
export function now(): number {
  return performance.now();
}
