# 射撃セッション（Shooting Session）— Requirements

Feature: 0001-shooting-session
Status: Approved        <!-- 2026-06-21 人間承認済み。plan はこれが Approved で着手 -->

承認済み `discovery.md`（Status: Approved）を清書した EARS 要件の台帳。各要件には `acceptance.feature` の Gherkin シナリオが `@R-x` タグでぶら下がる。要件は観測可能な振る舞いのみを規定し、実装（フロント／バックの分担・`performance.now`・エンドポイント形・永続化技術）は plan 段階に委ねる。

---

## 概要

FPS のエイムを鍛えたいプレイヤーが、画面に出る target を撃って自分の reaction_time と accuracy を1回の session で測れる。起動 → 撃つ → 結果を見る、までが一直線で完結する最小ループ。1回の session の開始 → target の spawn → クリック判定（hit / miss）→ 制限時間での自動終了 → 結果サマリ表示 → 完了 session の score 保存、までを範囲とする。

---

## スコープ

### 含む
- 1回の session の開始 → target の spawn（常に1つ）→ クリック判定（hit / miss）→ 終了 → 結果表示の1サイクル。
- target 内側クリック ＝ hit、reaction_time（spawn からクリックまで、ms）を記録。
- target 外側クリック ＝ miss。
- 制限時間（30秒）での自動終了。
- 終了時のサマリ表示（accuracy・平均 reaction_time・hits/total_clicks）。
- 完了した session の score 保存（accuracy・平均 reaction_time・hits・total_clicks・日時など）。
- 生データ（hits・total_clicks・hit 群の reaction_time）からの accuracy・平均 reaction_time の算出と不変条件の検証。

### 含まない
- 銃の選択 UI・銃挙動（fire_rate / recoil / 可変 target サイズ） → 0002。
- 成績推移・履歴一覧・グラフ・スコア一覧／推移取得 → 0003。
- 認証（JWT）・ランキング・ユーザー識別 → 0004。
- target の寿命・複数同時表示・移動する target → 将来。
- 難易度／target サイズ／出現間隔／制限時間の設定 UI → 将来（MVP は30秒固定の1パターン）。
- チート検証（署名付き spawn 等） → 0004 以降。
- ヒット毎の明細イベント保存 → 集約1行で足りる。要求が出れば非破壊で後付け。
- reaction_time 外れ値（タブ非アクティブ等）の特別処理 → 将来課題。

---

## 要件（EARS）

> 表記: EARS のキーワード（`WHEN` / `WHILE` / `WHERE` / `IF` / `THEN` / `the system SHALL` / `SHALL NOT`）は英語、条件と応答の本文は日本語で書く（Gherkin と同じ方針）。主語は `the system`（本機能＝射撃セッション）。値は測定可能な単位（ms・px・回数）で書き、target は中心と radius（px）を持つ円とする。用語（target / hit / miss / reaction_time / accuracy / total_clicks / session / score / gun / spawn / created_at）は用語集の識別子に従う。

### Rule 1 由来 — 内側クリックは hit、reaction_time を記録

- **R-1** WHEN 的が存在し、プレイヤーが的の中心からの距離が radius 以下の位置をクリックする, the system SHALL ヒットを記録し、total_clicks を 1 増やし、その的の spawn からクリックまでの時間を reaction_time としてミリ秒（ms）で記録する。
- **R-2** WHERE 的にヒットしたクリックが的の spawn と同一フレームで発生する場合, the system SHALL reaction_time として 0ms を有効値で記録する。また the system SHALL NOT 負の reaction_time を記録する。

### Rule 2 由来 — 外側クリックは miss（reaction_time は記録しない）

- **R-3** WHEN 的が存在し、プレイヤーが的の中心からの距離が radius より大きい位置をクリックする, the system SHALL ミスを記録し、total_clicks を 1 増やし、ヒット数を変更しない。また the system SHALL NOT そのクリックに reaction_time を記録する。
- **R-4** WHEN プレイヤーが空白領域を連続して複数回クリックする, the system SHALL そのすべてのクリックを miss として total_clicks に計上する。また the system SHALL NOT 連続するクリックの間でデバウンスやクールダウンを行う。

### Rule 3 由来 — hit されたら次の target を spawn（常に1つ・移動なし・寿命なし）

- **R-5** WHEN 的がヒットされる, the system SHALL 次の的をちょうど 1 つ spawn する。
- **R-6** WHILE セッションが進行中である間, the system SHALL 的をちょうど 1 つ存在させ、その的をヒットされるまで同じ位置に保つ。また the system SHALL NOT 経過時間によって的を移動または消滅させる。

### Rule 4 由来 — 制限時間（30秒）で自動終了

- **R-7** WHILE セッションが進行中で, WHEN セッション開始から 30 秒が経過する, the system SHALL セッションを終了し、結果集計に進む。
- **R-8** WHEN クリックがセッション終了時刻ちょうどに到達する, the system SHALL そのクリックを集計に含める。WHEN クリックがセッション終了時刻より後に到達する, the system SHALL そのクリックを集計から除外する。

### Rule 5 由来 — 終了時に結果サマリを表示

- **R-9** WHEN セッションが終了する, the system SHALL accuracy・平均 reaction_time・hits/total_clicks を含む結果サマリを表示する。
- **R-10** WHERE 結果サマリが表示されている場合, WHEN プレイヤーが「もう一度」を選ぶ, the system SHALL hits・total_clicks・記録された reaction_time を 0 にリセットして新しいセッションを開始する。

### Rule 6 由来 — 生データ送信、システムが算出・検証

- **R-11** WHEN 完了したセッションの生データ（hits・total_clicks・ヒットの reaction_time 群）が提出される, the system SHALL accuracy を hits ÷ total_clicks として算出する。
- **R-12** WHEN 完了したセッションの生データが提出される, the system SHALL 平均 reaction_time を、miss のクリックを除外しヒットのクリックのみで算出する。
- **R-13** IF 提出された集計データが不変条件（accuracy が 0〜1 の範囲外、hits が total_clicks より大きい、いずれかの reaction_time が 0 未満）に違反する, THEN the system SHALL その提出を拒否する。また the system SHALL NOT score を永続化する。

### Rule 7 由来 — 集約1行で永続化、created_at はシステム付与、失敗は通知

- **R-14** WHEN 完了したセッションの提出が検証を通過する, the system SHALL accuracy・平均 reaction_time・hits・total_clicks・セッションの制限時間・既定の gun 参照を含む score をちょうど 1 行だけ永続化する。また the system SHALL NOT ヒット毎の reaction_time 明細を永続化する。
- **R-15** WHEN score が永続化される, the system SHALL created_at のタイムスタンプを自身で付与する。また the system SHALL NOT クライアントが申告した時刻を created_at に使用する。
- **R-16** IF score の永続化に失敗する, THEN the system SHALL 結果サマリを表示したままにし、保存に失敗したことをプレイヤーに通知する。

### Rule 8 由来 — 完了 session のみ保存

- **R-17** IF セッションが制限時間 30 秒に達する前に終了する, THEN the system SHALL NOT そのセッションの score を永続化する。

### Rule 9 由来 — 空・ゼロ値でも破綻しない（0除算回避）

- **R-18** WHEN セッションが total_clicks = 0 で終了する, the system SHALL accuracy と平均 reaction_time をそれぞれ数値の代わりに「—」（em ダッシュ）で表示し、score を永続化する。
- **R-19** WHEN セッションが hits = 0 かつ total_clicks > 0 で終了する, the system SHALL accuracy を 0% で表示し、平均 reaction_time を「—」（em ダッシュ）で表示する。

### Rule 10 由来 — total_clicks に計上しないクリック

- **R-20** WHEN プレイヤーがヒット済みの的を再びクリックする, the system SHALL そのクリックを無視し、hits と total_clicks を変更しない。
- **R-21** WHEN プレイヤーがキャンバスのプレイ領域外、または HUD/ボタン領域をクリックする, the system SHALL そのクリックを集計上無視し、hits と total_clicks を変更しない。
- **R-22** WHEN プレイヤーがセッション終了後にクリックする, the system SHALL そのクリックを無視し、hits と total_clicks を変更しない。

> Rule 11（判定・計測の責務／ステートレスサーバ／`performance.now`）は設計の前提として扱う。観測可能な振る舞い部分は R-1（reaction_time を ms で記録）・R-15（created_at をシステムが付与）に反映済み。判定主体・単調時計・エンドポイント形は plan で具体化する。

---

## トレーサビリティ（Rule → 要件）

| discovery Rule | 要件 |
| --- | --- |
| Rule 1 | R-1, R-2 |
| Rule 2 | R-3, R-4 |
| Rule 3 | R-5, R-6 |
| Rule 4 | R-7, R-8 |
| Rule 5 | R-9, R-10 |
| Rule 6 | R-11, R-12, R-13 |
| Rule 7 | R-14, R-15, R-16 |
| Rule 8 | R-17 |
| Rule 9 | R-18, R-19 |
| Rule 10 | R-20, R-21, R-22 |
| Rule 11 | （設計の前提。R-1・R-15 に振る舞いを反映） |

要件↔シナリオの正式な紐付けは `acceptance.feature` の `@R-x` タグ。

---

## 用語

`ubiquitous-language`（用語集）を参照。本機能で使う用語: target / spawn / hit / miss / reaction_time / accuracy / total_clicks / session / score / gun。`total_clicks`（accuracy の分母 ＝ hit ＋ 空白 miss の合計）は discovery で用語集へ追加済み。新規追加語なし。
