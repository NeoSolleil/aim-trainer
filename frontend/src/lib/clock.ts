/**
 * clock — アプリが参照する時刻源（差し替え可能なシーム）。
 *
 * 既定は `time.now`（performance.now の単調時計ラッパー）。E2E では仮想時間を
 * 注入して 30 秒経過・終了時刻ちょうど・終了後クリック（R-7/R-8/R-22）を再現する。
 * `time.now` 自体は純粋なラッパーのまま保ち（その単体テストを壊さない）、
 * 注入はこのモジュールの差し替え関数で行う。注入経路は本番ビルドで露出しない
 * （`testSeam.ts` が環境フラグでガードする）。
 */

import { now as realNow } from "./time";

let clock: () => number = realNow;

/** 現在時刻（ms）。既定は単調時計、テストでは注入された仮想時計。 */
export function now(): number {
  return clock();
}

/** 時刻源を差し替える（E2E の仮想時間注入用）。 */
export function setClock(source: () => number): void {
  clock = source;
}

/** 時刻源を既定（単調時計）へ戻す。 */
export function resetClock(): void {
  clock = realNow;
}
