# GRP - GitHub Review Prompt Generator

`grp`コマンドでプルリクエストURLを指定すると、CodeRabbitレビューコメント対応用のプロンプトとTODOリストを生成します。

## 使用方法

### 環境変数の設定（初回のみ）

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 実行

```bash
./grp <プルリクエストURL>
```

### 例

```bash
# GitHub トークンを設定
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# プルリクエストの解析実行
./grp https://github.com/yohi/CursorCLI-Extensions/pull/5
```

### 実行時の流れ

1. GitHub APIからプルリクエスト基本情報を取得
2. レビューコメントを取得
3. GraphQL APIで解決済みコメントを検出
4. CodeRabbitコメントのみを抽出・処理
5. プロンプト形式で出力・ファイル保存

## 出力内容

### 1. レビュープロンプト
- 汎用的なレビューコメント対応プロンプト
- GitHub API返信機能付き
- レビュー種類別の対応指針

### 2. TODOリスト
- プルリクエストの基本情報
- 各レビューコメントのTODO項目
- ファイル・行番号・種類・問題説明付き

## 生成ファイル

実行すると以下のファイルが生成されます：

- `review_prompt_with_todos.md` - AI用プロンプト（完全版）

## 特徴

✅ **実際のGitHub API呼び出し** - 実際のプルリクエストからレビューコメントを取得
✅ **解決済みコメント除外** - GraphQL APIによる正確な解決状況判定
✅ **即座に実行可能** - Python環境があれば追加インストール不要
✅ **汎用対応** - あらゆるプログラミング言語に対応
✅ **GitHub API連携** - @coderabbitai への返信機能付き

## 前提条件

- Python 3.8以上
- GITHUB_TOKEN環境変数の設定（GitHub Personal Access Token）
- `src/github_review_prompts/` パッケージ（本プロジェクトに含まれています）

## ファイル構成

```
grp                    # メインコマンド
grp_simple.py         # コア実装
coderabbit_review_prompt.md  # プロンプトテンプレート
```

## サンプル出力

```markdown
# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。
プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## 対応方針
1. **一つずつ順番に処理**: 複数のコメントがある場合、必ず一つずつ順番に対応
2. **批判的評価**: レビューコメントが技術的に正しいかどうかを必ず検証
3. **対応判断**: ✅対応実施 / ❌対応不要 / 🤔要確認

## レビューコメント一覧

### TODO #1: ログメッセージ内のプロパティアクセスが安全でない
**ID**: 2290383963
**ファイル**: `src/infrastructure/adapters/cursor-api.adapter.ts`
**行**: 145
**種類**: Potential issue
**問題**: `error.message`を直接参照していますが、`error`が`Error`型でない可能性...
```

これでAIエージェントが効率的にレビューコメントに対応できるようになります！
