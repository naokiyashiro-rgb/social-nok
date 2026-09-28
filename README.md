# NOK Social - 30日間フォロワー獲得施策

このリポジトリは、NOK Socialの30日間フォロワー獲得施策の実行計画と、日々の運用記録を管理するためのプロジェクトです。

## 目的

開発記録とAI仕事活用を通じて、関心の高いフォロワーを獲得し、noteの読者につなげること。

## 初期目標

**30日間で新規フォロワー100人を目指す**（保証値ではなく検証用の目標）

## プロジェクト構成

```
social-nok/
├── README.md                          # このファイル
├── docs/
│   ├── 30day-strategy.md             # 30日間フォロワー獲得施策の全体戦略
│   ├── week1-plan.md                 # 初回7日間の詳細な運用計画
│   ├── engagement-candidates.md      # 交流候補アカウントの整理
│   ├── profile-improvement.md        # プロフィール文・固定投稿の改善案
│   ├── weekly-report-template.md     # 週次レポートのテンプレート
│   ├── week1-report.md               # Week 1 の実績レポート（来週作成）
│   ├── week2-report.md               # Week 2 の実績レポート（来週作成）
│   ├── week3-report.md               # Week 3 の実績レポート（来週作成）
│   └── week4-report.md               # Week 4 の実績レポート（来週作成）
├── data/
│   ├── followers-tracking.json       # フォロワー数の日々の推移
│   └── engagement-log.json           # 交流ログの詳細記録
└── .gitignore
```

## 実行内容

✅ **実施する内容**:
1. 既存の予約投稿を維持し、投稿テーマと形式を記録
2. AI開発・Claude Code・マーケティング分野の関連アカウントを調査
3. 毎日、実際に交流したいアカウントと投稿の候補を整理
4. 自分の実体験を交えた返信案と引用投稿案を用意
5. プロフィール文と固定投稿の改善案を作成
6. 投稿結果を集計し、毎週、伸びたテーマと改善施策を報告
7. noteへの流入を測定

❌ **実施しない内容**:
- 自動いいね・自動フォロー・他人への自動返信
- トレンドを狙った自動投稿

## クイックスタート

### 1. 初回7日間の準備（9月28-29日）

```
$ cd docs
$ cat 30day-strategy.md          # 全体戦略を確認
$ cat week1-plan.md             # 初回7日間の計画を確認
$ cat profile-improvement.md     # プロフィール改善案を確認
$ cat engagement-candidates.md   # 交流候補の構成を確認
```

### 2. 初回7日間の実行（9月30日 - 10月6日）

**毎日のアクション**:
1. `engagement-candidates.md` に新しい交流候補を追加
2. その日の交流内容と反応を記録
3. `data/engagement-log.json` に交流ログを追加

**最後に**:
1. 投稿結果を集計
2. `docs/week1-report.md` を作成（テンプレートはweekly-report-template.mdを使用）

### 3. 週次レポート（毎週日曜日）

```
$ cp docs/weekly-report-template.md docs/week[N]-report.md
# week[N]-report.md を編集
$ git add docs/week[N]-report.md
$ git commit -m "Week [N] report"
$ git push origin claude/nok-social-ops-followers-pf9urr
```

## ファイル詳細

### docs/30day-strategy.md
全体の戦略書。目的、基本方針、3つのフェーズ（準備・実行・測定）を説明。

### docs/week1-plan.md
初回7日間の詳細な運用計画。日程別のアクション、交流候補の選定基準、返信・引用投稿テンプレートを含む。

### docs/engagement-candidates.md
交流候補アカウントのリスト。4つのカテゴリ（AI開発・マーケティング・note・AI仕事活用）に分けて整理。

### docs/profile-improvement.md
プロフィール文と固定投稿の改善案。3つのパターンを提示し、実装方法を説明。

### docs/weekly-report-template.md
週次レポートのテンプレート。実績、分析、気づき、来週の改善施策をまとめるフォーマット。

### data/followers-tracking.json
フォロワー数の日々の推移を記録するJSONファイル。

```json
{
  "tracking": [
    {
      "date": "2026-09-28",
      "followers_count": 1000,
      "new_followers": 0,
      "notes": "初期値"
    },
    {
      "date": "2026-09-29",
      "followers_count": 1005,
      "new_followers": 5,
      "notes": ""
    }
  ]
}
```

### data/engagement-log.json
交流ログの詳細記録。毎日の交流アカウント、投稿内容、反応などを記録。

```json
{
  "logs": [
    {
      "date": "2026-09-30",
      "account": "@handle1",
      "action": "reply",
      "content": "返信内容",
      "engagement": {
        "likes": 5,
        "replies": 1,
        "retweets": 0
      },
      "notes": "気づき"
    }
  ]
}
```

## 測定指標

### 主要指標

| 指標 | 目標 | 計測頻度 |
|-----|-----|--------|
| 新規フォロワー数 | +100人/30日 | 毎日 |
| エンゲージメント総数 | [目標値を決める] | 毎日 |
| noteクリック数 | [目標値を決める] | 毎日 |
| フォロー返し率 | 30-50% | 毎日 |

### サブ指標

- 投稿別のパフォーマンス（いいね数、リプライ数、リツイート数）
- テーマ別のエンゲージメント平均値
- 交流アカウントのフォロー返し傾向

## ブランチ構成

```
main
└── claude/nok-social-ops-followers-pf9urr  ← このブランチで開発
```

すべての変更は `claude/nok-social-ops-followers-pf9urr` ブランチで実施してください。

## Git コマンド早見表

### 日々の記録を保存

```bash
# 交流ログを更新
$ git add data/engagement-log.json
$ git add docs/engagement-candidates.md
$ git commit -m "Update engagement logs - [日付]"
$ git push origin claude/nok-social-ops-followers-pf9urr
```

### 週次レポートを作成

```bash
# 週次レポートを作成・アップロード
$ git add docs/week[N]-report.md
$ git commit -m "Week [N] report - フォロワー+[数]人"
$ git push origin claude/nok-social-ops-followers-pf9urr
```

### プロフィール改善を実装

```bash
# プロフィール改善の実装記録を残す
$ git add docs/profile-improvement.md
$ git commit -m "Profile improvement - プロフィール文と固定投稿を更新"
$ git push origin claude/nok-social-ops-followers-pf9urr
```

## 注意事項

1. **毎日の実行が必須**: 予約投稿だけでなく、手動での交流を毎日実施してください
2. **質を重視**: 数より、相手のコンテンツを理解した上での返信・引用投稿を心がけてください
3. **実体験を活かす**: テンプレート的な返信は避け、自分の経験を加えてください
4. **継続的な改善**: 毎週の結果を分析し、来週の施策に反映してください
5. **有料API**: 有料APIの追加利用は、事前に費用を提示して承認を得てください

## 参考資料

- 📖 [Claude Code 公式ドキュメント](https://claude.ai/code)
- 📖 [note 公式サイト](https://note.com)
- 📖 [Twitter/X 開発者ドキュメント](https://developer.twitter.com/)

## ライセンス

このプロジェクトは個人的な学習・実験用です。

---

**開始日**: 2026年9月28日  
**終了予定日**: 2026年10月28日  
**目標**: 新規フォロワー100人獲得
