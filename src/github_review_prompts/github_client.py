"""GitHub API クライアント"""

from contextlib import suppress
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Set, Tuple, Any
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .models import (
    APIError,
    AuthenticationError,
    RateLimitError,
    GitHubPRInfo,
    ProcessingStats,
)
from .utils.parsers import parse_pr_url
from .utils.validators import validate_github_token, sanitize_content


class GitHubClient:
    """GitHub API クライアント（REST API + GraphQL API対応）"""

    def __init__(
        self, token: Optional[str] = None, base_url: str = "https://api.github.com"
    ):
        self.token = token
        self.base_url = base_url
        self.graphql_url = "https://api.github.com/graphql"
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

        # リトライ設定
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 認証設定
        if self.token:
            is_valid, token_type = validate_github_token(self.token)
            if not is_valid:
                raise AuthenticationError(f"無効なGitHubトークン: {token_type}")

            self.session.headers.update(
                {
                    "Authorization": f"token {os.getenv('GITHUB_TOKEN') or self.token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GitHub-Review-Prompts-AI-Agent/1.0.0",
                }
            )
            self.logger.info(f"GitHub認証設定完了: {token_type} token")
        else:
            self.logger.warning(
                "GitHub トークンが設定されていません。レート制限に注意してください。"
            )

    def parse_pr_url(self, pr_url: str) -> GitHubPRInfo:
        """プルリクエストURLを解析してGitHubPRInfoオブジェクトを返す"""
        try:
            owner, repo, pull_number = parse_pr_url(pr_url)
            return GitHubPRInfo(
                owner=owner, repo=repo, pull_number=pull_number, url=pr_url
            )
        except ValueError as e:
            raise APIError(f"プルリクエストURL解析エラー: {str(e)}") from e

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """共通のリクエスト処理（エラーハンドリング付き）"""
        try:
            # デフォルトのタイムアウト（呼び出し側で kwargs["timeout"] により上書き可能）
            kwargs.setdefault("timeout", (5, 30))  # (connect, read) 秒
            response = self.session.request(method, url, **kwargs)

            # レート制限チェック
            if response.status_code == 429:
                reset_time = int(
                    response.headers.get("X-RateLimit-Reset", time.time() + 60)
                )
                wait_time = max(reset_time - int(time.time()), 1)
                raise RateLimitError(
                    f"API レート制限に達しました。{wait_time}秒後に再試行してください。",
                    status_code=429,
                    response_data={"reset_time": reset_time, "wait_time": wait_time},
                )

            # 認証エラー
            if response.status_code == 401:
                raise AuthenticationError(
                    "GitHub API 認証に失敗しました。トークンを確認してください。",
                    status_code=401,
                )

            # 権限不足
            if response.status_code == 403:
                text_lower = response.text.lower()
                remaining = response.headers.get("X-RateLimit-Remaining")
                is_rate_limited = ("rate limit" in text_lower) or (remaining == "0")
                if is_rate_limited:
                    reset_time = int(
                        response.headers.get("X-RateLimit-Reset", time.time() + 60)
                    )
                    wait_time = max(reset_time - int(time.time()), 1)
                    raise RateLimitError(
                        f"API レート制限に達しました。{wait_time}秒後に再試行してください。",
                        status_code=403,
                        response_data={
                            "reset_time": reset_time,
                            "wait_time": wait_time,
                        },
                    )
                raise APIError(
                    "GitHub API アクセスが拒否されました。トークンの権限を確認してください。",
                    status_code=403,
                )

            # その他のHTTPエラー
            if not response.ok:
                error_data = {}
                with suppress(ValueError, json.JSONDecodeError):
                    error_data = response.json()

                raise APIError(
                    f"GitHub API エラー: {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    response_data=error_data,
                )

            return response

        except requests.exceptions.RequestException as e:
            raise APIError(f"GitHub API リクエストエラー: {str(e)}") from e

    def _make_graphql_request(
        self, query: str, variables: Dict[str, Any]
    ) -> requests.Response:
        """GraphQLリクエストの実行"""
        url = "https://api.github.com/graphql"
        payload = {"query": query, "variables": variables}
        return self._make_request("POST", url, json=payload)

    def _has_coderabbit_resolution_marker(self, comment_body: str) -> bool:
        """CodeRabbitの解決済みマーカーが含まれているかチェック"""
        if not comment_body:
            return False

        resolution_markers = [
            r"\[CR_RESOLUTION_CONFIRMED:.*?\]",
            r"✅ エンジニアによる技術的検証完了.*CodeRabbitによる解決済みマーク実行可能",
            r"\[/CR_RESOLUTION_CONFIRMED\]",
        ]

        # すべてのマーカーが含まれているかチェック
        for marker in resolution_markers:
            if not re.search(marker, comment_body, re.DOTALL | re.IGNORECASE):
                return False

        return True

    def test_authentication(self) -> Dict[str, Any]:
        """認証テストとユーザー情報取得"""
        try:
            response = self._make_request("GET", f"{self.base_url}/user")
            user_data = response.json()

            # レート制限情報も取得
            rate_limit = self.get_rate_limit_info()

            return {
                "authenticated": True,
                "user": {
                    "login": user_data.get("login"),
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                },
                "rate_limit": rate_limit,
            }

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"認証テスト失敗: {str(e)}") from e

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """APIレート制限情報を取得"""
        try:
            response = self._make_request("GET", f"{self.base_url}/rate_limit")
            return response.json()
        except APIError:
            return {"error": "レート制限情報の取得に失敗"}

    def get_pr_basic_info(self, pr_info: GitHubPRInfo) -> Dict[str, Any]:
        """プルリクエストの基本情報を取得"""
        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}"

        try:
            response = self._make_request("GET", url)
            pr_data = response.json()

            return {
                "title": pr_data.get("title", ""),
                "state": pr_data.get("state", ""),
                "created_at": pr_data.get("created_at", ""),
                "updated_at": pr_data.get("updated_at", ""),
                "author": pr_data.get("user", {}).get("login", ""),
                "base_branch": pr_data.get("base", {}).get("ref", ""),
                "head_branch": pr_data.get("head", {}).get("ref", ""),
                "base_repo": pr_data.get("base", {})
                .get("repo", {})
                .get("full_name", ""),
                "head_repo": pr_data.get("head", {})
                .get("repo", {})
                .get("full_name", ""),
                "commits": pr_data.get("commits", 0),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": pr_data.get("changed_files", 0),
            }

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"プルリクエスト情報取得エラー: {str(e)}") from e

    def get_pr_review_comments(
        self, pr_info: GitHubPRInfo, page_size: int = 100, unresolved_only: bool = False
    ) -> List[Dict[str, Any]]:
        """プルリクエストのレビューコメントを取得（未解決フィルタ対応）"""
        if unresolved_only:
            return self._get_unresolved_review_comments(pr_info, page_size)

        # 従来の全件取得
        all_comments = []
        page = 1

        self.logger.info(
            f"レビューコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        while True:
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
            per_page = min(page_size, 100)  # GitHub APIの最大値は100
            params = {"page": page, "per_page": per_page}

            try:
                response = self._make_request("GET", url, params=params)
                page_comments = response.json()

                if not page_comments:  # 空のページに到達
                    break

                all_comments.extend(page_comments)
                self.logger.debug(f"ページ {page}: {len(page_comments)} コメント取得")

                # 最後のページかどうか判定（実際に指定した per_page を用いる）
                if len(page_comments) < per_page:
                    break

                page += 1

                # レート制限を考慮した遅延
                time.sleep(0.1)

            except APIError:
                raise
            except Exception as e:
                raise APIError(
                    f"レビューコメント取得エラー (ページ {page}): {str(e)}"
                ) from e

        self.logger.info(f"レビューコメント取得完了: {len(all_comments)} 件")
        return all_comments

    def _get_unresolved_review_comments(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """未解決のレビューコメントのみを取得（GraphQL使用）"""

        self.logger.info(
            f"未解決レビューコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        # GraphQLクエリで未解決スレッドのみ取得
        query = """
        query GetUnresolvedReviewComments($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $number) {
              reviewThreads(first: 100) {
                nodes {
                  id
                  isResolved
                  comments(first: 10) {
                    nodes {
                      id
                      author {
                        login
                      }
                      body
                      createdAt
                      updatedAt
                      line
                      path
                      diffHunk
                      outdated
                      pullRequestReview {
                        id
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "owner": pr_info.owner,
            "repo": pr_info.repo,
            "number": pr_info.pull_number,
        }

        try:
            response = self._make_graphql_request(query, variables)
            data = response.json()

            if "errors" in data:
                raise APIError(f"GraphQL API エラー: {data['errors']}")

            review_threads = data["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ]
            unresolved_comments = []

            for thread in review_threads:
                # スレッドの未解決状態をチェック
                thread_is_resolved = thread["isResolved"]

                # スレッド内のコメントをチェック（時系列順）
                thread_comments = thread["comments"]["nodes"]
                if not thread_comments:
                    continue

                # CodeRabbitの解決済みマーカーチェック
                # 最後のコメントがcoderabbitaiかつ解決済みマーカーがある場合は解決済みとみなす
                last_comment = thread_comments[-1]
                if last_comment["author"]["login"] in [
                    "coderabbitai",
                    "coderabbitai[bot]",
                ] and self._has_coderabbit_resolution_marker(last_comment["body"]):
                    thread_is_resolved = True
                    self.logger.debug(
                        f"CodeRabbit解決済みマーカー検出: thread {thread['id']}"
                    )

                # 未解決スレッドのみを処理
                if not thread_is_resolved:
                    for comment in thread_comments:
                        # インラインコメントのみ（pathとlineがあるもの）
                        if comment["path"] and comment["line"]:
                            # REST API形式に変換
                            rest_format_comment = {
                                "id": comment["id"],
                                "user": {"login": comment["author"]["login"]},
                                "body": comment["body"],
                                "created_at": comment["createdAt"],
                                "updated_at": comment["updatedAt"],
                                "path": comment["path"],
                                "line": comment["line"],
                                "diff_hunk": comment["diffHunk"],
                                "outdated": comment["outdated"],
                                "pull_request_review_id": (
                                    comment["pullRequestReview"]["id"]
                                    if comment["pullRequestReview"]
                                    else None
                                ),
                                "is_resolved": False,  # 明示的に未解決マーク
                            }
                            unresolved_comments.append(rest_format_comment)

            self.logger.info(
                f"未解決レビューコメント取得完了: {len(unresolved_comments)} 件"
            )
            return unresolved_comments

        except Exception as e:
            raise APIError(f"未解決レビューコメント取得エラー: {str(e)}") from e

    def get_pr_issue_comments(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """プルリクエストのissue comments（Outside diff range comments含む）を全件取得"""
        all_comments = []
        page = 1

        self.logger.info(
            f"Issue コメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        while True:
            # Issue comments API endpoint (PRのissue commentsを取得)
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/issues/{pr_info.pull_number}/comments"
            per_page = min(page_size, 100)
            params = {"page": page, "per_page": per_page}

            try:
                response = self._make_request("GET", url, params=params)
                page_comments = response.json()

                if not page_comments:
                    break

                # Issue commentsにはdiff情報がないため、メタデータを追加
                for comment in page_comments:
                    comment["comment_type"] = "issue_comment"
                    comment["is_outside_diff"] = True
                    # pathとlineはNoneに設定（diff範囲外のため）
                    if "path" not in comment:
                        comment["path"] = None
                    if "line" not in comment:
                        comment["line"] = None

                all_comments.extend(page_comments)
                self.logger.debug(
                    f"ページ {page}: {len(page_comments)} Issue コメント取得"
                )

                if len(page_comments) < per_page:
                    break

                page += 1
                time.sleep(0.1)

            except APIError:
                raise
            except Exception as e:
                raise APIError(
                    f"Issue コメント取得エラー (ページ {page}): {str(e)}"
                ) from e

        self.logger.info(f"Issue コメント取得完了: {len(all_comments)} 件")
        return all_comments

    def get_all_pr_comments(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """プルリクエストの全コメント（GraphQL API優先、Outside diff range comments対応）

        Returns:
            Tuple[List[Dict], Dict]: (全コメントリスト, 統計情報)
        """
        try:
            # GraphQL APIでレビューとOutside diff commentsを取得
            self.logger.info("GraphQL APIでOutside diff range comments取得を試行...")
            graphql_reviews, outside_diff_comments = (
                self.get_pr_reviews_with_outside_diff_graphql(pr_info, page_size)
            )

            # REST APIでレビューコメントも取得（全件取得、解決済み判定はハイブリッドアプローチに委ねる）
            review_comments = self.get_pr_review_comments(
                pr_info, page_size, unresolved_only=False
            )

            # Issue コメント（Outside diff range含む）を取得
            issue_comments = self.get_pr_issue_comments(pr_info, page_size)

            # 全コメントを結合
            all_comments = (
                review_comments
                + graphql_reviews
                + outside_diff_comments
                + issue_comments
            )

            # 統計情報
            stats = {
                "review_comments": len(review_comments),
                "graphql_reviews": len(graphql_reviews),
                "outside_diff_comments": len(outside_diff_comments),
                "issue_comments": len(issue_comments),
                "total_comments": len(all_comments),
            }

            self.logger.info(
                f"GraphQL API取得完了: レビューコメント {stats['review_comments']} 件, "
                f"GraphQLレビュー {stats['graphql_reviews']} 件, "
                f"Outside diff {stats['outside_diff_comments']} 件, "
                f"Issue コメント {stats['issue_comments']} 件, "
                f"合計 {stats['total_comments']} 件"
            )

            return all_comments, stats

        except Exception as e:
            self.logger.warning(
                f"GraphQL API取得失敗、REST APIにフォールバック: {str(e)}"
            )

            # フォールバック: 既存のREST API使用
            # レビューコメント（diff range内、未解決のみ）を取得
            review_comments = self.get_pr_review_comments(
                pr_info, page_size, unresolved_only=True
            )

            # Issue コメント（Outside diff range含む）を取得
            issue_comments = self.get_pr_issue_comments(pr_info, page_size)

            # 統計情報
            stats = {
                "review_comments": len(review_comments),
                "issue_comments": len(issue_comments),
                "total_comments": len(review_comments) + len(issue_comments),
            }

            # 全コメントを結合
            all_comments = review_comments + issue_comments

            self.logger.info(
                f"REST API取得完了: レビューコメント {stats['review_comments']} 件, "
                f"Issue コメント {stats['issue_comments']} 件, 合計 {stats['total_comments']} 件"
            )

            return all_comments, stats

    def get_pr_reviews(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """プルリクエストのレビュー一覧を取得"""
        all_reviews = []
        page = 1

        self.logger.info(
            f"レビュー一覧取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        while True:
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/reviews"
            per_page = min(page_size, 100)
            params = {"page": page, "per_page": per_page}

            try:
                response = self._make_request("GET", url, params=params)
                page_reviews = response.json()

                if not page_reviews:
                    break

                all_reviews.extend(page_reviews)
                self.logger.debug(f"ページ {page}: {len(page_reviews)} レビュー取得")

                if len(page_reviews) < per_page:
                    break

                page += 1
                time.sleep(0.1)

            except APIError:
                raise
            except Exception as e:
                raise APIError(f"レビュー取得エラー (ページ {page}): {str(e)}") from e

        self.logger.info(f"レビュー取得完了: {len(all_reviews)} 件")
        return all_reviews

    def get_single_comment_detail(
        self, pr_info: GitHubPRInfo, comment_id: int
    ) -> Optional[Dict[str, Any]]:
        """単一コメントの詳細情報を取得"""
        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/comments/{comment_id}"

        try:
            response = self._make_request("GET", url)
            return response.json()

        except APIError as e:
            if e.status_code == 404:
                self.logger.warning(f"コメント ID {comment_id} が見つかりません")
                return None
            raise
        except Exception as e:
            raise APIError(f"コメント詳細取得エラー: {str(e)}") from e

    def get_comments_via_hybrid_approach(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> Tuple[Set[int], Dict[int, str]]:
        """ハイブリッドアプローチ: GraphQL + REST API補完でコメント取得"""
        self.logger.info(f"ハイブリッドアプローチでコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")

        # Step 1: GraphQL APIで解決済み判定付きコメント取得
        graphql_resolved_ids, graphql_comment_bodies = self.get_resolved_comments_via_graphql(pr_info, page_size)

        # Step 2: REST APIで全コメント取得（補完用）
        rest_all_comments = self._get_all_comments_via_rest(pr_info, page_size)

        # Step 3: 結果をマージ
        return self._merge_graphql_and_rest_results(
            graphql_resolved_ids, graphql_comment_bodies, rest_all_comments
        )

    def get_resolved_comments_via_graphql(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> Tuple[Set[int], Dict[int, str]]:
        """GraphQL APIを使用して解決済みコメントIDとコメント本文を取得"""
        if not self.token:
            self.logger.warning("GraphQL APIにはトークンが必要です")
            return set(), {}

        resolved_comment_ids = set()
        comment_bodies = {}
        coderabbit_resolved_count = 0
        total_threads_processed = 0

        # GraphQL クエリ実行のためのヘッダー
        graphql_headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or self.token}",
            "Content-Type": "application/json",
        }

        # ページネーション用の変数
        has_next_page = True
        after_cursor = None
        page_count = 0

        self.logger.info(
            f"GraphQL APIで解決済みコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        while has_next_page:
            page_count += 1
            self.logger.debug(f"GraphQL ページ {page_count} 処理中...")

            query = """
            query($owner: String!, $repo: String!, $number: Int!, $after: String) {
              repository(owner: $owner, name: $repo) {
                pullRequest(number: $number) {
                  reviewThreads(first: 100, after: $after) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      isResolved
                      comments(first: 50) {
                        pageInfo {
                          hasNextPage
                          endCursor
                        }
                        nodes {
                          databaseId
                          body
                          author {
                            login
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """

            variables = {
                "owner": pr_info.owner,
                "repo": pr_info.repo,
                "number": pr_info.pull_number,
                "after": after_cursor,
            }

            try:
                response = self._make_request(
                    "POST",
                    self.graphql_url,
                    json={"query": query, "variables": variables},
                    headers=graphql_headers,
                )

                data = response.json()

                if "errors" in data:
                    error_messages = [
                        error.get("message", str(error)) for error in data["errors"]
                    ]
                    raise APIError(f"GraphQL エラー: {'; '.join(error_messages)}")

                if not data.get("data", {}).get("repository", {}).get("pullRequest"):
                    raise APIError(
                        "GraphQL レスポンスにプルリクエストデータが含まれていません"
                    )

                review_threads = data["data"]["repository"]["pullRequest"][
                    "reviewThreads"
                ]
                threads = review_threads["nodes"]
                page_info = review_threads["pageInfo"]

                # ページネーション情報を更新
                has_next_page = page_info["hasNextPage"]
                after_cursor = page_info["endCursor"]

                total_threads_processed += len(threads)
                self.logger.debug(f"ページ {page_count}: {len(threads)} スレッド処理")

                for thread in threads:
                    comments_data = thread["comments"]

                    # スレッド内コメントのページネーション警告
                    if comments_data["pageInfo"]["hasNextPage"]:
                        self.logger.warning(
                            "スレッド内に50を超えるコメントがあります。一部取得されていない可能性があります。"
                        )

                    # 強化された解決済み判定ロジック
                    thread_is_truly_resolved = self._is_thread_truly_resolved(thread, comments_data)

                    if thread_is_truly_resolved:
                        # CodeRabbitのコメントを含むスレッドかチェック
                        has_coderabbit = any(
                            "coderabbitai"
                            in comment.get("author", {}).get("login", "").lower()
                            for comment in comments_data["nodes"]
                            if comment.get("author")
                        )

                        if has_coderabbit:
                            coderabbit_resolved_count += 1

                        # 真に解決済みのスレッドの全コメントIDを記録
                        for comment in comments_data["nodes"]:
                            if comment["databaseId"]:
                                resolved_comment_ids.add(comment["databaseId"])
                    else:
                        # GitHub APIで解決済みとされているが実際は未解決のケース
                        if thread["isResolved"]:
                            self.logger.warning(
                                f"スレッド {thread.get('id', 'unknown')} はGitHub APIで解決済みとされていますが、内容分析では未解決と判定されました"
                            )

                    # 全コメントの本文を保存（解決済み・未解決を問わず）
                    for comment in comments_data["nodes"]:
                        if comment["databaseId"] and comment.get("body"):
                            # セキュリティのためにコンテンツをサニタイズ
                            sanitized_body = sanitize_content(comment["body"])
                            comment_bodies[comment["databaseId"]] = sanitized_body

                # APIレート制限を考慮した遅延
                time.sleep(0.2)

            except APIError:
                raise
            except Exception as e:
                raise APIError(
                    f"GraphQL API 実行エラー (ページ {page_count}): {str(e)}"
                ) from e

        self.logger.info(
            f"GraphQL API完了: {page_count}ページ, {total_threads_processed}スレッド処理, "
            f"CodeRabbit解決済み: {coderabbit_resolved_count}件, "
            f"コメント本文: {len(comment_bodies)}件"
        )

        return resolved_comment_ids, comment_bodies

    def _is_thread_truly_resolved(self, thread: Dict[str, Any], comments_data: Dict[str, Any]) -> bool:
        """スレッドが真に解決済みかを判定（リプライがないインラインコメントは未解決とする効率的アプローチ）

        プロンプトコンテキストサイズを最適化するため、リプライの有無で解決状態を判定する。
        リプライがないコメントは開発者の対応待ちと見なし、未解決として扱う。

        Args:
            thread: GraphQL API のスレッドデータ
            comments_data: スレッド内のコメントデータ

        Returns:
            真に解決済みかどうか
        """
        comments = comments_data.get("nodes", [])

        # コメントが存在しない場合は未解決として扱う
        if not comments:
            return False

        # 1つのコメントのみ（リプライなし）の場合は未解決
        if len(comments) == 1:
            self.logger.debug("リプライなしのインラインコメント: 未解決として扱う")
            return False

        # 複数コメント（リプライあり）の場合、明示的な解決確認をチェック
        for comment in comments:
            comment_body = comment.get("body", "")

            # CodeRabbit解決確認マーカー
            if re.search(r"\[CR_RESOLUTION_CONFIRMED.*?\[/CR_RESOLUTION_CONFIRMED\]",
                        comment_body, re.IGNORECASE | re.DOTALL):
                self.logger.debug("CodeRabbit解決確認マーカー検出: 解決済み")
                return True

            # 開発者による明示的な解決コメント
            resolved_keywords = [
                "Fixed", "Resolved", "Done", "Completed", "Applied",
                "修正済み", "対応済み", "完了", "適用済み", "解決済み"
            ]

            if any(keyword in comment_body for keyword in resolved_keywords):
                # ただし、質問や議論の継続を示すパターンは除外
                discussion_patterns = [
                    "?", "？", "How", "Why", "どう", "なぜ", "どのよう",
                    "Should we", "するべき", "検討", "議論"
                ]

                if not any(pattern in comment_body for pattern in discussion_patterns):
                    self.logger.debug("開発者による解決コメント検出: 解決済み")
                    return True

        # リプライはあるが明示的な解決表明がない場合は未解決
        self.logger.debug("リプライあり、明示的解決なし: 未解決として扱う")
        return False

    def _get_all_comments_via_rest(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> Dict[int, Dict[str, Any]]:
        """REST APIで全コメント取得（GraphQLで欠落したコメントの補完用）"""
        all_comments = {}
        page = 1

        self.logger.info(f"REST APIで全コメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")

        while True:
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
            params = {"per_page": page_size, "page": page}

            try:
                response = self._make_request("GET", url, params=params)
                comments = response.json()

                if not comments:
                    break

                # コメント情報を辞書に格納
                for comment in comments:
                    comment_id = comment.get("id")
                    if comment_id:
                        all_comments[comment_id] = {
                            "id": comment_id,
                            "path": comment.get("path"),
                            "line": comment.get("line"),
                            "body": comment.get("body", ""),
                            "created_at": comment.get("created_at"),
                            "user": comment.get("user", {}).get("login"),
                            "source": "rest_api"
                        }

                self.logger.debug(f"REST API ページ {page}: {len(comments)}件のコメント取得")
                page += 1

                # ページサイズより少ない場合は最後のページ
                if len(comments) < page_size:
                    break

            except Exception as e:
                self.logger.error(f"REST APIコメント取得エラー (ページ {page}): {str(e)}")
                break

        self.logger.info(f"REST API取得完了: {len(all_comments)}件のコメント")
        return all_comments

    def _merge_graphql_and_rest_results(
        self,
        graphql_resolved_ids: Set[int],
        graphql_comment_bodies: Dict[int, str],
        rest_all_comments: Dict[int, Dict[str, Any]]
    ) -> Tuple[Set[int], Dict[int, str]]:
        """GraphQLとREST APIの結果をマージして完全性を確保"""
        merged_resolved_ids = set(graphql_resolved_ids)
        merged_comment_bodies = dict(graphql_comment_bodies)

        # GraphQLで欠落したコメントをREST APIから補完
        graphql_comment_ids = set(graphql_comment_bodies.keys())
        rest_comment_ids = set(rest_all_comments.keys())

        missing_in_graphql = rest_comment_ids - graphql_comment_ids

        if missing_in_graphql:
            self.logger.warning(f"GraphQLで欠落したコメント: {len(missing_in_graphql)}件")
            self.logger.debug(f"欠落コメントID: {sorted(missing_in_graphql)}")

            # 欠落コメントを補完（解決状況は保守的に未解決として扱う）
            for comment_id in missing_in_graphql:
                rest_comment = rest_all_comments[comment_id]
                merged_comment_bodies[comment_id] = rest_comment["body"]

                # 保守的アプローチ: 欠落コメントは未解決として扱う
                # （GraphQLで解決状況が不明なため）
                self.logger.debug(f"REST補完コメント {comment_id}: 未解決として扱う")

        self.logger.info(
            f"ハイブリッド結果: GraphQL={len(graphql_comment_ids)}件, "
            f"REST補完={len(missing_in_graphql)}件, "
            f"解決済み={len(merged_resolved_ids)}件"
        )

        return merged_resolved_ids, merged_comment_bodies

    def get_pr_reviews_with_outside_diff_graphql(
        self, pr_info: GitHubPRInfo, page_size: int = 100
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """GraphQL APIを使用してPRレビューとOutside diff range commentsを取得

        Returns:
            Tuple[List[Dict], List[Dict]]: (全レビューコメント, Outside diff range comments)
        """
        if not self.token:
            self.logger.warning("GraphQL APIにはトークンが必要です")
            return [], []

        all_reviews = []
        outside_diff_comments = []

        # GraphQL クエリ実行のためのヘッダー
        graphql_headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or self.token}",
            "Content-Type": "application/json",
        }

        # ページネーション用の変数
        has_next_page = True
        after_cursor = None
        page_count = 0

        self.logger.info(
            f"GraphQL APIでレビュー・Outside diff取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}"
        )

        while has_next_page:
            page_count += 1
            self.logger.debug(f"GraphQL ページ {page_count} 処理中...")

            query = """
            query($owner: String!, $repo: String!, $number: Int!, $after: String) {
              repository(owner: $owner, name: $repo) {
                pullRequest(number: $number) {
                  reviews(first: 10, after: $after) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      id
                      body
                      state
                      author {
                        login
                      }
                      createdAt
                      updatedAt
                    }
                  }
                }
              }
            }
            """

            variables = {
                "owner": pr_info.owner,
                "repo": pr_info.repo,
                "number": pr_info.pull_number,
                "after": after_cursor,
            }

            try:
                response = self._make_request(
                    "POST",
                    self.graphql_url,
                    json={"query": query, "variables": variables},
                    headers=graphql_headers,
                )

                data = response.json()

                if "errors" in data:
                    error_messages = [
                        error.get("message", str(error)) for error in data["errors"]
                    ]
                    raise APIError(f"GraphQL エラー: {'; '.join(error_messages)}")

                if not data.get("data", {}).get("repository", {}).get("pullRequest"):
                    raise APIError(
                        "GraphQL レスポンスにプルリクエストデータが含まれていません"
                    )

                reviews_data = data["data"]["repository"]["pullRequest"]["reviews"]
                reviews = reviews_data["nodes"]
                page_info = reviews_data["pageInfo"]

                # ページネーション情報を更新
                has_next_page = page_info["hasNextPage"]
                after_cursor = page_info["endCursor"]

                self.logger.debug(f"ページ {page_count}: {len(reviews)} レビュー処理")

                # レビューを処理してOutside diff range commentsを抽出
                for review in reviews:
                    review_body = review.get("body", "")

                    # レビュー全体を保存
                    all_reviews.append(
                        {
                            "id": review["id"],
                            "body": review_body,
                            "state": review.get("state", ""),
                            "author": review.get("author", {}).get("login", ""),
                            "created_at": review.get("createdAt", ""),
                            "updated_at": review.get("updatedAt", ""),
                            "comment_type": "review_comment",
                        }
                    )

                    # Outside diff range commentsを抽出
                    if review_body and "Outside diff range comments" in review_body:
                        try:
                            from .utils.parsers import extract_outside_diff_comments

                            extracted_outside = extract_outside_diff_comments(
                                review_body
                            )
                        except ImportError as e:
                            self.logger.error(f"Outside diff parser import failed: {e}")
                            extracted_outside = []
                        except Exception as e:
                            self.logger.error(f"Outside diff extraction failed: {e}")
                            extracted_outside = []

                        if extracted_outside:
                            self.logger.info(
                                f"Outside diff comments発見: {len(extracted_outside)}件"
                            )

                            # Outside diff commentsを通常のコメント形式に変換
                            for outside_comment in extracted_outside:
                                synthetic_comment = {
                                    "id": f"{review['id']}_outside_{len(outside_diff_comments)}",
                                    "body": f"🔧 **{outside_comment['title']}** (行: {outside_comment['line']})\n\n{outside_comment['content']}",
                                    "path": outside_comment["file_path"],
                                    "line": outside_comment["line"],
                                    "user": {
                                        "login": review.get("author", {}).get(
                                            "login", ""
                                        )
                                    },
                                    "created_at": review.get("createdAt", ""),
                                    "priority": outside_comment["priority"],
                                    "category": outside_comment["category"],
                                    "is_outside_diff": True,
                                    "comment_type": "outside_diff_comment",
                                    "original_review_id": review["id"],
                                }
                                outside_diff_comments.append(synthetic_comment)

                # APIレート制限を考慮した遅延
                time.sleep(0.2)

            except APIError:
                raise
            except Exception as e:
                raise APIError(
                    f"GraphQL API 実行エラー (ページ {page_count}): {str(e)}"
                ) from e

        self.logger.info(
            f"GraphQL API完了: {page_count}ページ, "
            f"レビュー: {len(all_reviews)}件, "
            f"Outside diff: {len(outside_diff_comments)}件"
        )

        return all_reviews, outside_diff_comments

    def get_processing_stats(self) -> ProcessingStats:
        """処理統計を取得（後でCommentProcessorで更新される）"""
        return ProcessingStats()

    def reply_to_comment(
        self, pr_info: GitHubPRInfo, comment_id: int, reply_body: str
    ) -> Dict[str, Any]:
        """プルリクエストのコメントに返信する

        Args:
            pr_info: プルリクエスト情報
            comment_id: 返信対象のコメントID
            reply_body: 返信内容

        Returns:
            作成された返信コメントの情報
        """
        # まず元のコメント情報を取得
        original_comment = self.get_single_comment_detail(pr_info, comment_id)
        if not original_comment:
            raise APIError(f"コメント ID {comment_id} が見つかりません")

        # 返信作成のためのデータ（GitHub API仕様: 返信エンドポイントではbodyのみ）
        reply_data = {
            "body": reply_body,
        }

        # 正しい返信エンドポイント: /comments/{comment_id}/replies
        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments/{comment_id}/replies"

        try:
            self.logger.info(f"コメント {comment_id} に返信中...")
            response = self._make_request("POST", url, json=reply_data)
            result = response.json()

            self.logger.info(f"返信コメント作成成功: ID {result.get('id')}")
            return result

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"コメント返信エラー: {str(e)}") from e

    def create_comment(
        self,
        pr_info: GitHubPRInfo,
        body: str,
        path: str,
        line: int,
        side: str = "RIGHT",
    ) -> Dict[str, Any]:
        """プルリクエストに新しいコメントを作成する

        Args:
            pr_info: プルリクエスト情報
            body: コメント内容
            path: ファイルパス
            line: 行番号
            side: コメント位置 ("LEFT" or "RIGHT")

        Returns:
            作成されたコメントの情報
        """
        comment_data = {"body": body, "path": path, "line": line, "side": side}

        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"

        try:
            self.logger.info(f"新しいコメントを作成中: {path}:{line}")
            response = self._make_request("POST", url, json=comment_data)
            result = response.json()

            self.logger.info(f"コメント作成成功: ID {result.get('id')}")
            return result

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"コメント作成エラー: {str(e)}") from e

    def update_comment(
        self, pr_info: GitHubPRInfo, comment_id: int, new_body: str
    ) -> Dict[str, Any]:
        """既存のコメントを更新する

        Args:
            pr_info: プルリクエスト情報
            comment_id: 更新対象のコメントID
            new_body: 新しいコメント内容

        Returns:
            更新されたコメントの情報
        """
        update_data = {"body": new_body}

        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/comments/{comment_id}"

        try:
            self.logger.info(f"コメント {comment_id} を更新中...")
            response = self._make_request("PATCH", url, json=update_data)
            result = response.json()

            self.logger.info(f"コメント更新成功: ID {result.get('id')}")
            return result

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"コメント更新エラー: {str(e)}") from e

    def delete_comment(self, pr_info: GitHubPRInfo, comment_id: int) -> bool:
        """コメントを削除する

        Args:
            pr_info: プルリクエスト情報
            comment_id: 削除対象のコメントID

        Returns:
            削除が成功したかどうか
        """
        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/comments/{comment_id}"

        try:
            self.logger.info(f"コメント {comment_id} を削除中...")
            response = self._make_request("DELETE", url)

            if response.status_code == 204:
                self.logger.info(f"コメント削除成功: ID {comment_id}")
                return True
            else:
                self.logger.warning(
                    f"コメント削除で予期しないステータス: {response.status_code}"
                )
                return False

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"コメント削除エラー: {str(e)}") from e

    def generate_curl_command(
        self, pr_info: GitHubPRInfo, action: str, **kwargs
    ) -> str:
        """curl コマンドを生成する

        Args:
            pr_info: プルリクエスト情報
            action: 実行するアクション ("reply", "create", "update", "delete")
            **kwargs: アクション固有のパラメータ

        Returns:
            実行可能な curl コマンド
        """
        if not self.token:
            raise APIError("curl コマンド生成にはGitHubトークンが必要です")

        base_headers = [
            '-H "Authorization: token ${GITHUB_TOKEN}"',
            '-H "Accept: application/vnd.github.v3+json"',
            '-H "Content-Type: application/json"',
        ]

        if action == "reply":
            comment_id = kwargs.get("comment_id")
            reply_body = kwargs.get("reply_body")

            if not comment_id or not reply_body:
                raise APIError("reply action には comment_id と reply_body が必要です")

            # 元のコメント情報を取得
            original_comment = self.get_single_comment_detail(pr_info, comment_id)
            if not original_comment:
                raise APIError(f"コメント ID {comment_id} が見つかりません")

            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments/{comment_id}/replies"
            # GitHub API仕様: 返信エンドポイントではbodyのみ
            data = {
                "body": reply_body,
            }

            import json

            data_json = json.dumps(data, ensure_ascii=False)

            return f"""curl -X POST \\
  {url} \\
  {' '.join(base_headers)} \\
  -d '{data_json}'"""

        elif action == "create":
            body = kwargs.get("body")
            path = kwargs.get("path")
            line = kwargs.get("line")
            side = kwargs.get("side", "RIGHT")

            if not all([body, path, line]):
                raise APIError("create action には body, path, line が必要です")

            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
            data = {"body": body, "path": path, "line": line, "side": side}

            import json

            data_json = json.dumps(data, ensure_ascii=False)

            return f"""curl -X POST \\
  {url} \\
  {' '.join(base_headers)} \\
  -d '{data_json}'"""

        elif action == "update":
            comment_id = kwargs.get("comment_id")
            new_body = kwargs.get("new_body")

            if not comment_id or not new_body:
                raise APIError("update action には comment_id と new_body が必要です")

            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/comments/{comment_id}"
            data = {"body": new_body}

            import json

            data_json = json.dumps(data, ensure_ascii=False)

            return f"""curl -X PATCH \\
  {url} \\
  {' '.join(base_headers)} \\
  -d '{data_json}'"""

        elif action == "delete":
            comment_id = kwargs.get("comment_id")

            if not comment_id:
                raise APIError("delete action には comment_id が必要です")

            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/comments/{comment_id}"

            return f"""curl -X DELETE \\
  {url} \\
  {' '.join(base_headers)}"""

        else:
            raise APIError(f"未対応のアクション: {action}")

    def batch_reply_to_comments(
        self, pr_info: GitHubPRInfo, replies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """複数のコメントに一括で返信する

        Args:
            pr_info: プルリクエスト情報
            replies: 返信情報のリスト [{"comment_id": int, "reply_body": str}, ...]

        Returns:
            作成された返信コメントのリスト
        """
        results = []
        errors = []

        self.logger.info(f"{len(replies)} 件のコメントに一括返信中...")

        for i, reply in enumerate(replies, 1):
            try:
                comment_id = reply["comment_id"]
                reply_body = reply["reply_body"]

                self.logger.debug(f"返信 {i}/{len(replies)}: コメントID {comment_id}")

                result = self.reply_to_comment(pr_info, comment_id, reply_body)
                results.append(result)

                # レート制限を考慮した遅延
                if i < len(replies):
                    time.sleep(0.5)

            except Exception as e:
                error_msg = f"コメント {reply.get('comment_id', 'unknown')} の返信に失敗: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            self.logger.warning(
                f"一括返信完了: 成功 {len(results)} 件, エラー {len(errors)} 件"
            )
            for error in errors:
                self.logger.error(f"  - {error}")
        else:
            self.logger.info(f"一括返信完了: 全 {len(results)} 件成功")

        return results
