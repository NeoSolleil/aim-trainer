# CLAUDE.md — Aim Trainer

FPSエイム練習アプリ。個人・学習用。SDD（仕様駆動開発）をフル装備で実践するための監督下プロジェクト。
このファイルはコードベースの索引である。詳細な手順・制約・強制は、各セクションが指すファイルに置かれている。

## このプロジェクトで何を作るか

画面上の的をクリックして反応速度・命中率を測る練習ツール。
銃の種類によって挙動（連射速度・反動・的サイズ）が変わり、スコアと反応時間を記録して成績推移を見られる。
発展としてユーザー認証とランキングを想定する。

詳細な要件は specs/ 配下の各機能フォルダを参照（EARS要件とギャーキンシナリオ）。

## 技術スタック

- フロント: Vite + React。描画は Canvas。
- バック: FastAPI（Python）。自動OpenAPIドキュメント生成。
- DB: SQLite。アクセスは SQLAlchemy 2.0 経由（ORM必須、直接SQL禁止）。将来 PostgreSQL へ載せ替え可能に保つ。
- テスト: backend は pytest + pytest-bdd。frontend は Vitest + Playwright。
- 初期データモデル: 銃マスタ（gun）とスコア記録（score）の2テーブル。外部キーで接続。
- パッケージ管理: Python は uv、Node は npm。いずれも lockfile をコミットして再現性を担保。
- 主要バージョン: Python 3.13+、Node.js LTS、React 19、TypeScript strict、Vite。
- 品質チェック（backend）: Ruff（lint＋format）、Pyright（strict 型）、import-linter（CA依存方向の検証）、xenon（複雑度）。
- 品質チェック（frontend）: ESLint、Prettier、tsc（strict 型）、Vite build。
- 強制: pre-commit（ローカル）と GitHub Actions CI（無料枠）で自動実行。CodeQL はリポジトリ公開時のみ。AWS/IaC は不採用（ローカル＋git 管理）。

## アーキテクチャ

backend は **Clean Architecture** に準拠する。レイヤは外側から infrastructure → adapters → application → domain（domain が最内）。

- **依存は内向きのみ**。`domain` は何にも依存しない（FastAPI・SQLAlchemy・Pydantic を import しない）。`application` は `domain` のみに依存。外側（adapters・infrastructure）は内側に依存してよいが、逆は禁止。
- **ドメインエンティティと SQLAlchemy モデルは分離する**（厳密版）。`domain/` は永続化に無依存の純粋クラス、`infrastructure/` に SQLAlchemy モデルとリポジトリ実装を置き、両者を相互変換する。
- application はリポジトリの**インターフェース（抽象）**を定義し、具象実装は infrastructure に置く（依存性逆転）。FastAPI と DB の結線は composition root（`app/main.py`）で行う。

依存方向の強制（import 違反のブロック等）は `.claude/rules/` とフックに置く。このセクションは事実の共有に徹する。

## ディレクトリ構成

```
aim-trainer/
├── CLAUDE.md              # このファイル（索引）
├── .claude/               # ハーネス（下記「ハーネス」参照）
├── specs/                 # SDD成果物（下記「SDDワークフロー」参照）
├── backend/               # FastAPI。app/ は Clean Architecture でレイヤ分割、tests/ にpytest-bdd
└── frontend/              # Vite+React。src/ にコード
```

backend は Clean Architecture（下記「アーキテクチャ」参照）でレイヤを切る。

- backend/app/domain/ … エンティティ・値オブジェクト（純粋。フレームワーク非依存、何も import しない）
- backend/app/application/ … ユースケース＋リポジトリのインターフェース（抽象）
- backend/app/adapters/api/ … FastAPIルーター（コントローラ）
- backend/app/adapters/schemas/ … Pydantic DTO（入出力の検証）
- backend/app/infrastructure/ … SQLAlchemyモデル・DB接続・リポジトリ実装・設定
- backend/tests/step_defs/ … pytest-bddのステップ定義
- frontend/src/canvas/ … 描画ロジック
- frontend/src/api/ … バックエンド呼び出し

各サブディレクトリ固有の規約は、そのディレクトリ内の CLAUDE.md または .claude/rules/ のパススコープルールに置く（このファイルには書かない）。

## SDDワークフロー

本プロジェクトは spec-first〜spec-anchored で進める。AIが各段階を起草し、人間が各ゲートでレビューする。
段階を駆動するプロンプトは .claude/skills/ のスキルとして定義されている。

| 段階 | スキル | 入力 | 出力 |
|------|--------|------|------|
| 1. specify | /specify | アイデア・要望 | specs/<feature>/requirements.md（EARS）＋ acceptance.feature（ギャーキン） |
| 2. plan | /plan | 上記仕様 | specs/<feature>/design.md（DDD設計・API契約・テーブル定義） |
| 3. tasks | /tasks | 設計 | specs/<feature>/tasks.md（作業分解。既存シナリオを参照しグルーピングするのみ） |
| 4. implement | /implement | 設計＋ギャーキン | テストコード（pytest-bdd変換）→ 最小実装（TDD: red→green→refactor） |

各段階の終わりは人間レビューのゲート。レビュー承認まで次段階に進まない。

スキルは2系統を**併用**する。

- **段階駆動スキル**（上表）: specify / plan / tasks / implement。SDDのワークフローを前進させる手続き役。
- **ドメイン参照スキル**: 段階駆動スキルが必要に応じて参照する知識役。
  - ubiquitous-language … ユビキタス言語（用語集）。全タスクで最初に参照。
  - backend-architecture … Clean Architecture・Pydantic v2・依存性逆転・負荷テスト設計。
  - frontend-architecture … Clean Architecture ＋ Atomic Design・Smart/Dumb 分離・SWR。
  - design … Tailwind CSS のデザイントークン（スペーシング・カラー等）。
  - bdd … Gherkin の書き方（Feature/Rule/Example、BRIEFの原則）。
  - e2e-testing … Playwright + playwright-bdd（Gherkin→コード生成、data-testid 必須）。

## 記法ルール

- 要件は EARS形式で書く（例: WHEN <トリガー>, the <システム> SHALL <応答>）。EARSは「ルールの台帳」。
- 受け入れ基準は ギャーキン（Given-When-Then）で書く。EARS要件1件に対しシナリオが複数ぶら下がる（正常系・異常系・境界値）。
- ギャーキンの一次著作は specify段階の1回のみ。下流（tasks/implement）はこれを参照・変換するだけで、新規作成しない。
- ギャーキン原本は specs/<feature>/acceptance.feature。pytest-bdd実行時は backend 側から参照する。
- 設計段階では DDDの語彙（境界づけられたコンテキスト・集約・ドメインイベント）を用いてモデリングする。

詳細な記法ガイドは .claude/skills/specify/ を参照。

## ハーネス（このプロジェクトでの監督の仕組み）

「設計通りに実装させる」ための4層。詳細は各ファイル。

- このファイル（CLAUDE.md）… 構成・規約の事実を共有する。
- .claude/rules/ … パススコープの制約（例: APIハンドラは入力検証必須、models配下はORM経由必須）。該当ファイルを触るときだけ読まれる。
- .claude/agents/ … 検証用サブエージェント（spec適合チェック役・テスト網羅チェック役）。独立コンテキストでレビューする。
- .claude/settings.json … Hooks登録。テスト未通過での完了不可、スコープ外編集ブロック等を決定論的に強制する。

注意: 「絶対に起きてはならないこと」はこのファイルの文章では強制できない。本物のガードレールは Hooks と権限設定に置く。

## コーディング規約

- コミットメッセージはセマンティック形式（feat/fix/test/refactor(scope): 説明）。
- backend: 型ヒント必須。Pydanticで入出力を検証。
- frontend: TypeScript strict。
- テストの無い実装を「完了」と見なさない（強制は Hooks）。
- specに無い機能を追加しない（スコープ厳守）。
```
