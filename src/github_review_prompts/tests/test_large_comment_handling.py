"""
大量コメント対応機能の包括的テスト
段階的実行戦略とリスク軽減システムの検証
"""

import pytest
from unittest.mock import Mock, patch
from io import StringIO

from github_review_prompts.core.prompt_engine import UnifiedPromptEngine


class TestLargeCommentHandling:
    """大量コメント対応機能のテストクラス"""

    @pytest.fixture
    def prompt_engine(self):
        """UnifiedPromptEngineのインスタンス"""
        return UnifiedPromptEngine()

    @pytest.fixture
    def large_comment_set(self):
        """105件の大量コメントセットを生成"""
        comments = []
        
        # 🔴 セキュリティ関連（3件）
        security_comments = [
            {
                "id": 1001,
                "body": "セキュリティリスク: AWS IAMポリシーでトークン漏洩の可能性があります",
                "path": "modules/security/iam.tf",
                "line": 10,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-22T10:00:00Z"
            },
            {
                "id": 1002,
                "body": "credential exposed in configuration file",
                "path": "modules/auth/config.tf",
                "line": 25,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-22T10:01:00Z"
            },
            {
                "id": 1003,
                "body": "github_pat token is hardcoded - security vulnerability",
                "path": "scripts/deploy.sh",
                "line": 5,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-22T10:02:00Z"
            }
        ]
        
        # 🟢 ドキュメント関連（7件）
        doc_comments = []
        for i in range(7):
            doc_comments.append({
                "id": 2000 + i,
                "body": f"README.md anchor link needs fixing: MD051 violation #{i+1}",
                "path": f"docs/guide_{i+1}.md",
                "line": 10 + i,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": f"2025-08-22T11:{i:02d}:00Z"
            })
        
        # 🟡 機能改善・品質向上（95件）
        functionality_comments = []
        for i in range(95):
            functionality_comments.append({
                "id": 3000 + i,
                "body": f"機能改善提案 #{i+1}: Terraformリソースの最適化が必要です",
                "path": f"modules/infrastructure/resource_{i+1}.tf",
                "line": 20 + (i % 50),
                "user": {"login": "coderabbitai[bot]"},
                "created_at": f"2025-08-22T12:{(i % 60):02d}:00Z"
            })
        
        # 全105件を結合
        all_comments = security_comments + doc_comments + functionality_comments
        return all_comments

    @pytest.fixture
    def pr_info_large(self):
        """大量コメント用のPR情報"""
        return {
            "owner": "test-org",
            "repo": "large-terraform-project",
            "number": 999,
            "title": "Massive Infrastructure Update - 105 Review Comments",
            "url": "https://github.com/test-org/large-terraform-project/pull/999"
        }

    def test_automatic_comment_classification(self, prompt_engine, large_comment_set, pr_info_large):
        """自動コメント分類の精度をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 分類精度の検証
        assert "🔴 緊急（セキュリティ・機能破綻）- 3件" in prompt
        assert "🟡 重要（機能改善・品質向上）- 95件" in prompt
        assert "🟢 低優先（スタイル・軽微改善）- 7件" in prompt
        
        # セキュリティ関連の自動検出
        assert "がセキュリティ関連" in prompt
        assert "トークン漏洩リスク" in prompt

    def test_phased_execution_strategy_generation(self, prompt_engine, large_comment_set, pr_info_large):
        """段階的実行戦略の生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # Phase 1-3の構成
        assert "Phase 1: 🔴緊急対応（最優先30-60分）" in prompt
        assert "Phase 2: 🟡重要対応（2-3時間以内）" in prompt
        assert "Phase 3: 🟢低優先対応（時間があれば）" in prompt
        
        # 件数制限
        assert "件数制限: 最大15件" in prompt
        assert "件数制限: 20-30件" in prompt
        
        # 成功基準
        assert "🔴項目100%完了" in prompt
        assert "🟡項目80%以上完了" in prompt
        assert "🟢項目50%以上完了（努力目標）" in prompt

    def test_risk_mitigation_system(self, prompt_engine, large_comment_set, pr_info_large):
        """リスク軽減システムの生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # バックアップシステム
        assert "バックアップブランチ作成" in prompt
        assert "git checkout -b backup-$(date +%Y%m%d-%H%M)" in prompt
        
        # 段階的セーフポイント
        assert "Phase 1完了時" in prompt
        assert "Phase 2完了時" in prompt
        assert "2時間経過時: 強制休憩" in prompt
        
        # エラー回復手順
        assert "軽微なエラー" in prompt
        assert "重大なエラー" in prompt
        assert "完全リセット" in prompt

    def test_realistic_success_criteria(self, prompt_engine, large_comment_set, pr_info_large):
        """現実的成功基準の生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 80%ルール
        assert "80%ルール" in prompt
        assert "完璧主義より実用性を優先" in prompt
        
        # 段階的成功定義
        assert "Phase 1成功: 🔴緊急項目90%以上完了" in prompt
        assert "Phase 2成功: 🟡重要項目70%以上完了" in prompt
        assert "全体成功: Phase 1成功 + Phase 2一部完了" in prompt

    def test_memory_management_instructions(self, prompt_engine, large_comment_set, pr_info_large):
        """メモリ管理指示の生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 将来対応メモリ管理
        assert "📝 将来対応メモリ管理" in prompt
        assert "CodeRabbitメモリ指示の重要性" in prompt
        assert "将来フェーズでのタスク忘れ防止" in prompt
        
        # メモリ指示テンプレート
        assert "@coderabbitai この指摘は技術的に妥当ですが" in prompt
        assert "将来のタスクとして記憶し" in prompt

    def test_todo_item_structure_105_items(self, prompt_engine, large_comment_set, pr_info_large):
        """105件のTODO項目構造をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # TODO項目の存在確認
        assert "### TODO #1:" in prompt
        assert "### TODO #105:" in prompt
        
        # YAML形式メタデータ
        assert "```yaml" in prompt
        assert "id:" in prompt
        assert "priority:" in prompt
        assert "type: security" in prompt
        assert "security_risk: true" in prompt
        
        # 分類の適切性
        todo_1_section = prompt.split("### TODO #1:")[1].split("### TODO #2:")[0]
        todo_105_section = prompt.split("### TODO #105:")[1] if "### TODO #105:" in prompt else ""
        
        # セキュリティ関連は🔴緊急として分類されているか
        assert "🔴緊急" in todo_1_section or "security_risk: true" in todo_1_section

    def test_performance_with_large_dataset(self, prompt_engine, large_comment_set, pr_info_large):
        """大量データでのパフォーマンステスト"""
        import time
        
        start_time = time.time()
        
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # パフォーマンス要件
        assert execution_time < 5.0  # 5秒以内で処理完了
        assert len(prompt) > 10000   # 十分な詳細出力
        assert len(large_comment_set) == 105  # 正確な件数処理

    def test_security_priority_handling(self, prompt_engine, large_comment_set, pr_info_large):
        """セキュリティ優先処理のテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # セキュリティコメントの優先表示
        security_section = prompt.split("🔴 緊急（セキュリティ・機能破綻）")[1].split("🟡 重要（機能改善・品質向上）")[0]
        assert "トークン漏洩リスク" in security_section
        assert "セキュリティリスク" in security_section
        
        # セキュリティキーワードの検出
        assert "credential" in prompt
        assert "github_pat" in prompt
        assert "security vulnerability" in prompt

    def test_progressive_reporting_template(self, prompt_engine, large_comment_set, pr_info_large):
        """段階的報告テンプレートのテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 段階的結果報告テンプレート
        assert "📊 段階的結果報告テンプレート（現実版）" in prompt
        assert "Phase別実施状況" in prompt
        assert "段階的Git操作状況" in prompt
        assert "効率的返信実行状況" in prompt
        assert "成功判定（現実基準）" in prompt
        assert "未完了項目・次回継続計画" in prompt

    def test_fatigue_management_system(self, prompt_engine, large_comment_set, pr_info_large):
        """疲労度管理システムのテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 疲労度考慮機能
        assert "時間・エネルギー管理" in prompt
        assert "エネルギーレベル: 高/中/低" in prompt
        assert "次回推奨開始時期" in prompt
        assert "強制休憩（15分以上）" in prompt

    def test_comment_optimization_format(self, prompt_engine):
        """コメント最適化フォーマットのテスト"""
        # 複雑なコメント例
        complex_comment = {
            "id": 999,
            "body": """_💡 Verification agent_

**AWS設定の問題**: インフラ構成に重大な問題があります

```diff
resource "aws_instance" "web" {
-  instance_type = "t3.micro"
+  instance_type = "t3.small"
   
-  security_groups = ["default"]
+  security_groups = [aws_security_group.web.id]
}
```

詳細な説明:
- パフォーマンス問題の解決
- セキュリティグループの適切な設定
""",
            "path": "modules/compute/instances.tf",
            "line": 45,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-22T15:30:00Z"
        }
        
        pr_info = {"owner": "test", "repo": "test", "number": 1}
        
        formatted = prompt_engine._format_single_comment(complex_comment, pr_info)
        
        # 最適化されたフォーマット
        assert "**問題**: AWS設定の問題" in formatted
        assert "**修正案**:" in formatted
        assert "```diff" in formatted
        assert "t3.micro" in formatted
        assert "t3.small" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])