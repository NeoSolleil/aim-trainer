/**
 * SaveErrorNotice（molecule・Dumb）— 保存失敗通知（R-16）。
 * `show` が true のときだけ通知を出す。サマリ自体は別途表示され続ける（R-16）。
 */

export interface SaveErrorNoticeProps {
  readonly show: boolean;
}

export function SaveErrorNotice({ show }: SaveErrorNoticeProps) {
  if (!show) {
    return null;
  }
  return (
    <p
      data-testid="save-error-notice"
      role="alert"
      className="rounded-md bg-surface px-4 py-2 text-danger"
    >
      スコアの保存に失敗しました
    </p>
  );
}
