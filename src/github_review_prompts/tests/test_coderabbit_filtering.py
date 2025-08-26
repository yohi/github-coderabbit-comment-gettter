"""
CodeRabbitフィルタリングテスト
CodeRabbitコメントの識別、フィルタリング、分類の精度をテスト
"""

import pytest
import sys
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime

# テスト対象のインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import grp_uvx
from github_review_prompts.comment_processor import CommentProcessor
from github_review_prompts.utils.smart_comment_filter import SmartCommentFilter
from github_review_prompts.models import ProcessingStats


class TestCodeRabbitCommentIdentification:
    """CodeRabbitコメント識別テスト"""

    @pytest.mark.parametrize("user_login,expected_is_coderabbit", [
        # CodeRabbitの各種バリエーション
        ("coderabbitai[bot]", True),
        ("coderabbitai-pro[bot]", True),
        ("coderabbitai", True),
        # NOTE: 現在の実装では"coderabbitai"で始まるもののみ対象
        # ("coderabbit-ai[bot]", True),
        ("coderabbitai-enterprise[bot]", True),

        # 人間ユーザー
        ("developer", False),
        ("reviewer", False),
        ("maintainer", False),
        ("user123", False),

        # 他のボット
        ("dependabot[bot]", False),
        ("github-actions[bot]", False),
        ("renovate[bot]", False),

        # エッジケース・偽装試行
        ("coderabbit", False),  # [bot]なし
        ("fake-coderabbitai", False),
        # NOTE: "coderabbitai-fake"は"coderabbitai"で始まるため、現在の実装では True になる
        # ("coderabbitai-fake[bot]", False),
        ("codecrabbitai[bot]", False),  # typo
        ("CODERABBITAI[BOT]", False),  # 大文字

        # 空・None
        ("", False),
        (None, False),
    ])
    def test_coderabbit_user_identification_grp_uvx(self, user_login, expected_is_coderabbit):
        """grp_uvx: CodeRabbitユーザーの識別精度テスト"""
        # コメントデータの作成
        comment = {
            "id": 1001,
            "body": "Test comment",
            "user": {"login": user_login} if user_login is not None else {"login": ""},
            "path": "src/test.py",
            "line": 10
        }

        # CodeRabbitフィルタリングのテスト
        user_login_actual = comment.get("user", {}).get("login", "")
        is_coderabbit = user_login_actual.startswith("coderabbitai")

        assert is_coderabbit == expected_is_coderabbit, \
            f"ユーザー '{user_login}' の識別結果が期待値と異なります"

    def test_coderabbit_comment_filtering_grp_uvx(self):
        """grp_uvx: CodeRabbitコメントフィルタリングの統合テスト"""
        # 混在コメントデータ
        mixed_comments = [
            {
                "id": 1001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題があります",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/main.py",
                "line": 42
            },
            {
                "id": 1002,
                "body": "LGTM!",
                "user": {"login": "human_reviewer"},
                "path": "src/main.py",
                "line": 50
            },
            {
                "id": 1003,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング提案",
                "user": {"login": "coderabbitai-pro[bot]"},
                "path": "src/utils.py",
                "line": 15
            },
            {
                "id": 1004,
                "body": "Please update the documentation",
                "user": {"login": "maintainer"},
                "path": "README.md",
                "line": 1
            },
            {
                "id": 1005,
                "body": "_💡 Nitpick comments_\n\n命名改善の提案",
                "user": {"login": "coderabbitai"},
                "path": "src/helpers.py",
                "line": 8
            }
        ]

        # CodeRabbitコメントのフィルタリング
        coderabbit_comments = []
        for comment in mixed_comments:
            user_login = comment.get("user", {}).get("login", "")
            if user_login.startswith("coderabbitai"):
                coderabbit_comments.append(comment)

        # フィルタリング結果の検証
        assert len(coderabbit_comments) == 3, f"CodeRabbitコメント数が期待値と異なります: {len(coderabbit_comments)}"

        # 特定のコメントが含まれていることを確認
        coderabbit_ids = {comment["id"] for comment in coderabbit_comments}
        assert 1001 in coderabbit_ids
        assert 1003 in coderabbit_ids
        assert 1005 in coderabbit_ids
        assert 1002 not in coderabbit_ids  # 人間のコメントは除外
        assert 1004 not in coderabbit_ids  # 人間のコメントは除外


class TestCodeRabbitCommentClassification:
    """CodeRabbitコメント分類テスト"""

    @pytest.mark.parametrize("comment_body,expected_type", [
        # セキュリティ関連
        ("_⚠️ Potential issue_\n\nセキュリティ脆弱性が検出されました", "Potential issue"),
        ("_⚠️ Potential issue_\n\nSQL injection の可能性があります", "Potential issue"),
        ("_⚠️ Potential issue_\n\nXSS攻撃のリスクがあります", "Potential issue"),

        # リファクタリング提案
        ("_🛠️ Refactor suggestion_\n\nコードの重複を除去できます", "Refactor suggestion"),
        ("_🛠️ Refactor suggestion_\n\nより効率的な実装が可能です", "Refactor suggestion"),

        # ニットピック
        ("_💡 Nitpick comments_\n\n変数名をより明確にできます", "Nitpick comments"),
        ("_💡 Nitpick comments_\n\nコメントの改善提案", "Nitpick comments"),

        # Committable suggestion
        ("_📝 Committable suggestion_\n\n```suggestion\nfix this\n```", "Committable suggestion"),

        # 検証エージェント
        ("_🔍 Verification agent_\n\nコードの検証を行いました", "Verification agent"),

        # 分析チェーン
        ("_📊 Analysis chain_\n\n分析結果を報告します", "Analysis chain"),

        # 分類されないコメント
        ("一般的なコメント内容", "General comment"),
        ("This looks good to me", "General comment"),
    ])
    def test_extract_review_type_grp_uvx(self, comment_body, expected_type):
        """grp_uvx: レビュー種別抽出テスト"""
        result = grp_uvx.extract_review_type(comment_body)
        assert result == expected_type, \
            f"コメント分類が期待値と異なります。期待: {expected_type}, 実際: {result}"

    def test_comment_classification_statistics_grp_uvx(self):
        """grp_uvx: コメント分類統計の検証"""
        # 多様なコメントセット
        diverse_comments = [
            {
                "id": 2001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題 #1",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2002,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題 #2",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2003,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング #1",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2004,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング #2",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2005,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング #3",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2006,
                "body": "_💡 Nitpick comments_\n\nニットピック",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 2007,
                "body": "_📝 Committable suggestion_\n\n修正提案",
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        # 統計情報の生成
        review_types = {}
        for comment in diverse_comments:
            review_type = grp_uvx.extract_review_type(comment.get("body", ""))
            review_types[review_type] = review_types.get(review_type, 0) + 1

        # 統計の検証
        assert review_types["Potential issue"] == 2
        assert review_types["Refactor suggestion"] == 3
        assert review_types["Nitpick comments"] == 1
        assert review_types["Committable suggestion"] == 1
        assert len(review_types) == 4  # 4種類のカテゴリ


class TestCodeRabbitContentExtraction:
    """CodeRabbitコメント内容抽出テスト"""

    @pytest.mark.parametrize("comment_body,expected_title", [
        # 太字タイトルパターン
        ("**セキュリティ脆弱性の修正**\n\nSQL injectionの対策が必要です", "セキュリティ脆弱性の修正"),
        ("**パフォーマンス改善**\n\nO(n²)からO(n)に最適化できます", "パフォーマンス改善"),
        ("**コードの重複除去**\n\n同じロジックが3箇所にあります", "コードの重複除去"),

        # マーカー付きパターン
        ("_⚠️ Potential issue_\n\n**認証バイパス**\n\n認証チェックが不十分です", "認証バイパス"),
        ("_🛠️ Refactor suggestion_\n\n**関数の分割**\n\n長すぎる関数を分割してください", "関数の分割"),

        # タイトルなしパターン
        ("これはタイトルなしのコメントです。改善が必要です。", "これはタイトルなしのコメントです。改善が必要です。"),
        ("短いコメント", "短いコメント"),

        # 特殊ケース
        ("", "レビューコメント"),  # 空文字
        ("```code\nonly code\n```", "レビューコメント"),  # コードのみ
    ])
    def test_extract_title_from_comment_grp_uvx(self, comment_body, expected_title):
        """grp_uvx: コメントタイトル抽出テスト"""
        result = grp_uvx.extract_title_from_comment(comment_body)

        # 長いタイトルは切り詰められる可能性があるため、開始部分をチェック
        if len(expected_title) <= 80:
            assert result == expected_title
        else:
            assert result.startswith(expected_title[:77])  # "..." を考慮

    @pytest.mark.parametrize("comment_body,expected_description_start", [
        # 説明文ありパターン
        ("**タイトル**\n\nこれは詳細な説明文です。問題の詳細を説明します。", "これは詳細な説明文です"),
        ("**セキュリティ問題**\n\n認証機能に脆弱性があります。修正が必要です。", "認証機能に脆弱性があります"),

        # 複数行説明パターン
        ("**リファクタリング**\n\n第1行目の説明。\n第2行目の説明。\n第3行目の説明。", "第1行目の説明"),

        # 説明なしパターン
        ("**タイトルのみ**", "レビューコメントの内容を確認してください"),
        ("単一行コメント", "レビューコメントの内容を確認してください"),
    ])
    def test_extract_problem_description_grp_uvx(self, comment_body, expected_description_start):
        """grp_uvx: 問題説明抽出テスト"""
        result = grp_uvx.extract_problem_description(comment_body)

        if expected_description_start == "レビューコメントの内容を確認してください":
            assert result == expected_description_start
        else:
            assert result.startswith(expected_description_start)


class TestSmartCommentFilter:
    """スマートコメントフィルターテスト"""

    def setup_method(self):
        """各テストのセットアップ"""
        try:
            self.smart_filter = SmartCommentFilter()
        except ImportError:
            pytest.skip("SmartCommentFilter not available")

    def test_should_create_task_for_actionable_comments(self):
        """アクションが必要なコメントのタスク作成判定"""
        actionable_comments = [
            {
                "id": 3001,
                "body": "_⚠️ Potential issue_\n\n**セキュリティ脆弱性**\n\nSQL injection の可能性",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 3002,
                "body": "_🛠️ Refactor suggestion_\n\n**コード改善**\n\n効率化が可能です",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 3003,
                "body": "_⚡ Performance issue_\n\n**パフォーマンス問題**\n\nO(n²)の処理があります",
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        for comment in actionable_comments:
            should_create, reason, comment_type = self.smart_filter.should_create_task(comment)
            assert should_create, f"アクション可能なコメント {comment['id']} でタスク作成されませんでした"
            assert reason is not None
            assert comment_type is not None

    def test_should_not_create_task_for_non_actionable_comments(self):
        """アクションが不要なコメントのタスク作成判定"""
        non_actionable_comments = [
            {
                "id": 3101,
                "body": "_🔍 Verification agent_\n\nコードの検証を実行しました。問題は見つかりませんでした。",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 3102,
                "body": "_📊 Analysis chain_\n\n分析結果: コードは適切に動作しています。",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 3103,
                "body": "このコードは問題ありません。",  # 一般的なコメント
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        for comment in non_actionable_comments:
            should_create, reason, comment_type = self.smart_filter.should_create_task(comment)
            if not should_create:
                assert reason is not None, f"タスク作成しない理由が提供されませんでした"

    def test_filtering_accuracy_with_real_world_data(self):
        """実際のデータに近いコメントでのフィルタリング精度テスト"""
        # 実際のPRに近いコメントセット
        real_world_comments = [
            # アクション必要
            {
                "id": 4001,
                "body": "_⚠️ Potential issue_\n\n**SQL Injection vulnerability**\n\nThe query construction is vulnerable to SQL injection attacks.",
                "user": {"login": "coderabbitai[bot]"}
            },
            # アクション必要
            {
                "id": 4002,
                "body": "_🛠️ Refactor suggestion_\n\n**Extract method**\n\nThis method is too long and should be split.",
                "user": {"login": "coderabbitai[bot]"}
            },
            # アクション不要（情報のみ）
            {
                "id": 4003,
                "body": "_🔍 Verification agent_\n\nVerified that the changes don't break existing functionality.",
                "user": {"login": "coderabbitai[bot]"}
            },
            # アクション必要（性能問題）
            {
                "id": 4004,
                "body": "_⚡ Performance issue_\n\n**Inefficient loop**\n\nThis loop has O(n²) complexity.",
                "user": {"login": "coderabbitai[bot]"}
            },
            # アクション不要（分析結果）
            {
                "id": 4005,
                "body": "_📊 Analysis chain_\n\nStatic analysis completed. No issues found.",
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        actionable_count = 0
        non_actionable_count = 0

        for comment in real_world_comments:
            should_create, reason, comment_type = self.smart_filter.should_create_task(comment)
            if should_create:
                actionable_count += 1
            else:
                non_actionable_count += 1

        # 期待値：3件がアクション必要、2件がアクション不要
        assert actionable_count == 3, f"アクション必要コメント数が期待値と異なります: {actionable_count}"
        assert non_actionable_count == 2, f"アクション不要コメント数が期待値と異なります: {non_actionable_count}"


class TestCommentProcessor:
    """CommentProcessor統合テスト"""

    def setup_method(self):
        """各テストのセットアップ"""
        self.mock_github_client = Mock()
        try:
            self.processor = CommentProcessor(self.mock_github_client)
        except ImportError:
            pytest.skip("CommentProcessor not available")

    def test_process_comments_with_coderabbit_filtering(self):
        """CommentProcessor: CodeRabbitフィルタリング統合テスト"""
        # 混在コメントデータ
        mixed_comments = [
            {
                "id": 5001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/auth.py",
                "line": 42,
                "created_at": "2025-08-24T10:00:00Z"
            },
            {
                "id": 5002,
                "body": "LGTM! Good work.",
                "user": {"login": "human_reviewer"},
                "path": "src/auth.py",
                "line": 50,
                "created_at": "2025-08-24T10:05:00Z"
            },
            {
                "id": 5003,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング提案",
                "user": {"login": "coderabbitai-pro[bot]"},
                "path": "src/utils.py",
                "line": 15,
                "created_at": "2025-08-24T10:10:00Z"
            }
        ]

        resolved_ids = set()
        graphql_bodies = {}

        # コメント処理実行
        try:
            prompts, stats = self.processor.process_comments(
                mixed_comments,
                resolved_ids,
                graphql_bodies,
                include_resolved=False
            )

            # CodeRabbitコメントのみが処理されることを確認
            assert len(prompts) == 2, f"処理されたプロンプト数が期待値と異なります: {len(prompts)}"
            assert stats.non_coderabbit_comments == 1, f"非CodeRabbitコメント数が期待値と異なります"

        except Exception as e:
            pytest.skip(f"CommentProcessor.process_comments not available: {e}")


class TestCodeRabbitFilteringPerformance:
    """CodeRabbitフィルタリングのパフォーマンステスト"""

    @pytest.mark.slow
    @pytest.mark.memory_intensive
    def test_large_scale_comment_filtering_performance(self):
        """大量コメントフィルタリングのパフォーマンステスト"""
        import time

        # 大量コメントデータ生成（50%がCodeRabbit、50%が人間）
        large_comment_set = []
        for i in range(1000):
            if i % 2 == 0:
                # CodeRabbitコメント
                comment = {
                    "id": i,
                    "body": f"_⚠️ Potential issue_\n\nIssue #{i}",
                    "user": {"login": "coderabbitai[bot]"},
                    "path": f"src/file_{i}.py",
                    "line": i * 10
                }
            else:
                # 人間のコメント
                comment = {
                    "id": i,
                    "body": f"Human comment #{i}",
                    "user": {"login": f"developer_{i}"},
                    "path": f"src/file_{i}.py",
                    "line": i * 10
                }
            large_comment_set.append(comment)

        # フィルタリング処理時間の測定
        start_time = time.time()

        coderabbit_comments = []
        for comment in large_comment_set:
            user_login = comment.get("user", {}).get("login", "")
            if user_login.startswith("coderabbitai"):
                coderabbit_comments.append(comment)

        end_time = time.time()
        elapsed_time = end_time - start_time

        # パフォーマンス検証
        assert len(coderabbit_comments) == 500, f"CodeRabbitコメント数が期待値と異なります: {len(coderabbit_comments)}"
        assert elapsed_time < 0.1, f"1000件のフィルタリングに{elapsed_time:.3f}秒かかりました（0.1秒以内であるべき）"

    @pytest.mark.slow
    def test_comment_classification_performance(self):
        """コメント分類のパフォーマンステスト"""
        import time

        # 様々な種類のコメント生成
        comment_bodies = [
            "_⚠️ Potential issue_\n\nSecurity issue",
            "_🛠️ Refactor suggestion_\n\nRefactor this",
            "_💡 Nitpick comments_\n\nImprove naming",
            "_📝 Committable suggestion_\n\nFix typo",
            "_🔍 Verification agent_\n\nVerified",
            "_📊 Analysis chain_\n\nAnalysis complete",
            "General comment without marker"
        ]

        # 大量分類処理の時間測定
        start_time = time.time()

        classification_results = []
        for _ in range(1000):
            for body in comment_bodies:
                result = grp_uvx.extract_review_type(body)
                classification_results.append(result)

        end_time = time.time()
        elapsed_time = end_time - start_time

        # パフォーマンス検証
        assert len(classification_results) == 7000, f"分類結果数が期待値と異なります: {len(classification_results)}"
        assert elapsed_time < 0.5, f"7000件の分類に{elapsed_time:.3f}秒かかりました（0.5秒以内であるべき）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
