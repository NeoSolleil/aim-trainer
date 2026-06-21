/**
 * ShootingSessionContainer（Smart・薄く）— 射撃セッションのオーケストレーション。
 *
 * 責務:
 * - セッション状態（lib/session の純粋関数 ＋ useReducer）。
 * - タイマー（rAF ＋ lib/clock.now で tick → finished。R-7）。
 * - クリック（GameCanvas の座標 → registerClick。領域判定・計上規則は lib/session。R-1〜R-8/R-20/21/22）。
 * - 終了検知（finished）→ submitSession を1回実行（Rule 11）。中断は submit しない（R-17）。
 * - 「もう一度」で 0 リセットして新規開始（R-10）。
 * - Canvas 描画は canvas/renderer に ref 経由で委譲（React state に乗せない）。
 * - E2E テストシーム（window.__aimTest）の取り付け（本番無効）。
 *
 * 状態は React、描画は ref。lib に startSession は無いのでコンテナが開始時に spawnTarget で初期化する。
 */

import { useCallback, useEffect, useReducer, useRef } from "react";

import { useSubmitSession } from "../api/submitSession";
import { startRenderLoop } from "../canvas/renderer";
import { now as clockNow } from "../lib/clock";
import {
  createSession,
  registerClick,
  spawnTarget,
  tick,
  TIME_LIMIT_MS,
  type SessionState,
} from "../lib/session";
import { computeAccuracy, computeAvgReactionTime, formatAccuracy, formatAvg } from "../lib/summary";
import { installTestSeam } from "../lib/testSeam";
import { GameCanvas } from "./GameCanvas";
import { PlayAgainButton } from "./PlayAgainButton";
import { ResultSummary } from "./ResultSummary";
import { SaveErrorNotice } from "./SaveErrorNotice";
import { StartButton } from "./StartButton";

type Action =
  | { readonly type: "start"; readonly now: number }
  | { readonly type: "click"; readonly x: number; readonly y: number; readonly now: number }
  | { readonly type: "tick"; readonly now: number }
  // テスト専用: 現在の的を「ヒット済み」状態にする（R-20 の再クリック無視を E2E から検証可能にする）。
  // 通常フローでは hit 後に即 respawn するため target.hit=true は発生しない。production では露出しない。
  | { readonly type: "__test_markTargetHit" };

function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "start":
      // 「もう一度」もここを通る＝hits/total_clicks/reaction_times を 0 に戻して新規開始（R-10）。
      return {
        status: "running",
        startedAt: action.now,
        hits: 0,
        totalClicks: 0,
        reactionTimes: [],
        target: spawnTarget(action.now, Math.random),
      };
    case "click":
      return registerClick(state, { x: action.x, y: action.y }, action.now, Math.random);
    case "tick":
      return tick(state, action.now);
    case "__test_markTargetHit":
      return { ...state, target: { ...state.target, hit: true } };
  }
}

export function ShootingSessionContainer() {
  const [state, dispatch] = useReducer(reducer, undefined, createSession);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { submit, error, reset: resetSubmit } = useSubmitSession();

  // 描画・シームが最新状態を読めるよう ref に保つ（React 再レンダーに依存しない）。
  const stateRef = useRef(state);
  stateRef.current = state;

  // 完了セッションを二重 submit しないためのフラグ。
  const submittedRef = useRef(false);

  // 描画ループ（rAF）。canvas マウント中だけ回す。
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }
    const handle = startRenderLoop(
      ctx,
      () => stateRef.current,
      () => clockNow(),
    );
    return () => handle.stop();
    // status の変化で canvas のマウント有無が変わるため依存に含める。
  }, [state.status]);

  // タイマー: running の間 rAF で tick し、30 秒で finished へ（R-7）。
  useEffect(() => {
    if (state.status !== "running") {
      return;
    }
    let rafId = 0;
    const loop = (): void => {
      dispatch({ type: "tick", now: clockNow() });
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [state.status]);

  // 終了検知 → 完了セッションのみ1回 submit（Rule 11・R-17: 中断は送らない）。
  useEffect(() => {
    if (state.status !== "finished" || submittedRef.current) {
      return;
    }
    submittedRef.current = true;
    void submit({
      hits: state.hits,
      totalClicks: state.totalClicks,
      reactionTimes: state.reactionTimes,
      // 完了セッションは制限時間まで走り切っている（R-7）。
      timeLimitMs: TIME_LIMIT_MS,
    });
  }, [state.status, state.hits, state.totalClicks, state.reactionTimes, submit]);

  // テストシーム取り付け（本番無効）。最新状態は ref から読む。
  // markTargetHit は R-20（ヒット済みの的の再クリック無視）を E2E から再現するための test-only hook。
  useEffect(
    () =>
      installTestSeam(
        () => stateRef.current,
        () => dispatch({ type: "__test_markTargetHit" }),
      ),
    [],
  );

  const handleStart = useCallback(() => {
    submittedRef.current = false;
    dispatch({ type: "start", now: clockNow() });
  }, []);

  const handleCanvasClick = useCallback((x: number, y: number) => {
    dispatch({ type: "click", x, y, now: clockNow() });
  }, []);

  const handlePlayAgain = useCallback(() => {
    submittedRef.current = false;
    resetSubmit();
    dispatch({ type: "start", now: clockNow() });
  }, [resetSubmit]);

  const accuracyText = formatAccuracy(computeAccuracy(state.hits, state.totalClicks));
  const avgText = formatAvg(computeAvgReactionTime(state.reactionTimes));

  return (
    <main className="mx-auto flex max-w-3xl flex-col items-center gap-4 p-4">
      <h1 className="text-2xl font-bold text-text">Aim Trainer</h1>

      {state.status === "idle" && <StartButton onStart={handleStart} />}

      {state.status === "running" && (
        <GameCanvas ref={canvasRef} onCanvasClick={handleCanvasClick} />
      )}

      {state.status === "finished" && (
        <section className="flex flex-col items-center gap-4">
          <ResultSummary
            accuracyText={accuracyText}
            avgText={avgText}
            hits={state.hits}
            totalClicks={state.totalClicks}
          />
          <SaveErrorNotice show={error !== undefined} />
          <PlayAgainButton onPlayAgain={handlePlayAgain} />
        </section>
      )}
    </main>
  );
}
