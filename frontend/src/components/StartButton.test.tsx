import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PlayAgainButton } from "./PlayAgainButton";
import { StartButton } from "./StartButton";

describe("StartButton", () => {
  it("クリックで onStart を呼ぶ（R-7 開始トリガ）", async () => {
    const onStart = vi.fn();
    render(<StartButton onStart={onStart} />);
    await userEvent.click(screen.getByTestId("start-button"));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("disabled のときは押せない", async () => {
    const onStart = vi.fn();
    render(<StartButton onStart={onStart} disabled />);
    await userEvent.click(screen.getByTestId("start-button"));
    expect(onStart).not.toHaveBeenCalled();
  });
});

describe("PlayAgainButton", () => {
  it("クリックで onPlayAgain を呼ぶ（R-10）", async () => {
    const onPlayAgain = vi.fn();
    render(<PlayAgainButton onPlayAgain={onPlayAgain} />);
    await userEvent.click(screen.getByTestId("play-again-button"));
    expect(onPlayAgain).toHaveBeenCalledTimes(1);
  });
});
