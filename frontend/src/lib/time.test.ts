import { afterEach, describe, expect, it, vi } from "vitest";

import { now } from "./time";

describe("now", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("performance.now() を返す（単調時計のラッパー）", () => {
    const spy = vi.spyOn(performance, "now").mockReturnValue(1234.5);
    expect(now()).toBe(1234.5);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("Date.now ではなく performance.now を計測に使う（差し替え可能なシーム）", () => {
    const perfSpy = vi.spyOn(performance, "now").mockReturnValue(42);
    const dateSpy = vi.spyOn(Date, "now").mockReturnValue(999999);
    expect(now()).toBe(42);
    expect(dateSpy).not.toHaveBeenCalled();
    perfSpy.mockRestore();
    dateSpy.mockRestore();
  });
});
