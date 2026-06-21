import { describe, expect, it } from "vitest";

import {
  PLAY_AREA_HEIGHT,
  PLAY_AREA_WIDTH,
  TIME_LIMIT_MS,
  createSession,
  endTime,
  registerClick,
  spawnTarget,
  tick,
  type SessionState,
  type Target,
} from "./session";

/** 決定的な的: 中心 (400,300)・半径 20・spawnedAt=0・未ヒット。 */
function makeTarget(overrides: Partial<Target> = {}): Target {
  return { x: 400, y: 300, radius: 20, spawnedAt: 0, hit: false, ...overrides };
}

/** 進行中セッション（startedAt=0・的あり）。respawn 用に固定 RNG を持つ。 */
function makeRunning(overrides: Partial<SessionState> = {}): SessionState {
  return {
    status: "running",
    startedAt: 0,
    hits: 0,
    totalClicks: 0,
    reactionTimes: [],
    target: makeTarget(),
    ...overrides,
  };
}

/** 常に中心 0.5 を返す決定的 RNG（再現性のため）。 */
const fixedRng = (): number => 0.5;

describe("createSession", () => {
  it("idle 状態を 0 カウントで作る", () => {
    const s = createSession();
    expect(s.status).toBe("idle");
    expect(s.hits).toBe(0);
    expect(s.totalClicks).toBe(0);
    expect(s.reactionTimes).toEqual([]);
  });
});

describe("spawnTarget", () => {
  it("プレイ領域内に固定半径の的を1つ生成する", () => {
    const t = spawnTarget(123, fixedRng);
    expect(t.spawnedAt).toBe(123);
    expect(t.hit).toBe(false);
    expect(t.radius).toBeGreaterThan(0);
    expect(t.x).toBeGreaterThanOrEqual(t.radius);
    expect(t.x).toBeLessThanOrEqual(PLAY_AREA_WIDTH - t.radius);
    expect(t.y).toBeGreaterThanOrEqual(t.radius);
    expect(t.y).toBeLessThanOrEqual(PLAY_AREA_HEIGHT - t.radius);
  });

  it("RNG 注入で位置が決定化される", () => {
    const a = spawnTarget(0, () => 0);
    const b = spawnTarget(0, () => 0);
    expect(a.x).toBe(b.x);
    expect(a.y).toBe(b.y);
  });
});

describe("registerClick — hit（R-1/R-2/R-5）", () => {
  it("内側クリックは hit: hits+1・totalClicks+1・reaction_time 記録（R-1）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, 320, fixedRng);
    expect(next.hits).toBe(1);
    expect(next.totalClicks).toBe(1);
    expect(next.reactionTimes).toEqual([320]);
  });

  it("縁ちょうど（distance == radius）は hit（R-1 境界）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 420, y: 300 }, 100, fixedRng);
    expect(next.hits).toBe(1);
    expect(next.reactionTimes).toEqual([100]);
  });

  it("出現と同時刻の hit は reaction_time 0ms を有効値として記録（R-2 境界）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, 0, fixedRng);
    expect(next.reactionTimes).toEqual([0]);
    expect(next.reactionTimes.every((ms) => ms >= 0)).toBe(true);
  });

  it("小数 now でも reaction_time は整数 ms に丸める（domain/API は int 前提）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, 487.3, fixedRng);
    expect(next.reactionTimes).toEqual([487]);
    expect(Number.isInteger(next.reactionTimes[0])).toBe(true);
  });

  it("hit すると次の的を1つ spawn する（R-5）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, 200, fixedRng);
    expect(next.target.hit).toBe(false);
    expect(next.target.spawnedAt).toBe(200);
    // 同一参照ではなく新しい的
    expect(next.target).not.toBe(s.target);
  });

  it("元の state を変更しない（純粋・不変）", () => {
    const s = makeRunning();
    registerClick(s, { x: 400, y: 300 }, 200, fixedRng);
    expect(s.hits).toBe(0);
    expect(s.totalClicks).toBe(0);
    expect(s.reactionTimes).toEqual([]);
  });
});

describe("registerClick — miss（R-3/R-4）", () => {
  it("領域内・的外は miss: totalClicks+1 のみ・reaction_time 記録せず（R-3）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 10, y: 10 }, 100, fixedRng);
    expect(next.hits).toBe(0);
    expect(next.totalClicks).toBe(1);
    expect(next.reactionTimes).toEqual([]);
  });

  it("miss では的を respawn しない（同じ的が残る）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 10, y: 10 }, 100, fixedRng);
    expect(next.target).toBe(s.target);
  });

  it("空白連打はデバウンスなしで全て計上（R-4）", () => {
    let s = makeRunning();
    for (let i = 0; i < 5; i++) {
      s = registerClick(s, { x: 10, y: 10 }, 10 + i, fixedRng);
    }
    expect(s.totalClicks).toBe(5);
    expect(s.hits).toBe(0);
  });
});

describe("registerClick — 無視されるクリック（R-20/R-21/R-22/R-8）", () => {
  it("hit 済みの的への再クリックは無視（R-20）", () => {
    // hit 済みの的（hit=true）が残っている状態を直接作る
    const s = makeRunning({ target: makeTarget({ hit: true }), hits: 1, totalClicks: 1 });
    const next = registerClick(s, { x: 400, y: 300 }, 200, fixedRng);
    expect(next.hits).toBe(1);
    expect(next.totalClicks).toBe(1);
    expect(next).toBe(s);
  });

  it("プレイ領域外のクリックは無視（R-21）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: -5, y: -5 }, 100, fixedRng);
    expect(next.hits).toBe(0);
    expect(next.totalClicks).toBe(0);
    expect(next).toBe(s);
  });

  it("領域の右下外も無視（R-21 境界）", () => {
    const s = makeRunning();
    const next = registerClick(
      s,
      { x: PLAY_AREA_WIDTH + 1, y: PLAY_AREA_HEIGHT + 1 },
      100,
      fixedRng,
    );
    expect(next).toBe(s);
  });

  it("status が finished のクリックは無視（R-22）", () => {
    const s = makeRunning({ status: "finished" });
    const next = registerClick(s, { x: 400, y: 300 }, 100, fixedRng);
    expect(next.hits).toBe(0);
    expect(next.totalClicks).toBe(0);
    expect(next).toBe(s);
  });

  it("終了時刻を過ぎた（now > endTime）クリックは無視（R-8/R-22）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, TIME_LIMIT_MS + 1, fixedRng);
    expect(next.hits).toBe(0);
    expect(next.totalClicks).toBe(0);
    expect(next).toBe(s);
  });

  it("終了時刻ちょうど（now == endTime）のクリックは含める（R-8 閉区間）", () => {
    const s = makeRunning();
    const next = registerClick(s, { x: 400, y: 300 }, TIME_LIMIT_MS, fixedRng);
    expect(next.hits).toBe(1);
    expect(next.totalClicks).toBe(1);
    expect(next.reactionTimes).toEqual([TIME_LIMIT_MS]);
  });
});

describe("tick（R-6/R-7）", () => {
  it("startedAt + 30000 で finished へ遷移する（R-7）", () => {
    const s = makeRunning();
    const next = tick(s, TIME_LIMIT_MS);
    expect(next.status).toBe("finished");
  });

  it("終了時刻ちょうど（now == endTime）も finished（閉区間で終了）", () => {
    const s = makeRunning();
    expect(tick(s, TIME_LIMIT_MS - 1).status).toBe("running");
    expect(tick(s, TIME_LIMIT_MS).status).toBe("finished");
  });

  it("経過前は running のまま的を動かさない／消さない（R-6）", () => {
    const s = makeRunning();
    const next = tick(s, 10000);
    expect(next.status).toBe("running");
    expect(next.target).toBe(s.target);
  });

  it("idle のセッションは tick で finished にならない", () => {
    const s = createSession();
    const next = tick(s, TIME_LIMIT_MS + 1000);
    expect(next.status).toBe("idle");
  });
});

describe("endTime", () => {
  it("startedAt + TIME_LIMIT_MS", () => {
    expect(endTime(makeRunning({ startedAt: 1000 }))).toBe(1000 + TIME_LIMIT_MS);
  });
});
