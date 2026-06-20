---
name: e2e-testing
description: ドメイン参照。Playwright + playwright-bdd による E2E の方針。acceptance.feature の @e2e シナリオから生成し、DOM は data-testid、DOM に無い描画はテストシームで操作する。UI を E2E 検証する際に参照する。
---

# e2e-testing — E2E（Playwright + playwright-bdd）

動く UI を、`specs/<feature>/acceptance.feature` の **`@e2e` シナリオ**で検証する。Gherkin 原本は1つ（`bdd` 参照）。backend は `@backend` を pytest-bdd、E2E は `@e2e` を playwright-bdd で実行する。

## 前提（ツール導入）

- `@playwright/test` と `playwright-bdd` を devDependencies に入れ、`npx playwright install` でブラウザを取得する。未導入なら最初にこの導入を行う。

## 方針

- **playwright-bdd** で Gherkin からテスト生成（`bddgen`）→ Playwright 実行。
- シナリオ選択は **`@e2e` タグ**（tag フィルタ）。`@backend` は E2E で走らせない。
- 原本 .feature を**コピーしない**。テスト設定から `specs/<feature>/acceptance.feature` を参照する。

## 要素の特定（汎用原則・重要）

- **DOM 要素は `data-testid` で特定する**（テキスト・CSS クラス・DOM 構造に依存しない＝壊れにくい）。`page.getByTestId(...)` を使う。
- **DOM に存在しない描画（Canvas / WebGL / 地図・チャート等）は data-testid を付けられない。** その場合は**テストシーム**で操作・検証する：
  - 座標ベースの操作（対象の位置が分かるよう、テスト時に座標や状態を露出する仕組みをアプリ側に用意）。
  - または「現在状態をテストから読める hook」を本番に影響しない形で設ける。
- 判断基準: **「その要素は DOM か？」** — DOM なら testid、非DOM ならテストシーム。

## ステップ定義

- Given/When/Then を Playwright 操作にマップ。When は単一操作、Then は `expect(locator).toBeVisible()` 等の観測可能な検証へ。

## data-testid の規約

- 役割をケバブで表す（`session-start`, `hit-count`）。一意に。

## CI

- E2E はブラウザ取得が重いので、lint/typecheck/build/unit とは**別ジョブ**にする。検証対象の UI が存在してから CI に追加する。

## アンチパターン

- テキスト・nth-child・CSS クラスでのセレクタ（壊れる）。
- 非DOM描画に無理やり data-testid を付けようとする（不可能。テストシームを使う）。
- E2E に業務ルールの網羅を負わせる（網羅は `@backend`／pytest-bdd。E2E は「画面で繋がって動く」を確認）。
- 原本 .feature の二重管理。
