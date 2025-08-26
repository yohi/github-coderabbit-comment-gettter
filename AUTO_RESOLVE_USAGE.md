# 解決済みマーク自動処理機能

解決済みマーク付きのCodeRabbitコメントを自動で解決済みステータスに更新する専用機能です。

## 概要

先日作成した「解決済みマーク付与判断依頼機能」で付与された解決済みマークを検出し、該当するコメントスレッドを自動的に解決済みステータスに更新します。

## 使用方法

### 基本的な使用方法

#### 1. ドライラン（実際の更新は行わない）
```bash
# 現在の grp コマンドと並行使用
python -m github_review_prompts auto-resolve --dry-run https://github.com/owner/repo/pull/123

# 詳細ログ付き
python -m github_review_prompts auto-resolve --dry-run --verbose https://github.com/owner/repo/pull/123
```

#### 2. 実際の解決済みステータス更新
```bash
# 基本実行
python -m github_review_prompts auto-resolve https://github.com/owner/repo/pull/123

# 詳細出力形式
python -m github_review_prompts auto-resolve --output detailed https://github.com/owner/repo/pull/123
```

### 出力形式オプション

```bash
# サマリー形式（デフォルト）
python -m github_review_prompts auto-resolve --output summary https://github.com/owner/repo/pull/123

# 詳細形式
python -m github_review_prompts auto-resolve --output detailed https://github.com/owner/repo/pull/123

# JSON形式（スクリプト処理用）
python -m github_review_prompts auto-resolve --output json https://github.com/owner/repo/pull/123
```

## 従来のgrpコマンドとの関係

### 自動実行（デフォルト）
従来の `grp` コマンドでは、プロンプト生成処理の **最初の段階** で自動的に解決済みマーク処理が実行されます：

```bash
# この実行時に解決済みマーク処理も自動で実行される
grp https://github.com/owner/repo/pull/123
```

### 独立実行（新機能）
解決済みマーク処理のみを独立して実行したい場合：

```bash
# 解決済みマーク処理のみを実行
python -m github_review_prompts auto-resolve https://github.com/owner/repo/pull/123
```

## 検出される解決済みマーク

以下のパターンが検出されます：

### 1. 完全なCodeRabbit解決済みマーカー
```
[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

### 2. 簡易マーカー
- `[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]`
- `[CR_RESOLUTION_CONFIRMED:FUTURE_PHASE_PLANNED]`
- `CodeRabbitによる解決済みマーク実行可能`

### 3. 追加パターン
- 問題ないと判断.*解決済みにマーク
- 将来対応と判断.*解決済みにマーク
- 指摘が間違い.*解決済みにマーク
- 修正完了
- 対応済み

## 出力例

### サマリー形式
```
🔍 プルリクエスト: owner/repo#123
📝 タイトル: Feature implementation
📊 処理サマリー: 2/3件のコメントを解決済みにしました
💭 総コメント数: 15
✅ 既解決コメント数: 5
🎯 マーカー検出数: 3
🏁 解決処理: 2/3 件成功
```

### 詳細形式
```
🔍 プルリクエスト: owner/repo#123
📝 タイトル: Feature implementation
📊 処理サマリー: 2/3件のコメントを解決済みにしました
💭 総コメント数: 15
✅ 既解決コメント数: 5
🎯 マーカー検出数: 3
🏁 解決処理: 2/3 件成功

📋 詳細情報:

🎯 マーカー検出コメント (3件):
  1. コメントID: 123456
     ステータス: 未解決
     検出パターン: CR_RESOLUTION_CONFIRMED (完全)
     内容: 技術的検証を実施しました...

  2. コメントID: 123457
     ステータス: 未解決
     検出パターン: TECHNICAL_ISSUE_RESOLVED
     内容: この指摘について...

🏁 解決処理結果 (3件):
  1. コメントID: 123456 - ✅ 成功
     メッセージ: 解決済みステータスに更新しました

  2. コメントID: 123457 - ✅ 成功
     メッセージ: 解決済みステータスに更新しました
```

## 環境変数

```bash
export GITHUB_TOKEN=your_github_token_here
```

## エラーハンドリング

- トークンが無効な場合は処理を停止
- GraphQL API エラーは詳細ログに記録
- 個別のコメント処理エラーは他のコメントに影響しない
- 部分的な成功も適切に報告

## 注意事項

1. **権限要件**: GitHub トークンにプルリクエストへの書き込み権限が必要
2. **GraphQL API使用**: レビュースレッド解決にはGraphQL APIを使用
3. **冪等性**: 既に解決済みのコメントは安全にスキップ
4. **ログ記録**: 全ての操作は詳細ログに記録

## 技術的な詳細

### 処理フロー
1. プルリクエスト情報の取得・検証
2. ハイブリッドアプローチでコメント取得
3. 解決済みマーカーパターンマッチング
4. GraphQL APIでスレッド解決処理
5. 結果の詳細レポート生成

### 使用API
- GitHub REST API: コメント取得
- GitHub GraphQL API: 解決状況取得・スレッド解決処理

### セキュリティ
- トークン検証
- 入力URLの検証
- エラー情報の適切なマスキング
