"""コメントスレッド処理モジュール

PRの未解決インラインコメントで複数のやり取りがある場合の処理を担当
- 最初のコメントとCodeRabbitの最後のコメントをタスクリストに追加
- 解決マーカーの判定はCodeRabbitの最後のコメントを基準とする
"""

import logging
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime

from .models import ReviewComment
from .github_client import GitHubClient


class CommentThreadProcessor:
    """コメントスレッド処理クラス"""

    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        self.logger = logging.getLogger(__name__)

    def process_comment_threads(
        self, comments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """コメントスレッドを処理し、適切なタスクリストを生成

        Args:
            comments: PRのコメント一覧

        Returns:
            処理されたコメント一覧（最初のコメントにCodeRabbitの最後のコメント情報を統合）
        """
        # スレッドごとにコメントをグループ化
        threads = self._group_comments_by_thread(comments)

        processed_comments = []

        for thread_id, thread_comments in threads.items():
            # スレッド内のコメントを時系列順にソート
            sorted_comments = sorted(
                thread_comments, key=lambda c: c.get("created_at", "")
            )

            # 最初のコメントを取得
            first_comment = sorted_comments[0] if sorted_comments else None

            if first_comment:
                # 最初のコメントがCodeRabbitのものかチェック
                if not self._is_coderabbit_comment(first_comment):
                    self.logger.debug(
                        f"CodeRabbit以外のコメントスレッド {thread_id} をスキップ"
                    )
                    continue

                # CodeRabbitの最後のコメントを取得
                last_coderabbit_comment = self._get_last_coderabbit_comment(
                    sorted_comments
                )

                # 最初のコメントにCodeRabbitの最後のコメント情報を統合
                processed_comment = self._create_enhanced_task_comment(
                    first_comment, last_coderabbit_comment, thread_id, sorted_comments
                )
                processed_comments.append(processed_comment)

        return processed_comments

    def _group_comments_by_thread(
        self, comments: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """コメントをスレッドごとにグループ化

        Args:
            comments: PRのコメント一覧

        Returns:
            スレッドID -> コメント一覧のマップ
        """
        threads = {}

        for comment in comments:
            # スレッドIDを決定（in_reply_toがある場合はそれを使用、なければ自身のID）
            thread_id = comment.get("in_reply_to_id") or comment.get("id")

            if thread_id not in threads:
                threads[thread_id] = []

            threads[thread_id].append(comment)

        return threads

    def _get_last_coderabbit_comment(
        self, thread_comments: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """スレッド内のCodeRabbitの最後のコメントを取得

        Args:
            thread_comments: スレッド内のコメント一覧（時系列順）

        Returns:
            CodeRabbitの最後のコメント、存在しない場合はNone
        """
        coderabbit_comments = [
            comment
            for comment in thread_comments
            if self._is_coderabbit_comment(comment)
        ]

        return coderabbit_comments[-1] if coderabbit_comments else None

    def _is_coderabbit_comment(self, comment: Dict[str, Any]) -> bool:
        """コメントがCodeRabbitによるものかチェック

        Args:
            comment: コメントデータ

        Returns:
            CodeRabbitのコメントの場合True
        """
        user_login = comment.get("user", {}).get("login", "").lower()
        return "coderabbitai" in user_login

    def _create_enhanced_task_comment(
        self,
        first_comment: Dict[str, Any],
        last_coderabbit_comment: Optional[Dict[str, Any]],
        thread_id: str,
        all_thread_comments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """最初のコメントにCodeRabbitの最後のコメント情報を統合したタスクコメントを作成

        Args:
            first_comment: スレッドの最初のコメント
            last_coderabbit_comment: CodeRabbitの最後のコメント
            thread_id: スレッドID
            all_thread_comments: スレッド内の全コメント

        Returns:
            統合されたタスクコメントデータ
        """
        processed_comment = first_comment.copy()

        # スレッド情報を追加
        thread_info = {
            "thread_id": thread_id,
            "total_comments": len(all_thread_comments),
            "has_coderabbit_response": last_coderabbit_comment is not None,
            "is_resolved": self.determine_resolution_status(all_thread_comments),
        }

        # CodeRabbitの最後のコメントがある場合、追加情報を統合
        if last_coderabbit_comment and last_coderabbit_comment.get(
            "id"
        ) != first_comment.get("id"):
            thread_info.update(
                {
                    "coderabbit_last_comment": {
                        "id": last_coderabbit_comment.get("id"),
                        "body": last_coderabbit_comment.get("body", ""),
                        "created_at": last_coderabbit_comment.get("created_at"),
                        "summary": self._extract_comment_summary(
                            last_coderabbit_comment.get("body", "")
                        ),
                    }
                }
            )

            # 本文に追加情報として統合
            original_body = processed_comment.get("body", "")
            coderabbit_summary = self._extract_comment_summary(
                last_coderabbit_comment.get("body", "")
            )

            processed_comment["body"] = (
                f"{original_body}\n\n---\n**CodeRabbit最新コメント**: {coderabbit_summary}"
            )

        processed_comment["_thread_info"] = thread_info
        processed_comment["_task_title"] = self._extract_comment_summary(
            first_comment.get("body", "")
        )

        return processed_comment

    def _extract_comment_summary(self, body: str) -> str:
        """コメント本文から要約を抽出

        Args:
            body: コメント本文

        Returns:
            コメントの要約（最大80文字）
        """
        if not body:
            return "コメント内容なし"

        # 最初の行を取得
        lines = body.strip().split("\n")
        first_line = lines[0].strip() if lines else ""

        # マークダウンの記号を除去
        first_line = first_line.lstrip("#*-_> ")

        # 80文字で切り詰め
        if len(first_line) > 80:
            return first_line[:77] + "..."

        return first_line or "レビューコメント"

    def determine_resolution_status(
        self, thread_comments: List[Dict[str, Any]]
    ) -> bool:
        """スレッドの解決状態を判定

        CodeRabbitの最後のコメントに解決マーカーがあるかチェック

        Args:
            thread_comments: スレッド内のコメント一覧

        Returns:
            解決済みの場合True
        """
        last_coderabbit_comment = self._get_last_coderabbit_comment(thread_comments)

        if not last_coderabbit_comment:
            return False

        body = last_coderabbit_comment.get("body", "")

        # 解決マーカーのパターンをチェック
        resolution_patterns = [
            r"\[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED\]",
            r"✅.*エンジニアによる技術的検証完了",
            r"CodeRabbitによる解決済みマーク実行可能",
        ]

        import re

        for pattern in resolution_patterns:
            if re.search(pattern, body, re.IGNORECASE | re.DOTALL):
                return True

        return False
