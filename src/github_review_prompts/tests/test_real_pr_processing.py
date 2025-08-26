"""
リアルPR処理結果に基づくテスト
PR#12の実際の処理結果を基準とした現実的なテストケース
"""

import pytest
from unittest.mock import Mock, patch
from io import StringIO

from github_review_prompts.core.prompt_engine import UnifiedPromptEngine
from github_review_prompts.utils.smart_comment_filter import SmartCommentFilter


class TestRealPRProcessing:
    """実際のPR処理結果に基づくテストクラス"""

    @pytest.fixture
    def prompt_engine(self):
        """UnifiedPromptEngineのインスタンス"""
        return UnifiedPromptEngine()

    @pytest.fixture
    def pr12_similar_comments(self):
        """PR#12と類似の構造を持つコメントセット（17コメント→28-29TODO生成を期待）"""
        comments = []
        
        # インラインコメント7件（技術的リファクタリング提案）
        inline_comments = []
        for i in range(7):
            inline_comments.append({
                "id": f"inline_{i+1}",
                "body": f"_🛠️ Refactor suggestion_\n\nTypeScript設計改善提案 #{i+1}: より型安全で保守しやすい実装への変更が推奨されます。",
                "path": f"src/application/handlers/handler_{i+1}.ts",
                "line": 100 + i * 30,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": f"2025-08-24T10:{i:02d}:00Z"
            })
        
        # Outside diff コメント10件（個別の技術的指摘含む）
        outside_diff_comments = []
        
        # 単一指摘のコメント7件
        for i in range(7):
            outside_diff_comments.append({
                "id": f"outside_single_{i+1}",
                "body": f"_⚠️ Potential issue_\n\n**個別技術課題 #{i+1}**: アーキテクチャレベルでの改善が必要です。",
                "path": None,
                "line": None,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": f"2025-08-24T11:{i:02d}:00Z"
            })
        
        # 複数指摘を含む複合コメント3件
        complex_outside_comments = [
            {
                "id": "outside_complex_1",
                "body": """_🛠️ Refactor suggestion_

**Module インポートの階層化とレイヤー分離の適用**: 
- DDD原則に基づくレイヤー分離
- 循環依存の除去
- インターフェース設計の改善

**統一されたエラー型階層の構築**:
- カスタムエラークラスの導入
- エラーハンドリング戦略の統一
- ログ出力の標準化""",
                "path": None,
                "line": None,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T12:00:00Z"
            },
            {
                "id": "outside_complex_2", 
                "body": """_⚡ Performance issue_

**実行時間・メモリ最適化**: 
- 非同期処理の効率化
- メモリリークの防止
- パフォーマンス監視の導入

**並行性制御の包括的見直し**:
- Promise処理の最適化
- タイムアウト管理の改善""",
                "path": None,
                "line": None,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T12:15:00Z"
            },
            {
                "id": "outside_complex_3",
                "body": """_🔒 Security issue_

**セキュリティ強化の統合アプローチ**:
- プロトタイプ汚染対策
- SQLインジェクション防止
- 入力値サニタイゼーション

**トランザクション整合性の改善**:
- データベース操作の原子性確保
- 部分更新の安全性向上""",
                "path": None,
                "line": None,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T12:30:00Z"
            }
        ]
        
        # 全17件を結合
        all_comments = inline_comments + outside_diff_comments + complex_outside_comments
        return all_comments

    @pytest.fixture
    def pr12_info(self):
        """PR#12相当のプルリクエスト情報"""
        return {
            "owner": "yohi",
            "repo": "CursorCLI-Extensions", 
            "number": 12,
            "title": "feat: エンタープライズグレードのコード品質設定",
            "url": "https://github.com/yohi/CursorCLI-Extensions/pull/12"
        }

    def test_pr12_comment_structure_processing(self, prompt_engine, pr12_similar_comments, pr12_info):
        """PR#12相当のコメント構造処理テスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=pr12_similar_comments,
            pr_info=pr12_info
        )
        
        # 基本的な処理結果の検証
        assert len(pr12_similar_comments) == 17  # 入力コメント数
        
        # TODO生成数の検証（28-30件の範囲を期待）
        todo_count = prompt.count("### TODO #")
        assert 25 <= todo_count <= 35, f"Expected 25-35 TODOs, got {todo_count}"
        
        # インラインコメント処理の検証
        assert "行: 100" in prompt  # インラインコメントの行番号
        assert "_🛠️ Refactor suggestion_" in prompt
        
        # Outside diffコメント処理の検証
        assert "Module インポートの階層化" in prompt
        assert "統一されたエラー型階層" in prompt
        assert "セキュリティ強化の統合アプローチ" in prompt

    def test_smart_comment_filtering_accuracy(self, pr12_similar_comments):
        """スマートコメントフィルタリングの精度テスト"""
        filter = SmartCommentFilter()
        
        actionable_count = 0
        technical_indicator_count = 0
        
        for comment in pr12_similar_comments:
            should_create, reason, comment_type = filter.should_create_task(comment)
            if should_create:
                actionable_count += 1
            
            # 技術的指摘マーカーの検出
            if any(indicator in comment["body"] for indicator in [
                "_⚠️ Potential issue_", "_🛠️ Refactor suggestion_", 
                "_⚡ Performance issue_", "_🔒 Security issue_"
            ]):
                technical_indicator_count += 1
        
        # フィルタリング精度の検証
        assert actionable_count >= 15, f"Expected at least 15 actionable comments, got {actionable_count}"
        assert technical_indicator_count == 17, f"Expected 17 technical indicators, got {technical_indicator_count}"
        
        # 技術的指摘の適切な処理（ほぼ全てがactionableになることを期待）
        assert actionable_count / len(pr12_similar_comments) >= 0.85, "Too many comments filtered out"

    def test_outside_diff_parsing_accuracy(self, prompt_engine, pr12_similar_comments, pr12_info):
        """Outside diffコメント解析精度のテスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=pr12_similar_comments,
            pr_info=pr12_info
        )
        
        # Outside diffコメントの個別指摘分離
        outside_diff_keywords = [
            "Module インポートの階層化",
            "統一されたエラー型階層", 
            "実行時間・メモリ最適化",
            "並行性制御",
            "セキュリティ強化",
            "トランザクション整合性"
        ]
        
        detected_keywords = sum(1 for keyword in outside_diff_keywords if keyword in prompt)
        assert detected_keywords >= 5, f"Expected at least 5 outside diff topics, detected {detected_keywords}"

    def test_technical_priority_classification(self, prompt_engine, pr12_similar_comments, pr12_info):
        """技術的優先度分類の正確性テスト"""
        prompt = prompt_engine.generate_main_prompt(
            comments=pr12_similar_comments,
            pr_info=pr12_info
        )
        
        # セキュリティ関連の優先分類
        security_todos = prompt.count("🔒 Security issue")
        performance_todos = prompt.count("⚡ Performance issue") 
        refactor_todos = prompt.count("🛠️ Refactor suggestion")
        
        # 技術的カテゴリの適切な分散
        assert security_todos >= 1, "Security issues should be detected"
        assert performance_todos >= 1, "Performance issues should be detected"
        assert refactor_todos >= 5, "Refactor suggestions should be majority"

    def test_yaml_metadata_structure(self, prompt_engine, pr12_similar_comments, pr12_info):
        """YAMLメタデータ構造の検証"""
        prompt = prompt_engine.generate_main_prompt(
            comments=pr12_similar_comments,
            pr_info=pr12_info
        )
        
        # YAML構造の存在確認
        assert "```yaml" in prompt
        assert "id:" in prompt
        assert "priority:" in prompt
        assert "type:" in prompt
        assert "author: coderabbitai[bot]" in prompt
        
        # 優先度マーカーの存在
        assert "🔴" in prompt or "🟡" in prompt or "🟢" in prompt

    @pytest.mark.slow
    def test_performance_with_realistic_dataset(self, prompt_engine, pr12_similar_comments, pr12_info):
        """リアルデータセットでのパフォーマンステスト"""
        import time
        
        start_time = time.time()
        
        prompt = prompt_engine.generate_main_prompt(
            comments=pr12_similar_comments,
            pr_info=pr12_info
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # パフォーマンス要件（現実的な範囲）
        assert execution_time < 3.0, f"Processing took too long: {execution_time:.2f}s"
        assert len(prompt) > 5000, "Output should be comprehensive"
        assert len(pr12_similar_comments) == 17, "Input size verification"

    def test_todo_generation_consistency(self, prompt_engine, pr12_similar_comments, pr12_info):
        """TODO生成の一貫性テスト"""
        # 複数回実行して一貫性を確認
        prompts = []
        todo_counts = []
        
        for _ in range(3):
            prompt = prompt_engine.generate_main_prompt(
                comments=pr12_similar_comments,
                pr_info=pr12_info
            )
            prompts.append(prompt)
            todo_counts.append(prompt.count("### TODO #"))
        
        # 生成結果の一貫性確認
        assert all(count == todo_counts[0] for count in todo_counts), f"Inconsistent TODO counts: {todo_counts}"
        assert all("技術的指摘マーカー" in prompt for prompt in prompts), "Missing technical markers"

    def test_edge_case_comment_handling(self, prompt_engine, pr12_info):
        """エッジケースコメント処理のテスト"""
        edge_case_comments = [
            {
                "id": "edge_empty",
                "body": "",
                "path": "test.ts",
                "line": 1,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T10:00:00Z"
            },
            {
                "id": "edge_large",
                "body": "_🛠️ Refactor suggestion_\n\n" + "詳細説明 " * 1000,  # 非常に長いコメント
                "path": None,
                "line": None,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T10:01:00Z"
            },
            {
                "id": "edge_special_chars",
                "body": "_⚠️ Potential issue_\n\n特殊文字テスト: <>&\"'`|\\n\\t[]{}",
                "path": "special.ts",
                "line": 50,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-24T10:02:00Z"
            }
        ]
        
        # エラーなしで処理完了することを確認
        prompt = prompt_engine.generate_main_prompt(
            comments=edge_case_comments,
            pr_info=pr12_info
        )
        
        assert len(prompt) > 0, "Should generate output even with edge cases"
        assert "### TODO #" in prompt, "Should generate at least some TODOs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])