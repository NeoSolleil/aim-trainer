# Aim Trainer

FPS エイム練習アプリ（個人・学習用）。SDD（仕様駆動開発）をフル装備で実践する監督下プロジェクト。
プロジェクトの方針・構成・規約は [CLAUDE.md](CLAUDE.md)（プロジェクト憲法）を正本とする。

## 構成（モノレポ）

- `backend/` … FastAPI + SQLAlchemy 2.0。Clean Architecture でレイヤ分割。パッケージ管理は uv。
- `frontend/` … Vite + React 19 + TypeScript。描画は Canvas。パッケージ管理は npm。
- `specs/` … SDD 成果物（EARS 要件・Gherkin・設計・タスク）。
- `.claude/` … ハーネス（rules / skills / agents / settings）。

## セットアップ

前提ツール（未インストールならまず導入）:

- [uv](https://docs.astral.sh/uv/)（Python パッケージ管理。Python 3.13 も uv が取得する）
- [Node.js](https://nodejs.org/) LTS（npm 同梱）

```bash
# backend
cd backend
uv sync                 # 依存解決 + uv.lock 生成、Python 3.13 を取得
uv run uvicorn app.main:app --reload

# frontend
cd frontend
npm install             # 依存解決 + package-lock.json 生成
npm run dev
```

## 品質チェック

```bash
# backend
cd backend
uv run ruff check .          # lint
uv run ruff format --check . # format
uv run pyright               # 型（strict）
uv run lint-imports          # Clean Architecture の依存方向（import-linter）
uv run xenon --max-absolute B --max-modules B --max-average A app
uv run pytest                # テスト

# frontend
cd frontend
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
```
