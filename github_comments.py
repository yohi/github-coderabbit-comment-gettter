#!/usr/bin/env python3
"""
GitHubプルリクエストのインラインコメントを取得するスクリプト

使用方法:
    uvx --from . gh-comments https://github.com/owner/repo/pull/123
"""

import re
import sys
import os
import requests
import click
from typing import List, Dict, Optional

# .envファイルから環境変数を読み込み（安全な方法で）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenvが利用できない場合はスキップ
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
                click.echo(f"プルリクエスト #{pull_number} が見つかりません",
                           err=True)
                return []
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"API リクエストエラー: {e}", err=True)
            return []

    def get_pr_issue_comments(self, owner: str, repo: str,
                              pull_number: int) -> List[Dict]:
        """プルリクエストの一般コメントを取得"""
        url = (f"{self.base_url}/repos/{owner}/{repo}/"
               f"issues/{pull_number}/comments")

        try:
            response = self.session.get(url)
            if response.status_code == 404:
                click.echo(f"プルリクエスト #{pull_number} が見つかりません",
                           err=True)
                return []
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"API リクエストエラー: {e}", err=True)
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


@click.command()
@click.argument('pr_url')
@click.option('--token', help='GitHub API トークン（環境変数 GITHUB_TOKEN も利用可能）')
@click.option('--include-general', is_flag=True, help='一般コメントも含める')
@click.option('--output', '-o', help='出力ファイルパス（指定しない場合は標準出力）')
def main(pr_url: str, token: Optional[str], include_general: bool,
         output: Optional[str]):
    """GitHubプルリクエストのインラインコメントを取得して出力します"""

    try:
        # GitHub クライアントを初期化
        client = GitHubClient(token)

        if not client.token:
            warning_msg = ("警告: GitHub API トークンが設定されていません。"
                           "レート制限に注意してください。")
            click.echo(warning_msg, err=True)
            token_help = "トークンを設定するには: export GITHUB_TOKEN=your_token"
            click.echo(token_help, err=True)
            click.echo()

        # プルリクエストURLを解析
        owner, repo, pull_number = client.parse_pr_url(pr_url)
        click.echo(f"プルリクエスト情報: {owner}/{repo}#{pull_number}")

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
        from datetime import datetime

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
                    click.echo(f"コメント {i+1} の処理中にエラー: {e}", err=True)
                    click.echo(f"コメントデータ: {comment}", err=True)
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
                    click.echo(f"一般コメント {i+1} の処理中にエラー: {e}", err=True)
                    click.echo(f"コメントデータ: {comment}", err=True)
                    continue
        elif include_general:
            output_lines.append("一般コメントはありません。")
            output_lines.append("")

        # 結果を出力
        result = "\n".join(output_lines)

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(result)
            click.echo(f"結果を {output} に保存しました。")
        else:
            click.echo(result)

    except ValueError as e:
        click.echo(f"エラー: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        import traceback
        click.echo(f"予期しないエラー: {e}", err=True)
        click.echo("詳細なエラー情報:", err=True)
        click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
