#!/usr/bin/env python3
"""
GitHub Review Prompts AI Agent - 改善項目Issue作成スクリプト

このスクリプトは分析結果に基づいて、構造化されたGitHub Issueを作成します。
新しいセッションのAIエージェントが内容をすぐに理解できるよう最適化されています。
"""

import os
import json
import requests
from typing import Dict, List, Any
from datetime import datetime


class ImprovementIssueCreator:
    """改善項目Issue作成クラス"""

    def __init__(self, repo_owner: str, repo_name: str, github_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.base_url = "https://api.github.com"

    def create_issue(
        self, title: str, body: str, labels: List[str] = None
    ) -> Dict[str, Any]:
        """GitHub Issueを作成"""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues"

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

        data = {"title": title, "body": body, "labels": labels or []}

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Issue作成失敗: {response.status_code} - {response.text}")


def get_critical_issues() -> List[Dict[str, Any]]:
    """🔴 緊急対応が必要な課題"""
    return [
        {
            "title": "🔴 [Critical] 大量コメント処理のパフォーマンス改善",
            "labels": ["critical", "performance", "enhancement"],
            "body": """## 📋 課題概要

**現状**: PR #98での49件コメント処理で長時間を要し、メモリ使用量が不明確
**影響**: 大規模PRでの実用性に問題、ユーザー体験の悪化

## 🎯 改善目標

- [ ] 並列処理による処理速度3-5倍向上
- [ ] メモリ使用量の最適化
- [ ] 進捗表示とキャンセル機能

## 🔧 技術的アプローチ

### 1. 並列処理導入
```python
# 現状: 順次処理
for comment in comments:
    process_comment(comment)

# 改善案: 並列処理
import asyncio
async def process_comments_parallel(comments):
    tasks = [process_comment_async(comment) for comment in comments]
    return await asyncio.gather(*tasks)
```

### 2. ストリーミング処理
- 全コメントをメモリに保持せず、段階的処理
- ジェネレーター使用によるメモリ効率化

### 3. 進捗管理
- リアルタイム進捗表示
- 処理時間予測（ETA）
- 中断・再開機能

## 📊 成功指標

- **処理速度**: 100件コメントを5分以内
- **メモリ使用量**: 現在の50%以下
- **ユーザー体験**: 進捗可視化、中断可能

## 🔗 関連ファイル

- `src/github_review_prompts/comment_processor.py`
- `src/github_review_prompts/core/prompt_engine.py`
- `src/github_review_prompts/utils/rate_limit_handler.py`

## 🏷️ 実装優先度

**Phase 1 (1-2週間)**: 最高優先度
- 大規模PR対応の基盤となる重要な改善

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在のボトルネック分析（プロファイリング）
2. 並列処理アーキテクチャ設計
3. 段階的実装とテスト
4. パフォーマンス測定と最適化
""",
        },
        {
            "title": "🔴 [Critical] エラーハンドリング・信頼性の強化",
            "labels": ["critical", "reliability", "bug"],
            "body": """## 📋 課題概要

**現状**: 1件のコメント処理エラーで全体が停止する可能性
**影響**: 大規模PR処理時の信頼性不足、部分的な成果物も失われるリスク

## 🎯 改善目標

- [ ] 個別エラー処理による続行機能
- [ ] 処理状態の永続化とリカバリ
- [ ] 詳細なエラーレポート機能

## 🔧 技術的アプローチ

### 1. 個別エラー処理
```python
# 現状: 全体停止リスク
def process_comments(comments):
    results = []
    for comment in comments:
        result = process_comment(comment)  # エラーで停止
        results.append(result)
    return results

# 改善案: エラー耐性
def process_comments_resilient(comments):
    results = []
    errors = []

    for comment in comments:
        try:
            result = process_comment(comment)
            results.append(result)
        except Exception as e:
            error_info = {
                'comment_id': comment.get('id'),
                'error': str(e),
                'timestamp': datetime.now(),
                'retry_count': 0
            }
            errors.append(error_info)
            continue

    return results, errors
```

### 2. チェックポイント機能
- 処理進捗の定期保存
- 中断時からの再開機能
- 部分的な結果の保護

### 3. リトライ機構
- 一時的なネットワークエラーの自動リトライ
- 指数バックオフによる負荷軽減
- 最大リトライ回数の設定

## 📊 成功指標

- **エラー耐性**: 50%のコメントでエラーが発生しても処理続行
- **リカバリ**: 中断から5分以内に再開可能
- **透明性**: 全エラーの詳細ログと対処法提示

## 🔗 関連ファイル

- `src/github_review_prompts/comment_processor.py` (L348-354)
- `src/github_review_prompts/unified_cli.py` (L151-191)
- `src/github_review_prompts/utils/rate_limit_handler.py`

## 🏷️ 実装優先度

**Phase 1 (1-2週間)**: 最高優先度
- 実用性確保のための必須改善

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在のエラーパターン分析
2. エラー分類とハンドリング戦略設計
3. チェックポイント・リカバリ機構実装
4. 包括的なエラーテスト作成
""",
        },
        {
            "title": "🔴 [Critical] 長文コメント処理の改善",
            "labels": ["critical", "usability", "enhancement"],
            "body": """## 📋 課題概要

**現状**: 10,000文字制限で長文コメントが切り詰められ、重要情報が失われる
**影響**: CodeRabbitの詳細な指摘や複雑な修正提案が不完全になる

## 🎯 改善目標

- [ ] 長文コメントの要約機能
- [ ] 段階的表示・展開機能
- [ ] 重要部分の自動抽出

## 🔧 技術的アプローチ

### 1. インテリジェント要約
```python
def smart_summarize_comment(comment_body: str, max_length: int = 2000) -> Dict[str, str]:
    \"\"\"コメントの重要部分を抽出・要約\"\"\"

    # 構造化要素の抽出
    code_blocks = extract_code_blocks(comment_body)
    diff_blocks = extract_diff_blocks(comment_body)
    problem_description = extract_problem_description(comment_body)

    # 優先度付き要約
    summary = {
        'problem': problem_description[:500],
        'solution': extract_solution(comment_body)[:500],
        'code_examples': code_blocks[:3],  # 最初の3つのコードブロック
        'full_text_available': len(comment_body) > max_length
    }

    return summary
```

### 2. 段階的表示
- 要約版の初期表示
- 「詳細を表示」オプション
- セクション別の展開機能

### 3. 重要度分析
- セキュリティ関連キーワードの優先表示
- 修正提案の優先抽出
- エラー・警告の強調表示

## 📊 成功指標

- **情報保持率**: 重要情報の95%以上を要約に含める
- **可読性**: 要約版で問題の本質を理解可能
- **効率性**: 長文処理時間を50%短縮

## 🔗 関連ファイル

- `src/github_review_prompts/utils/validators.py` (L51-63)
- `src/github_review_prompts/cli.py` (L776-829)
- `src/github_review_prompts/prompt_generator.py`

## 🏷️ 実装優先度

**Phase 1 (1-2週間)**: 最高優先度
- CodeRabbitコメントの完全活用に必須

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 長文コメントのパターン分析
2. 重要部分抽出アルゴリズム設計
3. 要約・段階表示機能実装
4. CodeRabbitコメント特化の最適化
""",
        },
    ]


def get_high_priority_issues() -> List[Dict[str, Any]]:
    """🟡 重要な改善項目"""
    return [
        {
            "title": "🟡 [High] 設定管理システムの統一",
            "labels": ["high-priority", "refactoring", "maintainability"],
            "body": """## 📋 課題概要

**現状**: 2つの設定システム（config.py, enhanced_config.py）が並存し、保守が困難
**影響**: 設定変更時の混乱、新機能追加の複雑化、バグの温床

## 🎯 改善目標

- [ ] 単一の統一設定システム
- [ ] 環境別設定の簡素化
- [ ] 設定検証とエラー報告の改善

## 🔧 技術的アプローチ

### 1. 設定システム統一
```python
# 統一設定クラス設計
@dataclass
class UnifiedConfig:
    # 基本設定
    github_token: str
    output_format: str = "markdown"

    # パフォーマンス設定
    max_concurrent_requests: int = 5
    rate_limit_delay: float = 1.0

    # 機能設定
    enable_caching: bool = True
    enable_progress_tracking: bool = True

    # 環境別設定
    environment: str = "development"
    debug_mode: bool = False

    @classmethod
    def from_file(cls, config_path: str) -> 'UnifiedConfig':
        # 設定ファイル読み込み
        pass

    def validate(self) -> List[str]:
        # 設定検証
        pass
```

### 2. マイグレーション機能
- 既存設定の自動変換
- 非互換設定の警告
- 段階的移行サポート

### 3. 設定テンプレート
- プロジェクト種別別テンプレート
- ベストプラクティス設定
- 設定ウィザード機能

## 📊 成功指標

- **統一性**: 単一の設定ファイルで全機能制御
- **互換性**: 既存設定の100%移行成功
- **使いやすさ**: 設定エラーの明確な説明

## 🔗 関連ファイル

- `src/github_review_prompts/config.py`
- `src/github_review_prompts/utils/enhanced_config.py`
- `src/github_review_prompts/models.py` (L125-157)

## 🏷️ 実装優先度

**Phase 2 (3-4週間)**: 高優先度
- 長期保守性確保のための重要な基盤整備

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在の2つの設定システムの詳細分析
2. 統一設定スキーマの設計
3. マイグレーション機能の実装
4. 既存機能の動作確認とテスト
""",
        },
        {
            "title": "🟡 [High] テスト網羅性の向上",
            "labels": ["high-priority", "testing", "quality"],
            "body": """## 📋 課題概要

**現状**: 統合テスト不足、実際のPRテストに限定されている
**影響**: リグレッション発生リスク、リファクタリング時の不安

## 🎯 改善目標

- [ ] 単体テストカバレッジ80%以上
- [ ] 統合テストの充実
- [ ] CI/CDパイプラインの構築

## 🔧 技術的アプローチ

### 1. テスト戦略
```python
# 単体テスト例
class TestCommentProcessor:
    def test_process_single_comment(self):
        # 正常ケース
        pass

    def test_process_malformed_comment(self):
        # 異常ケース
        pass

    def test_process_large_comment(self):
        # 境界値テスト
        pass

# 統合テスト例
class TestEndToEnd:
    def test_full_pr_processing(self):
        # 実際のPR処理フロー
        pass

    def test_error_recovery(self):
        # エラー回復テスト
        pass
```

### 2. テストデータ管理
- モックGitHub APIレスポンス
- 様々なコメントパターンのテストデータ
- エラーケースのシミュレーション

### 3. CI/CD統合
- 自動テスト実行
- カバレッジレポート
- パフォーマンステスト

## 📊 成功指標

- **カバレッジ**: 単体テスト80%、統合テスト60%
- **信頼性**: CI/CDでの自動品質チェック
- **効率性**: テスト実行時間5分以内

## 🔗 関連ファイル

- `src/github_review_prompts/tests/`
- `src/github_review_prompts/tests/test_terraform_pr_102.py`

## 🏷️ 実装優先度

**Phase 2 (3-4週間)**: 高優先度
- 品質保証とリファクタリング安全性のために重要

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在のテスト状況の詳細分析
2. テスト戦略とカバレッジ目標の設定
3. 段階的なテスト追加（重要機能から）
4. CI/CDパイプラインの構築
""",
        },
        {
            "title": "🟡 [High] セキュリティ・認証の強化",
            "labels": ["high-priority", "security", "enhancement"],
            "body": """## 📋 課題概要

**現状**: GitHub tokenの環境変数管理のみ、ローテーション・権限制御未対応
**影響**: セキュリティリスク、企業環境での採用障壁

## 🎯 改善目標

- [ ] セキュアなトークン管理
- [ ] 細粒度権限制御
- [ ] 監査ログ機能

## 🔧 技術的アプローチ

### 1. セキュアストレージ
```python
class SecureTokenManager:
    def __init__(self, storage_backend: str = "keyring"):
        self.backend = storage_backend

    def store_token(self, token: str, alias: str = "default"):
        # OS keyringまたは暗号化ファイルに保存
        pass

    def get_token(self, alias: str = "default") -> str:
        # セキュアストレージから取得
        pass

    def rotate_token(self, old_token: str, new_token: str):
        # トークンローテーション
        pass
```

### 2. 権限制御
- 読み取り専用モード
- 操作別権限チェック
- 最小権限の原則適用

### 3. 監査機能
- 全API呼び出しのログ
- 機密情報のマスキング
- 異常アクセスの検出

## 📊 成功指標

- **セキュリティ**: トークンの平文保存ゼロ
- **監査性**: 全操作の追跡可能
- **企業対応**: エンタープライズ要件の80%満足

## 🔗 関連ファイル

- `src/github_review_prompts/github_client.py`
- `src/github_review_prompts/config.py`

## 🏷️ 実装優先度

**Phase 2 (3-4週間)**: 高優先度
- 企業環境での採用に必要

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在のセキュリティ状況の監査
2. セキュアストレージの設計・実装
3. 権限制御機能の追加
4. 監査ログ機能の実装
""",
        },
    ]


def get_medium_priority_issues() -> List[Dict[str, Any]]:
    """🟢 将来的な改善項目"""
    return [
        {
            "title": "🟢 [Medium] プラグインアーキテクチャの導入",
            "labels": ["medium-priority", "architecture", "extensibility"],
            "body": """## 📋 課題概要

**現状**: モノリシック構造で機能拡張が困難
**影響**: 新機能追加時の複雑化、カスタマイズ性の不足

## 🎯 改善目標

- [ ] プラグイン・フック機構の導入
- [ ] サードパーティ拡張のサポート
- [ ] 設定可能なワークフロー

## 🔧 技術的アプローチ

### 1. プラグインシステム設計
```python
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.hooks = {}

    def register_plugin(self, plugin: Plugin):
        # プラグイン登録
        pass

    def execute_hook(self, hook_name: str, *args, **kwargs):
        # フック実行
        pass

class Plugin:
    def __init__(self, name: str):
        self.name = name

    def on_comment_processed(self, comment: Dict) -> Dict:
        # コメント処理後のフック
        pass

    def on_output_generated(self, output: str) -> str:
        # 出力生成後のフック
        pass
```

### 2. 拡張ポイント
- コメント前処理・後処理
- 出力フォーマット拡張
- 外部システム連携
- カスタム分析機能

## 📊 成功指標

- **拡張性**: 5つ以上の拡張ポイント提供
- **使いやすさ**: プラグイン開発ドキュメント完備
- **安定性**: プラグインエラーでも本体動作継続

## 🏷️ 実装優先度

**Phase 3 (2-3ヶ月)**: 中優先度
- 長期的な拡張性確保のために重要

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. 現在のアーキテクチャ分析
2. プラグインシステム設計
3. 段階的な実装とテスト
4. サンプルプラグインの作成
""",
        },
        {
            "title": "🟢 [Medium] Web UI・ダッシュボードの開発",
            "labels": ["medium-priority", "ui", "enhancement"],
            "body": """## 📋 課題概要

**現状**: CLI のみでの操作、視覚的な進捗確認や統計表示なし
**影響**: ユーザビリティの制限、チーム利用時の情報共有困難

## 🎯 改善目標

- [ ] Web ベースのダッシュボード
- [ ] リアルタイム進捗表示
- [ ] 統計・レポート機能

## 🔧 技術的アプローチ

### 1. Web UI フレームワーク
- FastAPI + React/Vue.js
- WebSocket によるリアルタイム更新
- レスポンシブデザイン

### 2. 主要機能
- PR 処理の進捗表示
- コメント統計・傾向分析
- 設定管理 UI
- 履歴・ログ表示

## 📊 成功指標

- **使いやすさ**: 非技術者でも操作可能
- **情報価値**: 統計による改善点の可視化
- **効率性**: CLI と同等の機能提供

## 🏷️ 実装優先度

**Phase 3 (2-3ヶ月)**: 中優先度
- ユーザー体験向上のために有用

## 💡 AIエージェント向け指示

この課題は以下の順序で実装してください：
1. UI/UX 要件の整理
2. バックエンド API の設計
3. フロントエンド開発
4. 統合テストと最適化
""",
        },
    ]


def create_master_issue() -> Dict[str, Any]:
    """マスター Issue（全体概要）"""
    return {
        "title": "🎯 [MASTER] GitHub Review Prompts AI Agent - 改善ロードマップ 2025",
        "labels": ["epic", "roadmap", "master-issue"],
        "body": """# 🎯 GitHub Review Prompts AI Agent - 改善ロードマップ 2025

## 📋 概要

このマスターIssueは、GitHub Review Prompts AI Agentの包括的な改善計画を管理します。
**分析日**: 2025年1月24日
**分析対象**: PR #98 (49件コメント) の実際の処理結果とソースコード詳細分析

## 🔍 分析サマリー

### 現状の問題点
- **パフォーマンス**: 大量コメント処理時の速度問題
- **信頼性**: エラー時の全体停止リスク
- **使いやすさ**: 長文コメントの切り詰め
- **保守性**: 2つの設定システムが並存

### 改善効果予測
- **Phase 1**: 処理速度3-5倍向上、エラー耐性大幅改善
- **Phase 2**: 保守性向上、企業環境対応
- **Phase 3**: 拡張性確保、ユーザー体験向上

## 🗓️ 実装ロードマップ

### Phase 1: 緊急課題対応 (1-2週間)
**目標**: 実用性の確保

- [ ] #[ISSUE_NUMBER] 🔴 大量コメント処理のパフォーマンス改善
- [ ] #[ISSUE_NUMBER] 🔴 エラーハンドリング・信頼性の強化
- [ ] #[ISSUE_NUMBER] 🔴 長文コメント処理の改善

**成功基準**:
- 100件コメントを5分以内で処理
- 50%エラー発生時でも処理続行
- 重要情報の95%以上を要約に保持

### Phase 2: 品質・安定性向上 (3-4週間)
**目標**: 企業環境での採用準備

- [ ] #[ISSUE_NUMBER] 🟡 設定管理システムの統一
- [ ] #[ISSUE_NUMBER] 🟡 テスト網羅性の向上
- [ ] #[ISSUE_NUMBER] 🟡 セキュリティ・認証の強化

**成功基準**:
- 単一設定ファイルで全機能制御
- テストカバレッジ80%以上
- エンタープライズセキュリティ要件80%満足

### Phase 3: 機能拡張 (2-3ヶ月)
**目標**: 長期的な競争優位性確保

- [ ] #[ISSUE_NUMBER] 🟢 プラグインアーキテクチャの導入
- [ ] #[ISSUE_NUMBER] 🟢 Web UI・ダッシュボードの開発
- [ ] #[ISSUE_NUMBER] 🟢 外部システム連携強化

**成功基準**:
- 5つ以上の拡張ポイント提供
- Web UIでの直感的操作
- CI/CD・通知システム連携

## 📊 進捗管理

### 全体進捗
- **Phase 1**: 0% (未開始)
- **Phase 2**: 0% (未開始)
- **Phase 3**: 0% (未開始)

### 重要メトリクス
- **処理速度**: 現在 49件/[測定時間] → 目標 100件/5分
- **エラー耐性**: 現在 不明 → 目標 50%エラー時継続
- **テストカバレッジ**: 現在 限定的 → 目標 80%

## 🎯 AIエージェント向け指示

### 新しいセッション開始時の手順
1. このマスターIssueを最初に確認
2. 現在のPhaseと優先度を把握
3. 関連する個別Issueの詳細を確認
4. 実装前に現状分析と設計レビュー実施

### 実装時の注意点
- **段階的実装**: 一度に複数のPhaseに手を出さない
- **テスト重視**: 新機能は必ずテストと共に実装
- **互換性維持**: 既存機能を破壊しない
- **ドキュメント更新**: 変更内容を適切に文書化

### 完了時の手順
1. 該当Issueのクローズ
2. このマスターIssueの進捗更新
3. 次のPhaseの準備状況確認
4. 必要に応じて計画の見直し

## 🔗 関連リソース

- **分析レポート**: [詳細分析結果のリンク]
- **技術仕様**: [アーキテクチャドキュメント]
- **テスト計画**: [テスト戦略ドキュメント]

## 📞 連絡先・サポート

- **プロジェクト管理**: GitHub Issues
- **技術相談**: [技術責任者連絡先]
- **緊急時対応**: [緊急連絡先]

---

**最終更新**: 2025年1月24日
**次回レビュー予定**: Phase 1完了時
""",
    }


def main():
    """メイン実行関数"""
    # 環境変数から設定取得
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("❌ エラー: GITHUB_TOKEN環境変数が設定されていません")
        return

    # リポジトリ情報（実際の値に変更してください）
    repo_owner = "yohi"
    repo_name = "github-coderabbit-comment-gettter"

    creator = ImprovementIssueCreator(repo_owner, repo_name, github_token)

    print("🚀 GitHub Issues作成開始...")

    try:
        # マスターIssue作成
        master_issue = create_master_issue()
        print(f"📋 マスターIssue作成中: {master_issue['title']}")
        master_result = creator.create_issue(
            master_issue["title"], master_issue["body"], master_issue["labels"]
        )
        print(f"✅ マスターIssue作成完了: #{master_result['number']}")

        # 緊急課題Issues作成
        critical_issues = get_critical_issues()
        for issue in critical_issues:
            print(f"🔴 緊急Issue作成中: {issue['title']}")
            result = creator.create_issue(
                issue["title"], issue["body"], issue["labels"]
            )
            print(f"✅ Issue作成完了: #{result['number']}")

        # 重要課題Issues作成
        high_priority_issues = get_high_priority_issues()
        for issue in high_priority_issues:
            print(f"🟡 重要Issue作成中: {issue['title']}")
            result = creator.create_issue(
                issue["title"], issue["body"], issue["labels"]
            )
            print(f"✅ Issue作成完了: #{result['number']}")

        # 中優先度Issues作成
        medium_priority_issues = get_medium_priority_issues()
        for issue in medium_priority_issues:
            print(f"🟢 中優先度Issue作成中: {issue['title']}")
            result = creator.create_issue(
                issue["title"], issue["body"], issue["labels"]
            )
            print(f"✅ Issue作成完了: #{result['number']}")

        print("\n🎉 全てのIssue作成が完了しました！")
        print(
            f"📊 作成されたIssue数: {1 + len(critical_issues) + len(high_priority_issues) + len(medium_priority_issues)}件"
        )
        print(f"🔗 リポジトリ: https://github.com/{repo_owner}/{repo_name}/issues")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
