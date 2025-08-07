#!/usr/bin/env python3
"""
GitHubプルリクエストのインラインコメントを取得するスクリプト（uvx用簡略版）

使用方法:
    uvx --from . gh-comments-simple https://github.com/owner/repo/pull/123
"""

import re
import sys
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime

# .envファイルから環境変数を読み込み（安全な方法で）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class GitHubClient:
    """GitHub API クライアント"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.session = requests.Session()

        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            })

    def parse_pr_url(self, pr_url: str) -> tuple[str, str, int]:
        """プルリクエストURLからowner, repo, pull_numberを抽出"""
        pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, pr_url)

        if not match:
            raise ValueError(f"無効なプルリクエストURL: {pr_url}")

        owner, repo, pull_number = match.groups()
        return owner, repo, int(pull_number)

    def get_pr_review_comments(self, owner: str, repo: str,
                               pull_number: int) -> List[Dict]:
        """プルリクエストのレビューコメント（インラインコメント）を取得"""
        url = (f"{self.base_url}/repos/{owner}/{repo}/"
               f"pulls/{pull_number}/comments")

        try:
            response = self.session.get(url)
            if response.status_code == 404:
                print(f"プルリクエスト #{pull_number} が見つかりません",
                      file=sys.stderr)
                return []
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API リクエストエラー: {e}", file=sys.stderr)
            return []

    def get_pr_issue_comments(self, owner: str, repo: str,
                              pull_number: int) -> List[Dict]:
        """プルリクエストの一般コメントを取得"""
        url = (f"{self.base_url}/repos/{owner}/{repo}/"
               f"issues/{pull_number}/comments")

        try:
            response = self.session.get(url)
            if response.status_code == 404:
                print(f"プルリクエスト #{pull_number} が見つかりません",
                      file=sys.stderr)
                return []
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API リクエストエラー: {e}", file=sys.stderr)
            return []


def format_comment(comment: Dict, comment_type: str) -> str:
    """コメントを指定されたフォーマットで整形"""
    user_info = comment.get('user')
    user = user_info.get('login', 'Unknown') if user_info else 'Unknown'
    created_at = comment.get('created_at') or 'Unknown'
    body = comment.get('body') or ''

    # インラインコメントの場合は追加情報を含める
    if comment_type == 'review':
        path = comment.get('path', '')
        line = comment.get('line') or comment.get('original_line', '')
        position = comment.get('position', '')

        header = f"[{comment_type.upper()}] {user} ({created_at})"
        if path:
            header += f" - {path}"
        if line:
            header += f":L{line}"
        if position:
            header += f" (pos:{position})"

        return f"{header}\n{body}\n{'-' * 80}"
    else:
        header = f"[{comment_type.upper()}] {user} ({created_at})"
        return f"{header}\n{body}\n{'-' * 80}"


def main():
    """メイン関数"""

    # 引数解析
    if len(sys.argv) < 2:
        print("使用方法: gh-comments-simple [--include-general] [-o OUTPUT] PR_URL")
        sys.exit(1)

    include_general = '--include-general' in sys.argv
    output_file = None
    pr_url = None

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--include-general':
            include_general = True
        elif arg == '-o' and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 1
        elif not arg.startswith('--') and not arg.startswith('-'):
            pr_url = arg
        i += 1

    if not pr_url:
        print("エラー: プルリクエストURLが指定されていません", file=sys.stderr)
        sys.exit(1)

    try:
        # GitHub クライアントを初期化
        client = GitHubClient()

        if not client.token:
            warning_msg = ("警告: GitHub API トークンが設定されていません。"
                           "レート制限に注意してください。")
            print(warning_msg, file=sys.stderr)
            print("トークンを設定するには: export GITHUB_TOKEN=your_token",
                  file=sys.stderr)
            print(file=sys.stderr)

        # プルリクエストURLを解析
        owner, repo, pull_number = client.parse_pr_url(pr_url)
        print(f"プルリクエスト情報: {owner}/{repo}#{pull_number}")

        # インラインコメント（レビューコメント）を取得
        review_comments = client.get_pr_review_comments(owner, repo,
                                                        pull_number)

        # 一般コメントも取得する場合
        issue_comments = []
        if include_general:
            issue_comments = client.get_pr_issue_comments(owner, repo,
                                                          pull_number)

        # 結果を整形
        output_lines = []

        output_lines.append("GitHub Pull Request Comments")
        output_lines.append(f"Repository: {owner}/{repo}")
        output_lines.append(f"Pull Request: #{pull_number}")
        output_lines.append(f"URL: {pr_url}")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        output_lines.append(f"取得日時: {current_time}")
        output_lines.append("=" * 80)
        output_lines.append("")

        # インラインコメント
        if review_comments:
            output_lines.append(f"インラインコメント ({len(review_comments)}件):")
            output_lines.append("")
            for i, comment in enumerate(review_comments):
                try:
                    formatted_comment = format_comment(comment, 'review')
                    output_lines.append(formatted_comment)
                    output_lines.append("")
                except Exception as e:
                    print(f"コメント {i+1} の処理中にエラー: {e}", file=sys.stderr)
                    continue
        else:
            output_lines.append("インラインコメントはありません。")
            output_lines.append("")

        # 一般コメント
        if include_general and issue_comments:
            output_lines.append(f"一般コメント ({len(issue_comments)}件):")
            output_lines.append("")
            for i, comment in enumerate(issue_comments):
                try:
                    formatted_comment = format_comment(comment, 'general')
                    output_lines.append(formatted_comment)
                    output_lines.append("")
                except Exception as e:
                    print(f"一般コメント {i+1} の処理中にエラー: {e}", file=sys.stderr)
                    continue
        elif include_general:
            output_lines.append("一般コメントはありません。")
            output_lines.append("")

        # 結果を出力
        result = "\n".join(output_lines)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"結果を {output_file} に保存しました。")
        else:
            print(result)

    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"予期しないエラー: {e}", file=sys.stderr)
        print("詳細なエラー情報:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
