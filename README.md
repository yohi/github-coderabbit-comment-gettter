# GitHub CodeRabbit Comment Tool

GitHubプルリクエストのインラインコメントを取得して整形出力するPythonツールです。

## 特徴

- GitHubプルリクエストURLを指定してインラインコメントを取得
- レビューコメント（コード行に対するコメント）と一般コメントの両方に対応
- 読みやすい形式での出力
- uvx での実行に対応
- GitHub API トークンによる認証サポート
- **NEW**: AIエージェント用レビュープロンプトの抽出機能

## 提供されるコマンド

### 1. `gh-comments` - 基本的なコメント取得

### 2. `gh-comments-simple` - Click不使用版（uvx推奨）

### 3. `gh-review-prompts` - AIエージェント用プロンプト抽出

## インストールと実行

### uvx を使用した実行（推奨）

```bash
# リポジトリをクローン
git clone <repository-url>
cd github-coderabbit-comment

# 基本的なコメント取得
uvx --from . gh-comments-simple https://github.com/owner/repo/pull/123

# AIエージェント用プロンプト抽出
uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123
```

### AIエージェント用プロンプト抽出機能

CodeRabbitなどのAIエージェントが生成した「Prompt for AI Agents」ブロックを抽出し、レビュー対応用の指示形式で出力します。

```bash
# 標準出力にレビュー指示を表示
uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123

# ファイルに出力
uvx --from . gh-review-prompts --output review_prompts.md https://github.com/owner/repo/pull/123

# 解決済みコメントを除外（デフォルト）
uvx --from . gh-review-prompts --exclude-resolved https://github.com/owner/repo/pull/123
```

#### 出力例

```markdown
次のAIエージェント用レビュー指摘プロンプトをひとつずつ対応してください。
ただし、指摘が正しいとは限らないので規約や環境、構造などを考慮し指摘されたことをしっかり精査した上で対応可否の判断を下すこと。
最後に対応不要と判断したプロンプトに関してはその書き出しと、対応不要と判断した理由を下記のように出力してください。

例）
```
1. In backend-auth/server.js around line 44,
    - 開発・ローカル環境ではMemoryStoreで十分。本番環境では別途Redis/MongoDBを使用するべきですが、この段階では不要。

2. In backend-auth/server.js around lines 127 to 163,
    - シンプルな開発用認証サーバーでは、HTMLのインライン埋め込みは許容範囲。テンプレートエンジンの導入は複雑性を増すだけ。

...
```

対応が全て終わったらGitにコミット・プッシュを行ってください。

# Prompt For AI Agents List

- この部分のロジックを改善できそうです。詳細なテストケースを追加してください。

- エラーハンドリングを追加してください。try-catch文でAPIエラーをキャッチしてください。
```

### 開発環境でのセットアップ

```bash
# 依存関係のインストール
pip install -e .

# 直接実行
python github_comments.py https://github.com/owner/repo/pull/123
```

## 使用方法

### 基本的な使用方法

```bash
# インラインコメントのみを取得
uvx --from . gh-comments https://github.com/owner/repo/pull/123

# 一般コメントも含めて取得
uvx --from . gh-comments --include-general https://github.com/owner/repo/pull/123

# ファイルに出力
uvx --from . gh-comments -o comments.txt https://github.com/owner/repo/pull/123
```

### GitHub API トークンの設定

GitHub API のレート制限を回避するため、API トークンの使用を推奨します：

```bash
# 環境変数として設定
export GITHUB_TOKEN=your_github_token_here

# または .env ファイルに設定
cp .env.example .env
# .env ファイルを編集してトークンを設定

# コマンドラインオプションで指定
uvx --from . gh-comments --token your_token https://github.com/owner/repo/pull/123
```

### GitHub トークンの作成方法

1. GitHub の Settings > Developer settings > Personal access tokens に移動
2. "Generate new token" をクリック
3. 適切なスコープを選択（`repo` スコープが必要）
4. 生成されたトークンを保存

## 出力フォーマット

```
GitHub Pull Request Comments
Repository: owner/repo
Pull Request: #123
URL: https://github.com/owner/repo/pull/123
取得日時: 2025-08-07 12:00:00
================================================================================

インラインコメント (2件):

[REVIEW] username (2025-08-07T12:00:00Z) - src/main.py:L42 (pos:10)
この部分のロジックを改善できそうです。
--------------------------------------------------------------------------------

[REVIEW] reviewer (2025-08-07T11:30:00Z) - src/utils.py:L15 (pos:5)
エラーハンドリングを追加してください。
--------------------------------------------------------------------------------
```

## コマンドラインオプション

- `pr_url`: プルリクエストのURL（必須）
- `--token`: GitHub API トークン
- `--include-general`: 一般コメントも含める
- `--output, -o`: 出力ファイルパス（指定しない場合は標準出力）
- `--help`: ヘルプメッセージを表示

## 必要な権限

- パブリックリポジトリ: 認証不要（ただしレート制限あり）
- プライベートリポジトリ: `repo` スコープを持つGitHub API トークンが必要

## エラーハンドリング

- 無効なプルリクエストURL
- GitHub API のレート制限
- ネットワークエラー
- 認証エラー

## 開発

```bash
# 開発環境のセットアップ
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -e .

# テスト実行
python github_comments.py --help
```
