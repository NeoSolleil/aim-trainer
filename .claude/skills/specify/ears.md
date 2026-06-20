# EARS 記法ガイド（requirements.md の書き方）

`specify` 段階で `requirements.md` を書くための記法リファレンス。
EARS（Easy Approach to Requirements Syntax）は、要件を**少数の決まった構文**に押し込めることで曖昧さを消す方法。EARS は「ルールの台帳」であり、各要件には Gherkin の合格条件（acceptance.feature）がぶら下がる。

## 基本形

すべて **the `<システム/コンポーネント>` SHALL `<応答>`** が核。前置きの節（WHEN/WHILE/…）で発動条件を限定する。

| パターン | 構文 | いつ使う |
| --- | --- | --- |
| ユビキタス | the `<system>` SHALL `<応答>` | 常に成り立つ普遍のルール |
| イベント駆動 | **WHEN** `<トリガー>`, the `<system>` SHALL `<応答>` | ある出来事が起きたとき |
| 状態駆動 | **WHILE** `<状態>`, the `<system>` SHALL `<応答>` | ある状態が続いている間 |
| オプション | **WHERE** `<機能が含まれる場合>`, the `<system>` SHALL `<応答>` | 特定構成・機能がある場合のみ |
| 望ましくない挙動 | **IF** `<異常条件>`, **THEN** the `<system>` SHALL `<応答>` | 異常・エラー・誤操作への対応 |
| 複合 | 上記の節を組み合わせる | 条件が重なるとき |

## 例（Aim Trainer）

- ユビキタス: *The system SHALL record each shot's reaction time in milliseconds.*
- イベント駆動: *WHEN the player clicks within a target, the system SHALL register a hit and record the reaction time from target spawn to click.*
- 状態駆動: *WHILE a session is in progress, the system SHALL display the elapsed time and current hit count.*
- オプション: *WHERE the selected gun has recoil, the system SHALL offset the aim point according to the gun's recoil pattern after each shot.*
- 望ましくない挙動: *IF the player clicks outside every target, THEN the system SHALL register a miss and SHALL NOT change the reaction-time average.*
- 複合: *WHILE a session is in progress, WHEN the time limit elapses, the system SHALL end the session and SHALL persist the score.*

## 良い要件の条件

- **1要件＝1 SHALL。** 「〜し、かつ〜する」で複数の検証点が混ざるなら分割する（または SHALL を並記し、各々にシナリオを用意）。
- **測定可能に書く。** 「速く」「適切に」「十分に」等の曖昧語を禁止。数値・単位・具体条件で書く（例: 反応時間はミリ秒、的サイズはピクセル）。
- **観測可能な応答にする。** 外から確認できる振る舞い（記録される／表示される／拒否される）を書く。内部実装には触れない。
- **能動態・現在形。** 主語は必ずシステム/コンポーネント。
- **正常系だけにしない。** 異常・境界（0件、上限、時間切れ、範囲外クリック等）も IF/THEN で要件化する。

## ID とトレーサビリティ

- 各要件に `R-1`, `R-2`, … と一意の ID を振る。
- acceptance.feature の各シナリオに対応 ID をタグ付け（`@R-1`）して、要件↔シナリオを双方向に追えるようにする。
- 1要件に最低でも「正常系・異常系・境界値」のシナリオを用意する（詳細は `bdd` スキル）。

## requirements.md の構成

```markdown
# <機能名>

## 概要
<この機能が誰の何を解決するか>

## スコープ
- 含む: <...>
- 含まない: <...>   ← スコープ厳守の明文化

## 要件（EARS）
- **R-1** WHEN <...>, the system SHALL <...>
- **R-2** IF <...>, THEN the system SHALL <...>
- ...

## 用語
ubiquitous-language を参照。新語があればここで追加提案する。
```

## よくある失敗

- 「ユーザーは〜できる」→ 主語がユーザーになっている。**システムの SHALL** に直す。
- 「高速に応答する」→ 測定不能。「200ms 以内に」等へ。
- 1文に AND/OR を詰め込む → 検証不能。分割する。
- 設計・実装（「SQLite に保存する」等）を要件に書く → それは plan 段階。要件は「永続化される」までに留める。

## チェックリスト（提出前）

- [ ] すべての要件が EARS パターンのいずれかに当てはまる
- [ ] 曖昧語がない（測定可能）
- [ ] 異常系・境界値の要件がある
- [ ] 全要件に ID があり、acceptance.feature のシナリオと相互対応する
- [ ] スコープ「含まない」が明記されている
