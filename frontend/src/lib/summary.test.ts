import { describe, expect, it } from "vitest";

import { computeAccuracy, computeAvgReactionTime, formatAccuracy, formatAvg } from "./summary";

describe("computeAccuracy", () => {
  it("totalClicks が 0 なら null（未定義）", () => {
    expect(computeAccuracy(0, 0)).toBeNull();
  });

  it("hits ÷ totalClicks を返す（R-9: 5/8 = 0.625）", () => {
    expect(computeAccuracy(5, 8)).toBeCloseTo(0.625, 10);
  });

  it("全ミスは 0（R-19: hits=0・total=8）", () => {
    expect(computeAccuracy(0, 8)).toBe(0);
  });
});

describe("computeAvgReactionTime", () => {
  it("空配列なら null（未定義 ＝ hits=0）", () => {
    expect(computeAvgReactionTime([])).toBeNull();
  });

  it("ヒットの算術平均を返す（300, 500 → 400）", () => {
    expect(computeAvgReactionTime([300, 500])).toBe(400);
  });

  it("0ms を含む平均も正しく算出（0ms は有効値）", () => {
    expect(computeAvgReactionTime([0, 100])).toBe(50);
  });
});

describe("formatAccuracy", () => {
  it("null は『—』（R-18）", () => {
    expect(formatAccuracy(null)).toBe("—");
  });

  it("0.625 は『62.5%』（R-9・L102）", () => {
    expect(formatAccuracy(0.625)).toBe("62.5%");
  });

  it("0 は『0%』（R-19・L197）", () => {
    expect(formatAccuracy(0)).toBe("0%");
  });

  it("1 は『100%』", () => {
    expect(formatAccuracy(1)).toBe("100%");
  });

  it("循環小数は不要な小数桁を出さない（1/3 → 33.3%）", () => {
    expect(formatAccuracy(1 / 3)).toBe("33.3%");
  });
});

describe("formatAvg", () => {
  it("null は『—』（R-18/19）", () => {
    expect(formatAvg(null)).toBe("—");
  });

  it("整数の ms に丸めて『### ms』形式（400 → 『400 ms』）", () => {
    expect(formatAvg(400)).toBe("400 ms");
  });

  it("0ms も有効に表示（『0 ms』）", () => {
    expect(formatAvg(0)).toBe("0 ms");
  });

  it("小数は四捨五入して整数 ms（416.6 → 『417 ms』）", () => {
    expect(formatAvg(416.6)).toBe("417 ms");
  });
});
