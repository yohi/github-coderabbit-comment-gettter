# 🤖 GitHub Review Prompts AI Agent

GitHub プルリクエストのレビューコメントから AI エージェント用プロンプトを抽出し、効率的なコードレビュー対応を支援する高度なツールです。

## 📋 目次

- [✨ 主な機能](#features)
- [📦 インストール](#install)
- [🚀 使用方法](#usage)
- [📖 実用例](#examples)
- [🛠️ トラブルシューティング](#troubleshooting)
- [🎯 コマンド比較表](#commands)
- [🔧 開発](#development)
- [📈 変更履歴](#changelog)

## ✨ 主な機能

- **🎯 高精度な解決済みコメント検出**: GitHub GraphQL API を使用して正確に解決済みコメントを識別
- **🤖 AI エージェント最適化プロンプト**: CodeRabbit 等のレビューツールからプロンプトを抽出・整形
- **💬 コメント返信機能**: 各CodeRabbitコメントに`in_reply_to`で直接返信するcurlコマンド自動生成
- **👤 複数ペルソナ対応**: コードレビュアー、セキュリティアナリスト、パフォーマンスオプティマイザー
- **📂 ブランチ情報自動取得**: ソース・ターゲットブランチ情報とチェックアウト指示を自動生成
- **🔍 包括的フィルタリング**: カテゴリ、優先度、ファイルパターンによる柔軟な絞り込み
- **📄 複数出力形式**: Markdown / JSON 形式での出力
- **📊 詳細な統計情報**: 処理サマリーとエラーレポート
- **⚡ 効率化オプション**: 確認スキップ・自動Git操作モード
- **🚀 UVX完全対応**: モダンなPython実行環境に最適化

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

## 📦 インストール
<a id="install"></a>

### 必要環境
- Python 3.8+
- GitHub API トークン

### uv を使用した環境セットアップ（推奨）
```bash
# uv がインストールされていない場合
curl -LsSf https://astral.sh/uv/install.sh | sh

# プロジェクトの依存関係をインストール
uv sync

# 開発用依存関係も含める場合
uv sync --dev
```

### pip を使用した場合
```bash
# 仮想環境の作成と有効化
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# 依存関係のインストール
pip install -e .
```

## 🔧 設定

### 環境変数
```bash
# 必須
export GITHUB_TOKEN="your_github_token_here"

# オプション
export DEFAULT_OUTPUT_FORMAT="markdown"
export DEFAULT_PERSONA="code-reviewer"
export LOG_LEVEL="INFO"
```

### 設定ファイル（オプション）
`.github-review-prompts.yml` を作成:
```yaml
github:
  token: ${GITHUB_TOKEN}

output:
  format: "markdown"
  default_file: "review-prompts.md"

personas:
  default: "code-reviewer"

processing:
  include_resolved: false
  max_concurrent_requests: 5
  cache_duration: 300
```

## 🚀 使用方法
<a id="usage"></a>

### 🏃‍♂️ クイックスタート

**推奨**: `uv run` を使用した実行
```bash
# 基本実行
uv run github-review-prompts https://github.com/owner/repo/pull/123

# 軽量版（依存関係なし）
uv run grp https://github.com/owner/repo/pull/123
```

**UVX使用**: ビルド済みパッケージから実行
```bash
uvx --from ./dist/github_review_prompts_ai_agent-1.0.0-py3-none-any.whl grp https://github.com/owner/repo/pull/123
```

### 💪 効率化オプション

**確認スキップモード**: 連続処理で効率アップ
```bash
# フル機能版
uv run github-review-prompts --no-confirm https://github.com/owner/repo/pull/123

# 軽量版
uv run grp --no-confirm https://github.com/owner/repo/pull/123
```

**自動Git操作モード**: 対応完了後に自動コミット・プッシュ
```bash
# フル機能版
uv run github-review-prompts --auto-commit https://github.com/owner/repo/pull/123

# 軽量版
uv run grp --auto-commit https://github.com/owner/repo/pull/123
```

**最強の組み合わせ**: 確認スキップ + 自動Git操作
```bash
uv run grp --no-confirm --auto-commit https://github.com/owner/repo/pull/123
```

### 🎨 フル機能版の高度なオプション

```bash
# ペルソナ指定
uv run github-review-prompts --persona security-analyst https://github.com/owner/repo/pull/123

# ファイル出力
uv run github-review-prompts -o prompts.md https://github.com/owner/repo/pull/123

# JSON形式で出力
uv run github-review-prompts --format json https://github.com/owner/repo/pull/123

# 解決済みコメントも含めて分析
uv run github-review-prompts --include-resolved https://github.com/owner/repo/pull/123

# 特定カテゴリのみ抽出
uv run github-review-prompts --categories security performance https://github.com/owner/repo/pull/123

# デバッグモード
uv run github-review-prompts --debug --analyze-all https://github.com/owner/repo/pull/123
```

### 🎭 利用可能なペルソナ

```bash
# ペルソナ一覧を表示
uv run github-review-prompts --list-personas
```

#### ペルソナの種類
- **👨‍💻 code-reviewer**: 総合的なコードレビュー（デフォルト）
- **🔒 security-analyst**: セキュリティ重点の分析
- **⚡ performance-optimizer**: パフォーマンス最適化重点

## 📖 実用例
<a id="examples"></a>

### 🎯 1. 基本的な使用パターン

**軽量・高速実行**:
```bash
# 軽量版で基本実行
uv run grp https://github.com/owner/repo/pull/123

# 出力確認
cat review_prompt_with_todos.md
```

**フル機能版**:
```bash
# 高度なフィルタリング
uv run github-review-prompts --persona security-analyst --categories security https://github.com/owner/repo/pull/123
```

### ⚡ 2. 効率化モード

**確認スキップで連続処理**:
```bash
uv run grp --no-confirm https://github.com/owner/repo/pull/123
```

**自動Git操作付き**:
```bash
uv run grp --auto-commit https://github.com/owner/repo/pull/123
```

**最強の効率化（推奨）**:
```bash
uv run grp --no-confirm --auto-commit https://github.com/owner/repo/pull/123
```

出力例（効率化モード）:
```markdown
# CodeRabbit レビューコメント対応プロンプト

## ⚡ 作業モード設定
**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。

## 🔄 Git自動操作設定
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

### Git操作手順
1. **ステージング**: `git add .` で変更ファイルをステージング
2. **コミット**: `git commit -m "CodeRabbit review comments addressed - [PR番号]"` でコミット
3. **プッシュ**: `git push` でリモートリポジトリに反映
```

### 🎯 3. CodeRabbit返信ワークフロー

**基本ワークフロー**:
```bash
# 1. CodeRabbitコメント分析
uv run grp https://github.com/owner/repo/pull/123

# 2. 生成されたプロンプトファイルを確認
cat review_prompt_with_todos.md

# 3. 各コメントの「🔧 このコメントへの返信用curlコマンド」セクションから適切なコマンドを選択

# 4. curlコマンドを実行（例：対応完了の場合）
curl -X POST \
  "https://api.github.com/repos/owner/repo/pulls/123/comments" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d '{"body": "@coderabbitai MD5からbcryptに変更しました。問題がなければこの課題を解決済みにしてください。", "in_reply_to": 456789}'
```

**返信の特徴**:
- ✅ `in_reply_to`パラメータで特定コメントに直接返信
- ✅ GitHub上でスレッド形式で表示
- ✅ コンテキストが保持され、どのコメントへの返信かが明確

### 📊 4. 詳細分析モード

```bash
# 全コメント分析
uv run github-review-prompts --analyze-all https://github.com/owner/repo/pull/123

# 特定コメントの詳細分析
uv run github-review-prompts --debug-comment 12345 https://github.com/owner/repo/pull/123
```

出力例：
```
🔄 CodeRabbit Review Prompt Generator (UVX)
📋 プルリクエスト: https://github.com/owner/repo/pull/123
プルリクエスト情報: owner/repo#123
タイトル: Fix security vulnerabilities in auth module
ソースブランチ: owner/repo:feature/security-fixes
ターゲットブランチ: owner/repo:main
レビューコメント取得中...
取得したコメント数: 24
解決済みコメント検出中...
GraphQL APIで 8 件の解決済みコメントを検出
解決済みコメント: 8 件
CodeRabbitコメント（未解決）: 5 件

レビュー種別の内訳:
  Potential issue: 3
  Refactor suggestion: 2
```

### 💾 4. 出力カスタマイズ

```bash
# ファイル出力
uv run github-review-prompts -o custom-prompts.md https://github.com/owner/repo/pull/123

# JSON形式
uv run github-review-prompts --format json https://github.com/owner/repo/pull/123
```

## 環境変数

- `GITHUB_TOKEN`: GitHub APIトークン（**必須**）
  - Personal Access Tokenまたは他の認証方法が使用可能
  - GraphQL APIアクセスに必要
  - CodeRabbit返信用curlコマンドで使用
  - Pull Request Comments APIへのアクセス権限が必要

## 出力形式

### 通常出力

AIエージェント用のプロンプトとして最適化された形式で出力されます：

1. 指示文（対応方法の説明）
2. 注意事項（精査の重要性）
3. プルリクエスト情報（タイトル、作成者、URL）
4. **ブランチ情報**（ソース・ターゲットブランチ）
5. **作業開始コマンド**（git checkout指示、フォーク対応）
6. 対応不要判断の出力方法の例
7. プロンプトリスト

#### プロンプト出力例

```markdown
# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## レビューコメント一覧

**プルリクエスト**: owner/repo#123
**URL**: https://github.com/owner/repo/pull/123
**タイトル**: Fix security vulnerabilities in auth module
**作成者**: @developer

### 📂 ブランチ情報
**ソースブランチ**: `owner/repo:feature/security-fixes`
**ターゲットブランチ**: `owner/repo:main`

### 🔄 作業開始コマンド
\```bash
# ローカルでソースブランチにチェックアウト
git checkout feature/security-fixes
git pull origin feature/security-fixes
\```

### TODO #1: パスワードハッシュ化の改善
**ID**: 12345
**ファイル**: `src/auth.py`
**行**: 42
**種類**: Potential issue
**問題**: bcryptの代わりにMD5を使用している...
```

### 分析出力

`--analyze-all`オプションでは以下の分析情報が標準エラーに出力されます：

- GraphQL APIによる解決済みコメント検出状況
- 各コメントの解決状況と判定理由
- 解決済み判定の内訳統計
- 総コメント数と解決済みコメント数

## 🛠️ トラブルシューティング
<a id="troubleshooting"></a>

### 🔑 APIレート制限・認証エラー

```bash
# GitHub トークンを設定（必須）
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# トークンの確認
echo $GITHUB_TOKEN

# 権限確認
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### 🔍 解決済み判定が不正確

```bash
# 詳細な分析を確認
uv run github-review-prompts --analyze-all https://github.com/owner/repo/pull/123

# 特定コメントの詳細を確認
uv run github-review-prompts --debug-comment 12345 https://github.com/owner/repo/pull/123

# GraphQL APIの動作確認
uv run github-review-prompts --debug https://github.com/owner/repo/pull/123
```

### 📦 実行環境エラー

```bash
# 依存関係の再インストール
uv sync --reinstall

# Pythonバージョン確認
python --version
uv --version

# ビルドテスト
uv build --wheel
```

## 🎯 コマンド比較表
<a id="commands"></a>

| コマンド | 説明 | 特徴 | 推奨用途 |
|----------|------|------|----------|
| **uv run grp** | 🚀 軽量版 | 依存関係なし、高速起動 | **日常使用** |
| **uv run github-review-prompts** | 🎨 フル機能版 | ペルソナ、フィルタリング | **高度な分析** |
| **uv run grp-reply** | 💬 コメント返信 | 返信、一括処理、curl生成 | **レビュー対応** |
| **uvx --from wheel grp** | 📦 ビルド版 | パッケージ化済み | **配布・デモ** |

### 💡 おすすめの使い分け

- **毎日のレビュー**: `uv run grp --no-confirm --auto-commit`
- **セキュリティ重視**: `uv run github-review-prompts --persona security-analyst`
- **CodeRabbit返信**: `uv run grp PR_URL` → 生成されたcurlコマンドで直接返信
- **コメント返信**: `uv run grp-reply reply PR_URL --comment-id ID --template fixed`
- **一括返信**: `uv run grp-reply batch-reply PR_URL --replies-file replies.json`
- **初回試用**: `uv run grp --help`

### 🔗 関連ドキュメント

- **コメント返信機能**: [COMMENT_REPLY_USAGE.md](COMMENT_REPLY_USAGE.md) - 詳細な使用方法とcurlコマンド生成
- **軽量版GRP**: [GRP_USAGE.md](GRP_USAGE.md) - 高速なコメント分析
- **シンプル使用法**: [SIMPLE_USAGE.md](SIMPLE_USAGE.md) - 基本的な使い方
- **UVX実行**: [UVX_USAGE.md](UVX_USAGE.md) - パッケージからの実行

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

## 🔧 開発
<a id="development"></a>

### ローカル開発

```bash
# リポジトリをクローン
git clone https://github.com/yohi/github-coderabbit-comment-getter.git
cd github-coderabbit-comment-getter

# uvxでローカル実行
export GITHUB_TOKEN=your_token
uvx --from . gh-review-prompts --help
```

### 📁 プロジェクト構造

```
github-coderabbit-comment-getter/
├── src/
│   ├── grp_uvx.py                      # 🚀 UVX専用軽量版
│   └── github_review_prompts/          # 📦 メインパッケージ
│       ├── __init__.py
│       ├── cli.py                      # 🎨 フル機能CLI
│       ├── coderabbit_review_prompt.md # 📄 プロンプトテンプレート
│       ├── github_client.py            # 🔌 GitHub API クライアント
│       ├── comment_processor.py        # 🔍 コメント処理エンジン
│       ├── prompt_generator.py         # ✨ AI プロンプト生成
│       ├── models.py                   # 📊 データモデル
│       ├── config.py                   # ⚙️ 設定管理
│       ├── output_formatter.py         # 📝 出力フォーマッター
│       ├── tests/                      # 🧪 テストスイート
│       └── utils/                      # 🛠️ ユーティリティ
├── pyproject.toml                      # 📋 パッケージ設定
├── uv.lock                            # 🔒 依存関係ロック
├── README.md                          # 📖 このファイル
├── GRP_USAGE.md                       # 📚 GRP使用ガイド
├── SIMPLE_USAGE.md                    # 🏃 簡単使用ガイド
└── UVX_USAGE.md                       # 🚀 UVX使用ガイド
```

## ライセンス

MIT License

## 📈 変更履歴
<a id="changelog"></a>

### v1.2.0 (2025-08-21) - CodeRabbit返信機能追加
- 💬 **CodeRabbit直接返信**: 各コメントに`in_reply_to`パラメータで直接返信するcurlコマンドを自動生成
- 🎯 **スレッド形式対応**: GitHub上でコメントツリーとして表示され、コンテキストが保持される仕組み
- 🔧 **個別curl生成**: 各コメントIDに対応した「対応不要」「対応完了」「要確認」の3パターンのcurlコマンド
- 📊 **Pull Request Comments API活用**: 特定コメント返信とPR全体コメントを適切に使い分け
- 🎨 **プロンプト最適化**: 返信手順とAPIの仕組みを詳細に説明
- 📋 **包括的対応**: フル機能版とGRP軽量版の両方で個別返信機能をサポート

### v1.1.0 (2025-08-21) - 効率化アップデート
- ⚡ **効率化オプション追加**: `--no-confirm` と `--auto-commit` オプション
- 🤖 **CodeRabbit返信指示強化**: 解決済み指示とマルチタスク防止メッセージ
- 🚀 **UVX完全対応**: `uvx --from wheel` での実行を安定化
- 🧹 **プロジェクト整理**: 不要ファイル削除とクリーンアップ（325KB+削減）
- 📝 **プロンプト改善**: 自動Git操作とワークフロー最適化指示を追加

### v1.0.0 (2025-01-17) - メジャーリリース
- 🎯 **GraphQL APIサポート**: 解決済みコメント検出精度を大幅向上
- 🚀 **UVX対応**: モダンなPython実行環境に完全対応
- 🎨 **CLI改善**: コマンドラインインターフェースの全面刷新
- 📊 **精度向上**: GitHub UIとの判定一致性を大幅向上（16件の正確な解決済み検出）
- 📚 **ドキュメント整備**: 包括的な使用ガイドと技術仕様

### v0.1.0 (2024-12-XX) - 初期バージョン
- 🎬 **初期リリース**: 基本的なCodeRabbitプロンプト抽出機能
- 🌐 **REST API基盤**: GitHub REST APIによる解決判定
- 📄 **基本出力**: Markdownファイル生成
