import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { formatAccuracy, formatAvg } from "../lib/summary";
import { ResultSummary } from "./ResultSummary";

describe("ResultSummary", () => {
  it("命中率・平均・ヒット数を表示する（R-9: 62.5% / 5/8）", () => {
    render(
      <ResultSummary
        accuracyText={formatAccuracy(0.625)}
        avgText={formatAvg(320)}
        hits={5}
        totalClicks={8}
      />,
    );
    expect(screen.getByTestId("summary-accuracy")).toHaveTextContent("62.5%");
    expect(screen.getByTestId("summary-avg")).toHaveTextContent("320 ms");
    expect(screen.getByTestId("summary-hits")).toHaveTextContent("5/8");
  });

  it("未定義（null）は「—」で表示する（R-18: total_clicks=0）", () => {
    render(
      <ResultSummary
        accuracyText={formatAccuracy(null)}
        avgText={formatAvg(null)}
        hits={0}
        totalClicks={0}
      />,
    );
    expect(screen.getByTestId("summary-accuracy")).toHaveTextContent("—");
    expect(screen.getByTestId("summary-avg")).toHaveTextContent("—");
    expect(screen.getByTestId("summary-hits")).toHaveTextContent("0/0");
  });

  it("全ミスは命中率 0%・平均は「—」（R-19）", () => {
    render(
      <ResultSummary
        accuracyText={formatAccuracy(0)}
        avgText={formatAvg(null)}
        hits={0}
        totalClicks={8}
      />,
    );
    expect(screen.getByTestId("summary-accuracy")).toHaveTextContent("0%");
    expect(screen.getByTestId("summary-avg")).toHaveTextContent("—");
    expect(screen.getByTestId("summary-hits")).toHaveTextContent("0/8");
  });
});
