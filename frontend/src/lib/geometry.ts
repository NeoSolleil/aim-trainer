/**
 * geometry — フレームワーク非依存の純粋な幾何判定。
 *
 * hit/miss 判定（R-1 / R-3）。平方根を避けて二乗距離で比較する（discovery の決定）。
 * 縁ちょうど（distance == radius）は hit とする（境界は閉区間）。
 */

/** クリック対象の的。中心座標と半径（px）を持つ。 */
export interface TargetCircle {
  readonly x: number;
  readonly y: number;
  readonly radius: number;
}

/**
 * クリック座標が的の内側（縁を含む）かどうかを返す。
 *
 * `(dx*dx + dy*dy) <= radius*radius` で判定する。平方根を取らないことで
 * 浮動小数の誤差と計算コストを避け、縁ちょうどを正確に hit と判定できる。
 */
export function isHit(clickX: number, clickY: number, target: TargetCircle): boolean {
  const dx = clickX - target.x;
  const dy = clickY - target.y;
  return dx * dx + dy * dy <= target.radius * target.radius;
}
