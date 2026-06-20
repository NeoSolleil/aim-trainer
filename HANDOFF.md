# ハンドオフ — Aim Trainer（セッション2終了時点 / 新PC・Ubuntu 移行用）

このドキュメントは、別PC（Ubuntu）でリポジトリをクローンして作業を再開するための引き継ぎ要約です。
**正本は [CLAUDE.md](CLAUDE.md)（プロジェクト憲法）**。本ファイルは「経緯・現在地・次の一手」を補う。

---

## 0. いまの現在地（3行）

- ハーネス4層のうち **CLAUDE.md（土台）が完成**し、**プロジェクトの最小スキャフォールド（backend/frontend）まで作成済み**。
- ただし **`uv sync` / `npm install` による実体化・検証は未完**（前PCの Windows 環境問題で中断。下記 §8・§9）。
- 次にやるのは「**新PCの Ubuntu でスキャフォールドを実体化・検証 → ハーネス残り3層（Rules/Hooks → Skills → Agents）の実装**」。

---

## 1. 作るもの

FPS エイム練習アプリ（個人・学習用、SPAベースのフルスタック）。

- 画面上の的をクリックして反応速度・命中率を測る。
- 銃の種類で挙動（連射速度・反動・的サイズ）が変わる。
- スコアと反応時間を記録し成績推移を見る。
- 発展でユーザー認証（JWT）とランキングを想定。

題材の出自: 以前「React + Python で旅館予約サイト」を作った経験（FARMスタック = FastAPI+React+MongoDB）。
今回は学習目的を主眼に、別アプリとしてエイム練習アプリを選定。MongoDB を学習向きの SQLite に置換した。

---

## 2. 確定した技術スタックとツールチェーン（このセッションの成果）

すべて CLAUDE.md「技術スタック」に反映済み。要点：

| 項目 | 決定 | 備考 |
| --- | --- | --- |
| フロント | Vite + React 19 + TypeScript strict | 描画は Canvas |
| バック | FastAPI（Python 3.13+） | 自動OpenAPI |
| DB | SQLite + SQLAlchemy 2.0（ORM必須・直接SQL禁止） | 将来 PostgreSQL へ載せ替え可能に保つ |
| Python パッケージ管理 | **uv** | lockfile（uv.lock）をコミット |
| Node パッケージ管理 | **npm** | lockfile（package-lock.json）をコミット。前回も npm、現在も主流という判断 |
| backend 品質 | Ruff（lint+format）/ Pyright（strict 型）/ **import-linter**（CA依存方向の検証）/ xenon（複雑度） | |
| frontend 品質 | ESLint / Prettier / tsc（strict）/ Vite build | |
| テスト | backend: pytest + pytest-bdd / frontend: Vitest + Playwright（playwright-bdd） | |
| 強制 | pre-commit（ローカル）+ GitHub Actions CI（無料枠） | CodeQL はリポジトリ公開時のみ。**AWS/IaC は不採用**（ローカル＋git 管理） |
| 初期DB | gun（銃マスタ）と score（スコア記録）の2テーブル、外部キー接続 | |

決定の経緯メモ：
- 「装備範囲」は前回の FARM 構成からフル装備（IaC/CloudFormation/MkDocs/CodeQL）を**コアに絞った**。AWS は使わずローカル＋git。CI/CD は GitHub Actions の無料枠で行う。pre-commit は行う。
- ディレクトリは `apps/web` ではなく **フラットな `backend/` + `frontend/`** を採用（2サービスの polyglot リポジトリで、JSモノレポツール非使用なら素直な定番、という判断）。

---

## 3. アーキテクチャ（Clean Architecture・厳密版）

backend は **Clean Architecture に準拠**。CLAUDE.md「アーキテクチャ」に反映済み。

- レイヤは外側から **infrastructure → adapters → application → domain**（domain が最内）。
- **依存は内向きのみ**。`domain` は何にも依存しない（FastAPI・SQLAlchemy・Pydantic を import しない）。`application` は `domain` のみに依存。
- **ドメインエンティティと SQLAlchemy モデルは分離（厳密版）**。`domain/` は純粋クラス、`infrastructure/` に SQLAlchemy モデルとリポジトリ実装、両者を相互変換。
- application がリポジトリの**インターフェース（抽象）**を定義し、具象は infrastructure に置く（依存性逆転）。
- FastAPI と DB の結線は composition root（`backend/app/main.py`）で行う。main.py は import-linter のレイヤ契約の外。
- **この依存方向を import-linter の layers 契約**（`backend/pyproject.toml` の `[tool.importlinter]`）で機械検証する。これが後段の Hooks/CI で「CA違反をブロック」する実体になる。

---

## 4. 開発手法（SDD フル装備）

- SDD（仕様駆動）を軸に spec-first〜spec-anchored。段階: **specify → plan → tasks → implement**。各段階をAIが起草、人間が各ゲートでレビュー。
- **EARS** = 抽象ルールの台帳（requirements.md）。**Gherkin** = その具体例＝合格条件（acceptance.feature）。EARS 1件に Gherkin が複数ぶら下がる。
- **Gherkin の一次著作は specify の1回のみ**。tasks/implement は参照・変換のみ（新規作成しない）。
- DDD の語彙（境界づけられたコンテキスト・集約・ドメインイベント）を設計段階で使う。
- BDD/TDD: Gherkin を pytest-bdd でテスト化（red）→ 最小実装（green）→ refactor。
- **Skills は2系統を併用**（CLAUDE.md「SDDワークフロー」参照）:
  - 段階駆動スキル: specify / plan / tasks / implement。
  - ドメイン参照スキル: ubiquitous-language / backend-architecture / frontend-architecture / design / bdd / e2e-testing。段階駆動スキルが必要に応じて参照する知識役。

---

## 5. ハーネス4層と進捗

「設計通りに実装させる」ための4層（CLAUDE.md「ハーネス」参照）。

| 層 | 置き場所 | 状態 |
| --- | --- | --- |
| 構成・規約の事実共有 | `CLAUDE.md` | **完成** |
| 層ごとの制約 | `.claude/rules/`（パススコープ） | 未着手 |
| SDD段階の駆動 | `.claude/skills/` | 未着手 |
| 設計適合の独立検証 | `.claude/agents/` | 未着手 |
| 逸脱の決定論的強制 | `.claude/settings.json`（Hooks） | 未着手 |

方針: 「禁止・強制はプロンプトに書かず、決定論的な仕組み（Hooks/権限）に置く」。

---

## 6. これまでに作成済みの成果物

### 6.1 CLAUDE.md（更新済み）
このセッションで以下を追記・修正:
- 技術スタックに uv/npm・主要バージョン・品質チェック・強制方針を追記。
- 「アーキテクチャ」節を新設（Clean Architecture、レイヤ順、domain と ORM の分離）。
- backend ディレクトリ構成を CA レイヤ（domain/application/adapters/infrastructure）へ書き換え。
- SDDワークフローの Skills を「段階駆動＋ドメイン参照の併用」に更新。

### 6.2 最小スキャフォールド（作成済み・未実体化）

```
aim-trainer/
├── .gitignore                         # Python/Node/OS。lockfile はコミットする旨を明記
├── README.md                          # セットアップ・品質チェック手順
├── CLAUDE.md                          # プロジェクト憲法（正本）
├── HANDOFF.md                         # このファイル
├── backend/
│   ├── pyproject.toml                 # uv 管理。deps + Ruff/Pyright/pytest/import-linter 設定込み
│   │                                  #   [tool.importlinter] に CA レイヤ契約を記述
│   ├── .python-version                # 3.13
│   └── app/
│       ├── __init__.py
│       ├── main.py                    # composition root。/health のみ
│       ├── domain/__init__.py         # 最内・依存ゼロ
│       ├── application/__init__.py    # ユースケース＋リポジトリ interface
│       ├── adapters/__init__.py
│       ├── adapters/api/__init__.py   # FastAPIルーター
│       ├── adapters/schemas/__init__.py  # Pydantic DTO
│       ├── infrastructure/__init__.py
│       └── infrastructure/db.py       # SQLAlchemy 2.0 Base/engine/SessionLocal
│   └── tests/
│       ├── __init__.py
│       ├── step_defs/__init__.py
│       └── features/.gitkeep
└── frontend/
    ├── package.json                   # React 19 / Vite / TS / ESLint / Prettier / Vitest
    ├── tsconfig.json                  # strict
    ├── vite.config.ts
    ├── eslint.config.js               # ESLint 9 flat config
    ├── .prettierrc
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── vite-env.d.ts
        ├── api/.gitkeep
        ├── canvas/.gitkeep
        └── components/.gitkeep
```

注意: 依存のバージョンは下限（`>=` / `^`）で記述。確定版は初回 `uv sync` / `npm install` 時に lockfile へ解決される。
**lockfile（uv.lock / package-lock.json）はまだ存在しない**。新PCで初回 sync した後にコミットすること。

---

## 7. 新PC（Ubuntu）での再開手順 ← まずここから

クローン後、プロジェクトルートで実行。

### 7.1 前提ツール導入（Ubuntu）
```bash
# uv（Python パッケージ管理。Python 3.13 も uv が取得する）
curl -LsSf https://astral.sh/uv/install.sh | sh
#   インストール後、シェルを開き直すか source して PATH 反映
uv --version

# Node.js LTS（nvm 推奨。npm 同梱）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
#   シェル再読込後
nvm install --lts
node --version && npm --version
```

### 7.2 スキャフォールドの実体化・検証（最初の検証ゲート）
```bash
# backend
cd backend
uv sync                          # 依存解決 + uv.lock 生成、Python 3.13 取得
uv run ruff check .              # lint
uv run ruff format --check .     # format
uv run pyright                   # 型（strict）
uv run lint-imports              # Clean Architecture の依存方向（import-linter）
uv run pytest                    # ※テスト未作成のため "no tests collected"（exit 5）が正常
cd ..

# frontend
cd frontend
npm install                      # 依存解決 + package-lock.json 生成
npm run lint
npm run typecheck
npm run build
cd ..
```

- ここでエラーが出たら、設定ファイル（pyproject.toml / tsconfig.json / eslint.config.js 等）を直す。
- 通ったら **uv.lock と package-lock.json をコミット**。これでスキャフォールドの検証ゲート通過。

---

## 8. 次にやること（ハーネス残り3層。上から順）

本人の方針「逸脱を止める仕組みを先に固めてから生成役へ」に従い、Rules/Hooks を先に。

1. **`.claude/rules/`（パススコープ制約）**
   - 例: `backend/app/domain/` 配下は ORM/フレームワークを import しない、API ハンドラは Pydantic で入力検証必須、models（infrastructure）配下は ORM 経由必須 等。
2. **`.claude/settings.json`（Hooks）＋ pre-commit ＋ GitHub Actions CI**
   - 決定論的強制: テスト未通過で完了不可、スコープ外編集ブロック、コミット時に Ruff/Pyright/import-linter/xenon・ESLint/Prettier/tsc を実行。
   - CI は `.github/workflows/` に。無料枠。pytest / vite build はここで。
3. **`.claude/skills/`（段階駆動＋ドメイン参照の併用）**
   - 段階駆動: specify / plan / tasks / implement の SKILL.md。
   - ドメイン参照: ubiquitous-language / backend-architecture / frontend-architecture / design / bdd / e2e-testing。
   - ※他人の著作物（参照した gaomond/prompts 等）は転用せずオリジナルで書き起こす（§10 参照）。
4. **`.claude/agents/`（検証用サブエージェント）**
   - spec 適合チェック役・テスト網羅チェック役。

その後、最初の機能 `specs/0001-shooting-session/` を /specify から着手する。

---

## 9. 環境メモ（前PC＝会社Windowsで起きた問題。新PCでは無関係の可能性が高い）

新PCに移行する直接の理由になった問題。**事実と推測を分けて記録**する。

- 【事実】会社の Windows で `python -m pip install uv` 後、`uv.exe` 本体だけが消えていた（`uvw.exe`/`uvx.exe` は残存）。
- 【推測】社内のウイルス対策ソフトが `uv.exe` を検疫した可能性が高い。
- 【事実】Claude Code 側の git-bash シェルは社内ネットワークの SSL 証明書を検証できず、pypi に到達不可だった（SSLCertVerificationError）。会社の PowerShell では成功していた＝シェル/証明書ストアの差。
- → これらは会社ネットワーク／会社PC固有。**新PC（おそらく個人の Ubuntu）では発生しない見込み**。ただし新PCが社内プロキシ配下なら、uv/npm の SSL で社内ルートCAの導入が要る場合がある（その時は Ubuntu の信頼ストアに CA を追加）。
- 【教訓】リポジトリは OneDrive 配下に置かない（node_modules/.venv の同期・ファイルロック・AV干渉の原因）。新PCでは普通のホーム配下（例 `~/aim-trainer`）に置く。

---

## 10. 本人の進め方の好み（文脈）

- 事実と仮説、自分の解釈と引用元を明確に分ける。誇張を嫌い、正確さを重視する。
- 他人の著作物（参照した gaomond/prompts の BDD プロンプト等）はクレジット・権利を避けたいので、転用せずオリジナルで書き起こす方針。
- 過去に SDD の Qiita 記事2本と Flask/pytest+Playwright のモノレポ実績あり。SDD・DDD・BDD・TDD は概念として習得済み。
- 開発手法は「一度ガチガチの正式版を通して学ぶ」方針。小規模題材なので破綻せず完走できる想定。

---

## 11. git 運用メモ（このリポジトリの初期化〜新PCクローン）

このリポジトリはまだ git 初期化されていない（このセッション時点）。前PCまたは新PCで：

```bash
git init
git add -A
git commit -m "chore: scaffold backend/frontend and harness foundation (CLAUDE.md)"
# GitHub 等にリモートを作成して push
git branch -M main
git remote add origin <REMOTE_URL>
git push -u origin main
```

新PCで：
```bash
git clone <REMOTE_URL> aim-trainer
cd aim-trainer
# → §7 の再開手順へ
```

コミットメッセージはセマンティック形式（feat/fix/test/refactor/chore(scope): 説明）。
