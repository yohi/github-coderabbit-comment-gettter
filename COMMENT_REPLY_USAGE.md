# 🤖 GitHub Comment Reply Tool

GitHub Pull Requestのレビューコメント（CodeRabbitなど）に対して**特定コメントに直接返信する**curlコマンドや直接APIで返信を行う高機能ツールです。`in_reply_to`パラメータによりGitHub上でスレッド形式で表示されます。

## 📋 目次

- [✨ 主な機能](#-主な機能)
- [🚀 インストールと設定](#-インストールと設定)
- [📖 基本的な使用方法](#-基本的な使用方法)
- [🎯 コマンド詳細](#-コマンド詳細)
- [📄 一括返信](#-一括返信)
- [🔧 curlコマンド生成](#-curlコマンド生成)
- [📝 返信テンプレート](#-返信テンプレート)
- [💡 実用例](#-実用例)
- [🛠️ トラブルシューティング](#️-トラブルシューティング)

## ✨ 主な機能

- **🎯 特定コメント直接返信**: `in_reply_to`パラメータで指定したコメントIDに直接返信
- **🧵 スレッド形式表示**: GitHub上でコメントツリーとして表示され、コンテキストが保持
- **📦 一括返信**: JSONファイルから複数のコメントに一括返信
- **📝 返信テンプレート**: よく使う返信内容を定型文として利用
- **🔧 curlコマンド自動生成**: 各コメントに対応した実行可能なcurlコマンドを自動生成
- **📊 新規コメント作成**: 任意の場所に新しいコメントを追加
- **✏️ コメント編集・削除**: 既存コメントの更新と削除
- **🚦 ドライラン機能**: 実際のAPI呼び出し前に動作確認
- **🔗 API適切使い分け**: Pull Request Comments API（返信）とIssue Comments API（全体）を状況に応じて使用

## 🚀 インストールと設定

### 必要環境

- Python 3.13+
- GitHub API トークン
- 既存のgithub-review-prompts-ai-agentプロジェクト

### インストール

```bash
# 依存関係のインストール（既にインストール済みの場合はスキップ）
uv sync

# 環境変数の設定
export GITHUB_TOKEN="your_github_token_here"
```

### 権限確認

```bash
# GitHub APIの認証テスト
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

## 📖 基本的な使用方法

### 🎯 クイックスタート

```bash
# 単一コメントに返信
uv run grp-reply reply https://github.com/owner/repo/pull/123 --comment-id 456789 --message "Fixed!"

# テンプレートを使用した返信
uv run grp-reply reply https://github.com/owner/repo/pull/123 --comment-id 456789 --template fixed

# curlコマンドを生成（実際のAPI呼び出しなし）
uv run grp-reply generate-curl https://github.com/owner/repo/pull/123 --action reply --comment-id 456789 --message "Fixed!"
```

### 🎨 利用可能なコマンド

| コマンド | 説明 | 使用例 |
|----------|------|--------|
| `reply` | 単一コメントに返信 | `grp-reply reply PR_URL --comment-id ID --message "text"` |
| `batch-reply` | 複数コメントに一括返信 | `grp-reply batch-reply PR_URL --replies-file replies.json` |
| `create` | 新しいコメントを作成 | `grp-reply create PR_URL --path file.py --line 42 --message "text"` |
| `update` | 既存コメントを更新 | `grp-reply update PR_URL --comment-id ID --message "new text"` |
| `delete` | コメントを削除 | `grp-reply delete PR_URL --comment-id ID` |
| `generate-curl` | curlコマンドを生成 | `grp-reply generate-curl PR_URL --action reply --comment-id ID` |
| `list-templates` | テンプレート一覧を表示 | `grp-reply list-templates` |

## 🎯 コマンド詳細

### 1. 単一コメント返信 (`reply`)

```bash
# 基本的な返信
uv run grp-reply reply https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --message "✅ Fixed! Thanks for the feedback."

# テンプレートを使用
uv run grp-reply reply https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --template fixed

# ファイルから返信内容を読み込み
echo "詳細な返信内容をここに記述..." > reply.txt
uv run grp-reply reply https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --file reply.txt

# ドライラン（実際のAPI呼び出しなし）
uv run grp-reply reply https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --message "Fixed!" \
  --dry-run
```

### 2. 新規コメント作成 (`create`)

```bash
# 指定した行に新しいコメントを作成
uv run grp-reply create https://github.com/owner/repo/pull/123 \
  --path src/main.py \
  --line 42 \
  --message "Great code! This implementation is very clean."

# 左側（変更前）の行にコメント
uv run grp-reply create https://github.com/owner/repo/pull/123 \
  --path src/main.py \
  --line 42 \
  --side LEFT \
  --message "This old implementation had issues."
```

### 3. コメント更新 (`update`)

```bash
# 既存コメントの内容を更新
uv run grp-reply update https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --message "✅ Updated: This issue has been resolved with additional error handling."
```

### 4. コメント削除 (`delete`)

```bash
# 確認付きでコメントを削除
uv run grp-reply delete https://github.com/owner/repo/pull/123 \
  --comment-id 456789

# 確認をスキップして削除
uv run grp-reply delete https://github.com/owner/repo/pull/123 \
  --comment-id 456789 \
  --confirm
```

## 📄 一括返信

複数のコメントに効率的に返信するための機能です。

### JSONファイルの形式

```json
[
  {
    "comment_id": 123456,
    "reply_body": "✅ Fixed! Thanks for catching this security issue."
  },
  {
    "comment_id": 123457,
    "template": "fixed"
  },
  {
    "comment_id": 123458,
    "reply_body": "👍 Good point about performance. I've optimized this section."
  }
]
```

### 一括返信の実行

```bash
# 基本的な一括返信
uv run grp-reply batch-reply https://github.com/owner/repo/pull/123 \
  --replies-file replies.json

# 返信間の遅延を調整（デフォルト0.5秒）
uv run grp-reply batch-reply https://github.com/owner/repo/pull/123 \
  --replies-file replies.json \
  --delay 1.0

# ドライランで内容確認
uv run grp-reply batch-reply https://github.com/owner/repo/pull/123 \
  --replies-file replies.json \
  --dry-run
```

### サンプルファイルの使用

```bash
# サンプルファイルをダウンロード
curl -o replies.json https://raw.githubusercontent.com/yohi/github-coderabbit-comment-getter/main/examples/batch-replies-sample.json

# コメントIDを実際の値に編集
vim replies.json

# 一括返信実行
uv run grp-reply batch-reply https://github.com/owner/repo/pull/123 --replies-file replies.json
```

## 🔧 curlコマンド生成

API呼び出しの代わりに、実行可能なcurlコマンドを生成します。

### 返信用curlコマンド

```bash
# 基本的な返信のcurlコマンド
uv run grp-reply generate-curl https://github.com/owner/repo/pull/123 \
  --action reply \
  --comment-id 456789 \
  --message "Fixed!"
```

出力例：
```bash
curl -X POST \
  https://api.github.com/repos/owner/repo/pulls/123/comments \
  -H "Authorization: token ghp_xxxxxxxxxxxx" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d '{"body":"Fixed!","in_reply_to":456789,"path":"src/file.py","line":42,"side":"RIGHT"}'
```

### 新規コメント作成用curlコマンド

```bash
uv run grp-reply generate-curl https://github.com/owner/repo/pull/123 \
  --action create \
  --path src/main.py \
  --line 42 \
  --message "Great code!"
```

### 更新・削除用curlコマンド

```bash
# 更新用
uv run grp-reply generate-curl https://github.com/owner/repo/pull/123 \
  --action update \
  --comment-id 456789 \
  --message "Updated message"

# 削除用
uv run grp-reply generate-curl https://github.com/owner/repo/pull/123 \
  --action delete \
  --comment-id 456789
```

## 📝 返信テンプレート

よく使う返信パターンを定型文として利用できます。

### 利用可能なテンプレート

```bash
# テンプレート一覧を表示
uv run grp-reply list-templates
```

| テンプレート名 | 内容 | 用途 |
|---------------|------|------|
| `fixed` | ✅ Fixed! Thanks for the feedback. | 修正完了時 |
| `acknowledged` | 👍 Acknowledged. I'll address this in the next update. | 確認・対応予定 |
| `clarification` | 🤔 Could you provide more details about this issue? | 詳細確認 |
| `wontfix` | ⚠️ I understand the concern, but this is intentional due to [reason]. | 意図的な実装 |
| `duplicate` | 🔄 This appears to be a duplicate of another comment. See: [reference] | 重複コメント |
| `resolved` | ✅ This issue has been resolved. | 解決済み |
| `investigating` | 🔍 Looking into this issue. Will update soon. | 調査中 |
| `question` | ❓ I have a question about this feedback: [question] | 質問・確認 |
| `future_phase` | ⏳ Valid point, but not for current phase. Please remember for [future phase]. | 将来Phase対応 |

### テンプレートの使用例

```bash
# よく使うパターン
uv run grp-reply reply PR_URL --comment-id ID --template fixed
uv run grp-reply reply PR_URL --comment-id ID --template acknowledged
uv run grp-reply reply PR_URL --comment-id ID --template investigating

# 一括返信でもテンプレートが使用可能
cat > replies.json << 'EOF'
[
  {"comment_id": 123456, "template": "fixed"},
  {"comment_id": 123457, "template": "acknowledged"},
  {"comment_id": 123458, "template": "investigating"}
]
EOF

uv run grp-reply batch-reply PR_URL --replies-file replies.json
```

## 💡 実用例

### ⚡ CodeRabbitコメントへの効率的な対応

```bash
# 1. まず既存ツールでCodeRabbitコメントを確認
uv run grp https://github.com/owner/repo/pull/123

# 2. 修正完了後、一括で「Fixed」返信
cat > coderabbit-replies.json << 'EOF'
[
  {"comment_id": 123456, "template": "fixed"},
  {"comment_id": 123457, "template": "fixed"},
  {"comment_id": 123458, "template": "acknowledged"}
]
EOF

uv run grp-reply batch-reply https://github.com/owner/repo/pull/123 \
  --replies-file coderabbit-replies.json

# 3. 特別な返信が必要なコメントは個別対応
uv run grp-reply reply https://github.com/owner/repo/pull/123 \
  --comment-id 123459 \
  --message "🤔 This implementation is intentional for performance reasons. The alternative approach would cause a 30% slowdown in our benchmarks."
```

### 🔄 段階的な対応フロー

```bash
# Phase 1: 確認・調査中の返信
uv run grp-reply batch-reply PR_URL --replies-file investigating.json

# Phase 2: 修正完了後の返信
uv run grp-reply batch-reply PR_URL --replies-file fixed.json

# Phase 3: 個別の詳細な回答
uv run grp-reply reply PR_URL --comment-id ID --file detailed-response.md
```

### 🚦 安全な操作（ドライラン活用）

```bash
# 1. ドライランで操作内容を確認
uv run grp-reply batch-reply PR_URL --replies-file replies.json --dry-run

# 2. 問題なければ実際に実行
uv run grp-reply batch-reply PR_URL --replies-file replies.json

# 3. curlコマンド生成でマニュアル実行も可能
uv run grp-reply generate-curl PR_URL --action reply --comment-id ID --template fixed
```

## 📊 GitHub API 制限とベストプラクティス

### レート制限への対応

```bash
# 一括返信時の遅延調整
uv run grp-reply batch-reply PR_URL --replies-file replies.json --delay 1.0

# 大量のコメントを分割して処理
split -l 10 large-replies.json batch-
for file in batch-*; do
  uv run grp-reply batch-reply PR_URL --replies-file "$file" --delay 2.0
  sleep 30  # バッチ間でさらに休憩
done
```

### エラー処理とリトライ

```bash
# ドライランで事前確認
uv run grp-reply batch-reply PR_URL --replies-file replies.json --dry-run

# デバッグモードで詳細ログ
uv run grp-reply reply PR_URL --comment-id ID --message "text" --debug

# 失敗時はcurlコマンドで手動実行
uv run grp-reply generate-curl PR_URL --action reply --comment-id ID --message "text"
```

## 🛠️ トラブルシューティング

### 🔑 認証エラー

```bash
# トークンの確認
echo $GITHUB_TOKEN

# 権限テスト
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# 新しいトークンを生成
# https://github.com/settings/tokens → Generate new token
```

### 📝 コメントID不明

```bash
# 既存ツールでコメント一覧を取得
uv run grp https://github.com/owner/repo/pull/123 --debug

# GitHub Web UIでコメントURLからIDを確認
# https://github.com/owner/repo/pull/123#issuecomment-456789
# → コメントID: 456789
```

### 🔍 API エラーの対応

```bash
# デバッグモードで詳細確認
uv run grp-reply reply PR_URL --comment-id ID --message "text" --debug

# curlコマンドで直接テスト
uv run grp-reply generate-curl PR_URL --action reply --comment-id ID --message "text"
# 生成されたcurlコマンドを実行してエラー詳細を確認
```

### 📄 ファイル形式エラー

```bash
# JSONファイルの構文チェック
python -m json.tool replies.json

# サンプルファイルから開始
cp examples/batch-replies-sample.json my-replies.json
# 必要な部分を編集
```

## 🎯 高度な使用方法

### カスタムテンプレートの作成

```bash
# 独自のテンプレートファイルを作成
cat > custom-templates.json << 'EOF'
{
  "security-fix": "🔒 Security issue addressed with input validation and sanitization.",
  "performance": "⚡ Performance optimized with caching and lazy loading.",
  "documentation": "📝 Added comprehensive documentation and examples.",
  "testing": "🧪 Added unit tests and integration tests for this functionality."
}
EOF

# テンプレートを使った返信
TEMPLATE_CONTENT=$(cat custom-templates.json | jq -r '.["security-fix"]')
uv run grp-reply reply PR_URL --comment-id ID --message "$TEMPLATE_CONTENT"
```

### 自動化スクリプトの例

```bash
#!/bin/bash
# auto-reply.sh - CodeRabbitコメントに自動返信

PR_URL="$1"
if [ -z "$PR_URL" ]; then
  echo "Usage: $0 PR_URL"
  exit 1
fi

# 1. 既存コメントの確認
echo "📋 Analyzing existing comments..."
uv run grp "$PR_URL" --no-confirm > comments.md

# 2. 一括返信の準備
echo "📝 Preparing batch replies..."
cat > auto-replies.json << 'EOF'
[
  {"comment_id": 123456, "template": "fixed"},
  {"comment_id": 123457, "template": "acknowledged"}
]
EOF

# 3. ドライランで確認
echo "🔍 Dry run check..."
uv run grp-reply batch-reply "$PR_URL" --replies-file auto-replies.json --dry-run

# 4. 確認後に実行
read -p "Execute batch replies? (y/N): " confirm
if [[ $confirm == [yY] ]]; then
  uv run grp-reply batch-reply "$PR_URL" --replies-file auto-replies.json
  echo "✅ Batch replies completed!"
fi
```

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照してください。

---

💡 **Tip**: このツールを既存の `github-review-prompts` と組み合わせることで、CodeRabbitコメントの分析から返信まで、完全なレビュー対応ワークフローを構築できます！