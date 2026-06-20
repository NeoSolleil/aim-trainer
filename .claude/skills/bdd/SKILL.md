---
name: bdd
description: ドメイン参照。Gherkin（受け入れシナリオ）の書き方。Feature/Rule/Scenario、BRIEF 原則、Example Map からの変換、タグ規約（@R-x / @backend / @e2e）。specify で清書し implement/e2e で実行する際に参照する。
---

# bdd — Gherkin の書き方

`discover` の 🟢Example を、`specify` で**実行可能な受け入れシナリオ**に清書するための記法。原本は `specs/<feature>/acceptance.feature`。implement（pytest-bdd）と e2e-testing（playwright-bdd）が同じ原本を読む。

## キーワードは英語、本文は日本語

`Feature` / `Rule` / `Scenario` / `Scenario Outline` / `Background` / `Given` / `When` / `Then` / `And` は**英語キーワード**を使い、ステップ本文は日本語で書く。
（理由: pytest-bdd・playwright-bdd の既定が英語で、EARS も英語構文。ツール整合と一貫性のため `# language: ja` は使わない。）

## 構造

- `Feature:` … 機能が生む価値（1機能=1ファイル）。
- `Rule:`（任意）… EARS の要件に対応するルールでまとめる。
- `Scenario:` … 具体例1件（Given-When-Then）。
- `Scenario Outline:` ＋ `Examples:` … 同型で値違い（境界値・データ駆動）に使う。
- `Background:` … 同一 Feature 内の共通 Given。

## BRIEF 原則

- **B**usiness language: 業務・ドメインの言葉（ubiquitous-language）で書く。実装用語を避ける。
- **R**eal data: 具体的な値（座標・ms・回数）を使う。
- **I**ntention revealing: 何を確かめたいかが伝わる名前にする。
- **E**ssential: 本質的な前提・操作・結果だけ。
- **F**ocused: 1シナリオ=1つの振る舞い。
- **B**rief: 短く。

## Given-When-Then の規律

- **Given** = 前提・文脈（状態の用意）。
- **When** = **ただ1つ**のトリガー操作。複数の When を並べない。
- **Then** = 観測可能な結果（記録された／表示された／拒否された）。
- UI 詳細（ボタンの色等）は業務シナリオに書かない（それは e2e の関心）。

## タグ規約

- `@R-x` … 対応する EARS 要件（requirements.md の ID）。**全シナリオに必須**。要件↔シナリオの**正式な紐付けはこのタグ**。`Rule:` は任意の可読グルーピングで、紐付けの正本ではない。
- `@backend` … pytest-bdd で**ドメイン／アプリ／API**として検証するシナリオ。
- `@e2e` … playwright-bdd で**動く UI**として検証するシナリオ。
- 1つの振る舞いを両レベルで確かめたい場合のみ、別シナリオに分けてそれぞれ付与する。

**タグはツールでこう効く**: pytest-bdd はタグを **pytest マーカー**に変換するので `pytest -m backend` で選択できる。playwright-bdd は **tag 式**（`--grep @e2e` 等）で選択する。これで実行時に検証レベルを分離する。

## Example Map → Gherkin の変換

- 🔵Rule → `Rule:`（または `@R-x` でグルーピング）。
- 🟢Example（正常）→ `Scenario:`。
- 🟢Example（境界・異常）→ それぞれ別 `Scenario:`（値違いが多ければ `Scenario Outline`）。

## 例（English keyword ＋ 日本語本文）

```gherkin
Feature: シューティングセッション

  @R-1 @backend
  Scenario: 的の内側クリックはヒットで反応時間を記録
    Given セッションが進行中である
    And 中央に的が出現している
    When プレイヤーが的の内側をクリックする
    Then システムはヒットを記録する
    And 反応時間が記録される

  @R-2 @backend
  Scenario: 的の外側クリックはミス
    Given セッションが進行中で、中央に的が1つある
    When プレイヤーが座標 (10,10) をクリックする
    Then システムはミスを記録する
    And 反応時間の平均は変化しない

  @R-1 @e2e
  Scenario: ヒットすると画面のヒット数が増える
    Given セッション画面を開いている
    When 出現した的をクリックする
    Then ヒット数の表示が 1 増える
```

## アンチパターン

- 1シナリオに複数 When を詰める。
- Then に観測できない内部状態を書く。
- `@R-x` 無しのシナリオ（要件と紐付かない＝台帳の外）。
- 実装語・UI 語で業務ルールを書く。
