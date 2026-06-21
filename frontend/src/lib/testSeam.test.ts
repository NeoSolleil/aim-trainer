import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createSession, spawnTarget } from "./session";
import { installTestSeam, isTestSeamEnabled } from "./testSeam";

describe("testSeam", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    delete window.__aimTest;
  });

  it("VITE_AIM_TEST が立っていなければ window.__aimTest を生やさない（本番無効化）", () => {
    vi.stubEnv("VITE_AIM_TEST", "");
    expect(isTestSeamEnabled()).toBe(false);
    const cleanup = installTestSeam(
      () => createSession(),
      () => {},
    );
    expect(window.__aimTest).toBeUndefined();
    cleanup();
  });

  describe("有効時", () => {
    beforeEach(() => {
      vi.stubEnv("VITE_AIM_TEST", "1");
    });

    it("getState/getTarget を露出し、cleanup で外す", () => {
      const state = {
        ...createSession(),
        status: "running" as const,
        hits: 2,
        totalClicks: 3,
        target: spawnTarget(0, () => 0.5),
      };
      const cleanup = installTestSeam(
        () => state,
        () => {},
      );
      expect(isTestSeamEnabled()).toBe(true);
      expect(window.__aimTest).toBeDefined();
      expect(window.__aimTest?.getState().hits).toBe(2);
      const target = window.__aimTest?.getTarget();
      expect(target).toEqual({ x: state.target.x, y: state.target.y, radius: state.target.radius });
      cleanup();
      expect(window.__aimTest).toBeUndefined();
    });

    it("markTargetHit を露出し、呼ぶと渡したコールバックが走る（R-20 用 test hook）", () => {
      let called = 0;
      const cleanup = installTestSeam(
        () => createSession(),
        () => {
          called += 1;
        },
      );
      window.__aimTest?.markTargetHit();
      expect(called).toBe(1);
      cleanup();
    });
  });
});
