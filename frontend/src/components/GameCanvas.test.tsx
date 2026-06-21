import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GameCanvas } from "./GameCanvas";

describe("GameCanvas", () => {
  it("data-testid game-canvas を持つ canvas を描く", () => {
    render(<GameCanvas onCanvasClick={vi.fn()} />);
    const canvas = screen.getByTestId("game-canvas");
    expect(canvas.tagName).toBe("CANVAS");
  });

  it("クリック座標をプレイ領域基準で親へ通知する", () => {
    const onCanvasClick = vi.fn();
    render(<GameCanvas onCanvasClick={onCanvasClick} />);
    const canvas = screen.getByTestId("game-canvas");
    // jsdom は getBoundingClientRect が 0 を返すため scale=1・rect.left/top=0。
    canvas.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 100, clientY: 50 }));
    expect(onCanvasClick).toHaveBeenCalledWith(100, 50);
  });
});
