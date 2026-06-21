import { describe, expect, it, vi } from "vitest";

import { createSession, spawnTarget } from "../lib/session";
import { drawFrame } from "./renderer";

/** drawFrame が触る最小限の 2D コンテキストのモック。 */
function fakeCtx(): CanvasRenderingContext2D {
  return {
    fillStyle: "",
    font: "",
    textBaseline: "top",
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
  } as unknown as CanvasRenderingContext2D;
}

describe("drawFrame", () => {
  it("running 中は的を1つ描く（arc を1回呼ぶ）", () => {
    const ctx = fakeCtx();
    const state = {
      ...createSession(),
      status: "running" as const,
      startedAt: 0,
      target: spawnTarget(0, () => 0.5),
    };
    drawFrame(ctx, state, 1000);
    expect(ctx.arc).toHaveBeenCalledTimes(1);
    expect(ctx.fillRect).toHaveBeenCalled();
    expect(ctx.fillText).toHaveBeenCalled();
  });

  it("idle 中は的を描かない（arc を呼ばない）", () => {
    const ctx = fakeCtx();
    drawFrame(ctx, createSession(), 0);
    expect(ctx.arc).not.toHaveBeenCalled();
  });
});
