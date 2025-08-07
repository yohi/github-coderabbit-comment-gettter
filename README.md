# GitHub CodeRabbit Comment Getter

GitHub PR のレビューコメントから「Prompt for AI Agents」ブロックを抽出し、フォーマットされたプロンプトリストを出力するツールです。

## 特徴

- **正確な解決状況判定**: GitHub GraphQL + REST APIを使用した高精度なコメント解決状況判定
- **CodeRabbitサポート**: CodeRabbitのAIエージェント用プロンプトを適切に抽出
- **Suggestionコメント除外**: GitHubのCommittable suggestionコメントを適切に除外
- **解決済みコメントのフィルタリング**: 開発者が手動でマークした解決済みコメントを自動検出・除外
- **uvx対応**: モダンなPythonツール実行環境uvxに完全対応

## 解決状況判定の仕組み

このツールは以下の方法でコメントの解決状況を判定します：

1. **GitHub GraphQL API（推奨）**:
   - `reviewThreads.isResolved`による正確な解決状態取得
   - 開発者が手動でマークした「Mark as resolved」を確実に検出

2. **GitHub REST API（フォールバック）**:
   - `conversation_resolved`フィールドによる判定
   - レビュー詳細APIを使用したコメント状態の確認
   - レビューステータス（APPROVED等）による判定

3. **Suggestionコメント処理**:
   - CodeRabbitのCommittable suggestionコメントは未解決として扱い
   - GitHub UIでの表示と一致する動作

4. **明示的解決キーワード**:
   - "resolved", "fixed", "done", "✅" 等のキーワードによる判定

## インストールと実行

### uvx使用（推奨）

```bash
# GitHubトークンを設定
export GITHUB_TOKEN=your_github_token

# ローカルパッケージからuvxで実行
uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123
```

### Python直接実行

```bash
# 依存関係をインストール
pip install requests

# 実行
export GITHUB_TOKEN=your_github_token
python github_review_prompts_clean.py https://github.com/owner/repo/pull/123
```

## コマンドラインオプション

```bash
# ヘルプ表示
uvx --from . gh-review-prompts --help

# 基本的な使用方法（解決済みコメントは除外）
uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123

# 結果をファイルに保存
uvx --from . gh-review-prompts -o output.md https://github.com/owner/repo/pull/123

# 解決済みコメントも含める
uvx --from . gh-review-prompts --include-resolved https://github.com/owner/repo/pull/123

# 全コメントの解決状況を分析
uvx --from . gh-review-prompts --analyze-all https://github.com/owner/repo/pull/123

# 特定コメントをデバッグ
uvx --from . gh-review-prompts --debug-comment 12345 https://github.com/owner/repo/pull/123
```

### オプション一覧

- `-h, --help`: ヘルプを表示
- `-o, --output FILE`: 出力ファイルを指定
- `--include-resolved`: 解決済みコメントも含める
- `--analyze-all`: 全コメントの解決状況を分析表示
- `--debug-comment ID`: 特定のコメントIDをデバッグ

## 使用例

### 1. 基本的な抽出

```bash
uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123
```

出力例：
```
次のAIエージェント用レビュー指摘プロンプトをひとつずつ対応してください。
ただし、指摘が正しいとは限らないので規約や環境、構造などを考慮し指摘されたことをしっかり精査した上で対応可否の判断を下すこと。

# Prompt For AI Agents List

- In src/main.py around line 15, replace the hardcoded string with a configuration variable to improve maintainability.
- In tests/test_main.py around line 30, add error handling for the network timeout scenario.
```

### 2. 全コメント分析

```bash
uvx --from . gh-review-prompts --analyze-all https://github.com/owner/repo/pull/123
```

出力例：
```
プルリクエスト情報: owner/repo#123
GraphQL APIを呼び出し中...
GraphQL APIで 10 個のCodeRabbit解決済みスレッドを検出
解決済みコメント 16 件をスキップしました

=== 全コメント解決状況分析（API基盤判定） ===
コメント  1 (ID: 12345): 解決済み (suggestion)
コメント  2 (ID: 12346): 未解決 (none)
コメント  3 (ID: 12347): 解決済み (api_based)

解決済み判定の内訳（API基盤）:
  suggestion: 14件
  api_based: 7件
  keyword: 1件
合計解決済み: 16件
総コメント数: 30件
```

### 3. 出力ファイルへの保存

```bash
uvx --from . gh-review-prompts -o prompts.md https://github.com/owner/repo/pull/123
```

## 環境変数

- `GITHUB_TOKEN`: GitHub APIトークン（**必須**）
  - Personal Access Tokenまたは他の認証方法が使用可能
  - GraphQL APIアクセスに必要

## 出力形式

### 通常出力

AIエージェント用のプロンプトとして最適化された形式で出力されます：

1. 指示文（対応方法の説明）
2. 注意事項（精査の重要性）
3. 対応不要判断の出力方法の例
4. プロンプトリスト

### 分析出力

`--analyze-all`オプションでは以下の分析情報が標準エラーに出力されます：

- GraphQL APIによる解決済みコメント検出状況
- 各コメントの解決状況と判定理由
- 解決済み判定の内訳統計
- 総コメント数と解決済みコメント数

## トラブルシューティング

### APIレート制限

```bash
# GitHub トークンを設定（必須）
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

### 解決済み判定が不正確

```bash
# 詳細な分析を確認
uvx --from . gh-review-prompts --analyze-all https://github.com/owner/repo/pull/123

# 特定コメントの詳細を確認
uvx --from . gh-review-prompts --debug-comment 12345 https://github.com/owner/repo/pull/123
```

### uvxでのインストールエラー

```bash
# 強制再インストール
uvx --force-reinstall --from . gh-review-prompts --help
```

## 技術仕様

### 対応GitHub機能

- Pull Request review comments（インラインコメント）
- GitHub GraphQL API v4（推奨）
- GitHub REST API v3（フォールバック）
- Review状態の詳細取得
- Conversation resolved状態

### API使用優先順位

1. **GraphQL API**（メイン）:
   - `repository.pullRequest.reviewThreads.isResolved`による正確な状態取得
   - 開発者が手動でマークした解決状態を確実に検出

2. **REST API**（フォールバック）:
   - GraphQL APIが利用できない場合の補完
   - `conversation_resolved`フィールドによる判定

### 除外対象

- Committable suggestionコメント
- 解決済みとマークされたコメント（デフォルト）
- AIプロンプト形式ではないコメント

### パッケージ情報

- **パッケージ名**: `github-coderabbit-comment-getter`
- **実行コマンド**: `gh-review-prompts`
- **Python要件**: >=3.8
- **依存関係**: `requests>=2.31.0`

## 開発

### ローカル開発

```bash
# リポジトリをクローン
git clone https://github.com/yohi/github-coderabbit-comment-getter.git
cd github-coderabbit-comment-getter

# uvxでローカル実行
export GITHUB_TOKEN=your_token
uvx --from . gh-review-prompts --help
```

### プロジェクト構造

```
github-coderabbit-comment-getter/
├── github_review_prompts_clean.py  # メインスクリプト
├── github_review_prompts.py        # 旧バージョン（バックアップ）
├── pyproject.toml                  # パッケージ設定
└── README.md                       # このファイル
```

## ライセンス

MIT License

## 変更履歴

### v1.0.0 (2025-01-17)
- GraphQL APIサポート追加により解決済みコメント検出精度を大幅向上
- uvx完全対応でモダンなPythonツール実行環境に対応
- コマンドラインインターフェースの改善（--helpオプション等）
- プロジェクト構造の整理とドキュメントの刷新
- GitHub UIとの判定一致性を大幅向上（16件の正確な解決済み検出を実現）

### v0.1.0 (初期バージョン)
- 初期リリース
- REST API基盤の解決判定
- 基本的なCodeRabbitプロンプト抽出機能
