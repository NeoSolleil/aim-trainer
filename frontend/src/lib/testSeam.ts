/**
 * testSeam — E2E 用テストシーム（本番ビルドで無効）。
 *
 * Canvas の的は DOM 要素でないため data-testid を付けられない。@e2e が的をクリック・
 * 状態を検証できるよう、現在の `SessionState` と的座標を `window.__aimTest` で露出する。
 * 併せて仮想時間（clock 差し替え）を注入できる hook を提供する（R-7/R-8/R-22 の時間制御）。
 *
 * 本番無効化: `import.meta.env.VITE_AIM_TEST` が "1" のときのみ有効化する。本番ビルドは
 * このフラグを立てないため `window.__aimTest` は生えず、シームが漏れない（design §8.5 決定）。
 * 実際の @e2e 実行・route mock は次委譲で行うが、土台（露出 API・無効化）は本タスクで入れる。
 */

import { resetClock, setClock } from "./clock";
import type { SessionState } from "./session";

/** E2E が読み取る的の最小情報（中心座標・半径）。 */
export interface TestTarget {
  readonly x: number;
  readonly y: number;
  readonly radius: number;
}

/** `window.__aimTest` の形。テスト時のみ生える。 */
export interface AimTestSeam {
  /** 現在のセッション状態を返す（status/hits/totalClicks/reactionTimes/target）。 */
  getState: () => SessionState;
  /** 現在の的の中心座標と半径を返す。 */
  getTarget: () => TestTarget;
  /** 仮想時計を注入する（ms を返す関数）。R-7/R-8/R-22 の時間制御。 */
  setClock: (source: () => number) => void;
  /** 時計を既定（単調時計）へ戻す。 */
  resetClock: () => void;
  /**
   * 現在の的を「ヒット済み」状態にする（test-only）。通常フローでは hit 後に即 respawn するため
   * `target.hit=true` の状態は UI 上に存在しない。R-20（ヒット済みの的の再クリック無視）を
   * E2E から再現するための hook。production では露出しない。
   */
  markTargetHit: () => void;
}

declare global {
  interface Window {
    __aimTest?: AimTestSeam;
  }
}

/** シームが有効か（本番ビルドでは false）。 */
export function isTestSeamEnabled(): boolean {
  return import.meta.env.VITE_AIM_TEST === "1";
}

/**
 * テストシームを `window.__aimTest` に取り付ける。`getState` は呼び出し時点の最新状態を
 * 返す必要があるため、状態取得関数を引数で受ける（コンテナの ref を読む）。
 * フラグ無効時は何もしない（本番で露出しない）。クリーンアップ関数を返す。
 */
export function installTestSeam(
  getState: () => SessionState,
  markTargetHit: () => void,
): () => void {
  if (!isTestSeamEnabled() || typeof window === "undefined") {
    return () => {};
  }
  window.__aimTest = {
    getState,
    getTarget: () => {
      const { target } = getState();
      return { x: target.x, y: target.y, radius: target.radius };
    },
    setClock,
    resetClock,
    markTargetHit,
  };
  return () => {
    delete window.__aimTest;
  };
}
