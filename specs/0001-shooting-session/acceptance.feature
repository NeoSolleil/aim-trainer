# Status: Approved

Feature: シューティングセッション
  FPS のエイムを鍛えたいプレイヤーが、画面に出る target を撃って
  1回の session で自分の reaction_time と accuracy を測れる。
  起動 → 撃つ → 結果を見る、までが一直線で完結する最小ループ。

  # タグ規約:
  #   @R-x      対応する requirements.md の EARS 要件（全シナリオ必須）
  #   @e2e      動く UI（Canvas）の振る舞い: hit/miss 判定・reaction_time 計測・respawn・タイマー・サマリ表示
  #   @backend  domain の算出（accuracy・平均 reaction_time）・不変条件の検証・永続化

  Rule: 内側クリックは hit、reaction_time を記録（discovery Rule 1）

    @R-1 @e2e
    Scenario: 的の内側クリックはヒットで反応時間を記録する（正常）
      Given セッションが進行中である
      And 中心 (400,300)・半径 20px の的が出現している
      When プレイヤーが的の出現から 320ms 後に中心 (400,300) をクリックする
      Then システムはヒットを記録する
      And total_clicks が 1 になる
      And reaction_time として 320ms が記録される

    @R-1 @e2e
    Scenario: 縁ちょうど（距離 = 半径）はヒット（境界）
      Given セッションが進行中である
      And 中心 (400,300)・半径 20px の的が出現している
      When プレイヤーが中心からの距離が 20.0px ちょうどの位置をクリックする
      Then システムはヒットを記録する

    @R-3 @e2e
    Scenario: 半径をわずかに超える位置はミス（境界）
      Given セッションが進行中である
      And 中心 (400,300)・半径 20px の的が出現している
      When プレイヤーが中心からの距離が 21px の位置をクリックする
      Then システムはミスを記録する
      And reaction_time は記録されない

    @R-2 @e2e
    Scenario: 出現と同フレームのヒットは reaction_time 0ms を有効値として記録（境界）
      Given セッションが進行中である
      And 中心 (400,300)・半径 20px の的が出現している
      When プレイヤーが的の出現と同フレームで中心 (400,300) をクリックする
      Then システムはヒットを記録する
      And reaction_time として 0ms が記録される
      And 負の reaction_time は記録されない

  Rule: 外側クリックは miss、reaction_time は記録しない（discovery Rule 2）

    @R-3 @e2e
    Scenario: 空白座標のクリックはミスで命中率が下がる（正常）
      Given セッションが進行中で、中央に的が1つある
      When プレイヤーが空白座標 (10,10) をクリックする
      Then システムはミスを記録する
      And total_clicks が 1 増える
      And ヒット数は変化しない

    @R-4 @e2e
    Scenario: 空白の連打はデバウンスなしですべて total_clicks に計上（境界）
      Given セッションが進行中で、中央に的が1つある
      When プレイヤーが空白座標を 100ms 以内に 5 回連打する
      Then システムはミスを 5 回記録する
      And total_clicks が 5 増える

  Rule: hit されたら次の的を spawn・常に1つ（discovery Rule 3）

    @R-5 @e2e
    Scenario: ヒット直後に次の的が1つ出現する（正常）
      Given セッションが進行中で、中央に的が1つある
      When プレイヤーがその的をクリックしてヒットする
      Then 次の的が 1 つだけ出現する

    @R-6 @e2e
    Scenario: 的は寿命で消えず、ヒットされるまで残る（境界）
      Given セッションが進行中で、中央に的が1つある
      When プレイヤーがその的をクリックせずに 10 秒間待つ
      Then 同じ的が 1 つだけ残っている

  Rule: 制限時間 30 秒で自動終了（discovery Rule 4）

    @R-7 @e2e
    Scenario: スタートから 30 秒でセッションが自動終了する（正常）
      Given プレイヤーがセッションを開始した
      When 開始から 30 秒が経過する
      Then システムはセッションを終了する
      And 結果の集計に進む

    @R-8 @e2e
    Scenario: 終了時刻ちょうどのクリックは集計に含める（境界）
      Given セッションが進行中である
      When プレイヤーが終了時刻ちょうどに的をクリックする
      Then そのクリックは集計に含まれる

    @R-8 @e2e
    Scenario: 終了時刻を過ぎたクリックは集計から除外する（異常）
      Given セッションが終了時刻に達した
      When プレイヤーが終了時刻を過ぎてからクリックする
      Then そのクリックは集計から除外される

  Rule: 終了時に結果サマリを表示（discovery Rule 5）

    @R-9 @e2e
    Scenario: 終了時に命中率・平均反応時間・ヒット数を表示する（正常）
      Given hits=5・total_clicks=8 のセッションが終了した
      When 結果サマリが表示される
      Then 命中率として 62.5% が表示される
      And 平均 reaction_time としてヒット 5 件の平均が表示される
      And ヒット数として 5/8 が表示される

    @R-10 @e2e
    Scenario: 結果画面の「もう一度」で新規セッションを開始する（正常）
      Given 結果サマリが表示されている
      When プレイヤーが「もう一度」を選ぶ
      Then 新しいセッションが開始する
      And hits・total_clicks・記録された reaction_time が 0 にリセットされる

  Rule: domain が accuracy・平均 reaction_time を算出（discovery Rule 6）

    @R-11 @backend
    Scenario: 生データから命中率を hits ÷ total_clicks で算出する（正常）
      Given hits=5・total_clicks=8・ヒット5件の reaction_time を持つ完了セッションのデータがある
      When そのデータが提出される
      Then システムは accuracy を 0.625 と算出する

    @R-12 @backend
    Scenario: 平均反応時間はヒットのみで算出する（正常）
      Given hits=2・total_clicks=5・ヒットの reaction_time が 300ms と 500ms の完了セッションのデータがある
      When そのデータが提出される
      Then システムは平均 reaction_time を 400ms と算出する
      And ミスのクリックは平均の算出に含まれない

    @R-13 @backend
    Scenario: Accuracy 値オブジェクトは範囲外の値を拒否する（異常）
      Given accuracy の値として 1.5 が与えられる
      When Accuracy 値オブジェクトを構築する
      Then InvariantViolation が送出される

    @R-13 @backend
    Scenario Outline: 不変条件に違反する申告を拒否する（異常）
      Given <説明> の完了セッションのデータがある
      When そのデータが提出される
      Then システムは提出を拒否する
      And score は保存されない

      Examples:
        | 説明                                       |
        | hits=9・total_clicks=8（hits が分母超過）   |
        | reaction_time に -1ms を含む（負の反応時間） |

  Rule: 集約1行で永続化・created_at はシステム付与・失敗は通知（discovery Rule 7）

    @R-14 @backend
    Scenario: 検証を通った完了セッションは score を1行だけ保存する（正常）
      Given hits=5・total_clicks=8 の検証を通る完了セッションのデータがある
      When そのデータが提出される
      Then score が 1 行だけ保存される
      And 保存項目に accuracy・平均 reaction_time・hits・total_clicks・制限時間・既定銃参照が含まれる
      And 各 reaction_time の明細は保存されない

    @R-15 @backend
    Scenario: created_at はシステムが付与し、クライアント時刻を信用しない（正常）
      Given クライアント時刻を含む完了セッションのデータが提出される
      When score が保存される
      Then created_at はシステムが付与する
      And クライアントが申告した時刻は created_at に使われない

    @R-16 @e2e
    Scenario: 永続化に失敗しても結果は表示し、保存失敗を通知する（異常）
      Given セッションが終了し、結果サマリが表示されている
      When score の保存に失敗する
      Then 結果サマリは表示されたままになる
      And 保存に失敗したことがプレイヤーに通知される

  Rule: 完了セッションのみ保存（discovery Rule 8）

    @R-17 @e2e
    Scenario: 制限時間到達前にやめたセッションは保存しない（異常）
      Given セッションが進行中である
      When プレイヤーが 30 秒に達する前にやめる
      Then そのセッションの score は保存されない

  Rule: 空・ゼロ値でも破綻しない（discovery Rule 9）

    @R-18 @e2e
    Scenario: 一度もクリックせず終了すると命中率と平均は「—」表示（境界）
      Given プレイヤーが一度もクリックせずに 30 秒経過してセッションが終了した
      When 結果サマリが表示される
      Then 命中率は「—」と表示される
      And 平均 reaction_time は「—」と表示される

    @R-18 @backend
    Scenario: total_clicks が 0 でも score は保存できる（境界）
      Given hits=0・total_clicks=0 の完了セッションのデータがある
      When そのデータが提出される
      Then score が保存される

    @R-19 @e2e
    Scenario: 全ミスのときは命中率 0%・平均は「—」表示（境界）
      Given hits=0・total_clicks=8 のセッションが終了した
      When 結果サマリが表示される
      Then 命中率は 0% と表示される
      And 平均 reaction_time は「—」と表示される

  Rule: total_clicks に計上しないクリック（discovery Rule 10）

    @R-20 @e2e
    Scenario: ヒット済みの的を再クリックしても無視する（異常）
      Given セッションが進行中で、ある的を既にヒットしている
      When プレイヤーが同じ的をもう一度クリックする
      Then そのクリックは無視される
      And hits と total_clicks は変化しない

    @R-21 @e2e
    Scenario: キャンバス外のクリックは集計に数えない（異常）
      Given セッションが進行中で、中央に的が1つある
      When プレイヤーがキャンバス外の座標 (-5,-5) をクリックする
      Then そのクリックは無視される
      And hits と total_clicks は変化しない

    @R-22 @e2e
    Scenario: セッション終了後のクリックは集計に数えない（異常）
      Given セッションが既に終了している
      When プレイヤーがキャンバス上をクリックする
      Then そのクリックは無視される
      And hits と total_clicks は変化しない
