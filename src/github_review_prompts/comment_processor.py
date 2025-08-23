"""コメント処理・フィルタリングロジック"""

import logging
import os
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime

from .models import ReviewComment, AIPrompt, ProcessingStats, ProcessingError
from .utils.parsers import (
    extract_ai_agent_prompt,
    categorize_prompt,
    determine_priority,
)
from .utils.validators import sanitize_content
from .github_client import GitHubClient
from .comment_thread_processor import CommentThreadProcessor


class CommentProcessor:
    """コメント処理・フィルタリングクラス"""

    # CodeRabbit解決済みマーカーのパターン
    CR_RESOLUTION_MARKER_PATTERN = re.compile(
        r"\[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED\].*?✅.*?エンジニアによる技術的検証完了.*?CodeRabbitによる解決済みマーク実行可能.*?\[/CR_RESOLUTION_CONFIRMED\]",
        re.DOTALL | re.IGNORECASE,
    )

    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        self.logger = logging.getLogger(__name__)
        self.stats = ProcessingStats()
        self.auto_resolved_comments = []  # 自動解決されたコメントのログ
        self.thread_processor = CommentThreadProcessor(github_client)

    def detect_resolution_markers(self, comment_bodies: Dict[int, str]) -> Set[int]:
        """コメント本文からCodeRabbit解決済みマーカーを検出

        Args:
            comment_bodies: コメントID -> コメント本文のマップ

        Returns:
            マーカーが検出されたコメントIDのセット
        """
        marked_comment_ids = set()

        for comment_id, body in comment_bodies.items():
            if self.CR_RESOLUTION_MARKER_PATTERN.search(body):
                marked_comment_ids.add(comment_id)
                self.logger.info(
                    f"CodeRabbit解決済みマーカーを検出: コメントID {comment_id}"
                )

        if marked_comment_ids:
            self.logger.info(f"解決済みマーカー検出: {len(marked_comment_ids)} 件")

        return marked_comment_ids

    def _auto_resolve_marked_comments(
        self, marked_comment_ids: Set[int], pr_info: Dict[str, Any]
    ) -> None:
        """マーカーが検出されたコメントスレッドを自動解決する

        Args:
            marked_comment_ids: マーカーが検出されたコメントIDのセット
            pr_info: プルリクエスト情報
        """
        if not marked_comment_ids:
            return

        self.logger.info(
            f"マーカー検出コメントの自動解決開始: {len(marked_comment_ids)} 件"
        )

        # GitHub APIを使ってコメントスレッドを解決済みにする
        # 注意: この機能はGraphQL APIまたは特別な権限が必要な場合があります
        resolved_count = 0
        failed_count = 0

        for comment_id in marked_comment_ids:
            try:
                success = self._resolve_comment_thread_via_graphql(comment_id, pr_info)
                if success:
                    resolved_count += 1
                    self.auto_resolved_comments.append(
                        {
                            "comment_id": comment_id,
                            "resolved_at": datetime.now().isoformat(),
                            "reason": "CodeRabbit resolution marker detected",
                        }
                    )
                    self.logger.info(f"コメントスレッド解決成功: ID {comment_id}")
                else:
                    failed_count += 1
                    self.logger.warning(f"コメントスレッド解決失敗: ID {comment_id}")
            except Exception as e:
                failed_count += 1
                self.logger.error(
                    f"コメントスレッド解決エラー (ID {comment_id}): {str(e)}"
                )

        self.logger.info(
            f"自動解決完了: 成功 {resolved_count} 件, 失敗 {failed_count} 件"
        )

    def _resolve_comment_thread_via_graphql(
        self, comment_id: int, pr_info: Dict[str, Any]
    ) -> bool:
        """GraphQL APIを使用してコメントスレッドを解決済みにする

        Args:
            comment_id: コメントID
            pr_info: プルリクエスト情報

        Returns:
            解決処理が成功したかどうか
        """
        if not self.github_client.token:
            self.logger.warning("GraphQL APIにはトークンが必要です")
            return False

        # GraphQL mutation for resolving a review thread
        mutation = """
        mutation($threadId: ID!) {
          resolveReviewThread(input: {threadId: $threadId}) {
            thread {
              id
              isResolved
            }
          }
        }
        """

        # まず、コメントIDからスレッドIDを取得する必要があります
        thread_id = self._get_thread_id_for_comment(comment_id, pr_info)
        if not thread_id:
            self.logger.warning(
                f"コメント {comment_id} のスレッドIDが取得できませんでした"
            )
            return False

        variables = {"threadId": thread_id}

        graphql_headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or self.github_client.token}",
            "Content-Type": "application/json",
        }

        try:
            response = self.github_client._make_request(
                "POST",
                self.github_client.graphql_url,
                json={"query": mutation, "variables": variables},
                headers=graphql_headers,
            )

            data = response.json()

            if "errors" in data:
                error_messages = [
                    error.get("message", str(error)) for error in data["errors"]
                ]
                self.logger.error(
                    f"GraphQL mutation エラー: {'; '.join(error_messages)}"
                )
                return False

            # 成功確認
            thread_data = (
                data.get("data", {}).get("resolveReviewThread", {}).get("thread", {})
            )
            is_resolved = thread_data.get("isResolved", False)

            return is_resolved

        except Exception as e:
            self.logger.error(f"GraphQL mutation 実行エラー: {str(e)}")
            return False

    def _get_thread_id_for_comment(
        self, comment_id: int, pr_info: Dict[str, Any]
    ) -> Optional[str]:
        """コメントIDからスレッドIDを取得する

        Args:
            comment_id: コメントID
            pr_info: プルリクエスト情報

        Returns:
            スレッドID（GraphQL形式）
        """
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $number) {
              reviewThreads(first: 100) {
                nodes {
                  id
                  comments(first: 50) {
                    nodes {
                      databaseId
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "owner": pr_info.get("owner"),
            "repo": pr_info.get("repo"),
            "number": pr_info.get("pull_number"),
        }

        graphql_headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or self.github_client.token}",
            "Content-Type": "application/json",
        }

        try:
            response = self.github_client._make_request(
                "POST",
                self.github_client.graphql_url,
                json={"query": query, "variables": variables},
                headers=graphql_headers,
            )

            data = response.json()

            if "errors" in data:
                return None

            threads = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
                .get("nodes", [])
            )

            for thread in threads:
                comments = thread.get("comments", {}).get("nodes", [])
                for comment in comments:
                    if comment.get("databaseId") == comment_id:
                        return thread.get("id")

            return None

        except Exception as e:
            self.logger.error(f"スレッドID取得エラー: {str(e)}")
            return None

    def process_comments(
        self,
        comments: List[Dict[str, Any]],
        resolved_ids: Set[int],
        graphql_bodies: Dict[int, str],
        include_resolved: bool = False,
        pr_info: Optional[Dict[str, Any]] = None,
        auto_resolve_marked: bool = True,
        enable_thread_processing: bool = True,
    ) -> Tuple[List[AIPrompt], ProcessingStats]:
        """コメントを処理してAIプロンプトを抽出"""
        start_time = datetime.now()
        ai_prompts = []

        self.stats.total_comments = len(comments)
        self.logger.info(f"コメント処理開始: {len(comments)} 件")

        # スレッド処理が有効な場合、コメントをスレッド処理
        if enable_thread_processing:
            self.logger.info("スレッド処理を実行中...")
            comments = self.thread_processor.process_comment_threads(comments)
            self.logger.info(f"スレッド処理完了: {len(comments)} 件のタスクを生成")

        # マーカー検出と自動解決処理
        marked_comment_ids = set()
        if auto_resolve_marked:
            marked_comment_ids = self.detect_resolution_markers(graphql_bodies)
            if marked_comment_ids and pr_info:
                self._auto_resolve_marked_comments(marked_comment_ids, pr_info)

        for comment in comments:
            try:
                comment_id = comment.get("id")
                if not comment_id:
                    self.logger.warning("コメントIDが見つかりません")
                    continue

                # CodeRabbitのコメントのみを対象とする
                user_login = comment.get("user", {}).get("login", "").lower()
                if "coderabbitai" not in user_login:
                    self.stats.non_coderabbit_comments += 1
                    self.logger.debug(
                        f"CodeRabbit以外のコメント {comment_id} をスキップ: {user_login}"
                    )
                    continue

                # 解決済みコメントの処理
                is_resolved = comment_id in resolved_ids
                is_marked_for_resolution = comment_id in marked_comment_ids

                if is_resolved:
                    self.stats.resolved_comments += 1
                    if not include_resolved:
                        self.logger.debug(f"解決済みコメント {comment_id} をスキップ")
                        continue
                elif is_marked_for_resolution:
                    # マーカーが検出されたコメントは対象から除外
                    self.stats.resolved_comments += 1
                    self.logger.info(f"マーカー検出により除外: コメントID {comment_id}")
                    continue
                else:
                    self.stats.unresolved_comments += 1

                # コメント本文の取得（GraphQLの完全版を優先）
                comment_body = graphql_bodies.get(comment_id, comment.get("body", ""))
                if not comment_body:
                    self.logger.debug(f"コメント {comment_id} の本文が空です")
                    continue

                # ReviewCommentオブジェクトを作成
                review_comment = self._create_review_comment(
                    comment, comment_body, is_resolved
                )

                # AIプロンプトを抽出
                ai_prompt = self._extract_ai_prompt_from_comment(
                    review_comment, pr_info
                )
                if ai_prompt:
                    ai_prompts.append(ai_prompt)
                    self.stats.prompts_extracted += 1
                    self.logger.debug(
                        f"AI プロンプト抽出成功: コメント ID {comment_id}"
                    )

            except Exception as e:
                error_msg = (
                    f"コメント処理エラー (ID: {comment.get('id', 'unknown')}): {str(e)}"
                )
                self.logger.error(error_msg)
                self.stats.errors.append(error_msg)
                continue

        # 処理統計を更新
        end_time = datetime.now()
        self.stats.processing_time = (end_time - start_time).total_seconds()

        self.logger.info(
            f"コメント処理完了: {self.stats.prompts_extracted} プロンプト抽出 "
            f"({self.stats.processing_time:.2f}秒)"
        )

        return ai_prompts, self.stats

    def _create_review_comment(
        self, comment: Dict[str, Any], body: str, is_resolved: bool
    ) -> ReviewComment:
        """コメントデータからReviewCommentオブジェクトを作成"""
        return ReviewComment(
            id=comment.get("id", 0),
            body=sanitize_content(body),
            path=comment.get("path", ""),
            line=comment.get("line"),
            original_line=comment.get("original_line"),
            author=comment.get("user", {}).get("login", ""),
            created_at=comment.get("created_at", ""),
            updated_at=comment.get("updated_at", ""),
            html_url=comment.get("html_url", ""),
            is_resolved=is_resolved,
            context=self._extract_comment_context(comment),
        )

    def _extract_comment_context(self, comment: Dict[str, Any]) -> Dict[str, Any]:
        """コメントから追加のコンテキスト情報を抽出"""
        context = {}

        # ファイル情報
        if comment.get("path"):
            context["file_extension"] = (
                comment["path"].split(".")[-1] if "." in comment["path"] else ""
            )
            context["directory"] = (
                "/".join(comment["path"].split("/")[:-1])
                if "/" in comment["path"]
                else ""
            )

        # 行番号情報
        if comment.get("line") or comment.get("original_line"):
            context["has_line_info"] = True
            context["line_range"] = self._calculate_line_range(comment)

        # 差分情報
        if comment.get("diff_hunk"):
            context["diff_context"] = self._extract_diff_context(comment["diff_hunk"])

        # コメント作成者情報
        user_info = comment.get("user", {})
        if user_info:
            context["author_type"] = user_info.get("type", "")
            context["is_bot"] = user_info.get("type", "").lower() == "bot"
            context["is_coderabbit"] = (
                "coderabbitai" in user_info.get("login", "").lower()
            )

        # Outside diff range commentsの情報
        if comment.get("is_outside_diff"):
            context["is_outside_diff"] = True
            context["comment_type"] = comment.get("comment_type", "issue_comment")

        # 作成・更新時間の解析
        created_at = comment.get("created_at")
        updated_at = comment.get("updated_at")
        if created_at and updated_at:
            context["was_edited"] = created_at != updated_at

        return context

    def _calculate_line_range(
        self, comment: Dict[str, Any]
    ) -> Optional[Dict[str, int]]:
        """コメントの行範囲を計算"""
        line = comment.get("line")
        original_line = comment.get("original_line")

        if line or original_line:
            return {
                "start": min(filter(None, [line, original_line])),
                "end": max(filter(None, [line, original_line])),
            }

        return None

    def _extract_diff_context(self, diff_hunk: str) -> Dict[str, Any]:
        """差分情報から周辺コンテキストを抽出"""
        context = {}

        if not diff_hunk:
            return context

        lines = diff_hunk.split("\n")

        # 追加・削除行数をカウント
        additions = len([line for line in lines if line.startswith("+")])
        deletions = len([line for line in lines if line.startswith("-")])

        context["additions"] = additions
        context["deletions"] = deletions
        context["total_changes"] = additions + deletions

        # 変更タイプを判定
        if additions > 0 and deletions == 0:
            context["change_type"] = "addition"
        elif additions == 0 and deletions > 0:
            context["change_type"] = "deletion"
        elif additions > 0 and deletions > 0:
            context["change_type"] = "modification"
        else:
            context["change_type"] = "unknown"

        return context

    def _extract_ai_prompt_from_comment(
        self, comment: ReviewComment, pr_info: Optional[Dict[str, Any]] = None
    ) -> Optional[AIPrompt]:
        """ReviewCommentからAIプロンプトを抽出"""
        if not comment.body:
            return None

        # AIプロンプトテキストを抽出
        prompt_content = extract_ai_agent_prompt(comment.body)
        if not prompt_content:
            return None

        # 場所情報を構築
        location_parts = []
        if comment.path:
            location_parts.append(f"In {comment.path}")
        else:
            # Outside diff range commentsの場合
            if hasattr(comment, "context") and comment.context.get("is_outside_diff"):
                location_parts.append("Outside diff range")

        line_info = comment.line or comment.original_line
        if line_info:
            location_parts.append(f"around line {line_info}")
        elif hasattr(comment, "context") and comment.context.get("is_outside_diff"):
            location_parts.append("(general comment)")

        location = ", ".join(location_parts) if location_parts else "Unknown location"

        # カテゴリと優先度を推定
        category = categorize_prompt(prompt_content, comment.path)
        priority = determine_priority(prompt_content, category)

        # contextにPR情報を追加
        context = {
            "is_resolved": comment.is_resolved,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
            "html_url": comment.html_url,
            **comment.context,
        }

        # PR情報をcontextに追加
        if pr_info:
            context.update(
                {
                    "pr_owner": pr_info.get("owner"),
                    "pr_repo": pr_info.get("repo"),
                    "pr_number": pr_info.get("pull_number"),
                }
            )

        try:
            return AIPrompt(
                content=prompt_content,
                location=location,
                file_path=comment.path,
                line_number=line_info,
                comment_id=comment.id,
                author=comment.author,
                priority=priority,
                category=category,
                context=context,
            )
        except Exception as e:
            self.logger.error(
                f"AIPrompt作成エラー (コメント ID: {comment.id}): {str(e)}"
            )
            return None

    def filter_prompts_by_criteria(
        self,
        prompts: List[AIPrompt],
        categories: Optional[List[str]] = None,
        priorities: Optional[List[str]] = None,
        authors: Optional[List[str]] = None,
        file_patterns: Optional[List[str]] = None,
    ) -> List[AIPrompt]:
        """指定された条件でプロンプトをフィルタリング"""
        filtered_prompts = prompts

        # カテゴリフィルター
        if categories:
            filtered_prompts = [p for p in filtered_prompts if p.category in categories]
            self.logger.debug(
                f"カテゴリフィルター適用後: {len(filtered_prompts)} プロンプト"
            )

        # 優先度フィルター
        if priorities:
            filtered_prompts = [p for p in filtered_prompts if p.priority in priorities]
            self.logger.debug(
                f"優先度フィルター適用後: {len(filtered_prompts)} プロンプト"
            )

        # 作成者フィルター
        if authors:
            filtered_prompts = [p for p in filtered_prompts if p.author in authors]
            self.logger.debug(
                f"作成者フィルター適用後: {len(filtered_prompts)} プロンプト"
            )

        # ファイルパターンフィルター
        if file_patterns:
            filtered_prompts = []
            for prompt in filtered_prompts:
                if any(
                    self._match_file_pattern(prompt.file_path, pattern)
                    for pattern in file_patterns
                ):
                    filtered_prompts.append(prompt)
            self.logger.debug(
                f"ファイルパターンフィルター適用後: {len(filtered_prompts)} プロンプト"
            )

        return filtered_prompts

    def _match_file_pattern(self, file_path: Optional[str], pattern: str) -> bool:
        """ファイルパスがパターンにマッチするかチェック"""
        if not file_path or not pattern:
            return False

        # 基本的なワイルドカード対応
        pattern = pattern.replace("*", ".*").replace("?", ".")
        return re.match(pattern, file_path, re.IGNORECASE) is not None

    def sort_prompts(
        self, prompts: List[AIPrompt], sort_by: str = "priority", reverse: bool = False
    ) -> List[AIPrompt]:
        """プロンプトをソート"""
        if sort_by == "priority":
            priority_order = {"high": 3, "medium": 2, "low": 1}
            return sorted(
                prompts,
                key=lambda p: priority_order.get(p.priority, 0),
                reverse=not reverse,
            )
        elif sort_by == "category":
            return sorted(prompts, key=lambda p: p.category, reverse=reverse)
        elif sort_by == "file_path":
            return sorted(prompts, key=lambda p: p.file_path, reverse=reverse)
        elif sort_by == "line_number":
            return sorted(prompts, key=lambda p: p.line_number or 0, reverse=reverse)
        elif sort_by == "author":
            return sorted(prompts, key=lambda p: p.author, reverse=reverse)
        else:
            self.logger.warning(f"不明なソート基準: {sort_by}")
            return prompts

    def get_processing_summary(self) -> Dict[str, Any]:
        """処理サマリーを取得"""
        return {
            "total_comments": self.stats.total_comments,
            "resolved_comments": self.stats.resolved_comments,
            "unresolved_comments": self.stats.unresolved_comments,
            "prompts_extracted": self.stats.prompts_extracted,
            "processing_time": self.stats.processing_time,
            "success_rate": (
                self.stats.prompts_extracted / max(self.stats.unresolved_comments, 1)
                if self.stats.unresolved_comments > 0
                else 0
            ),
            "errors": self.stats.errors,
            "auto_resolved_comments": len(self.auto_resolved_comments),
            "auto_resolved_details": self.auto_resolved_comments,
        }

    def validate_comment_data(
        self, comments: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """コメントデータの基本的な検証"""
        validation_errors = []

        if not comments:
            validation_errors.append("コメントデータが空です")
            return False, validation_errors

        required_fields = ["id", "body", "user"]

        for i, comment in enumerate(comments):
            if not isinstance(comment, dict):
                validation_errors.append(f"コメント {i}: 無効なデータ形式")
                continue

            for field in required_fields:
                if field not in comment:
                    validation_errors.append(
                        f"コメント {i}: 必須フィールド '{field}' が見つかりません"
                    )

            # IDが数値かチェック
            if "id" in comment and not isinstance(comment["id"], int):
                validation_errors.append(f"コメント {i}: IDが数値ではありません")

            # ユーザー情報の検証
            user_info = comment.get("user", {})
            if not isinstance(user_info, dict) or "login" not in user_info:
                validation_errors.append(f"コメント {i}: ユーザー情報が無効です")

        return len(validation_errors) == 0, validation_errors
