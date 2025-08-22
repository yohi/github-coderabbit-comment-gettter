# CodeRabbit TODO Generator - シンプル版

CodeRabbitレビューコメントからAI対応用TODOリストを生成するシンプルなスクリプトです。

## 特徴

- **外部ライブラリ不要**: Python標準ライブラリのみを使用
- **サンプルデータ付属**: 実際のGitHub APIを呼ばずにテスト可能
- **すぐに使える**: 追加インストール作業不要

## 使用方法

### 1. 基本実行

```bash
python3 simple_todo_generator.py
```

### 2. 出力ファイル

実行すると以下のファイルが生成されます：

- `sample_todos.md` - AI用プロンプト形式のTODOリスト
- `sample_todos.json` - プログラム処理用JSONデータ

### 3. 出力例

```markdown
## レビューコメント一覧

### TODO #1: ログメッセージ内のプロパティアクセスが安全でない
**ID**: 2290383963
**ファイル**: `shin-supercursor-framework/src/infrastructure/adapters/cursor-api.adapter.ts`
**行**: 145
**種類**: Potential issue
**問題**: `error.message`を直接参照していますが...
**現在のコード**:
```typescript
this.logger.warn(`Cursor command failed: ${error.message}`);
```
**提案されている修正**:
```typescript
this.logger.warn(`Cursor command failed: ${error instanceof Error ? error.message : String(error)}`);
```
```

## 対応しているレビュー種類

- ⚠️ **Potential issue** - 潜在的な問題
- 🛠️ **Refactor suggestion** - リファクタリング提案
- 📝 **Committable suggestion** - コミット可能な提案
- 💡 **Nitpick comments** - 細かい指摘
- 🔍 **Verification agent** - 検証エージェント
- 📊 **Analysis chain** - 分析チェーン

## AIプロンプトでの使用例

生成されたTODOリストは、以下のようなプロンプトで使用できます：

```
あなたはTypeScript専門エンジニアです。以下のCodeRabbitレビューコメントに対応してください：

[生成されたTODOリスト内容]

各コメントに対して：
1. ✅/❌/🤔 で対応要否を判断
2. 修正を実装 または 理由付きで対応不要と判断
3. 対応不要の場合はGitHub APIで@coderabbitaiに返信

一つずつ順番に処理してください。
```

## カスタマイズ方法

### サンプルデータの変更

`create_sample_data()` 関数内のデータを編集することで、異なるレビューコメントをテストできます：

```python
def create_sample_data():
    return [
        {
            "id": 12345,
            "body": """_⚠️ Potential issue_

**あなたのレビューコメント**

詳細な説明...
""",
            "path": "your-file.ts",
            "line": 100,
            "user": {"login": "coderabbitai[bot]"}
        }
    ]
```

### 実際のGitHub APIデータとの連携

フル機能版（`generate_review_todos.py`）は実際のGitHub APIからデータを取得できますが、外部ライブラリ（requests）が必要です。

## ファイル構成

```
simple_todo_generator.py  # メインスクリプト
sample_todos.md          # 生成されるTODOリスト
sample_todos.json        # 生成されるJSONデータ
```

## 実行結果例

```
CodeRabbit TODO Generator - Simple Standalone Version
============================================================
Processing 4 sample comments...
Found 3 CodeRabbit comments

TODO list saved to sample_todos.md
TODO data saved to sample_todos.json

Summary:
  Total comments processed: 4
  CodeRabbit comments found: 3

  Review type breakdown:
    Potential issue: 2
    Refactor suggestion: 1

Demo completed successfully!
```

## トラブルシューティング

- **Python 3.6以上が必要です**
- **エラーが発生した場合**: エラーメッセージを確認し、Pythonバージョンをチェックしてください

## その他のファイル

本プロジェクトには他にも以下のファイルが含まれています：

- `generate_review_todos.py` - フル機能版（GitHub API対応）
- `README_todo_generator.md` - 詳細ドキュメント
- `batch_generate_todos.sh` - バッチ処理スクリプト

サンプル用途には `simple_todo_generator.py` で十分です。
