# UVX での GitHub Review Prompts 使用方法

## ✅ UVX対応完了

このプロジェクトは `uvx` で直接実行できるように設定されています。

## 🚀 利用可能なコマンド

### 1. **`uv run` での実行**（推奨）
```bash
# フル機能版
uv run github-review-prompts https://github.com/owner/repo/pull/123

# 簡易版
uv run grp https://github.com/owner/repo/pull/123

# ファイル出力
uv run github-review-prompts -o prompts.md https://github.com/owner/repo/pull/123

# セキュリティアナリストペルソナ
uv run github-review-prompts --persona security-analyst https://github.com/owner/repo/pull/123

# JSON形式出力
uv run github-review-prompts --format json https://github.com/owner/repo/pull/123

# ヘルプ表示
uv run github-review-prompts --help
```

### 2. **スタンドアロン版**（依存関係なし）
```bash
# Python標準ライブラリのみで実行
python grp_standalone.py https://github.com/owner/repo/pull/123
```

### 3. **UVX での実行**（現在調整中）
```bash
# 注意: 現在モジュール解決に問題があります
# uvx --from . github-review-prompts https://github.com/owner/repo/pull/123
```

## 🔧 環境設定

### GitHub Token の設定（必須）
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### GitHub Token の取得方法
1. GitHub.com > Settings > Developer settings > Personal access tokens
2. "Generate new token" でトークンを作成
3. "repo" スコープを選択

## 📋 実行例

### フル機能版での実行
```bash
# 環境変数設定
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 基本実行
uv run github-review-prompts https://github.com/microsoft/vscode/pull/12345

# 解決済みコメントも含めて分析
uv run github-review-prompts --include-resolved https://github.com/microsoft/vscode/pull/12345

# 詳細分析モード
uv run github-review-prompts --analyze-all https://github.com/microsoft/vscode/pull/12345
```

### 簡易版での実行
```bash
# 環境変数設定
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# uv run での実行（推奨）
uv run grp https://github.com/microsoft/vscode/pull/12345

# スタンドアロン版での実行
python grp_standalone.py https://github.com/microsoft/vscode/pull/12345
```

## 🎯 出力内容

### フル機能版の出力
- 高度なフィルタリング機能
- 複数ペルソナ対応
- カスタマイズ可能な出力形式
- 詳細な統計情報

### 簡易版の出力
- 基本的なプロンプト生成
- ファイル自動保存（`review_prompt_with_todos.md`）
- シンプルな実行

## ⚠️ トラブルシューティング

### ModuleNotFoundError が発生する場合
```bash
# パッケージの再インストール
uvx --force-reinstall --from . github-review-prompts --help
```

### GITHUB_TOKEN エラーが発生する場合
```bash
# トークンが設定されているか確認
echo $GITHUB_TOKEN

# トークンの有効性を確認
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### API レート制限に達した場合
- GitHub Personal Access Token を使用することで制限を大幅に緩和
- 1時間あたり5,000リクエストまで可能

## 📊 パフォーマンス

### フル機能版
- GraphQL API + REST API のハイブリッド使用
- 解決済みコメントの正確な検出
- 大規模なプルリクエストにも対応

### 簡易版
- 軽量な実行
- 基本的な機能に特化
- 素早い結果取得

## 🔗 関連ファイル

- `coderabbit_review_prompt.md` - レビュープロンプトテンプレート
- `pyproject.toml` - パッケージ設定（UVXエントリーポイント）
- `src/github_review_prompts/` - メインパッケージ
- `GRP_USAGE.md` - GRPコマンドの詳細使用方法

## 💡 推奨用途

| 用途 | 推奨コマンド | 理由 |
|------|-------------|------|
| 日常的なレビュー対応 | `grp` | 簡単、高速 |
| 詳細な分析が必要 | `github-review-prompts` | 高機能、カスタマイズ可能 |
| セキュリティ重視 | `github-review-prompts --persona security-analyst` | セキュリティ特化 |
| 大量処理 | `github-review-prompts --format json` | プログラム処理向け |

UVXを使用することで、ローカルインストール不要で即座に最新版のツールを実行できます！