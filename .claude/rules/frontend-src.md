---
paths:
  - "frontend/src/**"
---

# frontend/src のルール

Vite + React 19 + TypeScript strict。描画は Canvas。

## MUST
- **TypeScript strict を守る**。`any` を使わない（`unknown` ＋ 絞り込み、または正確な型を定義）。
  → `tsc --noEmit`（strict）と ESLint で検査。
- **バックエンド呼び出しは `src/api/` 経由**に集約する。コンポーネント内に `fetch` を直書きしない。
- **Canvas の描画ロジックは `src/canvas/`** に置く（React コンポーネントから分離）。
- UI コンポーネントは `src/components/`。表示に専念させ、データ取得・副作用と分離する（Smart/Dumb 分離）。

## MUST NOT
- Prettier 整形を外れたコードをコミットしない（`npm run format:check`）。
- ビルド成果物（`dist/`）を編集・追跡しない（`.gitignore` / `.prettierignore` 済み）。

## 補足
詳細な frontend アーキテクチャ（Clean Architecture ＋ Atomic Design・SWR 等）は、後続の `frontend-architecture` スキルで定義する。本ファイルはディレクトリ責務の最小ルール。
