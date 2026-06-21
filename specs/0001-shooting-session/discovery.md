# 射撃セッション（Shooting Session）— Discovery

Feature: 0001-shooting-session
Status: Approved        <!-- 2026-06-21 人間承認済み。specify は Approved のみ着手 -->

スリーアミーゴス（product / quality / solution-analyst）で Example Mapping を行い、進行役が統合・人間ゲートで 🔴 を解決した発見メモ。次段階 `specify` がこれを EARS 要件＋Gherkin に清書する。

---

## Story / 価値

**FPSのエイムを鍛えたいプレイヤーが、画面に出る的（target）を撃って自分の reaction_time と accuracy を1回の session で測れる。** なぜなら「今どれだけ速く正確に狙えているか」を数値で見ないと、上達しているか分からないから。

提供価値:
- 漠然とした「うまくなりたい」を、セッション終了時の客観指標（命中率・平均反応時間）に変える。
- 銃選択も履歴もログインも要らず、**起動 → 撃つ → 結果を見る**まで一直線。練習1回が完結する最小ループ。
- この1機能だけで「今日のスコア」が出る ＝ 単体で価値が立つ縦切り。比較(0003)や銃差(0002)は無くても「測れる」こと自体が価値。

---

## スコープ

### 含む
- 1回の session の開始 → target の spawn（常に1つ）→ クリック判定（hit / miss）→ 終了 → 結果表示の1サイクル。
- target 内側クリック ＝ hit、reaction_time（spawn からクリックまで, ms）を記録。
- target 外側クリック ＝ miss。
- 制限時間（MVP=30秒）での自動終了。
- 終了時のサマリ表示（accuracy・平均 reaction_time・hits/total_clicks）。
- 完了した session の score 保存（accuracy・平均 reaction_time・日時など）。

### 含まない（送り先 / 理由）
- 銃の選択UI・銃挙動（fire_rate / recoil / 可変的サイズ）→ **0002**。挙動差を測るのは「測れる土台」が出来てから。
- 成績推移・履歴一覧・グラフ（複数 score の比較）→ **0003**。「1回出す」までが 0001、「並べて見る」は別価値。
- 認証(JWT)・ランキング・ユーザー識別 → **0004**。個人ローカル練習なので「誰の」を識別せずとも価値が出る。
- 的の寿命・複数同時表示・移動する的 → 将来。MVPは常に1つの静止的で「測れる」に十分。
- 難易度／的サイズ／出現間隔の調整UI、制限時間の設定UI → 将来。MVPは固定値1パターン（30秒）。
- チート検証（署名付き spawn 等）→ ランキング(0004)で初めて意味を持つ。学習用 MVP では over-engineering。
- ヒット毎の明細イベントテーブル → 集約1行で足り、要求が出たら非破壊で後付け可能。
- スコアの一覧／推移取得 API・グラフ → 0003。0001 のサマリは画面 state から表示し、読み取り API を作り込まない。

---

## Example Map

座標は説明用に「中心(400,300)・半径20px」を仮基準（実値は plan で確定）。🟢 は後の Gherkin シナリオ、🔵 は後の EARS 要件の素。

### Rule 1: 的の内側クリックは hit で reaction_time を記録
内側＝中心からの距離 ≤ radius。
- 🟢(正常) target が spawn し 320ms 後に中心(400,300)をクリック → hit、reaction_time=320ms
- 🟢(境界) 中心からの距離 20.0px ちょうど → hit（`distance ≤ radius` を内側とする）／距離 21px → miss
- 🟢(境界) reaction_time=0ms（spawn と同フレームで命中）→ hit、0ms を有効値として記録（負値は発生しない）

### Rule 2: 的の外側クリックは miss（reaction_time は記録しない）
- 🟢(正常) target がある状態で空白座標(10,10)をクリック → miss、total_clicks+1、hits 不変、accuracy 低下
- 🟢(境界) 空白を 100ms 内に5連打 → 5 miss、すべて total_clicks に計上（デバウンス／クールダウンなし）

### Rule 3: hit されたら次の的を spawn（常に1つ・移動なし・寿命なし）
- 🟢 hit 直後に次の target が1つ出現し、制限時間内は撃ち続けられる
- target は hit されるまで残る（一定時間で消えない）。同時に存在する的は常に1つ。

### Rule 4: 制限時間（30秒）でセッション自動終了
- 🟢(正常) スタート押下から30秒経過 → セッション終了、結果集計へ
- 🟢(境界) 終了時刻 t_end ちょうどに届いたクリックは集計に含める（包含）。t_end 超過・終了後のクリックは破棄

### Rule 5: 終了時に結果サマリを表示
accuracy・平均 reaction_time・hits/total_clicks を提示（＝「測れた」の核）。
- 🟢(正常) hits=5・total_clicks=8 → accuracy 62.5%、平均 reaction_time = hit 5件の平均
- 🟢 結果画面から「もう一度」で再挑戦できる（クライアント完結・新規セッション開始）

### Rule 6: 集計はクライアントが生データを送り、サーバの domain が算出・検証
- クライアントは `hits`・`total_clicks`・`hit群の reaction_time` を終了時に送信。
- サーバの domain（値オブジェクト）が `accuracy = hits ÷ total_clicks` と平均 reaction_time を算出し、不変条件（`0 ≤ accuracy ≤ 1`・`hits ≤ total_clicks`・`reaction_time ≥ 0`）を検証する。
- 🟢(異常) `hits > total_clicks` 等の不整合な申告 → サーバは保存を拒否（422/400 相当）

### Rule 7: スコアは集約1行で永続化
- 保存項目（候補。最終は plan）: accuracy・平均 reaction_time・hits・total_clicks・session設定（制限時間30s）・gun_id・created_at（サーバ付与）。
- gun_id は既定銃（seed 済み1件）を**固定参照**（NOT NULL）。ユーザーには銃を出さない。
- 永続化は SQLAlchemy ORM 経由のみ（直接SQL禁止）。明細リスト（各 reaction_time）は永続化しない。
- 🟢(正常) 30秒完走 → score 1行 INSERT
- 🟢(異常) 永続化失敗 → 結果は画面に表示しつつ「保存に失敗」を通知（結果自体は消さない）

### Rule 8: 完了セッションのみ保存（中断は破棄）
- 🟢 制限時間到達前にプレイヤーがやめる → その session の score は保存しない

### Rule 9: 空・ゼロ値でも破綻しない（0除算回避）
- 🟢(境界) 一度もクリックせず30秒経過 → total_clicks=0、accuracy「—」（未定義）、平均 reaction_time「—」、score は保存可
- 🟢(境界) クリックしたが全ミス（hits=0, total_clicks=8）→ accuracy=0%、平均 reaction_time「—」

### Rule 10: total_clicks に計上しないクリック
次は total_clicks（accuracy 分母）に数えない:
- ① hit 済み target の再クリック（2回目以降は無効）
- ② キャンバス領域外・HUD/ボタン領域のクリック
- ③ セッション終了後のクリック
- 🟢 同じ target を2回クリック → 2回目は無視（hits・total_clicks 不変）
- 🟢 キャンバス外(-5,-5) → 無視

### Rule 11: 判定と計測の責務（アーキテクチャ制約）
- hit/miss 判定と reaction_time 計測はクライアント（Canvas・`performance.now()` の単調時計）で行う。壁時計（`Date.now()`）は計測に使わない。
- サーバは**ステートレス**。進行中セッションの状態を持たず、終了時に1回だけ確定データを受け取り検証・永続化する。
- created_at はサーバが付与する（計測値以外でクライアント時刻を信用しない）。
- ※ これは設計の前提。API 契約としての具体化は specify / plan。

---

## 解決済みの疑問

### Group A（構造を分岐させる決定）
- **Q: 終了条件は制限時間か的数か** → **A: 制限時間（MVP=30秒）**。根拠: 一定時間でどれだけ捌けたかは直感的で、毎回の所要時間が一定 ＝ 0003 の推移比較がブレにくい。的数制は上手いほど母数（total_clicks）が変わり比較が不安定。秒数の最終値は plan。
- **Q: 0001 で gun をどう扱うか（score は gun FK を持つか）** → **A: 既定銃を1行 seed し、`score.gun_id` を NOT NULL でその固定 ID 参照**。根拠: スキーマを最初から最終形にすれば 0002 は「選択肢追加」だけで破壊的変更なし。将来の PostgreSQL 移行でも制約変更不要。0001 の UI に銃は出さない（不可視の固定値）。
- **Q: accuracy・平均 reaction_time の算出はどこで行うか** → **A: クライアントは生データ（hits・total_clicks・reaction_time 群）を送り、確定値と不変条件は domain 値オブジェクトで算出・検証**。根拠: 計算ロジックを domain に置けば不変条件を一箇所で守れ、純粋単体テストが書ける（CA の学習に厚い）。貧血ドメインを避ける。
- **Q: 開始と中断の扱い** → **A: スタートボタンで明示開始し、完了（30秒完走）したセッションのみ保存。中断は破棄**。根拠: reaction_time の起点を明確化。不完全な条件の score を混ぜず 0003 の比較を汚さない。

### Group B（推奨デフォルトを承認）
1. 的は常に1つ・寿命なし・移動なし（Rule 3）
2. `distance ≤ radius` を hit（縁ちょうどは当たり。実装は二乗距離比較を推奨）（Rule 1）
3. 空白クリックは miss 計上・デバウンスなし（Rule 2）
4. hit 済み的の再クリックは無効（total_clicks に数えない）（Rule 10）
5. 的ゼロの瞬間・キャンバス外・終了後のクリックは計上しない（Rule 10）
6. `accuracy = hits ÷ total_clicks`（用語集準拠。空白 miss は分母に入る）（Rule 6）
7. 平均 reaction_time は hit のみ。0ms は有効、負値は発生不可（Rule 1）
8. 0/0 は「—」表示（Rule 9）
9. reaction_time は `performance.now()`。タブ非アクティブの異常値は将来課題（特別扱いしない）（Rule 11）
10. score は集約1行のみ（ヒット明細テーブルなし）。created_at はサーバ付与（Rule 7）
11. サーバはステートレス・終了時1回 POST（Rule 11）
12. 0001 は保存まで（一覧/推移 API・グラフは 0003、サマリは画面 state から表示）
13. 永続化失敗時は結果表示＋失敗通知（Rule 7）

---

## 対象外と決めたこと
- 銃挙動（fire_rate / recoil / 可変的サイズ）＝ 0002
- 成績推移・履歴一覧・グラフ ＝ 0003
- 認証(JWT)・ランキング ＝ 0004
- 的の寿命・複数同時・移動する的 ＝ 将来
- チート検証（署名付き spawn 等）＝ 0004 以降
- ヒット明細イベントテーブル ＝ 要求が出れば非破壊で後付け
- スコア一覧／推移取得 API・グラフ ＝ 0003
- reaction_time 外れ値（タブ非アクティブ等）の特別処理 ＝ 将来課題
- 制限時間の設定UI ＝ 将来（MVPは30秒固定）

---

## 用語集への追加提案（ubiquitous-language）
- **total_clicks（総クリック数）**: accuracy の分母。hit ＋ 空白 miss の合計。次は数えない: hit 済み target の再クリック・キャンバス外/HUD クリック・セッション終了後クリック。
- 既存の `accuracy`（= hits ÷ total_clicks）・`reaction_time`・`session`・`score`・`gun`・`target`・`spawn`・`hit`・`miss` はそのまま使用（新規定義不要）。
- ※ specify 着手前に上記を用語集へ反映する（用語未定義のまま仕様を書かない）。

---

## plan / specify へ送る細目（発見では確定しない）
- 制限時間の確定値（MVP=30秒）と、残り時間カウントダウン表示の仕様（e2e 観点）。
- 既定銃 seed の投入方式（起動時 or マイグレーション）。
- score の最終保存カラム（accuracy / avg_reaction_time / hits / total_clicks / session設定 / gun_id / created_at）。
- API 契約の粒度（終了時 1 POST・エンドポイント名・入出力 DTO）。
- 結果画面「もう一度」の UX 詳細。
- distance 判定は二乗距離（`distance² ≤ radius²`）で平方根を回避（精度・速度）。

---

## Ready 判定（discover 完了基準）
- [x] 🔴 未解決の疑問がゼロ（Group A 4件＋Group B 13件すべて解決）
- [x] 🟡 価値が1文で言え、スコープの含む／含まないが明確
- [x] 🔵 が11件、各 🔵 に最低1つの 🟢
- [x] 人間が `Status: Approved` に変更（2026-06-21 承認済み）
