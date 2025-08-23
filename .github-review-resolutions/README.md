# GitHub Review Resolutions

このディレクトリは範囲外コメントの解決状態を管理します。

## ファイル構成

- `shared.json` - チーム共有の解決状態（Git管理対象）
- `personal-*.json` - 個人の解決状態（Git管理対象外）
- `cache/` - 一時キャッシュ（Git管理対象外）

## 使用方法

解決状態は自動的に検出・保存されます。手動での編集は推奨されません。

## 設定

プロジェクトルートに `.github-review-prompts.yml` を作成して設定をカスタマイズできます。

```yaml
resolution_storage:
  personal_storage:
    enabled: true
    auto_cleanup_days: 30
  shared_storage:
    enabled: true
    require_validation: true
```
