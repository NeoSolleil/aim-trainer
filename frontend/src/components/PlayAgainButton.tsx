/**
 * PlayAgainButton（atom・Dumb）— 「もう一度」（R-10）。
 * クリックを親へ通知し、親が状態を 0 リセットして新規開始する。
 */

export interface PlayAgainButtonProps {
  readonly onPlayAgain: () => void;
}

export function PlayAgainButton({ onPlayAgain }: PlayAgainButtonProps) {
  return (
    <button
      type="button"
      data-testid="play-again-button"
      onClick={onPlayAgain}
      className="rounded-md bg-primary px-4 py-2 font-medium text-text"
    >
      もう一度
    </button>
  );
}
