"""コメントスレッド処理のテスト"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from ..comment_thread_processor import CommentThreadProcessor


class TestCommentThreadProcessor:
    """CommentThreadProcessorのテストクラス"""

    def setup_method(self):
        """テストセットアップ"""
        self.mock_github_client = Mock()
        self.processor = CommentThreadProcessor(self.mock_github_client)

    def test_process_single_comment_thread(self):
        """単一コメントのスレッド処理テスト"""
        comments = [
            {
                "id": 1001,
                "body": "このコードにセキュリティ問題があります",
                "user": {"login": "reviewer"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
            }
        ]

        result = self.processor.process_comment_threads(comments)

        assert len(result) == 1
        assert result[0]["id"] == 1001
        assert result[0]["_thread_info"]["total_comments"] == 1
        assert result[0]["_thread_info"]["has_coderabbit_response"] is False

    def test_process_thread_with_coderabbit_response(self):
        """CodeRabbitの返信があるスレッドの処理テスト"""
        comments = [
            {
                "id": 1001,
                "body": "このコードにセキュリティ問題があります",
                "user": {"login": "reviewer"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
                "in_reply_to_id": None,
            },
            {
                "id": 1002,
                "body": "ご指摘ありがとうございます。修正方法を提案します。",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 10,
                "in_reply_to_id": 1001,
            },
        ]

        result = self.processor.process_comment_threads(comments)

        assert len(result) == 1
        assert result[0]["id"] == 1001
        assert result[0]["_thread_info"]["total_comments"] == 2
        assert result[0]["_thread_info"]["has_coderabbit_response"] is True
        assert "CodeRabbit最新コメント" in result[0]["body"]

    def test_process_thread_with_resolution_marker(self):
        """解決マーカーがあるスレッドの処理テスト"""
        comments = [
            {
                "id": 1001,
                "body": "このコードにセキュリティ問題があります",
                "user": {"login": "reviewer"},
                "created_at": "2025-08-23T10:00:00Z",
                "path": "src/main.py",
                "line": 10,
                "in_reply_to_id": None,
            },
            {
                "id": 1002,
                "body": "修正完了しました。[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]✅ エンジニアによる技術的検証完了[/CR_RESOLUTION_CONFIRMED]",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:05:00Z",
                "path": "src/main.py",
                "line": 10,
                "in_reply_to_id": 1001,
            },
        ]

        result = self.processor.process_comment_threads(comments)

        assert len(result) == 1
        assert result[0]["_thread_info"]["is_resolved"] is True

    def test_group_comments_by_thread(self):
        """コメントのスレッド別グループ化テスト"""
        comments = [
            {"id": 1001, "in_reply_to_id": None},
            {"id": 1002, "in_reply_to_id": 1001},
            {"id": 1003, "in_reply_to_id": 1001},
            {"id": 2001, "in_reply_to_id": None},
        ]

        threads = self.processor._group_comments_by_thread(comments)

        assert len(threads) == 2
        assert len(threads[1001]) == 3  # 元コメント + 2つの返信
        assert len(threads[2001]) == 1  # 元コメントのみ

    def test_get_last_coderabbit_comment(self):
        """CodeRabbitの最後のコメント取得テスト"""
        thread_comments = [
            {
                "id": 1001,
                "user": {"login": "reviewer"},
                "created_at": "2025-08-23T10:00:00Z",
            },
            {
                "id": 1002,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:05:00Z",
            },
            {
                "id": 1003,
                "user": {"login": "developer"},
                "created_at": "2025-08-23T10:10:00Z",
            },
            {
                "id": 1004,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:15:00Z",
            },
        ]

        last_coderabbit = self.processor._get_last_coderabbit_comment(thread_comments)

        assert last_coderabbit is not None
        assert last_coderabbit["id"] == 1004

    def test_is_coderabbit_comment(self):
        """CodeRabbitコメント判定テスト"""
        coderabbit_comment = {"user": {"login": "coderabbitai[bot]"}}
        user_comment = {"user": {"login": "developer"}}

        assert self.processor._is_coderabbit_comment(coderabbit_comment) is True
        assert self.processor._is_coderabbit_comment(user_comment) is False

    def test_extract_comment_summary(self):
        """コメント要約抽出テスト"""
        body = "## セキュリティ問題\n\nこのコードにはXSS脆弱性があります。"
        summary = self.processor._extract_comment_summary(body)

        assert "セキュリティ問題" in summary
        assert len(summary) <= 80

    def test_determine_resolution_status(self):
        """解決状態判定テスト"""
        # 解決済みマーカーありのスレッド
        resolved_thread = [
            {"user": {"login": "reviewer"}, "body": "問題があります"},
            {
                "user": {"login": "coderabbitai[bot]"},
                "body": "修正完了。[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]✅ エンジニアによる技術的検証完了[/CR_RESOLUTION_CONFIRMED]",
            },
        ]

        # 未解決のスレッド
        unresolved_thread = [
            {"user": {"login": "reviewer"}, "body": "問題があります"},
            {"user": {"login": "coderabbitai[bot]"}, "body": "確認中です"},
        ]

        assert self.processor.determine_resolution_status(resolved_thread) is True
        assert self.processor.determine_resolution_status(unresolved_thread) is False

    def test_multiple_threads_processing(self):
        """複数スレッドの処理テスト"""
        comments = [
            # スレッド1
            {
                "id": 1001,
                "body": "問題1",
                "user": {"login": "reviewer1"},
                "created_at": "2025-08-23T10:00:00Z",
                "in_reply_to_id": None,
            },
            {
                "id": 1002,
                "body": "CodeRabbit返信1",
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-23T10:05:00Z",
                "in_reply_to_id": 1001,
            },
            # スレッド2
            {
                "id": 2001,
                "body": "問題2",
                "user": {"login": "reviewer2"},
                "created_at": "2025-08-23T11:00:00Z",
                "in_reply_to_id": None,
            },
        ]

        result = self.processor.process_comment_threads(comments)

        assert len(result) == 2

        # スレッド1の検証
        thread1 = next(c for c in result if c["id"] == 1001)
        assert thread1["_thread_info"]["total_comments"] == 2
        assert thread1["_thread_info"]["has_coderabbit_response"] is True

        # スレッド2の検証
        thread2 = next(c for c in result if c["id"] == 2001)
        assert thread2["_thread_info"]["total_comments"] == 1
        assert thread2["_thread_info"]["has_coderabbit_response"] is False
