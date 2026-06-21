/**
 * StartButton（atom・Dumb）— セッション開始トリガ（R-7 の開始）。
 * props だけで描画し、クリックは親へ通知する。
 */

export interface StartButtonProps {
  readonly onStart: () => void;
  readonly disabled?: boolean;
}

export function StartButton({ onStart, disabled = false }: StartButtonProps) {
  return (
    <button
      type="button"
      data-testid="start-button"
      onClick={onStart}
      disabled={disabled}
      className="rounded-md bg-primary px-4 py-2 font-medium text-text disabled:opacity-50"
    >
      スタート
    </button>
  );
}
