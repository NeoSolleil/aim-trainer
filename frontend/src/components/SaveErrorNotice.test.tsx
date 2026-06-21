import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SaveErrorNotice } from "./SaveErrorNotice";

describe("SaveErrorNotice", () => {
  it("show=false のときは何も表示しない", () => {
    render(<SaveErrorNotice show={false} />);
    expect(screen.queryByTestId("save-error-notice")).toBeNull();
  });

  it("show=true のとき保存失敗を通知する（R-16）", () => {
    render(<SaveErrorNotice show={true} />);
    expect(screen.getByTestId("save-error-notice")).toBeInTheDocument();
  });
});
