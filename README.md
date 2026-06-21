# Aim Trainer

FPS のエイム（反応速度・命中率）を測る練習アプリ。**個人・学習用**だが、主眼は機能そのものより **「AI を監督下で開発するための仕組み（ハーネス）」と SDD（仕様駆動開発）・Clean Architecture をフル装備で実践すること**にある。

- 画面の的（target）をクリック → 30 秒のセッションで反応時間・命中率を計測 → スコアを保存。
- 縦切りの機能を `discover → specify → plan → tasks → implement` の SDD パイプラインで 1 本ずつ完成させる。
- プロジェクトの方針・構成・規約の**正本は [CLAUDE.md](CLAUDE.md)**（プロジェクト憲法）。

## 現在の状態

- ✅ **機能 0001「射撃セッション（shooting-session）」完成** — backend＋frontend、受け入れシナリオ **27 件（`@backend` 7 / `@e2e` 20）すべて green**、全品質ゲート緑。実プレイ（プレイ→スコア保存）まで動作確認済み。
- 🗺️ ロードマップ（予定）: **0002** 銃の選択・挙動（連射速度／反動／的サイズ）→ **0003** 成績推移の表示 → **0004** 認証(JWT)・ランキング。

## このリポジトリの主眼

- **SDD パイプライン**: 機能ごとに 5 段階（発見→仕様化→設計→分解→実装）。各段階に**人間レビューのゲート**（`Status: Draft → Approved`）。成果物は `specs/<feature>/` に蓄積する（EARS 要件＋Gherkin シナリオ＋設計＋タスク）。
- **Clean Architecture（厳密版）**: 依存は内向きのみ。`domain` はフレームワーク非依存の純粋層。依存方向は **import-linter で機械強制**する。
- **多層のガードレール（ハーネス）**: 事実共有（CLAUDE.md）／パススコープのルール（`.claude/rules/`）／決定論的強制（pre-commit・Claude フック・CI）／SDD を駆動する Skills とレビューする Agents（`.claude/skills`・`.claude/agents`）。詳細は CLAUDE.md。
- **BDD テスト**: 受け入れシナリオ（Gherkin）を 1 つの原本（`specs/<feature>/acceptance.feature`）にし、backend は `pytest-bdd`（`@backend`）、E2E は `playwright-bdd`（`@e2e`）で実行する。

## 技術スタック

| 層 | 採用 |
| --- | --- |
| フロント | Vite + React 19 + TypeScript(strict) ／ Canvas 描画 ／ Tailwind v4 ／ SWR |
| バック | FastAPI（Python 3.13）／ SQLAlchemy 2.0（ORM 必須・直接 SQL 禁止）／ Alembic ／ Pydantic v2 |
| DB | SQLite（将来 PostgreSQL へ移行可能に設計） |
| パッケージ管理 | Python: uv ／ Node: npm（lockfile をコミットして再現性担保） |
| テスト | backend: pytest + pytest-bdd ／ frontend: Vitest ／ E2E: Playwright + playwright-bdd |
| 品質 | backend: Ruff / Pyright(strict) / import-linter / xenon ／ frontend: ESLint / Prettier / tsc(strict) / Vite build |
| 強制 | pre-commit（ローカル）＋ GitHub Actions CI（backend / frontend / E2E ジョブ） |

## アーキテクチャ

backend は Clean Architecture。レイヤは外側から `infrastructure → adapters → application → domain`（**内向き依存のみ**）。

- `domain` … エンティティ・値オブジェクト（純粋。FastAPI/SQLAlchemy/Pydantic を import しない）。
- `application` … ユースケース＋リポジトリ抽象（依存性逆転）。
- `adapters` … FastAPI ルーター（`api/`）と Pydantic DTO（`schemas/`）。
- `infrastructure` … SQLAlchemy モデル・リポジトリ具象・設定・Alembic。
- 結線は composition root（`backend/app/main.py`）。

依存方向は **import-linter の契約**（`backend/pyproject.toml`）で機械的に検証する（`domain` への FW import などは CI/pre-commit でブロックされる）。

## ディレクトリ構成

```
aim-trainer/
├── CLAUDE.md          # プロジェクト憲法（正本）
├── .claude/           # ハーネス（rules / hooks / skills / agents / settings）
├── specs/             # SDD 成果物（機能ごと）
│   └── 0001-shooting-session/   # discovery / requirements(EARS) / acceptance(Gherkin) / design / tasks
├── backend/           # FastAPI（Clean Architecture）
│   ├── app/{domain,application,adapters,infrastructure}/
│   ├── alembic/       # マイグレーション
│   └── tests/         # pytest-bdd（@backend）＋ unit / infra
└── frontend/          # Vite + React
    ├── src/{lib,canvas,api,components}/
    └── e2e/           # playwright-bdd（@e2e）
```

## セットアップ & 起動

前提: [uv](https://docs.astral.sh/uv/)（Python 3.13 も uv が取得する）／ [Node.js](https://nodejs.org/) LTS（npm 同梱）。

```bash
# ① backend（http://localhost:8000）
cd backend
uv sync                                   # 依存解決
uv run alembic upgrade head               # DB(SQLite)＋テーブル作成（初回／DB 削除後は必須）
uv run uvicorn app.main:app --reload      # 起動（起動時に既定銃を seed）

# ② frontend（http://localhost:5173）— 別ターミナル
cd frontend
npm install
npm run dev
```

ブラウザで <http://localhost:5173> を開く → **スタート** → 30 秒間 的をクリック → 結果（命中率・平均反応時間・ヒット数）→ **もう一度**。スコアは Vite の dev proxy（`/api` → `:8000`）経由で backend に送られ、SQLite（`backend/aim_trainer.db`）に保存される。

> 注: `app/main.py` はテーブルを自動作成しない（スキーマは Alembic が管理）。DB ファイルを消した場合は再度 `alembic upgrade head` してから起動する（さもないと起動時の seed が `no such table` で失敗する）。

## テスト & 品質チェック

```bash
# backend
cd backend
uv run pytest                 # 全テスト（pytest-bdd 含む）
uv run pytest -m backend      # 受け入れ @backend シナリオのみ
uv run ruff check . && uv run ruff format --check .
uv run pyright                # 型（strict）
uv run lint-imports           # Clean Architecture 依存方向（import-linter）
uv run xenon --max-absolute B --max-modules B --max-average A app

# frontend
cd frontend
npm run test                  # Vitest（純粋ロジック・コンポーネント）
npm run test:e2e              # playwright-bdd（@e2e）※ 初回は `npx playwright install chromium`
npm run lint && npm run format:check && npm run typecheck && npm run build
```

push / PR で GitHub Actions CI が backend・frontend・E2E を再実行する（pre-commit と同じ関門を権威化）。

## ブランチ

- `main` … 機能開発の本線。
- `harness-only` … 機能コードを載せない「ハーネスだけ」の基点。他プロジェクトのテンプレートに流用できる。
