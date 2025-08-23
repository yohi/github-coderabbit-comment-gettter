"""CodeRabbitコメントフィルタリングのテスト"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from ..comment_processor import CommentProcessor
from ..models import ProcessingStats


class TestCodeRabbitFilter:
    """CodeRabbitコメントフィルタリングのテストクラス"""

    def setup_method(self):
        """テストセットアップ"""
        self.mock_github_client = Mock()
        self.processor = CommentProcessor(self.mock_github_client)

    def test_filter_non_coderabbit_comments(self):
        """CodeRabbit以外のコメントを除外するテスト"""
        comments = [
            {
                "id": 1001,
                "body": "CodeRabbitのコメント",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            },
            {
                "id": 1002,
                "body": "開発者のコメント",
                "user": {"login": "developer"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 15,
            },
            {
                "id": 1003,
                "body": "レビュアーのコメント",
                "user": {"login": "reviewer"},
                "created_at": "2025-08-23T10:10:00Z",
                "path": "src/main.py",
                "line": 20,
            },
        ]

        resolved_ids = set()
        graphql_bodies = {
            1001: "CodeRabbitのコメント",
            1002: "開発者のコメント",
            1003: "レビュアーのコメント",
        }

        ai_prompts, stats = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=False
        )

        # CodeRabbitのコメントのみが処理される
        assert len(ai_prompts) == 1
        assert stats.non_coderabbit_comments == 2
        assert stats.total_comments == 3

    def test_coderabbit_variations(self):
        """CodeRabbitの様々なユーザー名バリエーションのテスト"""
        comments = [
            {
                "id": 1001,
                "body": "コメント1",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            },
            {
                "id": 1002,
                "body": "コメント2",
                "user": {"login": "CodeRabbitAI"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 15,
            },
            {
                "id": 1003,
                "body": "コメント3",
                "user": {"login": "coderabbitai-bot"},
                "created_at": "2025-08-23T10:10:00Z",
                "path": "src/main.py",
                "line": 20,
            },
            {
                "id": 1004,
                "body": "コメント4",
                "user": {"login": "not-coderabbit"},
                "created_at": "2025-08-23T10:15:00Z",
                "path": "src/main.py",
                "line": 25,
            },
        ]

        resolved_ids = set()
        graphql_bodies = {
            1001: "コメント1",
            1002: "コメント2",
            1003: "コメント3",
            1004: "コメント4",
        }

        ai_prompts, stats = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=False
        )

        # coderabbitaiを含むユーザー名のコメントのみが処理される
        assert len(ai_prompts) == 3
        assert stats.non_coderabbit_comments == 1
        assert stats.total_comments == 4

    def test_empty_user_login(self):
        """ユーザーログインが空の場合のテスト"""
        comments = [
            {
                "id": 1001,
                "body": "ユーザー情報なし",
                "user": {},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            },
            {
                "id": 1002,
                "body": "ユーザーキーなし",
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 15,
            },
        ]

        resolved_ids = set()
        graphql_bodies = {1001: "ユーザー情報なし", 1002: "ユーザーキーなし"}

        ai_prompts, stats = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=False
        )

        # ユーザー情報がないコメントは除外される
        assert len(ai_prompts) == 0
        assert stats.non_coderabbit_comments == 2
        assert stats.total_comments == 2

    def test_case_insensitive_matching(self):
        """大文字小文字を区別しないマッチングのテスト"""
        comments = [
            {
                "id": 1001,
                "body": "コメント1",
                "user": {"login": "CODERABBITAI[BOT]"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            },
            {
                "id": 1002,
                "body": "コメント2",
                "user": {"login": "CodeRabbitAi"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 15,
            },
        ]

        resolved_ids = set()
        graphql_bodies = {1001: "コメント1", 1002: "コメント2"}

        ai_prompts, stats = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=False
        )

        # 大文字小文字を区別せずにマッチする
        assert len(ai_prompts) == 2
        assert stats.non_coderabbit_comments == 0
        assert stats.total_comments == 2

    def test_statistics_accuracy(self):
        """統計情報の正確性テスト"""
        comments = [
            {
                "id": 1001,
                "body": "CodeRabbitコメント",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            },
            {
                "id": 1002,
                "body": "開発者コメント1",
                "user": {"login": "developer1"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 15,
            },
            {
                "id": 1003,
                "body": "開発者コメント2",
                "user": {"login": "developer2"},
                "created_at": "2025-08-23T10:10:00Z",
                "path": "src/main.py",
                "line": 20,
            },
        ]

        resolved_ids = {1001}  # CodeRabbitのコメントが解決済み
        graphql_bodies = {
            1001: "CodeRabbitコメント",
            1002: "開発者コメント1",
            1003: "開発者コメント2",
        }

        ai_prompts, stats = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=False
        )

        # 統計情報の確認
        assert stats.total_comments == 3
        assert stats.resolved_comments == 1  # 解決済みのCodeRabbitコメント
        assert stats.non_coderabbit_comments == 2  # 除外された開発者コメント
        assert stats.unresolved_comments == 0  # 未解決のCodeRabbitコメント
        assert len(ai_prompts) == 0  # 解決済みなので抽出されない

        # include_resolved=Trueの場合
        ai_prompts_with_resolved, stats_with_resolved = self.processor.process_comments(
            comments, resolved_ids, graphql_bodies, include_resolved=True
        )

        assert len(ai_prompts_with_resolved) == 1  # 解決済みも含める
        assert stats_with_resolved.prompts_extracted == 1
