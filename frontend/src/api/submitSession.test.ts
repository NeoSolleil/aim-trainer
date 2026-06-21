import { afterEach, describe, expect, it, vi } from "vitest";

import { submitSession, SubmitSessionError, SUBMIT_SESSION_URL } from "./submitSession";

const body = {
  hits: 5,
  totalClicks: 8,
  reactionTimes: [300, 320, 280, 350, 290],
  timeLimitMs: 30000,
};

function mockFetch(impl: typeof fetch): void {
  vi.stubGlobal("fetch", vi.fn(impl));
}

describe("submitSession", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("生データを snake_case で POST する（accuracy/avg/gunId/createdAt は送らない）", async () => {
    const fetchSpy = vi.fn<typeof fetch>(async () => {
      return new Response(
        JSON.stringify({
          id: 1,
          hits: 5,
          total_clicks: 8,
          accuracy: 0.625,
          avg_reaction_time: 308,
          time_limit_ms: 30000,
          gun_id: 1,
          created_at: "2026-06-21T00:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchSpy);

    await submitSession(body);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe(SUBMIT_SESSION_URL);
    const sent = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(sent).toEqual({
      hits: 5,
      total_clicks: 8,
      reaction_times: [300, 320, 280, 350, 290],
      time_limit_ms: 30000,
    });
    expect(sent).not.toHaveProperty("accuracy");
    expect(sent).not.toHaveProperty("avg_reaction_time");
    expect(sent).not.toHaveProperty("gun_id");
    expect(sent).not.toHaveProperty("created_at");
  });

  it("レスポンスを camelCase の ScoreResponse へ変換する（null 許容）", async () => {
    mockFetch(async () => {
      return new Response(
        JSON.stringify({
          id: 7,
          hits: 0,
          total_clicks: 0,
          accuracy: null,
          avg_reaction_time: null,
          time_limit_ms: 30000,
          gun_id: 1,
          created_at: "2026-06-21T00:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    });

    const result = await submitSession({ ...body, hits: 0, totalClicks: 0, reactionTimes: [] });
    expect(result.id).toBe(7);
    expect(result.accuracy).toBeNull();
    expect(result.avgReactionTime).toBeNull();
    expect(result.gunId).toBe(1);
    expect(result.createdAt).toBe("2026-06-21T00:00:00Z");
  });

  it("非 2xx は SubmitSessionError を投げる（R-16 の保存失敗）", async () => {
    mockFetch(async () => new Response("boom", { status: 500 }));
    await expect(submitSession(body)).rejects.toBeInstanceOf(SubmitSessionError);
  });

  it("SubmitSessionError は status を保持する", async () => {
    mockFetch(async () => new Response("nope", { status: 422 }));
    await expect(submitSession(body)).rejects.toMatchObject({ status: 422 });
  });
});
