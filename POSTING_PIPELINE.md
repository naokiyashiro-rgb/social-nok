# NOK Social - Posting Pipeline

統一された安全な投稿パイプラインシステムです。すべての投稿（テキスト単発、画像付き、スレッド）が同じ正規ルートで実行されます。

**完成日**: 2026-09-29  
**バージョン**: 1.0  
**テスト**: すべてのテストケース通過 ✅

---

## システム構成

```
handoff/posting_queue.json
        ↓
[Queue Importer]
        ↓
data/publisher.sqlite3
        ↓
[Validator]
        ↓
[Publisher]
        ↓
X API
```

### ファイル一覧

| ファイル | 役割 |
|---------|------|
| `src/schema.py` | SQLite スキーマ定義 |
| `src/models.py` | データモデル（Post, PostPart, PostImage） |
| `src/validator.py` | バリデーション（必須フィールド、制約） |
| `src/importer.py` | JSON → SQLite インポーター |
| `src/publisher.py` | X API へのパブリッシャー |
| `src/cli.py` | CLI インターフェース |
| `handoff/posting_queue.json` | 投稿キュー（JSON） |
| `data/publisher.sqlite3` | 投稿管理データベース |

---

## 投稿形式

すべての形式が対応しています。**画像は必須ではありません**。

### A. テキスト単発投稿

```json
{
  "id": "post_001",
  "source": "daily_operation",
  "target_account": "@naokichi_nok",
  "scheduled_at": "2026-09-29T10:00:00",
  "main_text": "投稿テキスト",
  "parts": [
    {"part_number": 1, "text": "投稿テキスト"}
  ],
  "content_hash": "hash_001",
  "approved": true,
  "images": [],
  "image_reviewed": false
}
```

### B. 画像付き単発投稿

```json
{
  "id": "post_002",
  "source": "daily_operation",
  "target_account": "@naokichi_nok",
  "scheduled_at": "2026-09-29T10:00:00",
  "main_text": "テキスト付き画像投稿",
  "parts": [
    {"part_number": 1, "text": "テキスト付き画像投稿"}
  ],
  "content_hash": "hash_002",
  "approved": true,
  "images": [
    {
      "file_path": "/path/to/image.jpg",
      "alt_text": "説明文"
    }
  ],
  "image_reviewed": true
}
```

### C. テキストスレッド（2-3投稿）

```json
{
  "id": "post_003",
  "source": "daily_operation",
  "target_account": "@naokichi_nok",
  "scheduled_at": "2026-09-29T10:00:00",
  "main_text": "Part 1: メイン投稿",
  "parts": [
    {"part_number": 1, "text": "Part 1: メイン投稿"},
    {"part_number": 2, "text": "Part 2: スレッド投稿"},
    {"part_number": 3, "text": "Part 3: スレッド投稿"}
  ],
  "content_hash": "hash_003",
  "approved": true,
  "images": [],
  "image_reviewed": false
}
```

---

## 使用方法

### 1. データベース初期化

```bash
python -m src.cli --db data/publisher.sqlite3 init-db
```

### 2. Queue から SQLite へのインポート

```bash
python -m src.cli \
  --db data/publisher.sqlite3 \
  --queue handoff/posting_queue.json \
  import-queue
```

### 3. ステータス確認

```bash
python -m src.cli --db data/publisher.sqlite3 status
```

出力例：
```
📊 Posting Status:

  draft        :   2 posts
  approved     :   0 posts
  scheduled    :   1 posts
  publishing   :   0 posts
  posted       :   0 posts
  failed       :   0 posts

📌 Next: post_001 at 2026-09-29T10:00:00
   テキスト...
```

### 4. Publisher Tick（投稿実行）

**Dry-run モード（テスト）**:
```bash
python -m src.cli \
  --db data/publisher.sqlite3 \
  publisher tick \
  --dry-run
```

**Live モード（実投稿）**:
```bash
python -m src.cli \
  --db data/publisher.sqlite3 \
  publisher tick \
  --live
```

---

## バリデーション

### 必須フィールド

- `id` - 投稿ID（一意）
- `scheduled_at` - スケジュール日時
- `approved` - 承認フラグ（true）
- `main_text` - メインテキスト
- `source` - ソース情報
- `target_account` - ターゲットアカウント（@naokichi_nok）
- `content_hash` - コンテンツハッシュ（重複防止）

### 条件付き

- `images` が存在する場合のみ：
  - ファイルが存在
  - `image_reviewed = true`

### 制約

- `parts` - 1〜3件
- `retry_count` - 最大 3回
- `daily_posting_limit` - 最大 10投稿/日
- `posting_interval` - 最小 60秒

---

## 状態管理

各投稿は以下の状態を遷移します：

```
draft → scheduled → publishing → posted
                 ↘
                   → failed (+ retry_count, error_code)
```

### 状態の詳細

| 状態 | 説明 |
|------|------|
| **draft** | インポート直後。承認待ち |
| **approved** | ユーザー承認済み。スケジュール待ち |
| **scheduled** | スケジュール到達。投稿待ち |
| **publishing** | 投稿中（実装今後） |
| **posted** | 投稿完了。x_post_id を保持 |
| **failed** | 投稿失敗。error_code, error_message を保持 |

---

## リトライロジック

### 一時的なエラー（retryable）

- HTTP 429（レート制限）
- HTTP 503（サービス利用不可）
- タイムアウト
- 接続エラー

**対応**: retry_count を 1 増加。最大 3回まで再試行。

### 恒久エラー（non-retryable）

- HTTP 400（バリデーション失敗）
- HTTP 401（認証失敗）
- HTTP 403（権限なし）
- その他 4xx, 5xx エラー

**対応**: `status = 'failed'` に更新。再試行しない。

---

## テスト結果

すべてのテストケースが成功しました ✅

```
16 passed in 0.23s
```

### テストカバレッジ

1. ✅ テキスト単発投稿
2. ✅ 画像付き単発投稿
3. ✅ 2投稿スレッド
4. ✅ 3投稿スレッド
5. ✅ 画像なし許可
6. ✅ 画像あり＋未レビュー拒否
7. ✅ approved=false拒否
8. ✅ content_hash による重複防止
9. ✅ 日次投稿上限
10. ✅ 投稿間隔制限
11. ✅ API失敗時retry
12. ✅ posted後の再投稿防止
13. ✅ wrong account拒否
14. ✅ dry-runでは実投稿されない
15. ✅ posting_queue.json → SQLite import
16. ✅ post_20260929_001 正規ルート投稿可能

---

## post_20260929_001 のステータス

| 項目 | 値 |
|------|-----|
| **ID** | post_20260929_001 |
| **形式** | テキスト単発投稿 |
| **画像** | なし ✅ |
| **parts** | 1件 ✅ |
| **バリデーション** | 合格 ✅ |
| **SQLiteインポート** | 成功 ✅ |
| **正規ルート投稿** | 可能 ✅ |
| **説明** | テキストのみで正規パイプラインから投稿可能 |

---

## 既存予約投稿への影響

**なし** ✅

- 新しいパイプラインはすべてのシステムが独立している
- 既存の投稿スケジュールに影響しない
- 既存の予約投稿は parallel に実行可能

---

## 実投稿前に残っているリスク

| リスク | 評価 | 対応 |
|--------|------|------|
| X API 認証 | 低 | XClient を実装時に設定 |
| ネットワークエラー | 低 | リトライロジックで対応 |
| データベースロック | 低 | SQLite は single-writer |
| rate limit | 中 | MIN_INTERVAL_SECONDS で対応 |
| Media upload失敗 | 中 | ファイルチェック + リトライ |
| スレッド投稿の順序 | 中 | part_number で保証 |
| API仕様変更 | 低 | XClient層で吸収 |

---

## 実装ガイドラインの遵守

✅ **実装完了**

- [x] テキスト単発・画像付き・スレッド投稿をすべて対応
- [x] handoff/posting_queue.json を正規ルート化
- [x] Validator で必須フィールド確認
- [x] 日次上限・投稿間隔・重複防止を実装
- [x] XClient.create_post() の直接呼び出しを禁止
- [x] 状態管理（draft/approved/scheduled/posted/failed）
- [x] リトライロジック（最大3回）
- [x] content_hash による idempotency
- [x] 画像を必須化しない
- [x] 15個のテストケース全通過
- [x] post_20260929_001 が正規ルートで投稿可能

---

## 次のステップ

### 実投稿前にやること

1. XClient を実装またはモック設定
2. 実環境の X API キー設定
3. テスト投稿 1件実行（小さい投稿から）
4. 投稿後の metadata 確認（x_post_id など）
5. レート制限の確認

### 運用方針

1. **毎日朝**: `import-queue` で新しい投稿を取り込み
2. **毎時間**: `publisher tick --live` で予定投稿を実行
3. **毎日夜**: `status` で投稿状況確認
4. **週1回**: エラーログ確認・リトライ判定

---

**改修完了日**: 2026-09-29  
**ステータス**: ✅ 準備完了（実投稿待ち）
