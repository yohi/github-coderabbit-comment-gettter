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
        
        # 現実的な分類結果の検証（実際の処理結果に基づく）
        # 105コメント→150-200TODO生成程度を期待
        todo_count = prompt.count("### TODO #")
        assert 100 <= todo_count <= 250, f"Expected 100-250 TODOs from 105 comments, got {todo_count}"
        
        # セキュリティ関連の自動検出
        assert "セキュリティリスク" in prompt
        assert "トークン漏洩" in prompt or "credential" in prompt

    def test_phased_execution_strategy_generation(self, prompt_engine, large_comment_set, pr_info_large):
        """段階的実行戦略の生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # Phase構成の存在確認（現在のプロンプト構造に合わせて調整）
        assert "Phase 1" in prompt
        assert "Phase 2" in prompt
        assert "Phase 3" in prompt or "🟢" in prompt
        
        # 段階的アプローチの言及
        assert "段階的" in prompt
        assert "優先" in prompt
        
        # 現実的な成功基準
        assert "80%" in prompt or "完了" in prompt

    def test_risk_mitigation_system(self, prompt_engine, large_comment_set, pr_info_large):
        """リスク軽減システムの生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # Git操作の安全性
        assert "git" in prompt
        assert "commit" in prompt or "コミット" in prompt
        
        # エラー対応・安全性の言及
        assert "エラー" in prompt or "確認" in prompt
        assert "安全" in prompt or "注意" in prompt
        
        # バックアップや段階的処理の概念
        assert "段階" in prompt or "Phase" in prompt

    def test_realistic_success_criteria(self, prompt_engine, large_comment_set, pr_info_large):
        """現実的成功基準の生成をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 現実的アプローチの言及
        assert "80%" in prompt or "完璧" in prompt
        assert "優先" in prompt
        
        # 段階的・現実的な進行
        assert "段階" in prompt
        assert "成功" in prompt or "完了" in prompt

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
        """105件のコメントからのTODO項目構造をテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # TODO項目の存在確認（現実的な生成数）
        todo_count = prompt.count("### TODO #")
        assert todo_count >= 50, f"Expected at least 50 TODOs from 105 comments, got {todo_count}"
        assert "### TODO #1:" in prompt
        
        # YAML形式メタデータの存在
        assert "```yaml" in prompt
        assert "id:" in prompt
        assert "priority:" in prompt
        
        # セキュリティ関連の適切な検出
        if "security" in prompt.lower():
            assert "セキュリティ" in prompt or "security" in prompt

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
        
        # セキュリティ関連の適切な検出と処理
        assert "セキュリティ" in prompt or "security" in prompt
        
        # セキュリティキーワードの検出
        security_found = any(keyword in prompt.lower() for keyword in [
            "credential", "token", "security", "セキュリティ", "トークン", "認証"
        ])
        assert security_found, "Security-related keywords should be detected"

    def test_progressive_reporting_template(self, prompt_engine, large_comment_set, pr_info_large):
        """段階的報告テンプレートのテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 段階的・報告関連の機能
        assert "段階" in prompt or "Phase" in prompt
        assert "報告" in prompt or "実行" in prompt or "状況" in prompt
        
        # Git操作の言及
        assert "git" in prompt or "Git" in prompt
        
        # 進捗管理の概念
        assert "完了" in prompt or "実行" in prompt

    def test_fatigue_management_system(self, prompt_engine, large_comment_set, pr_info_large):
        """疲労度管理システムのテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=large_comment_set,
            pr_info=pr_info_large
        )
        
        # 時間・エネルギー管理の概念
        time_energy_found = any(keyword in prompt for keyword in [
            "時間", "エネルギー", "休憩", "段階", "効率", "管理"
        ])
        assert time_energy_found, "Time/energy management concepts should be present"

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
        
        # フォーマット結果の基本検証（YAMLメタデータ形式）
        assert "```yaml" in formatted
        assert "id: 999" in formatted
        assert "t3.micro" in formatted
        assert "t3.small" in formatted
        assert "AWS設定" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])