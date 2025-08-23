#!/usr/bin/env python3
"""Curlを使用したGitHub PR コメント返信機能

GitHub REST APIをcurlコマンドで直接呼び出してコメントに返信する
"""

import json
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class CurlReplyError(Exception):
    """Curl返信操作でのエラー"""

    pass


class GitHubCurlReply:
    """CurlでGitHub APIを使用したコメント返信クラス"""

    def __init__(self, token: str):
        """
        初期化

        Args:
            token: GitHub APIトークン
        """
        self.token = token
        self.base_url = "https://api.github.com"

        # curlの基本オプション
        self.curl_base_args = [
            "curl",
            "-s",  # silent mode
            "-H",
            f"Authorization: Bearer {os.getenv('GITHUB_TOKEN', token)}",
            "-H",
            "Accept: application/vnd.github.v3+json",
            "-H",
            "Content-Type: application/json",
            "-H",
            "User-Agent: github-review-prompts-curl/1.0",
        ]

    def _run_curl(
        self, method: str, url: str, data: Optional[Dict] = None
    ) -> Tuple[Dict, int]:
        """
        Curlコマンドを実行してAPIを呼び出す

        Args:
            method: HTTPメソッド (GET, POST, PUT, DELETE)
            url: API URL
            data: 送信するJSONデータ

        Returns:
            レスポンスデータとステータスコードのタプル

        Raises:
            CurlReplyError: Curlコマンド実行時のエラー
        """
        cmd = self.curl_base_args.copy()

        # HTTPメソッドを設定
        if method.upper() != "GET":
            cmd.extend(["-X", method.upper()])

        # データがある場合は追加
        if data is not None:
            cmd.extend(["-d", json.dumps(data)])

        # ステータスコードも取得
        cmd.extend(["-w", "\\n%{http_code}"])

        # URL追加
        cmd.append(url)

        logger.debug(f"Curl command: {' '.join(cmd[:3])} ... {cmd[-1]}")

        try:
            # curlコマンド実行
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise CurlReplyError(f"Curl command failed: {result.stderr}")

            # レスポンスを分解
            output_lines = result.stdout.strip().split("\\n")
            status_code = int(output_lines[-1])
            response_body = "\\n".join(output_lines[:-1])

            # JSONレスポンスをパース
            try:
                response_data = json.loads(response_body) if response_body else {}
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                logger.error(f"Response body: {response_body}")
                response_data = {"raw_response": response_body}

            logger.debug(f"HTTP {status_code}: {response_body[:200]}...")

            return response_data, status_code

        except subprocess.TimeoutExpired:
            raise CurlReplyError("Curl command timed out")
        except Exception as e:
            raise CurlReplyError(f"Curl execution error: {e}")

    def test_authentication(self) -> Dict:
        """
        認証をテストしてユーザー情報を取得

        Returns:
            ユーザー情報

        Raises:
            CurlReplyError: 認証失敗
        """
        url = f"{self.base_url}/user"

        try:
            response, status_code = self._run_curl("GET", url)

            if status_code == 200:
                logger.info(f"認証成功: {response.get('login', 'Unknown')}")
                return response
            elif status_code == 401:
                raise CurlReplyError("認証失敗: トークンが無効です")
            else:
                raise CurlReplyError(f"認証テスト失敗: HTTP {status_code}")

        except CurlReplyError:
            raise
        except Exception as e:
            raise CurlReplyError(f"認証テストエラー: {e}")

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> Dict:
        """
        プルリクエスト情報を取得

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            pr_number: PR番号

        Returns:
            PR情報
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            response, status_code = self._run_curl("GET", url)

            if status_code == 200:
                return response
            elif status_code == 404:
                raise CurlReplyError(f"PR not found: {owner}/{repo}#{pr_number}")
            else:
                raise CurlReplyError(f"PR情報取得失敗: HTTP {status_code}")

        except CurlReplyError:
            raise
        except Exception as e:
            raise CurlReplyError(f"PR情報取得エラー: {e}")

    def get_comment_info(self, owner: str, repo: str, comment_id: int) -> Dict:
        """
        コメント情報を取得

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            comment_id: コメントID

        Returns:
            コメント情報
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/comments/{comment_id}"

        try:
            response, status_code = self._run_curl("GET", url)

            if status_code == 200:
                return response
            elif status_code == 404:
                raise CurlReplyError(f"Comment not found: {comment_id}")
            else:
                raise CurlReplyError(f"コメント情報取得失敗: HTTP {status_code}")

        except CurlReplyError:
            raise
        except Exception as e:
            raise CurlReplyError(f"コメント情報取得エラー: {e}")

    def reply_to_review_comment(
        self, owner: str, repo: str, comment_id: int, reply_text: str
    ) -> Dict:
        """
        レビューコメントに返信

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            comment_id: 返信対象のコメントID
            reply_text: 返信テキスト

        Returns:
            作成された返信コメント情報

        Raises:
            CurlReplyError: 返信作成失敗
        """
        # まず対象コメント情報を取得してPR番号を確認
        comment_info = self.get_comment_info(owner, repo, comment_id)
        pr_url = comment_info.get("pull_request_url", "")

        if not pr_url:
            raise CurlReplyError("PR URLがコメント情報から取得できません")

        # PR番号を抽出
        pr_number = pr_url.split("/")[-1]

        # 返信コメント作成のAPIエンドポイント
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        # 返信データ
        reply_data = {"body": reply_text, "in_reply_to": comment_id}

        try:
            response, status_code = self._run_curl("POST", url, reply_data)

            if status_code == 201:
                logger.info(f"返信コメント作成成功: {response.get('id')}")
                return response
            elif status_code == 422:
                error_msg = response.get("message", "Validation failed")
                raise CurlReplyError(f"返信作成バリデーションエラー: {error_msg}")
            elif status_code == 403:
                raise CurlReplyError("返信作成権限がありません")
            elif status_code == 404:
                raise CurlReplyError("対象のコメントまたはPRが見つかりません")
            else:
                raise CurlReplyError(f"返信作成失敗: HTTP {status_code}")

        except CurlReplyError:
            raise
        except Exception as e:
            raise CurlReplyError(f"返信作成エラー: {e}")

    def create_pr_comment(
        self, owner: str, repo: str, pr_number: int, comment_text: str
    ) -> Dict:
        """
        PR全体に対する新しいコメントを作成

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            pr_number: PR番号
            comment_text: コメントテキスト

        Returns:
            作成されたコメント情報
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        comment_data = {"body": comment_text}

        try:
            response, status_code = self._run_curl("POST", url, comment_data)

            if status_code == 201:
                logger.info(f"PRコメント作成成功: {response.get('id')}")
                return response
            elif status_code == 422:
                error_msg = response.get("message", "Validation failed")
                raise CurlReplyError(f"コメント作成バリデーションエラー: {error_msg}")
            elif status_code == 403:
                raise CurlReplyError("コメント作成権限がありません")
            elif status_code == 404:
                raise CurlReplyError("対象のPRが見つかりません")
            else:
                raise CurlReplyError(f"コメント作成失敗: HTTP {status_code}")

        except CurlReplyError:
            raise
        except Exception as e:
            raise CurlReplyError(f"コメント作成エラー: {e}")

    def batch_reply(
        self, owner: str, repo: str, replies: List[Dict[str, Union[str, int]]]
    ) -> List[Dict]:
        """
        複数のコメントに一括返信

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            replies: 返信リスト [{"comment_id": int, "reply": str}, ...]

        Returns:
            作成された返信コメントのリスト
        """
        results = []
        errors = []

        for i, reply_info in enumerate(replies, 1):
            comment_id = reply_info.get("comment_id")
            reply_text = reply_info.get("reply")

            if not comment_id or not reply_text:
                error = f"返信 {i}: comment_id または reply が不正です"
                errors.append(error)
                logger.error(error)
                continue

            try:
                logger.info(f"返信 {i}/{len(replies)}: コメント {comment_id}")
                result = self.reply_to_review_comment(
                    owner, repo, comment_id, reply_text
                )
                results.append(result)

                # APIレート制限対策で少し待機
                import time

                time.sleep(1)

            except CurlReplyError as e:
                error = f"返信 {i} 失敗 (コメント {comment_id}): {e}"
                errors.append(error)
                logger.error(error)

        if errors:
            logger.warning(f"一括返信完了: {len(results)} 成功, {len(errors)} 失敗")
            for error in errors:
                logger.warning(f"  {error}")
        else:
            logger.info(f"一括返信完了: {len(results)} 件すべて成功")

        return results


def get_github_token() -> str:
    """GitHub トークンを取得"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ エラー: GITHUB_TOKEN 環境変数が設定されていません。")
        print("")
        print("以下のコマンドで設定してください:")
        print("  export GITHUB_TOKEN=your_github_token_here")
        sys.exit(1)
    return token


def parse_pr_url(pr_url: str) -> Tuple[str, str, int]:
    """
    PR URLをパースしてowner, repo, pr_numberを抽出

    Args:
        pr_url: GitHub PR URL

    Returns:
        (owner, repo, pr_number) のタプル

    Raises:
        ValueError: URL形式が不正
    """
    import re

    # GitHub PR URLの正規表現パターン
    pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, pr_url)

    if not match:
        raise ValueError(f"不正なPR URL形式: {pr_url}")

    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


if __name__ == "__main__":
    # 簡単なテスト用
    logging.basicConfig(level=logging.INFO)

    token = get_github_token()
    client = GitHubCurlReply(token)

    try:
        # 認証テスト
        user_info = client.test_authentication()
        print(f"✅ 認証成功: {user_info['login']}")

    except CurlReplyError as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)
