#!/usr/bin/env python3
"""
マスターIssue更新スクリプト

作成されたIssue番号を反映してマスターIssueを更新します。
"""

import os
import requests
from typing import Dict, Any


class MasterIssueUpdater:
    """マスターIssue更新クラス"""

    def __init__(self, repo_owner: str, repo_name: str, github_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.base_url = "https://api.github.com"

    def update_issue(
        self, issue_number: int, title: str = None, body: str = None
    ) -> Dict[str, Any]:
        """GitHub Issueを更新"""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}"

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body

        try:
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception(
                "Issue更新タイムアウト: リクエストが10秒以内に完了しませんでした"
            )
        except requests.exceptions.RequestException as e:
            status_code = getattr(e.response, "status_code", "Unknown")
            response_text = getattr(e.response, "text", "No response body")
            raise Exception(
                f"Issue更新失敗: HTTP {status_code} - {response_text[:200]}..."
            )


def get_updated_master_issue_body() -> str:
    """更新されたマスターIssueの本文を生成"""
    return """# 🎯 GitHub Review Prompts AI Agent - 改善ロードマップ 2025

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

- [ ] #7 🔴 [Critical] 大量コメント処理のパフォーマンス改善
- [ ] #8 🔴 [Critical] エラーハンドリング・信頼性の強化
- [ ] #9 🔴 [Critical] 長文コメント処理の改善

**成功基準**:
- 100件コメントを5分以内で処理
- 50%エラー発生時でも処理続行
- 重要情報の95%以上を要約に保持

### Phase 2: 品質・安定性向上 (3-4週間)
**目標**: 企業環境での採用準備

- [ ] #10 🟡 [High] 設定管理システムの統一
- [ ] #11 🟡 [High] テスト網羅性の向上
- [ ] #12 🟡 [High] セキュリティ・認証の強化

**成功基準**:
- 単一設定ファイルで全機能制御
- テストカバレッジ80%以上
- エンタープライズセキュリティ要件80%満足

### Phase 3: 機能拡張 (2-3ヶ月)
**目標**: 長期的な競争優位性確保

- [ ] #13 🟢 [Medium] プラグインアーキテクチャの導入
- [ ] #14 🟢 [Medium] Web UI・ダッシュボードの開発
- [ ] 🟢 [Medium] 外部システム連携強化（将来作成予定）

**成功基準**:
- 5つ以上の拡張ポイント提供
- Web UIでの直感的操作
- CI/CD・通知システム連携

## 📊 進捗管理

### 全体進捗
- **Phase 1**: 0% (未開始)
  - Issue #7: 0% (未開始)
  - Issue #8: 0% (未開始)
  - Issue #9: 0% (未開始)
- **Phase 2**: 0% (未開始)
  - Issue #10: 0% (未開始)
  - Issue #11: 0% (未開始)
  - Issue #12: 0% (未開始)
- **Phase 3**: 0% (未開始)
  - Issue #13: 0% (未開始)
  - Issue #14: 0% (未開始)

### 重要メトリクス
- **処理速度**: 現在 49件/[測定時間] → 目標 100件/5分
- **エラー耐性**: 現在 不明 → 目標 50%エラー時継続
- **テストカバレッジ**: 現在 限定的 → 目標 80%

## 🎯 AIエージェント向け指示

### 新しいセッション開始時の手順
1. このマスターIssue (#6) を最初に確認
2. 現在のPhaseと優先度を把握
3. 関連する個別Issueの詳細を確認
4. 実装前に現状分析と設計レビュー実施

### 実装優先順序
**Phase 1 (最優先)**:
1. **Issue #7**: パフォーマンス改善 - 並列処理導入
2. **Issue #8**: エラーハンドリング - 部分失敗対応
3. **Issue #9**: 長文コメント処理 - 要約機能

**Phase 2 (高優先度)**:
4. **Issue #10**: 設定管理統一 - 2システム統合
5. **Issue #11**: テスト充実 - カバレッジ80%
6. **Issue #12**: セキュリティ強化 - 企業対応

**Phase 3 (中優先度)**:
7. **Issue #13**: プラグイン機構 - 拡張性確保
8. **Issue #14**: Web UI開発 - ユーザビリティ

### 実装時の注意点
- **段階的実装**: 一度に複数のPhaseに手を出さない
- **テスト重視**: 新機能は必ずテストと共に実装
- **互換性維持**: 既存機能を破壊しない
- **ドキュメント更新**: 変更内容を適切に文書化

### 完了時の手順
1. 該当Issueのクローズ
2. このマスターIssue (#6) の進捗更新
3. 次のPhaseの準備状況確認
4. 必要に応じて計画の見直し

## 🔗 関連Issues詳細リンク

### 🔴 Phase 1 - 緊急対応
- [Issue #7: 大量コメント処理のパフォーマンス改善](https://github.com/yohi/github-coderabbit-comment-gettter/issues/7)
- [Issue #8: エラーハンドリング・信頼性の強化](https://github.com/yohi/github-coderabbit-comment-gettter/issues/8)
- [Issue #9: 長文コメント処理の改善](https://github.com/yohi/github-coderabbit-comment-gettter/issues/9)

### 🟡 Phase 2 - 品質向上
- [Issue #10: 設定管理システムの統一](https://github.com/yohi/github-coderabbit-comment-gettter/issues/10)
- [Issue #11: テスト網羅性の向上](https://github.com/yohi/github-coderabbit-comment-gettter/issues/11)
- [Issue #12: セキュリティ・認証の強化](https://github.com/yohi/github-coderabbit-comment-gettter/issues/12)

### 🟢 Phase 3 - 機能拡張
- [Issue #13: プラグインアーキテクチャの導入](https://github.com/yohi/github-coderabbit-comment-gettter/issues/13)
- [Issue #14: Web UI・ダッシュボードの開発](https://github.com/yohi/github-coderabbit-comment-gettter/issues/14)

## 🔗 関連リソース

- **分析レポート**: [PR #98 コメント分析結果](https://github.com/yohi/terraform/pull/98)
- **技術仕様**: `AI_AGENT_QUICK_REFERENCE.md`
- **実装スクリプト**: `create_improvement_issues.py`

## 📞 連絡先・サポート

- **プロジェクト管理**: GitHub Issues
- **緊急時対応**: マスターIssue (#6) にコメント

## 📈 進捗更新履歴

- **2025-01-24**: 初回作成、Issue #7-#14 作成完了
- **次回更新予定**: Phase 1 開始時

---

**最終更新**: 2025年1月24日
**次回レビュー予定**: Phase 1完了時

## 💡 クイックスタートガイド

### 新しいAIエージェントセッション開始時
```bash
# 1. リポジトリ確認
cd /path/to/github-coderabbit-comment-gettter

# 2. 環境確認
echo $GITHUB_TOKEN

# 3. 現状分析
uv run grp --help

# 4. テスト実行
uv run pytest src/github_review_prompts/tests/

# 5. Issue確認
# https://github.com/yohi/github-coderabbit-comment-gettter/issues
```

### Phase 1 開始準備
1. **Issue #7** の詳細確認
2. パフォーマンス測定ベースライン確立
3. 並列処理アーキテクチャ設計
4. 実装・テスト・検証のサイクル実行
"""


def main():
    """メイン実行関数"""
    # 環境変数から設定取得
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("❌ エラー: GITHUB_TOKEN環境変数が設定されていません")
        return

    # リポジトリ情報
    repo_owner = "yohi"
    repo_name = "github-coderabbit-comment-gettter"
    master_issue_number = 6  # マスターIssueの番号

    updater = MasterIssueUpdater(repo_owner, repo_name, github_token)

    print("🔄 マスターIssue更新開始...")

    try:
        # マスターIssueを更新
        updated_body = get_updated_master_issue_body()

        print(f"📝 マスターIssue #{master_issue_number} を更新中...")
        result = updater.update_issue(master_issue_number, body=updated_body)

        print(f"✅ マスターIssue更新完了!")
        print(f"🔗 URL: {result['html_url']}")
        print(f"📊 更新内容:")
        print(f"   - 具体的なIssue番号 (#7-#14) を追加")
        print(f"   - Phase別の詳細リンクを追加")
        print(f"   - 進捗管理セクションを詳細化")
        print(f"   - AIエージェント向けクイックスタートガイドを追加")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
