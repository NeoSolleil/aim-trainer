/**
 * renderer — Canvas への命令的描画（React の再レンダーから分離）。
 *
 * requestAnimationFrame ループで的と HUD（残り時間・hits/total_clicks）を描く。
 * 状態は React state に乗せず ref 経由で `SessionState` を読む（frontend-architecture:
 * 描画を React 再レンダーから分離）。色は Tailwind と同値のトークン定数（lib/tokens）を参照
 * （Canvas は CSS が効かないため）。本検証は次委譲の @e2e（ここは型・スモークのみ）。
 */

import { colorTokens } from "../lib/tokens";
import { endTime, PLAY_AREA_HEIGHT, PLAY_AREA_WIDTH, type SessionState } from "../lib/session";

/** 描画ループを止めるためのハンドル。 */
export interface RenderHandle {
  /** rAF ループを停止する。 */
  stop: () => void;
}

/** 残り時間（ms）を 0 以上で返す。finished/idle は 0。 */
function remainingMs(state: SessionState, now: number): number {
  if (state.status !== "running") {
    return 0;
  }
  return Math.max(0, endTime(state) - now);
}

/** 1 フレーム分の描画。テスト・スモーク用に純粋に近い形で公開する。 */
export function drawFrame(ctx: CanvasRenderingContext2D, state: SessionState, now: number): void {
  // 背景（プレイ領域の面）。
  ctx.fillStyle = colorTokens.surface;
  ctx.fillRect(0, 0, PLAY_AREA_WIDTH, PLAY_AREA_HEIGHT);

  // 進行中のみ的を描く（常に1つ・R-6）。
  if (state.status === "running" && !state.target.hit) {
    const { x, y, radius } = state.target;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = colorTokens.primary;
    ctx.fill();
  }

  // HUD: 残り時間・hits/total_clicks。
  ctx.fillStyle = colorTokens.muted;
  ctx.font = "16px system-ui, sans-serif";
  ctx.textBaseline = "top";
  const seconds = (remainingMs(state, now) / 1000).toFixed(1);
  ctx.fillText(`残り ${seconds}s`, 12, 12);
  ctx.fillStyle = colorTokens.text;
  ctx.fillText(`${state.hits} / ${state.totalClicks}`, 12, 36);
}

/**
 * rAF ループを開始する。`getState`・`getNow` を呼び出しごとに評価し、最新状態で描画する
 * （ref を読む想定）。返す handle の stop でループを止める。
 */
export function startRenderLoop(
  ctx: CanvasRenderingContext2D,
  getState: () => SessionState,
  getNow: () => number,
): RenderHandle {
  let rafId = 0;
  let running = true;

  const loop = (): void => {
    if (!running) {
      return;
    }
    drawFrame(ctx, getState(), getNow());
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);

  return {
    stop: () => {
      running = false;
      cancelAnimationFrame(rafId);
    },
  };
}
