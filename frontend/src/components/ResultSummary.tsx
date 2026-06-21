/**
 * ResultSummary（organism・Dumb）— 結果サマリ表示（R-9/R-18/R-19）。
 *
 * props だけで描画する。表示文字列（"62.5%" / "—" / "400 ms"）の整形は呼び出し側が
 * `lib/summary.format*` で済ませて `accuracyText`/`avgText` として渡す（null→"—" は format が担う）。
 * hits/total_clicks は "5/8" 形式で表示する。数値は tabular-nums で桁揃え。
 */

export interface ResultSummaryProps {
  readonly accuracyText: string;
  readonly avgText: string;
  readonly hits: number;
  readonly totalClicks: number;
}

export function ResultSummary({ accuracyText, avgText, hits, totalClicks }: ResultSummaryProps) {
  return (
    <dl className="grid grid-cols-2 gap-2 tabular-nums text-text">
      <dt className="text-muted">命中率</dt>
      <dd data-testid="summary-accuracy">{accuracyText}</dd>
      <dt className="text-muted">平均反応時間</dt>
      <dd data-testid="summary-avg">{avgText}</dd>
      <dt className="text-muted">ヒット数</dt>
      <dd data-testid="summary-hits">{`${hits}/${totalClicks}`}</dd>
    </dl>
  );
}
