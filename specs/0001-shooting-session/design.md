# 射撃セッション（Shooting Session）— Design

Feature: 0001-shooting-session
Status: Approved        <!-- 2026-06-21 人間承認済み。tasks はこれが Approved で着手 -->

承認済み `requirements.md`（EARS R-1〜R-22・Approved）と `acceptance.feature`（27 シナリオ・@backend/@e2e）を実装可能な設計に落とす。本書はコード・テストを含まない。新規要件・Gherkin を作らない。スコープは 0001 のみ（0002/0003/0004 を先取りしない）。

---

## 1. 概要

起動 → 撃つ → 結果を見る、までを一直線で完結させる最小ループ。アーキテクチャ上の中心的決定は **責務分担**:

- **フロント（Canvas）= 進行中セッションの状態と判定の主体**。hit/miss 判定・`reaction_time` 計測（`performance.now()` の単調時計）・respawn・常に的1つ・30 秒タイマー・サマリ表示・「もう一度」・計上規則（R-20/21/22）はすべてフロントが持つ。サーバへは進行中の状態を一切送らない。
- **バックエンド = ステートレス**。完了（30 秒完走）したセッションの**生データ**を終了時に1回だけ受け取り、**domain が** accuracy と平均 reaction_time を算出し、不変条件を検証し、合格時のみ score を1行永続化する。サーバは進行中セッションの状態を持たない。

この分担は requirements.md の Rule 11（設計の前提）と承認済み決定に従う。@e2e シナリオ（19 件）はフロント、@backend シナリオ（8 件）はバックエンド（domain＋永続化）で検証される（タグが責務分担と一致している）。

### 対象 EARS 要件

R-1〜R-22 のすべて。各要件の責務（フロント/バック）と対応設計要素は「§7 トレーサビリティ」に網羅する。

### 用語

`ubiquitous-language` に従う。識別子は Python/DB＝`snake_case`、TypeScript＝`camelCase`、型/クラス＝`PascalCase`。本機能で使う語: target / spawn / hit / miss / reaction_time / accuracy / total_clicks / session / score / gun / created_at。新規追加語なし（`total_clicks` は discovery で追加済み）。

---

## 2. ドメインモデル（DDD）

### 2.1 境界づけられたコンテキスト

**Scoring（採点）コンテキスト** 1つ。責務は「完了セッションの生データから確定スコアを算出・検証・永続化する」こと。進行中セッションの状態管理（タイマー・spawn・クリック判定）は**このコンテキストの外**（フロントの責務）にある。サーバ domain は「提出された確定済みセッション結果」だけを知る。

> 設計上の含意: サーバ domain に `Session`（進行中の集計を持つエンティティ）は**置かない**。サーバがステートレスである以上、進行中の `Session` は domain の関心ではない。提出されるのは「完了セッションの生データ ＝ `SessionResult`（不変の入力 DTO）」であり、domain はそこから `Score` 集約を生成する。これにより「サーバが session 状態を持つ」誤設計を構造的に排除する。

### 2.2 集約

**`Score`（集約ルート）** — 採点済みの1セッションの成績記録。1セッション = 1 `Score`（集約1行）。ヒット明細は保持しない（R-14）。

`Score` が保持する状態（すべて確定値・不変）:

| 属性 | 型 | 説明 |
| --- | --- | --- |
| `hits` | `int` | ヒット数（生データ由来） |
| `total_clicks` | `int` | 総クリック数（生データ由来。accuracy の分母） |
| `accuracy` | `Accuracy`（値オブジェクト） | hits ÷ total_clicks。total_clicks=0 なら未定義 |
| `avg_reaction_time` | `AverageReactionTime`（値オブジェクト） | ヒットのみの平均。hits=0 なら未定義 |
| `time_limit_ms` | `int` | セッション制限時間（30000 固定。R-14 の「制限時間」） |
| `gun_id` | `int` | 既定銃への参照（NOT NULL。R-14） |
| `created_at` | `datetime` | **サーバ付与**（R-15）。集約生成時には未確定でよく、永続化時に確定する |

> `created_at` の扱い: domain は「クライアント時刻を `created_at` に使わない」という不変条件を体現するため、`Score` は `created_at` をクライアント入力から**受け取らない**。サーバ付与のタイムスタンプは composition root／infrastructure 側で確定する（§4 で詳述）。これで R-15 を構造的に保証する。

### 2.3 値オブジェクト（不変・自己検証）

dataclass（`frozen=True`）で表現。生成時（`__post_init__`）に不変条件を検証し、違反時は domain 例外を送出する。FW/ORM/Pydantic を import しない（標準ライブラリのみ）。

**`Accuracy`** — 命中率。
- 内部表現: `value: Decimal | None`（`None` ＝ 未定義 ＝ total_clicks=0）。`Decimal` で保持し浮動小数の比較ブレを回避。循環小数（例 1/3）は**保存精度＝小数4桁（DB `Numeric(5,4)`）に量子化**し、domain=DB=API=表示で同値にする。
- 不変条件: `value` が `None` でなければ `0 ≤ value ≤ 1`（R-13）。範囲外は `InvariantViolation`。
- ファクトリ: `Accuracy.from_counts(hits: int, total_clicks: int) -> Accuracy`。`total_clicks == 0` → `value=None`（R-18）。それ以外 → `Decimal(hits) / Decimal(total_clicks)` を**小数4桁に量子化（ROUND_HALF_UP）**（R-11）。算出結果が範囲外になるのは `hits > total_clicks` のときで、これは下記 §2.4 の集約レベル検証で先に弾く。

**`ReactionTime`** — 反応時間（単一値、ms）。
- 内部表現: `ms: int`（または `Decimal`。ms 整数で十分）。
- 不変条件: `ms ≥ 0`（R-2「負を記録しない」・R-13「負の reaction_time を拒否」）。負値は `InvariantViolation`。`0` は有効値（R-2）。
- 用途: 提出された各ヒットの reaction_time を1件ずつ `ReactionTime` として検証する（負値混入の検出 ＝ R-13 の Scenario Outline「reaction_time に -1ms を含む」）。

**`AverageReactionTime`** — 平均反応時間（未定義許容）。
- 内部表現: `ms: Decimal | None`（`None` ＝ 未定義 ＝ hits=0）。平均は割り算なので `Decimal` で保持し、**小数3桁（DB `Numeric(8,3)`）に量子化**する。
- 不変条件: `None` でなければ `ms ≥ 0`。
- ファクトリ: `AverageReactionTime.from_hits(reaction_times: list[ReactionTime]) -> AverageReactionTime`。空リスト（hits=0）→ `ms=None`（R-19）。それ以外 → ヒットのみの算術平均を**小数3桁に量子化（ROUND_HALF_UP）**（R-12。miss は分母に入らない ＝ そもそもリストに含まれない）。

> `ReactionTime`（単一・必須非負）と `AverageReactionTime`（集計値・未定義許容）を**別の値オブジェクトに分ける**。前者は入力検証用、後者は集約が保持する確定値。混ぜると「平均は null 可・各値は null 不可」という別々の不変条件が1クラスに同居して崩れる。

### 2.4 集約のファクトリと集約レベル不変条件

`Score.create(hits: int, total_clicks: int, reaction_times: list[int], time_limit_ms: int, gun_id: int) -> Score`（domain の集約ファクトリ）。**入力は素の値**（domain は application／FW を import しない）。提出された生データは application の入力境界（§3 の `SessionResult`：hits・total_clicks・reaction_times・time_limit_ms）が運び、usecase がそれを展開し、`gun_id`（usecase が `GunRepository` で解決した既定銃 ID）と併せて個別値として本ファクトリへ渡す。

検証順序（すべて違反は `InvariantViolation` を送出 → 永続化しない。R-13）:

1. **個別 reaction_time の非負**: 各 raw reaction_time を `ReactionTime(ms=...)` で構築 → 負値があれば送出（R-13: -1ms）。
2. **件数整合**: `hits ≥ 0`、`total_clicks ≥ 0`、`hits ≤ total_clicks`（R-13: hits>total_clicks）。さらに「提出された reaction_time の件数 == hits」を検証（ヒット数とヒットの反応時間群が整合していること。生データの内部整合性チェック）。
3. **accuracy 算出**: `Accuracy.from_counts(hits, total_clicks)`。§2.3 の通り 0〜1 を保証。`accuracy=1.5` のような直接申告は**そもそも受け取らない**（accuracy はクライアントが申告せず domain が算出する ＝ R-11）。R-13 の「accuracy=1.5 を申告」シナリオは、API 契約が accuracy を入力に**持たない**ことで根本的に防ぐ（§3.3 にリスクとして明記）。
4. **平均算出**: `AverageReactionTime.from_hits([...])`。
5. すべて合格 → `Score`（`created_at` 未確定）を生成して返す。

> 「不変条件は集約の生成時に1箇所で守る」。検証を散らさず `Score.create` に集約することで、純粋単体テスト（DB・FW 不要）で R-11/12/13/18/19 を網羅できる（@backend シナリオ）。

### 2.5 ドメインイベント

0001 では**採用しない**。score は終了時に1回 INSERT されるだけで、他コンテキストへの波及（履歴集計＝0003、ランキング＝0004）は範囲外。イベント駆動は将来 0003/0004 で必要になれば非破壊で追加する（YAGNI）。本書では「イベントは不要」と明示的に判断したことを記録する。

### 2.6 domain 例外

- **`DomainError`**（基底）。
- **`InvariantViolation(DomainError)`** — 不変条件違反（R-13 全般）。違反の種類を示すメッセージ／コード（例: `accuracy_out_of_range`・`hits_exceed_total`・`negative_reaction_time`・`hit_count_mismatch`）を持つ。adapters/api がこれを捕捉し 422＋エラー DTO に変換する（§3.4）。

domain は HTTP を知らない（純粋）。ステータスへの対応づけは adapters の責務。

---

## 3. レイヤ配置（Clean Architecture）と API 契約

### 3.1 レイヤ配置（各層に置く要素・1行ずつ）

- **domain**（`backend/app/domain/`・純粋／標準ライブラリのみ）: `Score` 集約、値オブジェクト `Accuracy`/`ReactionTime`/`AverageReactionTime`、`SessionResult` が満たすべき不変条件の検証ロジック（`Score.create`）、`DomainError`/`InvariantViolation`。FW/ORM/Pydantic を import しない。
- **application**（`backend/app/application/`・domain のみ依存）: ユースケース `RecordSessionResult`（完了セッションを記録して score を作る）、入力 dataclass `SessionResult`、リポジトリ抽象 `ScoreRepository`（Protocol）・`GunRepository`（既定銃 ID の取得・抽象）、サーバ時刻を供給する抽象 `Clock`（Protocol）。素の dataclass のみ。FastAPI/SQLAlchemy/Pydantic 不使用。
- **adapters/api**（`backend/app/adapters/api/`・薄いコントローラ）: FastAPI ルーター（`POST /api/sessions`）。Pydantic DTO で入力検証、`Depends` で**抽象**リポジトリ／ユースケースを注入、domain 例外 → 一貫したエラー DTO＋ステータス変換。infrastructure を import しない。
- **adapters/schemas**（`backend/app/adapters/schemas/`）: Pydantic v2 DTO `SessionResultRequest`（入力）・`ScoreResponse`（出力）・`ErrorResponse`（エラー）。domain エンティティとは別物。境界で `SessionResult`（application dataclass）↔ DTO を相互変換。
- **infrastructure**（`backend/app/infrastructure/`）: SQLAlchemy 2.0 ORM モデル `GunModel`/`ScoreModel`、`ScoreRepository`/`GunRepository` の具象実装（entity↔ORM 変換・ORM を外へ漏らさない）、`SystemClock`（`Clock` 具象）、エンジン/セッション（1リクエスト1セッション）、設定（pydantic-settings）、既定銃 seed の仕組み。
- **composition root**（`backend/app/main.py`・レイヤ契約の外）: FastAPI 生成、DB エンジン/セッション結線、抽象→具象の注入、起動時の既定銃 seed 実行、ルーター登録。

### 3.2 ユースケース（application）

**`RecordSessionResult`** — 「完了セッションを記録して score を作る」。
- 入力: `SessionResult`（application の dataclass。hits・total_clicks・reaction_times（ms の list）・time_limit_ms。**`gun_id` は持たない**＝サーバ解決）。
- 手順:
  1. `gun_id = gun_repository.get_default_id()`（既定銃 ID をサーバ解決。R-14。クライアントは申告しない）。
  2. `Score.create(hits, total_clicks, reaction_times, time_limit_ms, gun_id)` を呼ぶ（**`SessionResult` を展開して個別値で渡す**＝domain は application 型を受けない。算出＋不変条件検証。違反は `InvariantViolation` 伝播）。
  3. `created_at = clock.now()`（サーバ時刻。R-15）。
  4. `score_repository.add(score, created_at)` で永続化（1行 INSERT。R-14）。戻り値は永続化後の domain `Score`（id・created_at 確定）。
  5. 永続化結果を返す。例外（リポジトリ失敗）はそのまま上位へ伝播し、api が 5xx＋エラー DTO に変換（R-16 の「保存失敗通知」はフロントがこのレスポンスを見て出す）。
- 依存はすべて**抽象**（`ScoreRepository`・`GunRepository`・`Clock`）。in-memory フェイクで単体テスト可能。

> `gun_id` の供給: 0001 は UI に銃を出さない（固定の既定銃）。クライアントが `gun_id` を申告するのではなく、**サーバが既定銃 ID を解決する**方が改ざん耐性・単純さで優る。よって API 入力に `gun_id` を含めず、ユースケースが `GunRepository.get_default_id()` で既定銃 ID を取得して `Score` に付与する設計とする（§3.3 の入力 DTO に `gun_id` を置かない理由）。

### 3.3 API 契約

**エンドポイント**: `POST /api/sessions`
- 意味: 「完了セッションの生データを提出し、採点済み score を作成する」。リソースは作成される score。
- 完了セッションのみ提出される（中断は送られない ＝ R-17 はフロントが送らないことで保証。サーバは「来たものは完了済み」と扱う）。

**リクエスト DTO `SessionResultRequest`**（Pydantic v2・adapters/schemas）:

| フィールド | 型 | 制約 | 由来 |
| --- | --- | --- | --- |
| `hits` | `int` | `Field(ge=0)` | 生データ |
| `total_clicks` | `int` | `Field(ge=0)` | 生データ |
| `reaction_times` | `list[int]` | 各要素 `ge=0` を**型レベルでは強制しない**（負値は domain で検出させ R-13 の検証主体を domain に保つ） | ヒットの reaction_time 群（ms） |
| `time_limit_ms` | `int` | `Field(gt=0)`。MVP は 30000 を期待 | セッション制限時間（R-14） |

- **含めないフィールド**: `accuracy`・`avg_reaction_time`（domain が算出 ＝ R-11/12。クライアント申告を受けない）。`gun_id`（サーバが既定銃を解決 ＝ §3.2）。`created_at`／クライアント時刻（サーバ付与 ＝ R-15。受け取っても無視するのではなく、そもそも契約に置かない）。
- **検証の二段構え**: Pydantic は「形（型・非負の素朴な範囲）」のみ最低限担保。**ビジネス不変条件（accuracy 範囲・hits≤total_clicks・負の reaction_time）は domain（`Score.create`）が検証**する（R-13 の検証主体を domain に固定）。Pydantic で全部弾くと domain の不変条件が形骸化し @backend シナリオが domain を検証しなくなるため、意図的に薄くする。

> 設計判断（リスクとして人間ゲートに明示）: R-13 の Scenario Outline に「accuracy=1.5 を申告」がある。本設計は **accuracy をそもそも入力に持たない**（domain が算出）ため、この申告は API レベルで受理されず（未知フィールドは Pydantic で無視または拒否）、accuracy 範囲違反は「hits>total_clicks 由来でのみ起こりうる」。Scenario の主旨（不正な accuracy を保存しない）は満たすが、「accuracy フィールドを直接渡す」経路は存在しない。`Accuracy` 値オブジェクトの範囲不変条件は domain 単体テストで直接検証する（値オブジェクトに 1.5 を渡せば送出される）。この解釈で @backend シナリオを満たせるか実装時に確認する（§8 論点）。

**レスポンス（成功）`ScoreResponse`**（201 Created）:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `id` | `int` | 作成された score の ID |
| `hits` | `int` | |
| `total_clicks` | `int` | |
| `accuracy` | `float \| null` | 未定義（total_clicks=0）は `null`（R-18） |
| `avg_reaction_time` | `float \| null` | 未定義（hits=0）は `null`（R-19）。ms |
| `time_limit_ms` | `int` | |
| `gun_id` | `int` | 既定銃 |
| `created_at` | `datetime`（ISO 8601） | サーバ付与 |

> フロントはサマリを**自分の画面 state から表示**する（R-9 はフロント完結）。レスポンスの accuracy/avg は「サーバが算出した確定値」の確認用であり、保存成功の可否（R-16）を判断する主目的に使う。「—」表示はフロントの責務（null → 「—」）。

**ステータス／エラー**:

| 状況 | ステータス | ボディ | 要件 |
| --- | --- | --- | --- |
| 作成成功 | `201 Created` | `ScoreResponse` | R-14 |
| 不変条件違反（`InvariantViolation`） | `422 Unprocessable Entity` | `ErrorResponse`（`detail`・`code`） | R-13 |
| 形式不正（Pydantic 検証失敗） | `422`（FastAPI 既定） | FastAPI 検証エラー形式 | — |
| 永続化失敗（リポジトリ例外） | `500 Internal Server Error` | `ErrorResponse` | R-16（フロントが受けて通知） |

**`ErrorResponse`**（Pydantic）: `{ "detail": str, "code": str }`。domain の `InvariantViolation` のコード（`accuracy_out_of_range` 等）を `code` に載せ、一貫した形にする。422 は「意味は分かるが不変条件違反で処理不能」、Pydantic の 422 は「形が不正」で、どちらも 422 だが `code` で区別できる。

> R-16（保存失敗通知）の責務分担: サーバは失敗時に非 2xx を返すだけ。「結果サマリは表示したまま・保存失敗を通知」という**振る舞いはフロント**（@e2e の R-16 シナリオ）。サーバはエラーを正しく返す責務に限定。

### 3.4 例外 → HTTP 変換（adapters/api）

- ルーターで `RecordSessionResult` を実行し、`try/except InvariantViolation` で捕捉 → 422＋`ErrorResponse`。
- リポジトリ例外（DB 失敗）は捕捉して 500＋`ErrorResponse`（ビジネス例外を 500 で漏らさない／DB 例外を生の 500 で漏らさない）。
- domain 例外は HTTP を知らないため、変換は完全に adapters の責務（依存方向を内向きに保つ）。
- セッション境界: 1 リクエスト1 セッション。ユースケース成功で commit、例外時 rollback（FastAPI 依存で供給）。

---

## 4. データモデル

SQLAlchemy 2.0（`DeclarativeBase` ＋ `Mapped[...]` ＋ `mapped_column`）。アクセスは ORM のみ（直接 SQL 禁止）。SQLite 固有機能に依存せず、URL 1行で PostgreSQL へ切替可能に保つ。ORM モデルは infrastructure に置き、domain エンティティ（`Score`）とは相互変換（ORM を外へ漏らさない）。

### 4.1 `gun` テーブル（最小・0002 の挙動列は今は足さない）

| カラム | 型 | PK/FK | nullable | 説明 |
| --- | --- | --- | --- | --- |
| `id` | `int` | PK | NOT NULL | 既定銃の ID |
| `name` | `str`（例 `String(50)`） | | NOT NULL | 銃名（既定銃の表示用。例 "Default Pistol"） |

- 0002 の挙動列（`fire_rate`・`recoil`・`target_size`）は**今は足さない**（承認済み決定）。後から非破壊で `ADD COLUMN`（nullable もしくは default 付き）で追加可能。
- 既定銃を**冪等に seed**（「無ければ1件 INSERT」）。**スキーマ構築は Alembic を 0001 で導入（決定・2026-06-21）**: migration でテーブルを作成し、以降のスキーマ変更（0002 の gun 挙動列追加等）も migration で積む。既定銃 seed は data migration または起動時の冪等 seed で実装（具体方式は tasks で確定）。
- `score.gun_id` がこの行を NOT NULL 参照する（R-14）。

### 4.2 `score` テーブル（完了セッション1回 = 1行・明細なし）

| カラム | 型 | PK/FK | nullable | 説明 | 要件 |
| --- | --- | --- | --- | --- | --- |
| `id` | `int` | PK | NOT NULL | スコア ID | |
| `hits` | `int` | | NOT NULL | ヒット数 | R-14 |
| `total_clicks` | `int` | | NOT NULL | 総クリック数 | R-14 |
| `accuracy` | `Numeric`（例 `Numeric(5,4)`） | | **NULL 可** | hits÷total_clicks。total_clicks=0 で NULL（R-18） | R-11/18 |
| `avg_reaction_time` | `Numeric`（例 `Numeric(8,3)`、ms） | | **NULL 可** | ヒットのみ平均。hits=0 で NULL（R-19） | R-12/19 |
| `time_limit_ms` | `int` | | NOT NULL | セッション制限時間（30000） | R-14 |
| `gun_id` | `int` | **FK → gun.id** | NOT NULL | 既定銃参照 | R-14 |
| `created_at` | `datetime`（TZ aware 推奨。`DateTime(timezone=True)`） | | NOT NULL | **サーバ付与** | R-15 |

- **明細テーブルなし**（各 reaction_time の行は作らない ＝ R-14）。集約1行で完結。
- `accuracy`・`avg_reaction_time` を **nullable** にするのが本機能の肝（R-18/19 の「—」＝未定義を DB で `NULL` 表現）。`Numeric`（`Decimal`）で保持。**domain の値オブジェクトが保存精度（accuracy 4桁・avg 3桁）に量子化済み**なので domain=DB=API=表示が同値（循環小数も一貫）。浮動小数は使わない。
- `created_at` はサーバ付与。クライアント時刻は使わない（R-15）。DB の `server_default`／`func.now()` ではなく、`Clock` 抽象（`SystemClock`）が供給した値を渡す設計とし、「サーバが付与した」ことを application 層で明示・テスト可能にする（DB default に隠すより CA 的に明快）。
- インデックス: 0001 は読み取り API なし（一覧/推移は 0003）。`created_at` のソート用インデックスは 0003 で並べるときに追加すればよく、0001 では `gun_id` の FK インデックス（多くの DB で自動）以外は不要。過剰なインデックスを今足さない。
- 将来 PostgreSQL 移行: `Numeric`・`DateTime(timezone=True)`・標準 FK のみ使用。SQLite 固有を避ける。

### 4.3 entity ↔ ORM 変換（infrastructure のリポジトリ）

- `ScoreRepository.add(score: Score, created_at: datetime) -> PersistedScore`: domain `Score` の値オブジェクト（`Accuracy.value: Decimal|None`・`AverageReactionTime.ms: Decimal|None`）を ORM の nullable カラムへ写像 → INSERT（`flush` で id 採番。commit は composition root の UoW 境界）→ 採番された `id`・`created_at` と domain `Score` を application の出力 dataclass `PersistedScore`（`id`・`score`・`created_at`）に載せて返す。**domain `Score` は frozen で id/created_at を持たない（§2.2）ため変更せず**、永続化由来の id/created_at を集約の外に保つ。ORM インスタンスは外へ返さない。
- `GunRepository.get_default_id() -> int`: 既定銃の ID を返す（seed 済み前提）。無ければ起動 seed が作るので、通常は1件存在。

---

## 5. フロント設計（Vite + React・Canvas）

進行中セッションの状態・判定・計測・タイマー・サマリ・「もう一度」・計上規則をすべて担う（@e2e 19 シナリオ）。React + TypeScript strict（`any` 禁止）。Atomic Design ＋ Smart/Dumb 分離。

### 5.1 `lib/`（フレームワーク非依存・純粋・単体テスト可）

描画・React・DOM に依存しない純粋関数。Vitest で単体テスト（@e2e と別に純粋ロジックを固める）。

- **`geometry.ts`**
  - `isHit(clickX, clickY, target: {x, y, radius}): boolean` — 二乗距離比較 `(dx*dx + dy*dy) <= radius*radius` で hit 判定（R-1/R-3。平方根回避 ＝ discovery の決定。縁ちょうど `distance == radius` は hit）。
- **`session.ts`**（純粋なセッション/集計ロジック。状態を引数で受け取り新状態を返す関数群）
  - セッション状態型 `SessionState = { status: 'idle'|'running'|'finished', startedAt, hits, totalClicks, reactionTimes: number[], target }`。
  - `registerClick(state, click, now): SessionState` — クリック1つを適用し新状態を返す。内部で R-1〜R-8・R-20/21/22 の計上規則を判断:
    - 終了後（`status==='finished'` または `now > endTime`）→ 無視（R-22）。
    - 終了時刻ちょうど（`now == endTime`）→ 含める（R-8）。
    - hit 済み的の再クリック → 無視（R-20。的を hit 済みにする＝即 respawn なので「同じ的」が残らない実装でも、判定時に的が既に消費済みなら無視）。
    - キャンバス/プレイ領域外（呼び出し側が領域内クリックのみ渡す前提。座標が領域外なら無視 ＝ R-21）。
    - hit（`isHit` 真）→ `hits+1`・`totalClicks+1`・`reactionTimes.push(now - target.spawnedAt)`（reaction_time。0ms 有効・負値は単調時計で発生しない ＝ R-1/R-2）・次の的を spawn（R-5）。
    - miss（領域内・的外）→ `totalClicks+1`・hits 不変・reaction_time 記録せず（R-3/R-4。デバウンスなし＝連打は各回計上）。
  - `spawnTarget(): Target` — 次の的を1つ生成（プレイ領域内のランダム位置・固定 radius）。常に1つ（R-6）。寿命・移動なし（時間で消さない／動かさない ＝ R-6）。
  - `tick(state, now): SessionState` — 経過時間で `status` を `finished` に遷移（30 秒 ＝ R-7）。的の移動・消滅は**しない**（R-6）。
  - `endTime = startedAt + time_limit_ms`（30000）。
- **`summary.ts`**（サマリ用プレビュー算出。サーバと同じ規則をフロントでも算出して表示）
  - `computeAccuracy(hits, totalClicks): number | null` — `totalClicks===0 ? null : hits/totalClicks`（R-9/18/19。null は「—」）。
  - `computeAvgReactionTime(reactionTimes): number | null` — `reactionTimes.length===0 ? null : 平均`（R-9/18/19）。
  - `formatAccuracy(value: number|null): string` — `null → "—"`、それ以外 → `"62.5%"`（R-18/19）。
  - `formatAvg(value: number|null): string` — `null → "—"`、それ以外 → `"### ms"`（R-18/19）。
- **`time.ts`**: `now(): number` を `performance.now()` でラップ（単調時計。壁時計 `Date.now()` を計測に使わない ＝ Rule 11）。テストで差し替え可能にするためのシーム。

> サマリ算出をフロント `lib/` にも置く理由: R-9/18/19 は @e2e（フロント完結）。サーバ算出（domain）は永続化用の確定値であり、画面表示はフロントが自分の state から出す（discovery 決定12: サマリは画面 state から表示）。同じ規則を二箇所に持つが、純粋関数として両者でテストでき、責務（表示=フロント／永続化=サーバ）が明確。

### 5.2 `canvas/`（命令的描画・React state に乗せない）

- **`renderer.ts`** — `requestAnimationFrame` ループで Canvas に的と HUD（残り時間・hits/total_clicks）を描く。React の再レンダーから分離（state に乗せない ＝ frontend-architecture）。
- 入力: 現在の `SessionState`（描画専用に ref で渡す）。出力: Canvas 描画のみ。
- 色・余白は `design`（Tailwind トークン）と揃える（Canvas は CSS が効かないのでトークンの値を定数化して参照）。

### 5.3 `api/`（backend 呼び出し集約・SWR）

- **`submitSession.ts`** — `POST /api/sessions` の1呼び出しのみ（完了時1回 ＝ Rule 11）。fetch 直書きせず集約。
- 送信ボディ: `{ hits, totalClicks, reactionTimes, timeLimitMs }`（accuracy/avg/gunId/createdAt は送らない ＝ §3.3）。
- 戻り値型 `ScoreResponse`（`api/` に型定義）。`accuracy`・`avgReactionTime` は `number | null`。
- **SWR の使い方**: これは作成（POST）なので取得用 SWR フックではなく、`useSWRMutation`（または `mutate` ベースの submit フック）で `isMutating`/`error` を扱う。`error` を UI が拾って R-16（保存失敗通知）を出す。`isLoading`/`error` を必ず扱う（frontend-architecture）。

### 5.4 `components/`（Atomic Design・Smart/Dumb）

- **Smart（薄く）**
  - `ShootingSessionContainer`（organism/page 相当・Smart）: セッション状態（`useReducer`/`useState` ＋ `lib/session` の純粋関数）・タイマー（`requestAnimationFrame`＋`time.now`）・クリックハンドラ（Canvas の `onClick` → 領域判定 → `registerClick`）・終了検知（`tick` が `finished`）→ `submitSession` 実行（SWR mutation）・「もう一度」でリセット（R-10）。状態は React、描画は ref 経由で `canvas/renderer` へ。
- **Dumb（多く・props のみ・Vitest でテスト）**
  - `StartButton`（atom）— スタート（R-7 の開始トリガ）。`data-testid="start-button"`。
  - `GameCanvas`（molecule・Dumb 寄りだが canvas ref を持つ）— `<canvas>` 要素。クリック座標を親へ通知。`data-testid="game-canvas"`。
  - `ResultSummary`（organism・Dumb）— サマリ表示（R-9/18/19）。props: `accuracyText`・`avgText`・`hits`・`totalClicks`。`data-testid`: `summary-accuracy`・`summary-avg`・`summary-hits`（"5/8" 形式）。
  - `PlayAgainButton`（atom）— 「もう一度」（R-10）。`data-testid="play-again-button"`。
  - `SaveErrorNotice`（molecule・Dumb）— 保存失敗通知（R-16）。`error` があるとき表示。`data-testid="save-error-notice"`。
  - `Hud`（molecule・Dumb）— 残り時間・現在 hits/total_clicks（任意。Canvas 内描画でも可）。

### 5.5 `data-testid` 計画（@e2e の操作・検証対象 DOM）

| testid | 要素 | 用途（シナリオ） |
| --- | --- | --- |
| `start-button` | スタートボタン | セッション開始（R-7） |
| `game-canvas` | `<canvas>` | クリック操作の的（座標はテストシーム経由） |
| `summary-accuracy` | サマリの命中率 | R-9（62.5%）・R-18/19（"—"・0%） |
| `summary-avg` | サマリの平均反応時間 | R-9・R-18/19（"—"） |
| `summary-hits` | サマリの hits/total_clicks | R-9（"5/8"） |
| `play-again-button` | もう一度 | R-10 |
| `save-error-notice` | 保存失敗通知 | R-16 |

### 5.6 E2E テストシーム（Canvas は DOM が無い）

Canvas の的は DOM 要素でないため `data-testid` を付けられない。@e2e（playwright-bdd は implement で導入）が的をクリック・状態を検証できるよう、**テスト用のシーム**を計画する（本番挙動を変えない、テスト時のみ露出）:

- **的座標の露出**: 現在の的の中心 `(x, y)`・`radius` を `window.__aimTest?.getTarget()` 等で読み取れるようにする（テストはこの座標を Playwright の `mouse.click` に渡し、内側/縁/外側を撃ち分ける ＝ R-1/R-2/R-3 の境界）。
- **セッション状態の露出**: `status`・`hits`・`totalClicks`・`reactionTimes.length`・残り時間を `window.__aimTest?.getState()` で読めるようにする（R-5/6/8/20/21/22 の検証）。
- **時間の制御**: タイマーを `time.now`（`performance.now` ラッパー）に集約し、E2E では仮想時間／早送り（30 秒経過・終了時刻ちょうど・終了後クリックの検証 ＝ R-7/R-8/R-22）を注入できるシームを用意（実装方式は implement／e2e-testing で確定。Playwright の clock API または注入関数）。
- **保存失敗の注入**: `submitSession` をネットワークレベルで失敗させる（Playwright の route abort）→ R-16 の通知を検証。テストシームというよりネットワークスタブ。

> data-testid は本番に残してよい（属性のみ）。`window.__aimTest` 系は**本番ビルドで無効化**（環境フラグでガード）し、テスト時のみ有効にする方針（実装時に確定）。

---

## 6. 全体のデータフロー（責務分担の要約）

1. プレイヤーが `start-button` → フロントがセッション開始（`status='running'`・`startedAt = time.now()`・最初の的を spawn）。R-7 開始。
2. クリックごとにフロント `lib/session.registerClick` が hit/miss・reaction_time・respawn・計上規則を適用（R-1〜R-6・R-8・R-20/21/22）。サーバ通信なし。
3. `tick` が 30 秒で `status='finished'`（R-7）→ サマリを画面 state から表示（`summary.format*`。R-9/18/19）。
4. 同時に `submitSession` が生データ（hits・total_clicks・reaction_times・time_limit_ms）を `POST /api/sessions`（Rule 11・完了時1回）。
5. サーバ: Pydantic で形検証 → `RecordSessionResult` → `Score.create`（domain が accuracy・平均算出＋不変条件検証。R-11/12/13/18/19）→ 既定銃 ID 解決 → `created_at` 付与（R-15）→ ORM で1行 INSERT（R-14）→ 201＋`ScoreResponse`。違反は 422、DB 失敗は 500。
6. フロント: 成功なら通知なし（サマリ表示継続）。失敗（非 2xx）なら `save-error-notice` を表示しサマリは残す（R-16）。
7. `play-again-button` → フロントが hits・total_clicks・reaction_times を 0 リセットし新セッション開始（R-10）。中断（30 秒前にやめる）は submit しない（R-17）。

---

## 7. トレーサビリティ（R-1〜R-22 全件 → 設計要素・責務）

責務: **F**=フロント（@e2e）／**B**=バックエンド（@backend）。

| R-x | 要件要旨 | 責務 | 設計要素 |
| --- | --- | --- | --- |
| R-1 | 内側クリック=hit、total_clicks+1、reaction_time(ms) 記録 | F | `lib/geometry.isHit`（二乗距離）・`lib/session.registerClick`（hit 分岐・reactionTimes.push）・`lib/time.now`（performance.now） |
| R-2 | 同フレーム hit は 0ms 有効・負を記録しない | F（＋B 検証） | `lib/session`（now-spawnedAt、単調時計で非負）／domain `ReactionTime`（ms≥0・0 有効） |
| R-3 | 外側クリック=miss、total_clicks+1、hits 不変、reaction_time 記録せず | F | `lib/geometry.isHit` 偽・`lib/session.registerClick`（miss 分岐） |
| R-4 | 空白連打は全 miss 計上・デバウンスなし | F | `lib/session.registerClick`（クールダウン無し・各クリック計上） |
| R-5 | hit で次の的を1つ spawn | F | `lib/session.spawnTarget`（hit 後に1つ生成） |
| R-6 | 常に的1つ・寿命なし・移動なし | F | `lib/session`（target は単一・`tick` で消さない/動かさない）・`canvas/renderer`（1つ描画） |
| R-7 | 30 秒で自動終了→集計へ | F | `lib/session.tick`（startedAt+30000 で finished）・`ShootingSessionContainer`（rAF タイマー） |
| R-8 | 終了時刻ちょうどは含める／超過は除外 | F | `lib/session.registerClick`（now==endTime 含む・now>endTime 除外） |
| R-9 | 終了時に accuracy・平均・hits/total を表示 | F | `lib/summary.compute*`/`format*`・`ResultSummary`（testid: summary-accuracy/avg/hits） |
| R-10 | 「もう一度」で 0 リセットして新規開始 | F | `ShootingSessionContainer` のリセット・`PlayAgainButton`（testid: play-again-button） |
| R-11 | accuracy=hits÷total_clicks を算出 | B | domain `Accuracy.from_counts`・`Score.create`／（表示プレビューは F `lib/summary`） |
| R-12 | 平均 reaction_time はヒットのみで算出 | B | domain `AverageReactionTime.from_hits`（miss は list 非包含） |
| R-13 | 不変条件違反は拒否・永続化しない（hits>total / 負 reaction / accuracy 範囲外） | B | domain `Score.create` の検証＋`InvariantViolation`／api 422＋`ErrorResponse`（accuracy=1.5 は §3.3 の通り入力非受理＋値オブジェクト単体検証） |
| R-14 | 検証通過で score 1行永続化（accuracy・平均・hits・total・制限時間・既定銃参照）・明細保存せず | B | usecase `RecordSessionResult`・`ScoreRepository.add`・`score` テーブル（明細なし） |
| R-15 | created_at はサーバ付与・クライアント時刻不使用 | B | `Clock`/`SystemClock`・usecase で付与・入力 DTO に時刻なし・`score.created_at` |
| R-16 | 永続化失敗時はサマリ維持＋保存失敗通知 | F（＋B が非2xx 返却） | `api/submitSession`（SWR error）・`SaveErrorNotice`（testid: save-error-notice）／api 500＋`ErrorResponse` |
| R-17 | 30 秒未達の中断は永続化しない | F | `ShootingSessionContainer`（finished 時のみ submit。中断は POST しない） |
| R-18 | total_clicks=0 → accuracy/平均「—」表示・score は保存 | F＋B | F `lib/summary.format*`（null→"—"）・`ResultSummary`／B `Accuracy.from_counts`(None)・`score.accuracy` nullable・保存可 |
| R-19 | hits=0 & total>0 → accuracy 0%・平均「—」 | F＋B | F `lib/summary`（accuracy=0 表示・avg null→"—"）／B `AverageReactionTime.from_hits([])`=None・nullable |
| R-20 | hit 済み的の再クリックは無視（hits/total 不変） | F | `lib/session.registerClick`（hit 済み的は consume 済みで無視） |
| R-21 | キャンバス外/HUD クリックは無視（hits/total 不変） | F | `ShootingSessionContainer`/`GameCanvas`（領域判定で `registerClick` を呼ばない）・`lib/session`（領域外無視） |
| R-22 | 終了後クリックは無視（hits/total 不変） | F | `lib/session.registerClick`（status finished/now>endTime で無視） |

**網羅集計**: R-1〜R-22 の **22 件すべて**を設計要素に対応づけた。内訳 — フロントのみ: R-1, R-3, R-4, R-5, R-6, R-7, R-8, R-9, R-10, R-17, R-20, R-21, R-22（13 件）／バックエンドのみ: R-11, R-12, R-13, R-14, R-15（5 件）／フロント＋バック両面: R-2（記録=F／非負検証=B）, R-16（通知=F／非2xx=B）, R-18（表示=F／算出・nullable=B）, R-19（表示=F／算出・nullable=B）（4 件）。これは acceptance.feature のタグ分布（@e2e 19・@backend 8）と整合する。

---

## 8. 人間ゲートで確認すべき設計上の論点・リスク

1. **R-13「accuracy=1.5 を申告」の解釈**（最重要）。本設計は accuracy をクライアント入力に**持たせない**（domain が算出）ため、「accuracy フィールドに 1.5 を渡す」経路が存在しない。Scenario Outline の主旨（不正 accuracy を保存しない）は `Accuracy` 値オブジェクトの範囲不変条件＋domain 単体テストで満たすが、「API に 1.5 を POST して 422」という形の検証はできない（未知フィールドは無視/拒否）。この解釈で @backend シナリオを満たせるか、ステップ定義の書き方を implement 前に合意したい。代替案: accuracy を入力に含めて domain で「申告 accuracy と算出 accuracy の不一致／範囲外」を弾く設計もありうるが、R-11（domain が算出）と二重管理になり非推奨。**推奨は本設計（持たせない）**。

2. **マイグレーション方式**（Alembic を 0001 で導入するか）。MVP は `create_all`＋起動時 seed でも動くが、将来 PostgreSQL 移行・0002 の非破壊カラム追加を見据えると Alembic 導入が無難。一方で学習用最小構成なら 0001 は `create_all` で始め 0002 で Alembic 化も可。**どちらで始めるか**を決めたい（design では「起動時 seed・非破壊追加可能」までを規定し、ツール選定は実装方針として残す）。

3. **`created_at` のサーバ付与を「アプリ層の Clock」か「DB server_default」か**。本設計は `Clock` 抽象（アプリ層）で付与し「サーバが付けた」ことをテスト可能にした（CA 的に明快）。DB default に寄せる案もあるが、application でのテスト容易性と「クライアント時刻不使用」の明示性を優先。この方針で良いか。

4. **gun_id をサーバが解決（入力に含めない）**。0001 は固定の既定銃で、クライアント申告より改ざん耐性・単純さで優るためサーバ解決とした。requirements は「既定の gun 参照」とのみ規定し申告主体を縛っていないので逸脱ではないが、明示確認したい。

5. **E2E テストシーム（`window.__aimTest`）の本番無効化**。Canvas の的・状態・時間を露出するシームは E2E に必須だが、本番ビルドで無効化（環境フラグ）する前提。露出の具体 API 形・時間制御の方式（Playwright clock か注入か）は e2e-testing 参照で implement 時に確定。設計としてシームの**必要性と無効化方針**を承認したい。

6. **サマリ算出の二重持ち**（フロント `lib/summary` とサーバ domain の両方が accuracy/平均を算出）。表示=フロント完結（R-9 は @e2e）／永続化=サーバ算出という責務分担の必然だが、「同じ式が2箇所」になる。純粋関数として両者でテスト可能・責務は分離、という整理で許容する判断。問題ないか。

7. **時間境界（R-8）の単調時計依存**。`now==endTime ちょうど含む／超過除外` は `performance.now()` の連続値では「ちょうど一致」が実機では起きにくい。判定は `now <= endTime` を含む・`now > endTime` を除外、という**閉区間境界**で実装する（シナリオの意図＝「ちょうどは含む」を `<=` で表現）。この境界実装で R-8 を満たすことを確認したい。

---

## 8.5 人間ゲートでの決定（2026-06-21）

- **論点1（R-13 accuracy=1.5）→ 設計維持**。accuracy をクライアント入力に持たせない現設計を採用。「accuracy=1.5」は `Accuracy` 値オブジェクトの範囲不変条件の @backend 単体テストとして acceptance.feature を再構成（scenario-author 担当）。重複していた単体 R-13 シナリオ（hits=9/total=8）も整理。→ **acceptance.feature 再確認が必要**。
- **論点2（マイグレーション）→ Alembic を 0001 で導入**（§4.1 に反映）。以降のスキーマ変更も migration で積む。
- **論点3〜7 → 承認**: created_at は Clock で付与／gun_id はサーバ解決／E2E テストシームは本番無効化／サマリ算出の二重持ちを許容／R-8 は閉区間境界（`now ≤ endTime` 含む・`> endTime` 除外）で実装。

---

## 9. 完了の定義（この design）

design.md が揃い、R-1〜R-22 のすべてが設計要素（ドメイン／ユースケース／エンドポイント／テーブル／フロントのモジュール・純粋関数）に対応づき、人間が承認して本書を `Status: Approved` にした状態。→ 次は `tasks`。
