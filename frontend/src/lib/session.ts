/**
 * session — 進行中セッションの状態と計上規則（フレームワーク非依存の純粋関数）。
 *
 * React / DOM / 描画に依存しない。状態を引数で受け取り新状態を返す（不変・純粋）。
 * hit/miss 判定・reaction_time 計測・respawn・常に的1つ・30 秒タイマー・
 * 計上規則（R-1〜R-8・R-20/21/22）をここに集約する。サーバ通信は持たない。
 */

import { isHit } from "./geometry";

/** セッション制限時間（ms）。30 秒で自動終了（R-7）。 */
export const TIME_LIMIT_MS = 30000;

/** プレイ領域の幅（px）。領域外クリックは無視する（R-21）。 */
export const PLAY_AREA_WIDTH = 800;

/** プレイ領域の高さ（px）。 */
export const PLAY_AREA_HEIGHT = 600;

/** 的の固定半径（px）。0001 では銃による可変は扱わない。 */
export const TARGET_RADIUS = 20;

/** 0〜1 の乱数を返す関数。テストで決定化するため注入可能にする。 */
export type Rng = () => number;

/** 進行中の的。中心座標・半径に加え、出現時刻と消費済みフラグを持つ。 */
export interface Target {
  readonly x: number;
  readonly y: number;
  readonly radius: number;
  /** 出現時刻（単調時計 ms）。reaction_time の起点。 */
  readonly spawnedAt: number;
  /** 既にヒットされたか。true の的への再クリックは無視（R-20）。 */
  readonly hit: boolean;
}

/** セッションの進行状態。 */
export type SessionStatus = "idle" | "running" | "finished";

/** クリック座標（プレイ領域基準）。 */
export interface Click {
  readonly x: number;
  readonly y: number;
}

/** 進行中セッションの全状態。 */
export interface SessionState {
  readonly status: SessionStatus;
  /** セッション開始時刻（単調時計 ms）。 */
  readonly startedAt: number;
  readonly hits: number;
  readonly totalClicks: number;
  readonly reactionTimes: readonly number[];
  readonly target: Target;
}

/** 未開始（idle）のセッションを作る。カウントは 0。 */
export function createSession(): SessionState {
  return {
    status: "idle",
    startedAt: 0,
    hits: 0,
    totalClicks: 0,
    reactionTimes: [],
    // idle 中は描画されないプレースホルダの的（開始時に再 spawn される）。
    target: { x: 0, y: 0, radius: TARGET_RADIUS, spawnedAt: 0, hit: false },
  };
}

/** プレイ領域内に固定半径の的を1つ生成する（常に1つ・R-5/R-6）。 */
export function spawnTarget(spawnedAt: number, rng: Rng = Math.random): Target {
  const x = TARGET_RADIUS + rng() * (PLAY_AREA_WIDTH - 2 * TARGET_RADIUS);
  const y = TARGET_RADIUS + rng() * (PLAY_AREA_HEIGHT - 2 * TARGET_RADIUS);
  return { x, y, radius: TARGET_RADIUS, spawnedAt, hit: false };
}

/** セッションの終了時刻（startedAt + TIME_LIMIT_MS）。 */
export function endTime(state: SessionState): number {
  return state.startedAt + TIME_LIMIT_MS;
}

/** クリックがプレイ領域内（縁を含む）か。 */
function isInsidePlayArea(click: Click): boolean {
  return click.x >= 0 && click.x <= PLAY_AREA_WIDTH && click.y >= 0 && click.y <= PLAY_AREA_HEIGHT;
}

/**
 * クリック1つを適用して新しい状態を返す。
 *
 * 計上規則:
 * - 進行中でない（idle/finished）→ 無視（R-22）。
 * - now > endTime（終了時刻超過）→ 無視（R-22）。now == endTime は含める（R-8 閉区間）。
 * - プレイ領域外 → 無視（R-21）。
 * - hit 済みの的への再クリック → 無視（R-20）。
 * - hit（isHit 真）→ hits+1・totalClicks+1・reaction_time(now-spawnedAt) 記録・次の的を spawn（R-1/R-2/R-5）。
 * - miss（領域内・的外）→ totalClicks+1 のみ（R-3/R-4・デバウンスなし）。
 *
 * 無視するクリックは元の state をそのまま返す（参照不変）。
 */
export function registerClick(
  state: SessionState,
  click: Click,
  now: number,
  rng: Rng = Math.random,
): SessionState {
  // 終了後 / 終了時刻超過は無視（now == endTime は含める）。
  if (state.status !== "running" || now > endTime(state)) {
    return state;
  }

  // プレイ領域外は無視（R-21）。
  if (!isInsidePlayArea(click)) {
    return state;
  }

  // hit 済みの的への再クリックは無視（R-20）。
  if (state.target.hit) {
    return state;
  }

  if (isHit(click.x, click.y, state.target)) {
    // reaction_time は整数 ms（domain/API は int 前提）。performance.now() の小数を丸める。
    const reactionTime = Math.round(now - state.target.spawnedAt);
    return {
      ...state,
      hits: state.hits + 1,
      totalClicks: state.totalClicks + 1,
      reactionTimes: [...state.reactionTimes, reactionTime],
      target: spawnTarget(now, rng),
    };
  }

  // miss（領域内・的外）: total_clicks のみ加算。respawn しない。
  return {
    ...state,
    totalClicks: state.totalClicks + 1,
  };
}

/**
 * 経過時間でステータスを更新する。
 *
 * running かつ now >= endTime なら finished へ遷移（R-7・閉区間で終了）。
 * 的の移動・消滅はしない（R-6）。
 */
export function tick(state: SessionState, now: number): SessionState {
  if (state.status !== "running") {
    return state;
  }
  if (now >= endTime(state)) {
    return { ...state, status: "finished" };
  }
  return state;
}
