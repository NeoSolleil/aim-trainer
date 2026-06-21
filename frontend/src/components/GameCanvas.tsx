/**
 * GameCanvas（molecule・Dumb 寄り）— `<canvas>` 要素。
 *
 * canvas ref を親へ渡し（描画は canvas/renderer が ref 経由で行う）、クリック座標を
 * プレイ領域基準（左上原点）に変換して親へ通知する。判定・計上はしない（親＝Smart の責務）。
 * data-testid="game-canvas"（@e2e のクリック操作対象）。
 */

import { forwardRef, type MouseEvent } from "react";
import { PLAY_AREA_HEIGHT, PLAY_AREA_WIDTH } from "../lib/session";

export interface GameCanvasProps {
  /** クリック座標（プレイ領域基準）を親へ通知する。 */
  readonly onCanvasClick: (x: number, y: number) => void;
}

export const GameCanvas = forwardRef<HTMLCanvasElement, GameCanvasProps>(function GameCanvas(
  { onCanvasClick },
  ref,
) {
  const handleClick = (event: MouseEvent<HTMLCanvasElement>): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    // 表示サイズが内部解像度と異なる場合に備えて座標をスケールする。
    const scaleX = rect.width === 0 ? 1 : PLAY_AREA_WIDTH / rect.width;
    const scaleY = rect.height === 0 ? 1 : PLAY_AREA_HEIGHT / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    onCanvasClick(x, y);
  };

  return (
    <canvas
      ref={ref}
      data-testid="game-canvas"
      width={PLAY_AREA_WIDTH}
      height={PLAY_AREA_HEIGHT}
      onClick={handleClick}
      className="rounded-md bg-surface"
    />
  );
});
