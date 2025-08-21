"""GitHub API クライアント"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Any
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .models import (
    APIError, AuthenticationError, RateLimitError, 
    ReviewComment, GitHubPRInfo, ProcessingStats
)
from .utils.parsers import parse_pr_url
from .utils.validators import validate_github_token, sanitize_content


class GitHubClient:
    """GitHub API クライアント（REST API + GraphQL API対応）"""
    
    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.github.com"):
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
            
            self.session.headers.update({
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-Review-Prompts-AI-Agent/1.0.0"
            })
            self.logger.info(f"GitHub認証設定完了: {token_type} token")
        else:
            self.logger.warning("GitHub トークンが設定されていません。レート制限に注意してください。")
    
    def parse_pr_url(self, pr_url: str) -> GitHubPRInfo:
        """プルリクエストURLを解析してGitHubPRInfoオブジェクトを返す"""
        try:
            owner, repo, pull_number = parse_pr_url(pr_url)
            return GitHubPRInfo(
                owner=owner,
                repo=repo, 
                pull_number=pull_number,
                url=pr_url
            )
        except ValueError as e:
            raise APIError(f"プルリクエストURL解析エラー: {str(e)}") from e
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """共通のリクエスト処理（エラーハンドリング付き）"""
        try:
            response = self.session.request(method, url, **kwargs)
            
            # レート制限チェック
            if response.status_code == 429:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_time = max(reset_time - int(time.time()), 1)
                raise RateLimitError(
                    f"API レート制限に達しました。{wait_time}秒後に再試行してください。",
                    status_code=429,
                    response_data={"reset_time": reset_time, "wait_time": wait_time}
                )
            
            # 認証エラー
            if response.status_code == 401:
                raise AuthenticationError("GitHub API 認証に失敗しました。トークンを確認してください。", status_code=401)
            
            # 権限不足
            if response.status_code == 403:
                error_msg = "GitHub API アクセスが拒否されました。"
                if "rate limit" in response.text.lower():
                    error_msg += " レート制限に達している可能性があります。"
                else:
                    error_msg += " トークンの権限を確認してください。"
                raise APIError(error_msg, status_code=403)
            
            # その他のHTTPエラー
            if not response.ok:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                raise APIError(
                    f"GitHub API エラー: {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            return response
            
        except requests.exceptions.RequestException as e:
            raise APIError(f"GitHub API リクエストエラー: {str(e)}") from e
    
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
                    "email": user_data.get("email")
                },
                "rate_limit": rate_limit
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
                "base_repo": pr_data.get("base", {}).get("repo", {}).get("full_name", ""),
                "head_repo": pr_data.get("head", {}).get("repo", {}).get("full_name", ""),
                "commits": pr_data.get("commits", 0),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": pr_data.get("changed_files", 0)
            }
            
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"プルリクエスト情報取得エラー: {str(e)}") from e
    
    def get_pr_review_comments(self, pr_info: GitHubPRInfo, page_size: int = 100) -> List[Dict[str, Any]]:
        """プルリクエストのレビューコメントを全件取得（ページネーション対応）"""
        all_comments = []
        page = 1
        
        self.logger.info(f"レビューコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")
        
        while True:
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
            params = {
                "page": page,
                "per_page": min(page_size, 100)  # GitHub APIの最大値は100
            }
            
            try:
                response = self._make_request("GET", url, params=params)
                page_comments = response.json()
                
                if not page_comments:  # 空のページに到達
                    break
                
                all_comments.extend(page_comments)
                self.logger.debug(f"ページ {page}: {len(page_comments)} コメント取得")
                
                # 最後のページかどうか判定
                if len(page_comments) < page_size:
                    break
                
                page += 1
                
                # レート制限を考慮した遅延
                time.sleep(0.1)
                
            except APIError:
                raise
            except Exception as e:
                raise APIError(f"レビューコメント取得エラー (ページ {page}): {str(e)}") from e
        
        self.logger.info(f"レビューコメント取得完了: {len(all_comments)} 件")
        return all_comments
    
    def get_pr_reviews(self, pr_info: GitHubPRInfo, page_size: int = 100) -> List[Dict[str, Any]]:
        """プルリクエストのレビュー一覧を取得"""
        all_reviews = []
        page = 1
        
        self.logger.info(f"レビュー一覧取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")
        
        while True:
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/reviews"
            params = {
                "page": page,
                "per_page": min(page_size, 100)
            }
            
            try:
                response = self._make_request("GET", url, params=params)
                page_reviews = response.json()
                
                if not page_reviews:
                    break
                
                all_reviews.extend(page_reviews)
                self.logger.debug(f"ページ {page}: {len(page_reviews)} レビュー取得")
                
                if len(page_reviews) < page_size:
                    break
                
                page += 1
                time.sleep(0.1)
                
            except APIError:
                raise
            except Exception as e:
                raise APIError(f"レビュー取得エラー (ページ {page}): {str(e)}") from e
        
        self.logger.info(f"レビュー取得完了: {len(all_reviews)} 件")
        return all_reviews
    
    def get_single_comment_detail(self, pr_info: GitHubPRInfo, comment_id: int) -> Optional[Dict[str, Any]]:
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
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # ページネーション用の変数
        has_next_page = True
        after_cursor = None
        page_count = 0
        
        self.logger.info(f"GraphQL APIで解決済みコメント取得開始: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")
        
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
                "after": after_cursor
            }
            
            try:
                response = self._make_request(
                    "POST",
                    self.graphql_url,
                    json={"query": query, "variables": variables},
                    headers=graphql_headers
                )
                
                data = response.json()
                
                if "errors" in data:
                    error_messages = [error.get("message", str(error)) for error in data["errors"]]
                    raise APIError(f"GraphQL エラー: {'; '.join(error_messages)}")
                
                if not data.get("data", {}).get("repository", {}).get("pullRequest"):
                    raise APIError("GraphQL レスポンスにプルリクエストデータが含まれていません")
                
                review_threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]
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
                        self.logger.warning("スレッド内に50を超えるコメントがあります。一部取得されていない可能性があります。")
                    
                    if thread["isResolved"]:
                        # CodeRabbitのコメントを含むスレッドかチェック
                        has_coderabbit = any(
                            "coderabbitai" in comment.get("author", {}).get("login", "").lower()
                            for comment in comments_data["nodes"]
                            if comment.get("author")
                        )
                        
                        if has_coderabbit:
                            coderabbit_resolved_count += 1
                        
                        # 解決済みスレッドの全コメントIDを記録
                        for comment in comments_data["nodes"]:
                            if comment["databaseId"]:
                                resolved_comment_ids.add(comment["databaseId"])
                    
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
                raise APIError(f"GraphQL API 実行エラー (ページ {page_count}): {str(e)}") from e
        
        self.logger.info(
            f"GraphQL API完了: {page_count}ページ, {total_threads_processed}スレッド処理, "
            f"CodeRabbit解決済み: {coderabbit_resolved_count}件, "
            f"コメント本文: {len(comment_bodies)}件"
        )
        
        return resolved_comment_ids, comment_bodies
    
    def get_processing_stats(self) -> ProcessingStats:
        """処理統計を取得（後でCommentProcessorで更新される）"""
        return ProcessingStats()

    def reply_to_comment(self, pr_info: GitHubPRInfo, comment_id: int, reply_body: str) -> Dict[str, Any]:
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
        
        # 返信作成のためのデータ
        reply_data = {
            "body": reply_body,
            "in_reply_to": comment_id,
            "path": original_comment["path"],
            "line": original_comment.get("line"),
            "side": original_comment.get("side", "RIGHT")
        }
        
        # diff_hunk の情報も必要な場合は追加
        if original_comment.get("diff_hunk"):
            reply_data["diff_hunk"] = original_comment["diff_hunk"]
        
        url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
        
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

    def create_comment(self, pr_info: GitHubPRInfo, body: str, path: str, line: int, side: str = "RIGHT") -> Dict[str, Any]:
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
        comment_data = {
            "body": body,
            "path": path,
            "line": line,
            "side": side
        }
        
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

    def update_comment(self, pr_info: GitHubPRInfo, comment_id: int, new_body: str) -> Dict[str, Any]:
        """既存のコメントを更新する
        
        Args:
            pr_info: プルリクエスト情報
            comment_id: 更新対象のコメントID
            new_body: 新しいコメント内容
            
        Returns:
            更新されたコメントの情報
        """
        update_data = {
            "body": new_body
        }
        
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
                self.logger.warning(f"コメント削除で予期しないステータス: {response.status_code}")
                return False
                
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"コメント削除エラー: {str(e)}") from e

    def generate_curl_command(self, pr_info: GitHubPRInfo, action: str, **kwargs) -> str:
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
            f'-H "Authorization: token {self.token}"',
            '-H "Accept: application/vnd.github.v3+json"',
            '-H "Content-Type: application/json"'
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
            
            url = f"{self.base_url}/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/comments"
            data = {
                "body": reply_body,
                "in_reply_to": comment_id,
                "path": original_comment["path"],
                "line": original_comment.get("line"),
                "side": original_comment.get("side", "RIGHT")
            }
            
            if original_comment.get("diff_hunk"):
                data["diff_hunk"] = original_comment["diff_hunk"]
            
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
            data = {
                "body": body,
                "path": path,
                "line": line,
                "side": side
            }
            
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
            data = {
                "body": new_body
            }
            
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

    def batch_reply_to_comments(self, pr_info: GitHubPRInfo, replies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            self.logger.warning(f"一括返信完了: 成功 {len(results)} 件, エラー {len(errors)} 件")
            for error in errors:
                self.logger.error(f"  - {error}")
        else:
            self.logger.info(f"一括返信完了: 全 {len(results)} 件成功")
        
        return results