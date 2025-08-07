#!/usr/bin/env python3
"""
GitHubプルリクエストのインラインコメントからAIエージェント用プロンプトを抽出し、
レビュー対応フォーマットで出力するスクリプト

使用方法:
    uvx --from . gh-review-prompts https://github.com/owner/repo/pull/123
"""

import re
import sys
import os
import requests
from typing import List, Dict, Optional, Tuple

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

    def is_comment_resolved(self, comment: Dict) -> bool:
        """コメントが解決済みかどうかを判定"""
        # GitHub API の review comment には直接的な「解決済み」フラグはないため、
        # 以下の条件で判定する：
        # 1. コメントが更新されている（編集された）
        # 2. コメント本文に解決を示すキーワードが含まれている
        # 3. 後続のコメントで解決が確認されている

        body = comment.get('body', '').lower()
        updated_at = comment.get('updated_at')
        created_at = comment.get('created_at')

        # 解決を示すキーワードをチェック
        resolved_keywords = [
            'resolved', '解決', '修正済み', 'fixed', 'done', '完了',
            '対応済み', '対応完了', 'addressed', 'implemented'
        ]

        for keyword in resolved_keywords:
            if keyword in body:
                return True

        # コメントが更新されている場合（編集による解決の可能性）
        if updated_at and created_at and updated_at != created_at:
            # 更新後のコメントに解決を示す内容があるかチェック
            if any(keyword in body for keyword in ['✅', '☑️', '完了', 'done']):
                return True

        return False


def extract_ai_agent_prompt(comment_body: str) -> Optional[str]:
    """コメント本文からPrompt for AI Agentsブロックを抽出"""
    # Prompt for AI Agentsブロックを検索
    patterns = [
        (r'<details>\s*<summary>🤖 Prompt for AI Agents</summary>\s*'
         r'(.*?)\s*</details>'),
        r'🤖 Prompt for AI Agents.*?\n```\n(.*?)\n```',
        r'Prompt for AI Agents.*?\n```\n(.*?)\n```',
    ]

    for pattern in patterns:
        match = re.search(pattern, comment_body, re.DOTALL | re.IGNORECASE)
        if match:
            prompt_text = match.group(1).strip()
            # HTMLエンティティやマークダウンを除去
            prompt_text = re.sub(r'```[a-zA-Z]*\n?', '', prompt_text)
            prompt_text = re.sub(r'\n```', '', prompt_text)
            prompt_text = prompt_text.strip()
            # 改行を削除して1行にまとめる
            prompt_text = re.sub(r'\s*\n\s*', ' ', prompt_text)
            return prompt_text

    return None


def format_review_prompt(comment: Dict) -> Optional[Tuple[str, str]]:
    """コメントからレビュープロンプト情報を抽出してフォーマット"""
    body = comment.get('body', '')
    path = comment.get('path', '')
    line = comment.get('line') or comment.get('original_line', '')

    # AI Agentプロンプトを抽出
    ai_prompt = extract_ai_agent_prompt(body)
    if not ai_prompt:
        return None

    # ファイルパスと行番号情報を構築
    location_info = f"In {path}"
    if line:
        if isinstance(line, int):
            location_info += f" around line {line},"
        else:
            location_info += f" around lines {line},"
    else:
        location_info += ","

    return location_info, ai_prompt


def main():
    """メイン関数"""

    # 引数解析
    if len(sys.argv) < 2:
        usage_msg = ("使用方法: gh-review-prompts [--output OUTPUT] "
                     "[--exclude-resolved] PR_URL")
        print(usage_msg)
        sys.exit(1)

    output_file = None
    pr_url = None
    exclude_resolved = True  # デフォルトで解決済みを除外

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--output' or arg == '-o':
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
                i += 1
            else:
                print("エラー: --output オプションには値が必要です", file=sys.stderr)
                sys.exit(1)
        elif arg == '--exclude-resolved':
            exclude_resolved = True
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
        print(f"プルリクエスト情報: {owner}/{repo}#{pull_number}", file=sys.stderr)

        # インラインコメント（レビューコメント）を取得
        review_comments = client.get_pr_review_comments(owner, repo,
                                                        pull_number)

        # AI Agentプロンプトを抽出
        prompts = []
        resolved_count = 0
        for comment in review_comments:
            try:
                # 解決済みコメントをスキップ（オプションが指定された場合）
                if exclude_resolved and client.is_comment_resolved(comment):
                    resolved_count += 1
                    continue

                prompt_info = format_review_prompt(comment)
                if prompt_info:
                    prompts.append(prompt_info)
            except Exception as e:
                print(f"コメント処理中にエラー: {e}", file=sys.stderr)
                continue

        if exclude_resolved and resolved_count > 0:
            msg = f"解決済みコメント {resolved_count} 件をスキップしました"
            print(msg, file=sys.stderr)

        # 結果を整形
        output_lines = []

        if prompts:
            prompt_text1 = ("次のAIエージェント用レビュー指摘プロンプトを"
                            "ひとつずつ対応してください。")
            output_lines.append(prompt_text1)

            caution_text = ("ただし、指摘が正しいとは限らないので規約や環境、"
                            "構造などを考慮し指摘されたことをしっかり精査した上で"
                            "対応可否の判断を下すこと。")
            output_lines.append(caution_text)

            instruction_text = ("最後に対応不要と判断したプロンプトに関しては"
                                "その書き出しと、対応不要と判断した理由を"
                                "下記のように出力してください。")
            output_lines.append(instruction_text)

            output_lines.append("例）")
            output_lines.append("```")
            output_lines.append("1. In backend-auth/server.js around line 44,")

            example1 = ("    - 開発・ローカル環境ではMemoryStoreで十分。"
                        "本番環境では別途Redis/MongoDBを使用するべきですが、"
                        "この段階では不要。")
            output_lines.append(example1)
            output_lines.append("")

            example2_title = ("2. In backend-auth/server.js "
                              "around lines 127 to 163,")
            output_lines.append(example2_title)

            example2_text = ("    - シンプルな開発用認証サーバーでは、"
                             "HTMLのインライン埋め込みは許容範囲。"
                             "テンプレートエンジンの導入は複雑性を増すだけ。")
            output_lines.append(example2_text)
            output_lines.append("")
            output_lines.append("...")
            output_lines.append("```")
            output_lines.append("")

            commit_instruction = ("対応が全て終わったら"
                                  "Gitにコミット・プッシュを行ってください。")
            output_lines.append(commit_instruction)
            output_lines.append("")
            output_lines.append("# Prompt For AI Agents List")
            output_lines.append("")

            for i, (location, prompt) in enumerate(prompts):
                output_lines.append(f"- {prompt}")
                if i < len(prompts) - 1:  # 最後の項目以外は空行を追加
                    output_lines.append("")
        else:
            output_lines.append("AIエージェント用プロンプトは見つかりませんでした。")
            output_lines.append("")

        # 結果を出力
        result = "\n".join(output_lines)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"結果を {output_file} に保存しました。", file=sys.stderr)
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
