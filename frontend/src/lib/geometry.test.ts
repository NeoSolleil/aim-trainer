import { describe, expect, it } from "vitest";

import { isHit } from "./geometry";

const target = { x: 400, y: 300, radius: 20 };

describe("isHit", () => {
  it("クリックが的の中心ちょうどならヒット", () => {
    expect(isHit(400, 300, target)).toBe(true);
  });

  it("クリックが的の内側ならヒット", () => {
    expect(isHit(410, 305, target)).toBe(true);
  });

  it("縁ちょうど（距離 == 半径）はヒット（境界・閉区間）", () => {
    // 中心から x 方向に radius ちょうど離れた点 → distance == radius
    expect(isHit(420, 300, target)).toBe(true);
  });

  it("半径をわずかに超える位置はミス（境界）", () => {
    // distance = 21px > 20px
    expect(isHit(421, 300, target)).toBe(false);
  });

  it("遠く離れた空白座標はミス", () => {
    expect(isHit(10, 10, target)).toBe(false);
  });

  it("斜め方向の縁内側はヒット、外側はミス（平方根回避の二乗距離比較）", () => {
    // (dx, dy) = (12, 16) → distance^2 = 144 + 256 = 400 = radius^2 → 縁ちょうど → hit
    expect(isHit(412, 316, target)).toBe(true);
    // (dx, dy) = (12, 17) → distance^2 = 144 + 289 = 433 > 400 → miss
    expect(isHit(412, 317, target)).toBe(false);
  });
});
