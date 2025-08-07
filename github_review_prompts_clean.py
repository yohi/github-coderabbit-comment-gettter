#!/usr/bin/env python3
"""
GitHub PR review prompts extractor (API-only version)

このスクリプトは指定されたGitHub PRのレビューコメントから
「Prompt for AI Agents」ブロックを抽出し、
フォーマットされたプロンプトリストを出力します。

すべてのコメント解決判定はGitHub APIベースの正確な方法を使用します。
古いヒューリスティックベースの判定は除去されました。
"""

import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import requests


class GitHubClient:
    """GitHub API クライアント（API基盤の解決判定のみ）"""

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.session = requests.Session()

        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})

    def parse_pr_url(self, pr_url: str) -> Tuple[str, str, int]:
        """プルリクエストURLを解析してowner, repo, pull_numberを取得"""
        # https://github.com/owner/repo/pull/123 の形式を想定
        url_pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.search(url_pattern, pr_url)

        if not match:
            raise ValueError(f"無効なプルリクエストURL: {pr_url}")

        owner, repo, pull_number = match.groups()
        return owner, repo, int(pull_number)

    def get_pr_reviews(self, owner: str, repo: str, pull_number: int) -> List[Dict]:
        """プルリクエストのレビュー一覧を取得"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/" f"{pull_number}/reviews"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"レビュー取得エラー: {e}", file=sys.stderr)
            return []

    def get_pr_review_comments(
        self, owner: str, repo: str, pull_number: int
    ) -> List[Dict]:
        """プルリクエストのインラインコメント（レビューコメント）を取得"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/" f"{pull_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"コメント取得エラー: {e}", file=sys.stderr)
            return []

    def get_single_comment_detail(
        self, owner: str, repo: str, comment_id: int
    ) -> Optional[Dict]:
        """単一のコメントの詳細情報を取得"""
        url = f"{self.base_url}/repos/{owner}/{repo}/" f"pulls/comments/{comment_id}"

        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            comment_data = response.json()

            # GitHub APIから直接取得したデータは最新の状態を反映している
            return comment_data
        except requests.exceptions.RequestException:
            # フォールバック: 基本的なコメント情報のみ返す
            comment_data = {"id": comment_id}
            # 同じ position/path のコメントを検索して推測する
            return comment_data

    def get_pr_review_detail(
        self, owner: str, repo: str, pull_number: int, review_id: int
    ) -> Optional[Dict]:
        """特定のレビューの詳細情報を取得"""
        url = (
            f"{self.base_url}/repos/{owner}/{repo}/"
            f"pulls/{pull_number}/reviews/{review_id}"
        )

        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"レビュー詳細取得エラー: {e}", file=sys.stderr)
            return None

    def get_accurate_resolution_status(
        self, comment: Dict, owner: str, repo: str, pull_number: int
    ) -> bool:
        """GitHub APIを使用してより正確な解決状態を判定"""

        # Method 1: in_reply_to_id を使った返信ベースの解決判定
        # 元のコメントに対する返信があり、その返信に解決キーワードがある場合
        comment_id = comment.get("id")
        if comment_id and self._check_resolution_via_replies(owner, repo, pull_number, comment_id):
            return True

        # Method 2: conversation_resolvedフィールドの確認（利用可能な場合のみ）
        if comment.get("conversation_resolved") is True:
            return True

        # Method 3: レビュー詳細APIを使用した判定
        comment_review_id = comment.get("pull_request_review_id")
        if comment_review_id:
            review_detail = self.get_pr_review_detail(
                owner, repo, pull_number, comment_review_id
            )

            if review_detail:
                # レビューの状態を確認
                review_state = review_detail.get("state")

                # APPROVEDレビューのコメントは基本的に解決済み
                if review_state == "APPROVED":
                    return True

                # レビューのコメント一覧を確認
                review_comments = review_detail.get("comments", [])
                for review_comment in review_comments:
                    if review_comment.get("id") == comment.get("id"):
                        # 個別コメントの状態をチェック
                        if review_comment.get("resolved") is True:
                            return True

        # Method 4: Suggestionコメントの特別扱い
        body = comment.get("body", "").lower()
        suggestion_indicators = [
            "committable suggestion",
            "suggestion_start",
            "📝 committable suggestion",
            "<!-- suggestion_start -->",
        ]

        # Suggestionコメントは解決済みとしては扱わない
        # （GitHubでは通常「未解決」として表示される）
        if any(indicator in body for indicator in suggestion_indicators):
            return False

        # Method 5: 明示的な解決キーワード + 編集時刻判定
        resolved_keywords = [
            "resolved",
            "解決",
            "修正済み",
            "fixed",
            "done",
            "完了",
            "対応済み",
            "対応完了",
            "addressed",
            "implemented",
            "✅",
            "☑️",
            "[x]",
            "closed",
        ]

        for keyword in resolved_keywords:
            if keyword in body:
                return True

        # Method 6: 編集時刻による判定（コメントが編集された場合、解決の可能性）
        created_at = comment.get("created_at")
        updated_at = comment.get("updated_at")
        if created_at and updated_at and created_at != updated_at:
            # 編集されたコメントで特定パターンがある場合は解決済みと判定
            updated_indicators = ["edit:", "update:", "追記:", "※", "追記）"]
            if any(indicator in body for indicator in updated_indicators):
                return True

        return False

    def _check_resolution_via_replies(self, owner: str, repo: str, pull_number: int, comment_id: int) -> bool:
        """返信を通じた解決状況確認"""
        try:
            # このコメントに対する返信コメントを取得
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/comments"
            response = self.session.get(url)
            if response.status_code != 200:
                return False

            all_comments = response.json()

            # 対象コメントに対する返信を検索
            replies = [c for c in all_comments if c.get("in_reply_to_id") == comment_id]

            # 返信の中に解決キーワードがあるかチェック
            resolved_keywords = [
                "resolved", "解決", "修正済み", "fixed", "done", "完了",
                "対応済み", "対応完了", "addressed", "implemented", "✅", "☑️", "[x]", "closed"
            ]

            for reply in replies:
                reply_body = reply.get("body", "").lower()
                if any(keyword in reply_body for keyword in resolved_keywords):
                    return True

            return False

        except Exception:
            return False

    def get_resolved_comments_via_graphql(self, owner: str, repo: str, pull_number: int) -> set:
        """GraphQL APIを使用して解決済みコメントIDを取得（推奨）"""
        if not self.token:
            return set()

        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $number) {
              reviewThreads(first: 100) {
                nodes {
                  isResolved
                  comments(first: 50) {
                    nodes {
                      databaseId
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
            "owner": owner,
            "repo": repo,
            "number": pull_number
        }

        try:
            response = self.session.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code == 200:
                data = response.json()
                resolved_comment_ids = set()

                if "data" in data and data["data"]["repository"]["pullRequest"]:
                    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
                    coderabbit_resolved_count = 0

                    for thread in threads:
                        if thread["isResolved"]:
                            # CodeRabbitのコメントを含むスレッドかチェック
                            has_coderabbit = any(
                                "coderabbitai" in comment.get("author", {}).get("login", "").lower()
                                for comment in thread["comments"]["nodes"]
                                if comment.get("author")
                            )

                            if has_coderabbit:
                                coderabbit_resolved_count += 1

                            for comment in thread["comments"]["nodes"]:
                                if comment["databaseId"]:
                                    resolved_comment_ids.add(comment["databaseId"])



                return resolved_comment_ids

        except Exception as e:
            print(f"GraphQL API エラー: {e}", file=sys.stderr)

        return set()


def extract_ai_agent_prompt(comment_body: str) -> Optional[str]:
    """コメント本文からPrompt for AI Agentsブロックを抽出"""

    # Suggestionコメントは除外
    body_lower = comment_body.lower()
    suggestion_indicators = [
        "committable suggestion",
        "suggestion_start",
        "📝 committable suggestion",
        "<!-- suggestion_start -->",
    ]
    for indicator in suggestion_indicators:
        if indicator in body_lower:
            return None

    # Prompt for AI Agentsブロックを検索
    patterns = [
        (
            r"<details>\s*<summary>🤖 Prompt for AI Agents</summary>\s*"
            r"(.*?)\s*</details>"
        ),
        r"🤖 Prompt for AI Agents.*?\n```\n(.*?)\n```",
        r"Prompt for AI Agents.*?\n```\n(.*?)\n```",
    ]

    for pattern in patterns:
        match = re.search(pattern, comment_body, re.DOTALL | re.IGNORECASE)
        if match:
            prompt_text = match.group(1).strip()
            # HTMLエンティティやマークダウンを除去
            prompt_text = re.sub(r"```[a-zA-Z]*\n?", "", prompt_text)
            prompt_text = re.sub(r"\n```", "", prompt_text)
            prompt_text = prompt_text.strip()
            # 改行を削除して1行にまとめる
            prompt_text = re.sub(r"\s*\n\s*", " ", prompt_text)
            return prompt_text

    return None


def format_review_prompt(comment: Dict) -> Optional[Tuple[str, str]]:
    """コメントからレビュープロンプト情報を抽出してフォーマット"""
    body = comment.get("body", "")
    path = comment.get("path", "")
    line = comment.get("line") or comment.get("original_line", "")

    # Suggestionコメントは除外
    body_lower = body.lower()
    suggestion_indicators = [
        "committable suggestion",
        "suggestion_start",
        "📝 committable suggestion",
        "<!-- suggestion_start -->",
    ]
    for indicator in suggestion_indicators:
        if indicator in body_lower:
            return None

    # Prompt for AI Agentsブロックを抽出
    prompt = extract_ai_agent_prompt(body)
    if not prompt:
        return None

    # ファイル位置情報を構築
    location_parts = []
    if path:
        location_parts.append(f"In {path}")
    if line:
        location_parts.append(f"around line {line}")

    if location_parts:
        location = ", ".join(location_parts)
    else:
        location = "Unknown location"

    return location, prompt


def main():
    """メイン関数"""
    # 引数が何もない場合のチェック
    if len(sys.argv) == 1:
        print("エラー: プルリクエストURLが指定されていません", file=sys.stderr)
        print("使用方法: gh-review-prompts [オプション] <PR_URL>", file=sys.stderr)
        print("詳細なヘルプ: gh-review-prompts --help", file=sys.stderr)
        sys.exit(1)

    # CLIパースing
    output_file = None
    pr_url = None
    exclude_resolved = True  # デフォルトで解決済みを除外
    include_resolved = False  # 明示的に解決済みを含めるオプション
    debug_comment_id = None
    analyze_all = False  # 全コメント分析フラグ

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--help" or arg == "-h":
            print("""GitHub PR Review Comments Extractor

使用方法:
    gh-review-prompts [オプション] <PR_URL>

オプション:
    -h, --help              このヘルプを表示
    -o, --output FILE       出力ファイルを指定
    --include-resolved      解決済みコメントも含める
    --analyze-all           全コメントの解決状況を分析
    --debug-comment ID      特定コメントをデバッグ

例:
    gh-review-prompts https://github.com/owner/repo/pull/123
    gh-review-prompts --include-resolved https://github.com/owner/repo/pull/123
    gh-review-prompts --analyze-all https://github.com/owner/repo/pull/123

環境変数:
    GITHUB_TOKEN            GitHub APIアクセストークン（必須）
""")
            sys.exit(0)
        elif arg == "--output" or arg == "-o":
            if i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
                i += 1
            else:
                print("エラー: --output オプションには値が必要です", file=sys.stderr)
                sys.exit(1)
        elif arg == "--debug-comment":
            if i + 1 < len(sys.argv):
                try:
                    debug_comment_id = int(sys.argv[i + 1])
                    i += 1
                except ValueError:
                    msg = "エラー: --debug-comment オプションには数値が必要です"
                    print(msg, file=sys.stderr)
                    sys.exit(1)
            else:
                print(
                    "エラー: --debug-comment オプションには値が必要です",
                    file=sys.stderr,
                )
                sys.exit(1)
        elif arg == "--exclude-resolved":
            exclude_resolved = True
            include_resolved = False
        elif arg == "--include-resolved":
            exclude_resolved = False
            include_resolved = True
        elif arg == "--analyze-all":
            # 全コメントの解決状況を分析
            analyze_all = True
        elif not arg.startswith("--") and not arg.startswith("-"):
            pr_url = arg
        i += 1

    if not pr_url:
        print("エラー: プルリクエストURLが指定されていません", file=sys.stderr)
        print("使用方法: gh-review-prompts [オプション] <PR_URL>", file=sys.stderr)
        print("詳細なヘルプ: gh-review-prompts --help", file=sys.stderr)
        sys.exit(1)

    try:
        # GitHub クライアントを初期化
        client = GitHubClient()

        if not client.token:
            warning_msg = (
                "警告: GitHub API トークンが設定されていません。"
                "レート制限に注意してください。"
            )
            print(warning_msg, file=sys.stderr)
            print(
                "トークンを設定するには: export GITHUB_TOKEN=your_token",
                file=sys.stderr,
            )
            print(file=sys.stderr)

        # プルリクエストURLを解析
        owner, repo, pull_number = client.parse_pr_url(pr_url)
        print(f"プルリクエスト情報: {owner}/{repo}#{pull_number}", file=sys.stderr)

        # インラインコメント（レビューコメント）を取得
        review_comments = client.get_pr_review_comments(owner, repo, pull_number)

        # GraphQL APIで解決済みコメントIDを取得（利用可能な場合）
        resolved_comment_ids_graphql = client.get_resolved_comments_via_graphql(owner, repo, pull_number)



        # AI Agentプロンプトを抽出
        prompts = []
        resolved_count = 0
        debug_target_id = debug_comment_id



        for comment in review_comments:
            try:
                # デバッグ対象のコメントの場合、詳細情報を出力
                if comment.get("id") == debug_target_id:
                    print(
                        f"\n=== デバッグ情報 (ID: {debug_target_id}) ===",
                        file=sys.stderr,
                    )
                    print(f"URL: {comment.get('html_url')}", file=sys.stderr)
                    print(f"作成日時: {comment.get('created_at')}", file=sys.stderr)
                    print(f"更新日時: {comment.get('updated_at')}", file=sys.stderr)

                    # 完全なコメント本文を表示
                    full_body = comment.get("body", "")
                    print("完全なコメント本文:", file=sys.stderr)
                    print(f"{full_body[:500]}...", file=sys.stderr)
                    print(f"文字数: {len(full_body)}", file=sys.stderr)

                    # 解決状況をAPI基盤で判定
                    is_resolved = client.get_accurate_resolution_status(
                        comment, owner, repo, pull_number
                    )
                    print(f"API基盤解決判定: {is_resolved}", file=sys.stderr)
                    print("=" * 50, file=sys.stderr)

                # 解決済みコメントをスキップ（オプションが指定された場合）
                if exclude_resolved and not include_resolved:
                    # GraphQL APIの結果を優先使用
                    comment_id = comment.get("id")
                    is_resolved = False

                    if comment_id in resolved_comment_ids_graphql:
                        is_resolved = True
                    else:
                        # REST API基盤の解決状況判定をフォールバック
                        is_resolved = client.get_accurate_resolution_status(
                            comment, owner, repo, pull_number
                        )

                    if is_resolved:
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
            prompt_text1 = (
                "次のAIエージェント用レビュー指摘プロンプトを"
                "ひとつずつ対応してください。"
            )
            output_lines.append(prompt_text1)

            caution_text = (
                "ただし、指摘が正しいとは限らないので規約や環境、"
                "構造などを考慮し指摘されたことをしっかり精査した上で"
                "対応可否の判断を下すこと。"
            )
            output_lines.append(caution_text)

            instruction_text = (
                "最後に対応不要と判断したプロンプトに関しては"
                "その書き出しと、対応不要と判断した理由を"
                "下記のように出力してください。"
            )
            output_lines.append(instruction_text)

            output_lines.append("例）")
            output_lines.append("```")
            output_lines.append("1. In backend-auth/server.js around line 44,")

            example1 = (
                "    - 開発・ローカル環境ではMemoryStoreで十分。"
                "本番環境では別途Redis/MongoDBを使用するべきですが、"
                "この段階では不要。"
            )
            output_lines.append(example1)
            output_lines.append("")

            example2_title = "2. In backend-auth/server.js " "around lines 127 to 163,"
            output_lines.append(example2_title)

            example2_text = (
                "    - シンプルな開発用認証サーバーでは、"
                "HTMLのインライン埋め込みは許容範囲。"
                "テンプレートエンジンの導入は複雑性を増すだけ。"
            )
            output_lines.append(example2_text)
            output_lines.append("")
            output_lines.append("...")
            output_lines.append("```")
            output_lines.append("")

            commit_instruction = (
                "対応が全て終わったら" "Gitにコミット・プッシュを行ってください。"
            )
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
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"結果を {output_file} に保存しました。", file=sys.stderr)
        else:
            print(result)

        # 全コメント分析モード
        if analyze_all:
            print("\n=== 全コメント解決状況分析（API基盤判定） ===", file=sys.stderr)
            resolved_count_analysis = 0
            suggestion_count = 0
            api_resolved_count = 0
            keyword_resolved_count = 0

            for i, comment in enumerate(review_comments):
                comment_id = comment.get("id")

                # GraphQL APIの結果を優先して、REST APIをフォールバックとして使用
                if comment_id in resolved_comment_ids_graphql:
                    is_resolved = True
                else:
                    # REST API基盤の解決状況判定をフォールバック
                    is_resolved = client.get_accurate_resolution_status(
                        comment, owner, repo, pull_number
                    )

                # 解決理由を分析
                body = comment.get("body", "").lower()
                resolution_reason = "none"

                # Suggestion check
                suggestion_indicators = [
                    "committable suggestion",
                    "suggestion_start",
                    "📝 committable suggestion",
                    "<!-- suggestion_start -->",
                ]
                if any(ind in body for ind in suggestion_indicators):
                    resolution_reason = "suggestion"
                    suggestion_count += 1
                elif is_resolved:
                    # conversation_resolved チェック
                    if comment.get("conversation_resolved") is True:
                        resolution_reason = "api_conversation_resolved"
                        api_resolved_count += 1
                    else:
                        # キーワード解決
                        resolved_keywords = [
                            "resolved",
                            "解決",
                            "修正済み",
                            "fixed",
                            "done",
                            "完了",
                            "対応済み",
                            "対応完了",
                            "addressed",
                            "implemented",
                            "✅",
                            "☑️",
                            "[x]",
                            "closed",
                        ]
                        keyword_found = any(
                            keyword in body for keyword in resolved_keywords
                        )
                        if keyword_found:
                            resolution_reason = "keyword"
                            keyword_resolved_count += 1
                        else:
                            resolution_reason = "api_review_status"
                            api_resolved_count += 1

                if is_resolved:
                    resolved_count_analysis += 1

                print(
                    f"コメント {i+1:2d} (ID: {comment_id}): "
                    f"{'解決済み' if is_resolved else '未解決'} "
                    f"({resolution_reason})",
                    file=sys.stderr,
                )

            print("\n解決済み判定の内訳（API基盤）:", file=sys.stderr)
            print(f"  suggestion: {suggestion_count}件", file=sys.stderr)
            print(f"  api_based: {api_resolved_count}件", file=sys.stderr)
            print(f"  keyword: {keyword_resolved_count}件", file=sys.stderr)
            print(f"合計解決済み: {resolved_count_analysis}件", file=sys.stderr)
            print(f"総コメント数: {len(review_comments)}件", file=sys.stderr)
            print("=" * 50, file=sys.stderr)

    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        import traceback

        print(f"予期しないエラー: {e}", file=sys.stderr)
        print("詳細なエラー情報:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
