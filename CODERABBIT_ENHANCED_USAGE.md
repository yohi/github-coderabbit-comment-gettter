# 🚀 CodeRabbit統合システム使用ガイド

CodeRabbitアドバイスに基づいて大幅に強化されたGitHub Review Promptsシステムの使用方法を説明します。

## 🎯 主要な改善点

### 1. **高度な優先度分類システム**
- セキュリティリスクの自動評価
- Terraform固有の問題分析
- ファイルパス別の重要度調整
- 40+種類のキーワードパターン認識

### 2. **GitHub API制限対策**
- 指数バックオフ戦略
- 適応的レート制限
- バッチ処理対応
- 自動リトライ機能

### 3. **SQLiteベースの進捗追跡**
- 永続的なデータ保存
- 詳細な統計分析
- 速度トレンド追跡
- 自動クリーンアップ

### 4. **重複Issue防止システム**
- 高精度な重複検出
- コンテンツハッシュ比較
- キーワードマッチング
- 既存Issue自動更新

## 🛠️ セットアップ

### 1. 設定ファイルの作成

```bash
# サンプル設定をコピー
cp github-review-prompts.sample.yml .github-review-prompts.yml

# 設定を編集
vim .github-review-prompts.yml
```

### 2. 環境変数の設定

```bash
export GITHUB_TOKEN="your_github_token"
export GITHUB_REVIEW_PROMPTS_ENV="development"  # development, staging, production
```

### 3. 基本的な使用方法

```python
from github_review_prompts import CodeRabbitEnhancedSystem

# システム初期化
system = CodeRabbitEnhancedSystem(
    config_path=".github-review-prompts.yml",
    environment="development"
)

# CodeRabbitレビューコメントの処理
result = system.process_coderabbit_review(
    pr_number=123,
    pr_url="https://github.com/user/repo/pull/123",
    comment_body=coderabbit_comment_text
)

print(f"処理結果: {result['outside_comments_count']}件のコメントを処理")
```

## 📊 高度な機能

### 1. 包括的なレビュー処理

```python
# CodeRabbitコメントの完全処理
result = system.process_coderabbit_review(
    pr_number=123,
    pr_url="https://github.com/user/repo/pull/123",
    comment_body="""
**Actionable comments posted: 4**

`201-241`: **aws_lb.optimized に precondition を追加して必須入力を早期検証**
ALB新規作成時の VPC/Subnet/SG 未指定は apply 時に落ちます...

---
**Duplicate comments posted: 2**
...
"""
)

# 結果の確認
print(f"優先度分布: {result['priority_distribution']}")
print(f"Issue作成統計: {result['issue_creation_stats']}")
print(f"推定作業時間: {result['total_estimated_hours']}時間")
```

### 2. 強化されたプロンプト生成

```python
# データベース連携の高度なプロンプト生成
prompt = system.generate_enhanced_prompt(
    pr_number=123,
    pr_url="https://github.com/user/repo/pull/123"
)

print(prompt)
# 出力例:
# # 🚨 CodeRabbit統合レビュー対応プロンプト
#
# ## 📊 進捗サマリー
# - **総コメント数**: 15
# - **解決済み**: 8
# - **未解決**: 7
# - **完了率**: 53.3%
# - **推定残り時間**: 14.5時間
#
# ## 🎯 対応が必要なコメント
#
# ### 🚨 TODO #1: modules/security/main.tf
# **優先度**: critical
# **カテゴリ**: security
# **推定時間**: 4.0時間
# **行番号**: 201
#
# **問題内容**:
# aws_lb.optimized に precondition を追加して必須入力を早期検証...
```

### 3. 進捗追跡と分析

```python
# 進捗統計の取得
stats = system.db_tracker.get_progress_stats(pr_number=123)
print(f"完了率: {stats.completion_rate:.1f}%")
print(f"平均解決時間: {stats.average_resolution_time:.1f}時間")

# 速度トレンドの分析
trend = system.db_tracker.get_velocity_trend(pr_number=123, days=7)
for point in trend:
    print(f"{point['date']}: {point['velocity']:.2f} コメント/時間")

# 包括的レポートの生成
report = system.generate_comprehensive_report(pr_number=123)
print(f"システム推奨事項: {report['system_recommendations']}")
```

### 4. GitHub Issue自動管理

```python
# 個別コメントのIssue作成
comment_data = {
    'pr_number': 123,
    'pr_url': 'https://github.com/user/repo/pull/123',
    'file_path': 'modules/security/main.tf',
    'line_number': 201,
    'comment_body': 'aws_lb.optimized に precondition を追加...',
    'priority': 'critical',
    'category': 'security',
    'severity': 'caution'
}

result = system.github_manager.create_issue_if_not_exists(comment_data)
if result.success:
    print(f"Issue作成: #{result.issue_number} - {result.issue_url}")
else:
    print(f"スキップ: {result.message}")

# バッチ処理
comments_batch = [comment_data1, comment_data2, comment_data3]
results = system.github_manager.batch_create_issues(comments_batch)

# 作成レポート
report = system.github_manager.generate_creation_report(results)
print(f"作成: {report['created']}件, 更新: {report['updated']}件")
```

## 🔧 設定のカスタマイズ

### 1. 優先度分類のカスタマイズ

```yaml
# .github-review-prompts.yml
processing_rules:
  auto_create_threshold: "high"  # critical, high, medium, low
  enable_security_analysis: true
  enable_terraform_analysis: true
  enable_duplicate_detection: true
```

### 2. Issueテンプレートのカスタマイズ

```yaml
issue_templates:
  custom_template:
    title_prefix: "[Custom]"
    labels: ["custom", "review"]
    assignee: "team-lead"
    auto_create: true
    body_template: |
      ## カスタム問題レポート

      **ファイル**: {file_path}
      **優先度**: {priority}

      ### 詳細
      {comment_body}

      ### 対応者
      @{assignee}
```

### 3. レート制限戦略の選択

```yaml
github:
  rate_limit_strategy: "adaptive"  # 推奨
  # または
  rate_limit_strategy: "exponential_backoff"  # 保守的
  # または
  rate_limit_strategy: "batch_processing"  # 大量処理向け
```

## 📈 監視とメンテナンス

### 1. システム状態の確認

```python
# システム全体の状態確認
status = system.get_system_status()
print(f"システム状態: {status['system_status']}")
print(f"データベースサイズ: {status['database_info']['database_size_mb']}MB")
print(f"GitHub API制限: {status['github_rate_limits']['remaining']}/5000")
```

### 2. 定期的なクリーンアップ

```python
# 30日以上古いデータをクリーンアップ
cleanup_result = system.cleanup_and_maintenance(days=30)
print(f"クリーンアップ完了: {cleanup_result['database_records_cleaned']}件削除")
```

### 3. データのエクスポート

```python
# 進捗データのエクスポート
from pathlib import Path
export_path = Path("progress_export.json")
system.db_tracker.export_data(export_path, pr_number=123)
print(f"データエクスポート完了: {export_path}")
```

## 🚨 トラブルシューティング

### 1. GitHub API制限エラー

```python
# レート制限状況の確認
rate_status = system.github_manager.rate_limiter.get_rate_limit_status()
if rate_status['is_rate_limited']:
    wait_time = rate_status['time_until_reset']
    print(f"レート制限中: {wait_time}秒後にリセット")
```

### 2. データベースエラー

```python
# データベース情報の確認
db_info = system.db_tracker.get_database_info()
if 'error' in db_info:
    print(f"データベースエラー: {db_info['error']}")
    # データベースファイルの再作成が必要な場合があります
```

### 3. 設定エラー

```python
# 設定の検証
config_summary = system.config_manager.get_config_summary()
if not config_summary['has_github_token']:
    print("GitHub トークンが設定されていません")
    print("環境変数 GITHUB_TOKEN を設定してください")
```

## 🎉 ベストプラクティス

### 1. **段階的な導入**
```python
# 最初は低い閾値でテスト
system.config.processing_rules.auto_create_threshold = "high"
# 慣れてきたら閾値を下げる
system.config.processing_rules.auto_create_threshold = "medium"
```

### 2. **定期的な監視**
```python
# 週次でシステム状態をチェック
def weekly_health_check():
    status = system.get_system_status()
    report = system.generate_comprehensive_report()

    # アラートの条件
    if status['github_rate_limits']['usage_percentage'] > 80:
        print("⚠️ GitHub API使用量が80%を超えています")

    if report['progress_statistics']['completion_rate'] < 50:
        print("📈 完了率が低いです - 作業の見直しを検討してください")
```

### 3. **チーム連携**
```python
# チーム向けの進捗レポート生成
def generate_team_report(pr_numbers):
    team_report = {
        'total_prs': len(pr_numbers),
        'pr_summaries': []
    }

    for pr_num in pr_numbers:
        stats = system.db_tracker.get_progress_stats(pr_num)
        team_report['pr_summaries'].append({
            'pr_number': pr_num,
            'completion_rate': stats.completion_rate,
            'remaining_comments': stats.total_comments - stats.resolved_comments
        })

    return team_report
```

このシステムにより、CodeRabbitのレビューコメントを効率的に管理し、チーム全体の生産性を大幅に向上させます。

## 📞 サポート

問題が発生した場合は、以下の情報を含めてお問い合わせください：
- システム状態レポート (`system.get_system_status()`)
- エラーログ
- 設定ファイル（トークンは除く）
- 使用環境の詳細
