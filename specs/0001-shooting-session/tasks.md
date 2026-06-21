# 射撃セッション（Shooting Session）— Tasks

Feature: 0001-shooting-session
Status: Approved        <!-- 2026-06-21 人間承認済み。implement はこれが Approved で着手 -->

承認済み `design.md`（Status: Approved）を、Clean Architecture の内側→外側・TDD（red → 最小実装で green → refactor）のビルド順に分解した作業台帳。
本書はコード・テストを含まない。新規 Gherkin・要件を作らない（`acceptance.feature` の既存 27 シナリオを `@R-x` で参照・グルーピングするのみ）。スコープは 0001 のみ（0002/0003/0004 を先取りしない）。

各実装タスクは「対象シナリオ（`@R-x`）を pytest-bdd / playwright-bdd 化して red → 最小実装で green → refactor」を内包する。
各タスクの**完了条件**は「どのテスト／品質チェックが緑になれば終わりか」で定義する。

---

## 0. 凡例・前提

- **層**: domain / application / infrastructure / adapters-schemas / adapters-api / composition-root / frontend-setup / frontend-lib / frontend-canvas-api-ui / ci。内側（domain）を先に積む。
- **green にすべき `@R-x`**: そのタスク完了時に green になる acceptance.feature のシナリオ（タグ）。「—（基盤）」はシナリオを直接 green にしない土台タスク。
- **品質ゲート（backend 共通・該当タスクで緑必須）**: Ruff（lint＋format）、Pyright（strict）、import-linter（CA 依存方向・domain/application の FW 非依存）、xenon（複雑度）、pytest（pytest-bdd 含む）が緑。
- **品質ゲート（frontend 共通）**: ESLint、Prettier、`tsc --noEmit`（strict・`any` 禁止）、Vite build、Vitest（純粋ロジック）、playwright-bdd（@e2e）が緑。
- **シナリオ総数 27 = @backend 7 ＋ @e2e 20**（`acceptance.feature` 実体に準拠。design §8.5 のゲートで再構成済み）。@backend → backend タスク、@e2e → frontend タスクで green にする。
- **責務分担（design §1）**: 進行中セッションの状態・判定・計測・タイマー・サマリ・「もう一度」・計上規則 = フロント（@e2e）。完了セッションの生データから算出・検証・永続化 = バックエンド（@backend・domain＋永続化）。

---

## A. backend（@backend 7 シナリオを green にする）

### T-01 — domain: 値オブジェクト `ReactionTime`・`Accuracy`・`AverageReactionTime` ＋ domain 例外
- **層**: domain
- **内容**:
  - `DomainError`（基底）・`InvariantViolation(DomainError)`（コード/メッセージ付き。例 `accuracy_out_of_range`・`negative_reaction_time`）を定義（design §2.6）。
  - `ReactionTime`（`frozen` dataclass。`ms: int`。`__post_init__` で `ms ≥ 0`、負値は `InvariantViolation`。`0` は有効）（design §2.3）。
  - `Accuracy`（`frozen` dataclass。`value: Decimal | None`。`None` でなければ `0 ≤ value ≤ 1`、範囲外は `InvariantViolation`。ファクトリ `from_counts(hits, total_clicks)`：`total_clicks==0 → value=None`、それ以外 `Decimal(hits)/Decimal(total_clicks)`）（design §2.3）。
  - `AverageReactionTime`（`frozen` dataclass。`ms: Decimal | None`。`None` でなければ `ms ≥ 0`。ファクトリ `from_hits(reaction_times: list[ReactionTime])`：空 → `ms=None`、それ以外は算術平均）（design §2.3）。
  - 標準ライブラリのみ（`dataclasses`/`decimal`）。FW/ORM/Pydantic を import しない。
- **TDD**: 純粋単体テスト（pytest）。**`@R-13` の「Accuracy 値オブジェクトは範囲外(1.5)を拒否」（acceptance.feature L132）を pytest-bdd で red → green**。`Accuracy(value=Decimal("1.5"))` で `InvariantViolation` が送出されること。あわせて `from_counts`（0.625・0/0→None）・`from_hits`（[300,500]→400・空→None）・`ReactionTime`（0 有効・-1 拒否）を単体で固める。
- **依存**: なし（最内・最初）。
- **green にすべき @R-x**: **@R-13（L132・Accuracy 範囲外拒否）**。
- **完了条件**: 上記 pytest / pytest-bdd（L132）が green。Ruff・Pyright・import-linter（domain が何も外部 import しない）・xenon 緑。

### T-02 — domain: 集約 `Score` と集約ファクトリ `Score.create`（不変条件の一元検証）
- **層**: domain
- **内容**:
  - `Score`（集約ルート。`hits`・`total_clicks`・`accuracy: Accuracy`・`avg_reaction_time: AverageReactionTime`・`time_limit_ms`・`gun_id`・`created_at` は保持しない/未確定。design §2.2）。ヒット明細は持たない（R-14）。
  - `Score.create(hits, total_clicks, reaction_times, time_limit_ms, gun_id) -> Score`（集約ファクトリ。**入力は素の値**＝domain は application 型を受けない。検証順序は design §2.4）：
    1. 各 raw reaction_time を `ReactionTime` で構築（負値 → `InvariantViolation`。R-13 の -1ms）。
    2. 件数整合：`hits ≥ 0`・`total_clicks ≥ 0`・`hits ≤ total_clicks`（R-13 の hits>total）。さらに「reaction_time の件数 == hits」を検証。
    3. `Accuracy.from_counts(hits, total_clicks)`。
    4. `AverageReactionTime.from_hits([...])`。
    5. 合格 → `Score`（`created_at` 未確定）を返す。
  - 違反はすべて `InvariantViolation`。永続化はしない（domain は DB を知らない）。
  - **入力は素の値で受ける（確定）**: `Score.create` は `hits`・`total_clicks`・`reaction_times`・`time_limit_ms`・`gun_id` を個別引数で受け、domain は application の `SessionResult` 型を import しない。application（T-03）の usecase が `SessionResult` を展開し、`gun_id` を `GunRepository` で解決して本ファクトリへ渡す。これで domain→application の逆依存を作らない（import-linter で検証）。
- **TDD**: 純粋単体テスト＋pytest-bdd。**`@R-11`（L119・accuracy=0.625）**、**`@R-12`（L125・平均=400ms・miss 非包含）**、**`@R-13` Scenario Outline（L138・hits=9/total=8、reaction_time=-1ms → 拒否・保存されない）**、**`@R-18`（L191・hits=0/total=0 でも `Score` 生成可＝保存可の domain 部分）** を red → green。
- **依存**: T-01。
- **green にすべき @R-x**: **@R-11（L119）・@R-12（L125）・@R-13（L138 Outline・domain 検証部分）・@R-18（L191・domain で `Score` 生成可）**。
- **完了条件**: 上記 pytest-bdd（L119・L125・L138・L191 の domain 検証）が green。import-linter で domain が application/infrastructure を import しないことを確認。Ruff・Pyright・xenon 緑。

> 注: @R-13（L138）と @R-18（L191）は domain 検証で「拒否される／`Score` が生成できる」ところまでを T-02 で green にし、**API レベルの 422／201・実 DB 保存**は T-08（adapters-api）・T-05（infrastructure）で完成させる。@R-14/@R-15 の保存系も同様に下流で完結する（下記）。

### T-03 — application: ユースケース `RecordSessionResult`・入力 `SessionResult`・抽象 `ScoreRepository`/`GunRepository`/`Clock`
- **層**: application
- **内容**:
  - `SessionResult`（入力 dataclass：`hits`・`total_clicks`・`reaction_times: list[int]`・`time_limit_ms`。`gun_id` は持たない＝サーバ解決。design §3.2）。
  - 抽象（`typing.Protocol`）：`ScoreRepository.add(score, created_at) -> Score`、`GunRepository.get_default_id() -> int`、`Clock.now() -> datetime`（design §3.1/§3.2）。
  - `RecordSessionResult`（ユースケース）：手順 = `gun_id = GunRepository.get_default_id()` → `Score.create(...)`（domain・違反は `InvariantViolation` 伝播）→ `created_at = Clock.now()`（R-15）→ `ScoreRepository.add(score, created_at)`（R-14）→ 永続化結果を返す。リポジトリ例外はそのまま上位へ伝播（api が 5xx 変換）。
  - 素の dataclass のみ。FastAPI/SQLAlchemy/Pydantic 不使用。domain のみ依存。
- **TDD**: in-memory フェイク（`ScoreRepository`/`GunRepository`/`Clock` のフェイク）を注入した単体テスト（pytest・DB 不要）。正常系（検証通過 → `add` が1回呼ばれ `created_at` がフェイク Clock 由来）・違反系（`InvariantViolation` が `add` 前に送出され保存されない）・**`@R-15` の「クライアント時刻を使わない」を Clock フェイクで（入力に時刻が無く、`created_at` が Clock 値）**・**`@R-14` の「1行保存・明細なし」をフェイクで**（フェイク add の呼び出し回数・引数を検証）。
- **依存**: T-02。
- **green にすべき @R-x**: **@R-14（L152）・@R-15（L160）をフェイクで（ユースケース層の論理）**。実 DB での最終 green は T-05・T-08。
- **完了条件**: フェイク注入の pytest が green（正常・違反・R-14/R-15 のユースケース論理）。import-linter で application が infrastructure/FW を import しないことを確認。Ruff・Pyright・xenon 緑。

### T-04 — infrastructure: 設定・DB エンジン/セッション・SQLAlchemy ORM `GunModel`/`ScoreModel`
- **層**: infrastructure
- **内容**:
  - 設定（pydantic-settings。DB URL 1行で SQLite↔PostgreSQL 切替可能。design §4 冒頭）。
  - エンジン／セッション（1リクエスト1セッション供給の土台。design §3.4）。
  - `DeclarativeBase` ＋ `Mapped[...]`＋`mapped_column` で ORM 定義（design §4.1/§4.2）：
    - `gun`：`id`（PK）・`name`（NOT NULL）。0002 の挙動列（fire_rate/recoil/target_size）は足さない。
    - `score`：`id`（PK）・`hits`・`total_clicks`（NOT NULL）・`accuracy`（`Numeric` **NULL 可**）・`avg_reaction_time`（`Numeric` ms **NULL 可**）・`time_limit_ms`（NOT NULL）・`gun_id`（FK→gun.id・NOT NULL）・`created_at`（`DateTime(timezone=True)`・NOT NULL）。明細テーブルなし。
  - SQLite 固有機能に依存しない（`Numeric`・`DateTime(timezone=True)`・標準 FK のみ）。
- **TDD**: ORM の定義・メタデータ整合を確認する最小テスト（テーブル作成・カラム nullable 設定の検証）。この時点で `text(...)`/生 SQL を使わない（ORM/Core 式のみ）。
- **依存**: T-03（リポジトリ抽象の形に合わせる）。
- **green にすべき @R-x**: —（基盤。T-05/T-08 で @R-14/15/18 を完結させるための ORM 土台）。
- **完了条件**: ORM メタデータの最小テストが green。no-raw-sql チェック緑。Ruff・Pyright・import-linter（infrastructure は内側に依存可・逆は不可）緑。

### T-05 — infrastructure: Alembic 導入＋初期マイグレーション・既定銃 seed・リポジトリ具象・`SystemClock`
- **層**: infrastructure
- **内容**:
  - **Alembic 導入＋初期マイグレーション**（design §4.1・§8.5 決定2）：`gun`/`score` を migration でテーブル作成。以降のスキーマ変更も migration で積む方針の土台。
  - **既定銃 seed**（冪等。「無ければ1件 INSERT」。data migration または起動時冪等 seed。design §4.1。具体方式を本タスクで確定）。
  - `ScoreRepository` 具象：`add(score, created_at)` で domain `Score` の値オブジェクト（`Accuracy.value: Decimal|None`・`AverageReactionTime.ms: Decimal|None`）を ORM の nullable カラムへ写像 → INSERT → 採番 `id`・`created_at` を載せた domain `Score` を再構築して返す（ORM を外へ漏らさない。design §4.3）。
  - `GunRepository` 具象：`get_default_id()` が seed 済み既定銃の ID を返す。
  - `SystemClock`（`Clock` 具象。`now()` がサーバ時刻）。
- **TDD**: テスト用 SQLite（インメモリ or 一時ファイル）で具象を検証（pytest）。`ScoreRepository.add` が1行 INSERT し、`accuracy`/`avg_reaction_time` が NULL 可で写像される（**@R-18 の実 DB 保存：hits=0/total=0 → accuracy/avg=NULL で1行保存**）。**@R-14 の実 DB 保存：1行のみ・明細テーブルに行が増えない**。seed の冪等性（2回実行で銃が重複しない）。`GunRepository.get_default_id()` が ID を返す。
- **依存**: T-04。
- **green にすべき @R-x**: **@R-14（L152・実 DB の1行保存・明細なし）・@R-18（L191・実 DB で nullable 保存）の永続化部分**。@R-15 の最終 green は T-09（composition root で `SystemClock` 注入）後の統合で確認。
- **完了条件**: テスト用 SQLite の具象テストが green（add 1行・nullable 写像・seed 冪等・get_default_id）。no-raw-sql・import-linter・Ruff・Pyright・xenon 緑。

### T-06 — adapters/schemas: Pydantic v2 DTO `SessionResultRequest`/`ScoreResponse`/`ErrorResponse`
- **層**: adapters-schemas
- **内容**（design §3.3）：
  - `SessionResultRequest`（入力）：`hits: Annotated[int, Field(ge=0)]`・`total_clicks: Annotated[int, Field(ge=0)]`・`reaction_times: list[int]`（**各要素 ge を型で強制しない**＝負値は domain に検出させ R-13 の検証主体を domain に保つ）・`time_limit_ms: Annotated[int, Field(gt=0)]`。`accuracy`/`avg_reaction_time`/`gun_id`/`created_at`/クライアント時刻は**含めない**。
  - `ScoreResponse`（出力）：`id`・`hits`・`total_clicks`・`accuracy: float | None`・`avg_reaction_time: float | None`・`time_limit_ms`・`gun_id`・`created_at`（ISO 8601）。
  - `ErrorResponse`：`{ detail: str, code: str }`。
  - `model_config = ConfigDict(...)`（v2 イディオム）。domain `SessionResult` ↔ DTO の相互変換を境界で行う方針を確定。
- **TDD**: DTO の単体テスト（pytest）。形検証が「薄い」こと（負の reaction_time は Pydantic で弾かない＝受理して domain へ渡す）・出力の null 表現（accuracy/avg が `None` を許容）を検証。
- **依存**: T-03（`SessionResult` と対応づけるため）。
- **green にすべき @R-x**: —（基盤。T-08 で @R-13/14 等の API 完結に使う）。
- **完了条件**: DTO 単体テストが green。Ruff・Pyright・import-linter 緑。

### T-07 — adapters/api: ルーター `POST /api/sessions` ＋ 例外→HTTP 変換
- **層**: adapters-api
- **内容**（design §3.3/§3.4）：
  - FastAPI ルーター `POST /api/sessions`：`SessionResultRequest` で入力検証 → `SessionResult` へ変換 → `Depends` で**抽象** `RecordSessionResult`（ユースケース）を注入して実行 → 成功は `201 Created`＋`ScoreResponse`。
  - 例外変換：`try/except InvariantViolation` → `422`＋`ErrorResponse`（`code` に domain コード）。リポジトリ例外（DB 失敗）→ `500`＋`ErrorResponse`（ビジネス例外を 500 で漏らさない／DB 例外を生 500 で漏らさない）。Pydantic 形式不正は FastAPI 既定 422。
  - infrastructure を import しない（抽象に依存）。セッション境界：成功で commit・例外で rollback（FastAPI 依存で供給）。
- **TDD**: pytest-bdd（FastAPI TestClient＋抽象のフェイク/テスト用具象）で `@backend` の API 観点を green：
  - **@R-14（L152）**：検証通過 → 201・`ScoreResponse`・score 1行（明細なし）。
  - **@R-13（L132・L138）**：不正申告 → 拒否（範囲外 Accuracy は値オブジェクト由来の `InvariantViolation` → 422／hits>total・-1ms → 422）・score 保存されない。
  - **@R-15（L160）**：クライアント時刻を入力に持たない契約で、`created_at` がサーバ付与（レスポンスの `created_at` が Clock 由来）。
  - **@R-18（L191）**：hits=0/total=0 → 201 で保存（accuracy/avg は null）。
- **依存**: T-05・T-06。
- **green にすべき @R-x**: **@R-11（L119）・@R-12（L125）・@R-13（L132・L138）・@R-14（L152）・@R-15（L160）・@R-18（L191）の API レベル**（＝ **@backend 全 7 シナリオ**がこの段で API 経由でも green）。
- **完了条件**: `@backend` タグの pytest-bdd 7 シナリオが API 経由で green（pytest-bdd を `@backend` で実行）。Ruff・Pyright・import-linter（adapters-api が infrastructure を import しない）・xenon 緑。

### T-08 — composition root: `app/main.py`（抽象→具象注入・起動時 seed・ルーター登録）
- **層**: composition-root
- **内容**（design §3.1 末・§4）：
  - FastAPI 生成、DB エンジン/セッション結線、抽象（`ScoreRepository`/`GunRepository`/`Clock`）→具象（infrastructure 実装・`SystemClock`）の注入、起動時の既定銃 seed 実行、ルーター登録。
  - main.py はレイヤ契約の外（composition root）。
- **TDD**: アプリ起動 → `POST /api/sessions` のエンドツーエンド（backend 内）で実 DB（テスト用 SQLite）に1行保存され 201 が返ること（**@R-14/@R-15/@R-18 の統合 green を最終確認**）。seed が起動時に冪等実行される。
- **依存**: T-05・T-07。
- **green にすべき @R-x**: **@backend 7 シナリオの統合 green を最終確認**（特に @R-14・@R-15・@R-18 の実 DB 経路）。
- **完了条件**: backend のエンドツーエンド（TestClient 経由・実 DB）pytest が green。`@backend` 7 シナリオすべて green。Ruff・Pyright・import-linter・xenon 緑。

---

## B. frontend 立ち上げ（@e2e を green にする前提の土台）

### T-09 — frontend-setup: Vite+React 雛形・TypeScript strict・ESLint/Prettier・Vitest 導入
- **層**: frontend-setup
- **内容**: `frontend/` の Vite+React+TypeScript strict（`any` 禁止）プロジェクト初期化、ESLint/Prettier/Vitest 設定、`tsc --noEmit`・`vite build` が通る最小構成。`package.json`＋lockfile（npm）をコミット。
- **TDD**: ダミーの純粋関数1つに対する Vitest が緑（テスト基盤の疎通確認）。
- **依存**: なし（backend と並行可。ただし @e2e green は backend 稼働後）。
- **green にすべき @R-x**: —（基盤）。
- **完了条件**: `tsc --noEmit`・ESLint・Prettier・`vite build`・Vitest（疎通）が緑。

### T-10 — frontend-setup: Tailwind 導入＋デザイントークン・Playwright + playwright-bdd 導入
- **層**: frontend-setup
- **内容**（design §5.2/§5.6・e2e-testing 前提）：
  - Tailwind 導入、`design`（デザイントークン）の色・スペーシング・タイポ・角丸をトークン化（Canvas 用に値を定数として参照できる形も用意）。
  - `@playwright/test` ＋ `playwright-bdd` を devDependencies 導入、`npx playwright install`、`bddgen` 設定で**原本 `specs/0001-shooting-session/acceptance.feature` を参照**（コピーしない）、`@e2e` タグでフィルタ。`@backend` は E2E で走らせない。
  - data-testid／テストシーム（`window.__aimTest`）方針の土台と**本番ビルド無効化**（環境フラグ）の枠を用意（design §5.6・§8.5 決定）。
- **TDD**: playwright-bdd の生成→実行パイプラインが疎通（最小 @e2e 1 本がフレームワーク上で起動する）こと。
- **依存**: T-09。
- **green にすべき @R-x**: —（基盤。@e2e を載せる土台）。
- **完了条件**: `bddgen`＋Playwright が `@e2e` を起動できる。Tailwind トークンが build に乗る。ESLint/Prettier/`tsc` 緑。

---

## C. frontend lib（純粋ロジック・Vitest）

### T-11 — frontend-lib: `geometry.ts`・`time.ts`
- **層**: frontend-lib
- **内容**（design §5.1）：
  - `geometry.isHit(clickX, clickY, target)`：二乗距離比較 `(dx*dx+dy*dy) <= radius*radius`（平方根回避・縁ちょうど `distance==radius` は hit）。
  - `time.now()`：`performance.now()` ラッパー（単調時計。`Date.now()` を計測に使わない）。テスト差し替えシーム。
- **TDD**: Vitest 単体（内側・縁ちょうど・わずか外側の hit/miss 判定。`time.now` の差し替え可能性）。
- **依存**: T-09。
- **green にすべき @R-x**: —（純粋ロジック。@e2e の hit/miss 系 R-1/R-2/R-3 を T-15 で green にする土台）。
- **完了条件**: Vitest（geometry・time）緑。`tsc`・ESLint・Prettier 緑。

### T-12 — frontend-lib: `session.ts`（進行中セッションの状態・計上規則）
- **層**: frontend-lib
- **内容**（design §5.1）：
  - `SessionState` 型（`status`・`startedAt`・`hits`・`totalClicks`・`reactionTimes`・`target`）。
  - `registerClick(state, click, now)`：R-1〜R-8・R-20/21/22 の計上規則を判断（hit→hits+1/totalClicks+1/reactionTimes.push(now-spawnedAt)・next spawn；miss→totalClicks+1のみ；hit 済み的の再クリック無視；領域外無視；終了後/超過無視；終了時刻ちょうどは含む＝閉区間 `now ≤ endTime`、design §8.5 決定）。
  - `spawnTarget()`：プレイ領域内ランダム位置・固定 radius・常に1つ。
  - `tick(state, now)`：`startedAt + 30000` で `finished` 遷移（R-7）。的は移動/消滅しない（R-6）。
- **TDD**: Vitest 単体（hit/miss 計上・respawn・0ms 有効・hit 済み再クリック無視・領域外無視・終了時刻ちょうど含む/超過除外・30 秒で finished・連打デバウンスなし）。**純粋ロジックとして R-1〜R-8・R-20/21/22 の計上規則をここで固める**（E2E は T-15 で画面結線を green に）。
- **依存**: T-11。
- **green にすべき @R-x**: —（純粋ロジック。対応 @e2e の最終 green は T-15）。
- **完了条件**: Vitest（session の全分岐）緑。`tsc`・ESLint・Prettier 緑。

### T-13 — frontend-lib: `summary.ts`（サマリ算出・表示整形）
- **層**: frontend-lib
- **内容**（design §5.1）：
  - `computeAccuracy(hits, totalClicks)`：`totalClicks===0 ? null : hits/totalClicks`。
  - `computeAvgReactionTime(reactionTimes)`：`length===0 ? null : 平均`。
  - `formatAccuracy(value)`：`null → "—"`、それ以外 `"62.5%"`。
  - `formatAvg(value)`：`null → "—"`、それ以外 `"### ms"`。
- **TDD**: Vitest 単体（62.5%・0%・null→"—"・平均整形）。**R-9/18/19 の表示算出をここで固める**。
- **依存**: T-09。
- **green にすべき @R-x**: —（純粋ロジック。@e2e の R-9/18/19 表示の最終 green は T-15）。
- **完了条件**: Vitest（summary の全分岐）緑。`tsc`・ESLint・Prettier 緑。

---

## D. frontend canvas / api / components / E2E（@e2e 20 シナリオを green にする）

### T-14 — frontend: `canvas/renderer.ts`・`api/submitSession.ts`（SWR mutation）・components（Smart/Dumb・data-testid）・テストシーム
- **層**: frontend-canvas-api-ui
- **内容**（design §5.2/§5.3/§5.4/§5.5/§5.6）：
  - `canvas/renderer.ts`：`requestAnimationFrame` ループで的・HUD（残り時間・hits/total_clicks）を描画。React state に乗せない（ref で `SessionState` を渡す）。色は Tailwind トークンの定数を参照。
  - `api/submitSession.ts`：`POST /api/sessions` を1呼び出し（完了時1回）。ボディ `{ hits, totalClicks, reactionTimes, timeLimitMs }`（accuracy/avg/gunId/createdAt は送らない）。戻り値型 `ScoreResponse`（`accuracy`/`avgReactionTime` は `number | null`）を `api/` に定義。`useSWRMutation`（または mutate ベース submit）で `isMutating`/`error` を扱う。
  - components（Smart/Dumb・data-testid）：
    - Smart `ShootingSessionContainer`：状態（`useReducer`/`useState`＋`lib/session`）・タイマー（rAF＋`time.now`）・クリックハンドラ（領域判定→`registerClick`）・終了検知（`tick`→finished）→ `submitSession` 実行・「もう一度」リセット（R-10）。**中断（finished でない）は submit しない（R-17）**。
    - Dumb：`StartButton`（`start-button`）・`GameCanvas`（`game-canvas`・クリック座標を親通知）・`ResultSummary`（`summary-accuracy`/`summary-avg`/`summary-hits`）・`PlayAgainButton`（`play-again-button`）・`SaveErrorNotice`（`save-error-notice`・`error` 時表示）・`Hud`（任意）。
  - テストシーム（本番ビルド無効化・環境フラグ）：`window.__aimTest.getTarget()`（的中心・radius）・`getState()`（status・hits・totalClicks・reactionTimes.length・残り時間）・時間制御（`time.now` 集約で仮想時間/早送り。方式は Playwright clock か注入、e2e-testing 参照で確定）・保存失敗注入（Playwright route abort）。
- **TDD**:
  - Dumb components と `api/submitSession` の型・SWR error ハンドリングを Vitest で（props 描画・null→"—"・error 表示の有無）。
  - **playwright-bdd で `@e2e` 20 シナリオを red → green**（DOM は `data-testid`、Canvas はテストシーム座標、時間はシーム、保存失敗は route abort）：
    - hit/miss・reaction_time：**@R-1（L15・L24）・@R-2（L39）・@R-3（L31・L50）・@R-4（L58）**。
    - spawn/常時1つ：**@R-5（L67）・@R-6（L73）**。
    - タイマー/境界：**@R-7（L81）・@R-8（L88・L94）**。
    - サマリ/もう一度：**@R-9（L102）・@R-10（L110）**。
    - 保存失敗/中断：**@R-16（L167・route abort で通知＆サマリ継続）・@R-17（L176・中断は submit しない）**。
    - ゼロ/空値表示：**@R-18（L184・total_clicks=0→"—"）・@R-19（L197・0%・"—"）**。
    - 無視するクリック：**@R-20（L206）・@R-21（L213）・@R-22（L220）**。
- **依存**: T-08（backend 稼働＝@e2e の submit/保存失敗を実エンドポイントで）・T-10（Playwright/Tailwind）・T-11・T-12・T-13。
- **green にすべき @R-x**: **@e2e 20 シナリオすべて**（上記の L 番号一覧）。
- **完了条件**: `@e2e` の playwright-bdd 20 シナリオが green。Vitest（Dumb・api）緑。`tsc --noEmit`（strict・`any` 禁止）・ESLint・Prettier・`vite build` 緑。テストシームが本番ビルドで無効（環境フラグ）。

> T-14 は大きいので、実装時に「canvas/renderer」「api/submitSession＋型」「Dumb 群」「Smart Container＋テストシーム」「@e2e シナリオ群（Rule 単位でグルーピング）」のサブタスクに割って red→green を回してよい。E2E は acceptance.feature の **Rule 単位**（内側/外側/spawn/タイマー/サマリ/算出は @backend なので除外/永続化通知/完了のみ/ゼロ値/無視クリック）でグルーピングして進める。

---

## E. CI（強制）

### T-15 — ci: GitHub Actions に backend 品質ジョブ・frontend 品質ジョブ・E2E 別ジョブを追加
- **層**: ci
- **内容**（CLAUDE.md ハーネス・e2e-testing「CI は別ジョブ」）：
  - backend ジョブ：Ruff・Pyright・import-linter・xenon・pytest（pytest-bdd 含む・`@backend`）。
  - frontend ジョブ：ESLint・Prettier・`tsc --noEmit`・`vite build`・Vitest。
  - **E2E は別ジョブ**（ブラウザ取得が重い）：playwright-bdd（`@e2e`）。検証対象 UI が存在してから追加（T-14 後）。
  - pre-commit（ローカル）との二重化を保つ。CodeQL はリポジトリ公開時のみ（今は入れない）。AWS/IaC は不採用。
- **TDD**: CI 上で上記ジョブがすべて緑になること（PR で確認）。
- **依存**: T-08（backend 緑）・T-14（frontend/E2E 緑）。
- **green にすべき @R-x**: —（強制基盤。全 27 シナリオを CI で継続 green に保つ）。
- **完了条件**: GitHub Actions の全ジョブ（backend／frontend／E2E）が緑。`@backend` 7・`@e2e` 20 が CI で green。

---

## F. 推奨ビルド順（内側→外側・TDD）

```
T-01 domain VO/例外
  → T-02 domain Score/集約ファクトリ
    → T-03 application ユースケース/抽象（フェイク単体）
      → T-04 infra 設定/DB/ORM
        → T-05 infra Alembic/seed/リポジトリ具象/SystemClock
          → T-06 adapters/schemas DTO
            → T-07 adapters/api ルーター/例外変換（@backend を API で green）
              → T-08 composition root（@backend 統合 green）  ← backend 完成

T-09 frontend 雛形（backend と並行可）
  → T-10 Tailwind / Playwright+playwright-bdd 導入
    → T-11 lib geometry/time
      → T-12 lib session
        → T-13 lib summary
          → T-14 canvas/api/components/E2E（@e2e 20 を green）  ← T-08・T-10 完了後に E2E green

T-15 CI（T-08・T-14 後）
```

- **frontend は backend（T-08）と Playwright/Tailwind 導入（T-10）の後**に @e2e を green にする（@e2e の submit/保存失敗は実エンドポイント前提）。
- 純粋ロジック（T-11〜T-13）は backend 稼働を待たず先に Vitest で固められる（並行可）。

---

## G. 網羅確認（27 シナリオすべてがタスクに紐づく）

### @backend（7 シナリオ）→ backend タスク

| シナリオ（行） | @R-x | green にするタスク |
| --- | --- | --- |
| L119 命中率 0.625 | @R-11 | T-02（domain）→ T-07（API）→ T-08（統合） |
| L125 平均 400ms・miss 非包含 | @R-12 | T-02（domain）→ T-07（API）→ T-08（統合） |
| L132 Accuracy 範囲外(1.5) 拒否 | @R-13 | **T-01（domain VO）** → T-07（API） |
| L138 Outline（hits>total・-1ms）拒否・未保存 | @R-13 | T-02（domain）→ T-07（API・422） |
| L152 score 1行保存・明細なし | @R-14 | T-03（フェイク）→ T-05（実 DB）→ T-07/T-08 |
| L160 created_at システム付与 | @R-15 | T-03（Clock フェイク）→ T-07/T-08 |
| L191 total_clicks=0 でも保存 | @R-18 | T-02（domain 生成可）→ T-05（nullable 保存）→ T-07/T-08 |

### @e2e（20 シナリオ）→ frontend タスク

すべて **T-14**（canvas/api/components/E2E）で green。純粋ロジックの土台は T-11（geometry/time）・T-12（session）・T-13（summary）。

| シナリオ（行） | @R-x | 土台 lib |
| --- | --- | --- |
| L15 内側=hit・320ms | @R-1 | T-11/T-12 |
| L24 縁ちょうど=hit | @R-1 | T-11 |
| L31 半径わずか超え=miss | @R-3 | T-11/T-12 |
| L39 同フレーム=0ms | @R-2 | T-11/T-12 |
| L50 空白=miss | @R-3 | T-12 |
| L58 空白連打デバウンスなし | @R-4 | T-12 |
| L67 hit直後に次の的1つ | @R-5 | T-12 |
| L73 寿命で消えず残る | @R-6 | T-12 |
| L81 30秒で自動終了 | @R-7 | T-12 |
| L88 終了時刻ちょうど含む | @R-8 | T-12 |
| L94 終了時刻超過は除外 | @R-8 | T-12 |
| L102 サマリ 62.5%/平均/5/8 | @R-9 | T-13 |
| L110 もう一度でリセット | @R-10 | T-12 |
| L167 保存失敗通知・サマリ継続 | @R-16 | T-14（api/SWR error） |
| L176 中断は保存しない | @R-17 | T-14（Smart：finished 時のみ submit） |
| L184 total_clicks=0→"—" | @R-18 | T-13 |
| L197 全ミス 0%・"—" | @R-19 | T-13 |
| L206 hit済み再クリック無視 | @R-20 | T-12 |
| L213 キャンバス外無視 | @R-21 | T-12 |
| L220 終了後クリック無視 | @R-22 | T-12 |

**結論**: 27 シナリオ（@backend 7・@e2e 20）すべてが、どれかのタスクで green になるよう割り当て済み（漏れゼロ）。

---

## H. トレーサビリティ（要件 R-1〜R-22 → タスク）

| R-x | 責務 | 主タスク |
| --- | --- | --- |
| R-1 | F | T-11（isHit）・T-12（registerClick）・T-14（E2E） |
| R-2 | F＋B | T-12/T-14（0ms 記録）・T-01（ReactionTime ms≥0） |
| R-3 | F | T-11・T-12・T-14 |
| R-4 | F | T-12・T-14 |
| R-5 | F | T-12（spawnTarget）・T-14 |
| R-6 | F | T-12（tick で消さない）・T-14・T-14（renderer 1つ描画） |
| R-7 | F | T-12（tick finished）・T-14（rAF タイマー） |
| R-8 | F | T-12（閉区間 `now ≤ endTime`）・T-14 |
| R-9 | F | T-13（compute/format）・T-14（ResultSummary） |
| R-10 | F | T-12/T-14（リセット）・T-14（PlayAgainButton） |
| R-11 | B | T-01（Accuracy.from_counts）・T-02（Score.create）・T-07/T-08 |
| R-12 | B | T-01（AverageReactionTime.from_hits）・T-02・T-07/T-08 |
| R-13 | B | T-01（VO 範囲）・T-02（集約検証）・T-07（422） |
| R-14 | B | T-03（usecase）・T-05（add 1行・明細なし）・T-07/T-08 |
| R-15 | B | T-03（Clock）・T-05（SystemClock）・T-07/T-08 |
| R-16 | F＋B | T-14（SaveErrorNotice/SWR error）・T-07（500） |
| R-17 | F | T-14（finished 時のみ submit） |
| R-18 | F＋B | T-13（"—"）・T-01/T-02（None）・T-05（nullable）・T-07/T-08 |
| R-19 | F＋B | T-13（0%・"—"）・T-01/T-02（None）・T-05（nullable） |
| R-20 | F | T-12・T-14 |
| R-21 | F | T-12・T-14（領域判定） |
| R-22 | F | T-12・T-14 |

R-1〜R-22 の 22 件すべてがタスクに対応づけ済み。

---

## I. 順序・依存上のリスク／実装前に決めるべき点

1. **`SessionResult` の配置と CA 整合（解決済み・2026-06-21）**: `Score.create` は**素の値**（`hits`・`total_clicks`・`reaction_times`・`time_limit_ms`・`gun_id`）を個別引数で受ける（domain は application の `SessionResult` を import しない）。application の usecase が `SessionResult` を展開し、`gun_id` を `GunRepository` で解決して渡す。design §2.4／§3.2 と T-02 に反映済み。import-linter が逆依存をブロックする。
2. **@R-13「accuracy=1.5」の検証経路（design §8.5 決定1）**: API に accuracy を入力で持たせない設計のため、L132 は **`Accuracy` 値オブジェクトの単体テスト**（T-01）で green にする（API POST で 1.5 を送る経路は無い）。L138 Outline（hits>total・-1ms）は API 422（T-07）で green。pytest-bdd のステップ定義で「値オブジェクト構築」と「データ提出」を別ステップに書き分ける（implement 時に確定）。
3. **既定銃 seed の方式（T-05）**: data migration（Alembic）か起動時冪等 seed か。冪等性（重複 INSERT 回避）と「テストでも seed 済み前提を満たす」両立を T-05 着手時に1方式へ確定。
4. **E2E の時間制御方式（T-10/T-14）**: R-7/R-8/R-22（30 秒経過・終了時刻ちょうど・終了後）を E2E で再現するため、Playwright clock API か `time.now` への注入かを e2e-testing 参照で確定。`time.now` 集約（T-11）をシーム化しておくこと（後から差し替え困難を避ける）。
5. **テストシーム本番無効化（T-14）**: `window.__aimTest` の環境フラグ無効化を T-14 の早い段で枠組みとして入れる（後付けだと露出が本番に漏れるリスク）。
6. **@e2e は backend 稼働前提（T-14 ← T-08）**: 保存失敗通知（R-16・route abort）・submit（R-17）は実エンドポイント前提。frontend 純粋ロジック（T-11〜T-13）は先行可だが、@e2e 20 の green は T-08・T-10 完了後。
7. **CI の E2E 別ジョブ（T-15）**: ブラウザ取得が重く UI 完成後に追加。backend ジョブと frontend/E2E ジョブのトリガ・キャッシュを分ける。

---

## J. 完了の定義（この tasks）

tasks.md が `acceptance.feature` の全 27 シナリオ（@backend 7・@e2e 20）をいずれかのタスクに割り当て、各タスクに層・対象 `@R-x`・依存・完了条件を備え、内側→外側の推奨ビルド順を示し、人間が承認して本書を `Status: Approved` にした状態。→ 次は `implement`。
