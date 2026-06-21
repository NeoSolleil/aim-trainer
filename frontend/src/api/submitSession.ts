/**
 * submitSession — 完了セッションの生データを backend に提出する（POST /api/sessions）。
 *
 * Rule 11: 完了時に1回だけ送る。中断は送らない（R-17 はコンテナが finished 時のみ呼ぶ）。
 * fetch 直書きは api/ に集約する（components から fetch しない）。
 * 送信ボディは生データのみ。accuracy/avg/gunId/createdAt は送らない（domain が算出・
 * サーバが付与する＝design §3.3）。
 *
 * SWR の書き込みフックとして `useSubmitSession` を提供し、`isMutating`/`error` を露出する
 * （R-16 の保存失敗通知は UI が `error` を拾って出す）。
 */

import useSWRMutation from "swr/mutation";

/** POST /api/sessions の送信ボディ（生データのみ）。 */
export interface SubmitSessionBody {
  readonly hits: number;
  readonly totalClicks: number;
  readonly reactionTimes: readonly number[];
  readonly timeLimitMs: number;
}

/**
 * 採点済み score のレスポンス（design §3.3）。
 * accuracy / avgReactionTime は未定義（total_clicks=0 / hits=0）で null。
 */
export interface ScoreResponse {
  readonly id: number;
  readonly hits: number;
  readonly totalClicks: number;
  readonly accuracy: number | null;
  readonly avgReactionTime: number | null;
  readonly timeLimitMs: number;
  readonly gunId: number;
  readonly createdAt: string;
}

/** 提出先エンドポイント。 */
export const SUBMIT_SESSION_URL = "/api/sessions";

/** HTTP エラー（非 2xx）。R-16 の保存失敗通知の判定に使う。 */
export class SubmitSessionError extends Error {
  readonly status: number;
  constructor(status: number) {
    super(`セッションの保存に失敗しました (status ${status})`);
    this.name = "SubmitSessionError";
    this.status = status;
  }
}

/**
 * 生データを提出して採点済み score を受け取る。非 2xx は `SubmitSessionError` を投げる
 * （SWR mutation の error に乗り、UI が通知を出す）。snake_case のサーバ JSON を
 * camelCase の `ScoreResponse` へ変換する。
 */
export async function submitSession(body: SubmitSessionBody): Promise<ScoreResponse> {
  const response = await fetch(SUBMIT_SESSION_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hits: body.hits,
      total_clicks: body.totalClicks,
      reaction_times: body.reactionTimes,
      time_limit_ms: body.timeLimitMs,
    }),
  });

  if (!response.ok) {
    throw new SubmitSessionError(response.status);
  }

  const json: unknown = await response.json();
  return toScoreResponse(json);
}

/** サーバ JSON（snake_case）を `ScoreResponse`（camelCase）へ変換する。 */
function toScoreResponse(json: unknown): ScoreResponse {
  if (typeof json !== "object" || json === null) {
    throw new SubmitSessionError(200);
  }
  const raw = json as Record<string, unknown>;
  return {
    id: asNumber(raw.id),
    hits: asNumber(raw.hits),
    totalClicks: asNumber(raw.total_clicks),
    accuracy: asNullableNumber(raw.accuracy),
    avgReactionTime: asNullableNumber(raw.avg_reaction_time),
    timeLimitMs: asNumber(raw.time_limit_ms),
    gunId: asNumber(raw.gun_id),
    createdAt: asString(raw.created_at),
  };
}

function asNumber(value: unknown): number {
  return typeof value === "number" ? value : Number(value);
}

function asNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return asNumber(value);
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : String(value);
}

/** SWR mutation フックの戻り値（コンテナが使う最小インターフェース）。 */
export interface UseSubmitSessionResult {
  readonly submit: (body: SubmitSessionBody) => Promise<ScoreResponse | undefined>;
  readonly isMutating: boolean;
  readonly error: Error | undefined;
  readonly reset: () => void;
}

/**
 * セッション提出の SWR mutation フック。`isMutating`/`error` を扱う（R-16）。
 * `submit` は body を渡して提出する。`reset`（key の cache をクリア）で「もう一度」時に
 * 前回の error をクリアできる（R-10）。
 */
export function useSubmitSession(): UseSubmitSessionResult {
  const { trigger, isMutating, error, reset } = useSWRMutation<
    ScoreResponse,
    Error,
    typeof SUBMIT_SESSION_URL,
    SubmitSessionBody
  >(SUBMIT_SESSION_URL, (_key, { arg }) => submitSession(arg));

  return {
    submit: (body) => trigger(body),
    isMutating,
    error,
    reset,
  };
}
