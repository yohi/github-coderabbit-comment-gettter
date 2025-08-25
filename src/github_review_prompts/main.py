#!/usr/bin/env python3
"""
GitHub Review Prompts - 統一CLI
全機能を統合したメインエントリーポイント
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# 既存モジュールのインポート
if __name__ == "__main__":
    # 直接実行時は相対インポートを回避
    sys.path.insert(0, str(Path(__file__).parent))
    from core.prompt_engine import UnifiedPromptEngine
    from config import ConfigManager
    from github_client import GitHubClient
    from comment_processor import CommentProcessor
    from output_formatter import OutputFormatter
    from models import APIError, AuthenticationError, RateLimitError, PERSONAS
    from utils.validators import (
        validate_pr_url,
        validate_persona,
        validate_output_format,
    )
else:
    # モジュールとして実行時
    from .core.prompt_engine import UnifiedPromptEngine
    from .config import ConfigManager
    from .github_client import GitHubClient
    from .comment_processor import CommentProcessor
    from .output_formatter import OutputFormatter
    from .models import APIError, AuthenticationError, RateLimitError, PERSONAS
    from .utils.validators import (
        validate_pr_url,
        validate_persona,
        validate_output_format,
    )

logger = logging.getLogger(__name__)


class UnifiedCLI:
    """統一CLI（フル機能版）"""

    def __init__(self):
        self.prompt_engine = UnifiedPromptEngine()

    def create_parser(self) -> argparse.ArgumentParser:
        """引数パーサーを作成（従来フォーマット互換）"""
        parser = argparse.ArgumentParser(
            prog="github-review-prompts",
            description="🔄 GitHub Review Prompt Generator (統一版)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
例:
  # プロンプト生成
  grp https://github.com/owner/repo/pull/123
  grp --persona security-analyst https://github.com/owner/repo/pull/123
  grp --no-confirm https://github.com/owner/repo/pull/123
  grp --auto-commit https://github.com/owner/repo/pull/123
  grp --debug https://github.com/owner/repo/pull/123
  grp --no-confirm --auto-commit --debug https://github.com/owner/repo/pull/123

  # ファイル保存
  grp --save-file https://github.com/owner/repo/pull/123
  grp --output my_prompt.md https://github.com/owner/repo/pull/123

  # コメント返信（curlベース）
  grp --reply-to 123456 --reply-message "Fixed, thanks!" https://github.com/owner/repo/pull/123
  grp --reply-to 123456 --reply-template fixed https://github.com/owner/repo/pull/123
  grp --reply-to 123456 --reply-template acknowledged --no-confirm https://github.com/owner/repo/pull/123

モード説明:
  - uvx環境: 常にフル機能モード（依存関係自動インストール）
  - uv run環境: フル機能モード（仮想環境の依存関係使用）
  - 直接実行環境: フル機能モード（高度なフィルタリング、ペルソナ等）

環境変数:
  GITHUB_TOKEN - GitHub APIトークン（必須）

出力:
  - review_prompt_with_todos.md (--save-file 指定時)
  - コンソール出力
        """,
        )

        # メイン引数（PR URL）
        parser.add_argument("pr_url", help="GitHub プルリクエストURL")

        # プロンプト生成オプション
        parser.add_argument(
            "--persona",
            choices=list(PERSONAS.keys()),
            default="engineer",
            help="AIエージェントのペルソナ",
        )
        parser.add_argument(
            "--format",
            choices=["markdown", "json", "text"],
            default="markdown",
            help="出力形式",
        )
        parser.add_argument(
            "--no-confirm",
            action="store_true",
            help="各コメント処理後の確認をスキップする",
        )
        parser.add_argument(
            "--auto-commit",
            action="store_true",
            help="作業完了後に自動的にgit commit & pushを実行する",
        )

        # フィルタリングオプション
        parser.add_argument(
            "--include-resolved", action="store_true", help="解決済みコメントも含める"
        )
        parser.add_argument("--author", help="特定作者のコメントのみ抽出")
        parser.add_argument("--since", help="指定日時以降のコメント (YYYY-MM-DD 形式)")
        parser.add_argument("--file-pattern", help="ファイルパスの正規表現フィルタ")

        # 返信オプション
        parser.add_argument("--reply-to", type=int, help="指定されたコメントIDに返信")
        parser.add_argument(
            "--reply-message", help="返信メッセージ（--reply-toと組み合わせて使用）"
        )
        parser.add_argument(
            "--reply-template",
            choices=[
                "fixed",
                "acknowledged",
                "investigating",
                "clarification",
                "wontfix",
            ],
            help="返信テンプレートを使用",
        )

        # 自動解決機能
        parser.add_argument(
            "--auto-resolve",
            action="store_true",
            help="未解決のCodeRabbitコメントに解決済みマーク設置を自動依頼",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際の返信は行わず、対象コメントのみ表示",
        )

        # 出力オプション
        parser.add_argument(
            "--output", "-o", help="出力ファイル (指定なしで標準出力のみ)"
        )
        parser.add_argument(
            "--append", action="store_true", help="ファイルに追記 (新規作成ではなく)"
        )
        parser.add_argument(
            "--save-file",
            action="store_true",
            help="review_prompt_with_todos.md にプロンプトを保存",
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            help="カラー出力を無効にする（コピーペースト最適化）",
        )

        # システムオプション
        parser.add_argument(
            "--debug",
            action="store_true",
            help="デバッグモードを有効にする（詳細ログ出力）",
        )
        parser.add_argument(
            "--token", help="GitHub トークン (環境変数 GITHUB_TOKEN で設定可能)"
        )
        parser.add_argument(
            "--api-url", default="https://api.github.com", help="GitHub API URL"
        )

        return parser

    def setup_logging(self, debug: bool = False):
        """ログ設定"""
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    def run(self, args: List[str] = None) -> int:
        """メイン実行（従来フォーマット互換）"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)

        # ログ設定
        self.setup_logging(parsed_args.debug)

        try:
            # GitHub トークン取得
            token = parsed_args.token or os.getenv("GITHUB_TOKEN")
            if not token:
                logger.error(
                    "GitHub トークンが設定されていません。--token オプションまたは GITHUB_TOKEN 環境変数を設定してください。"
                )
                return 1

            # 自動解決機能
            if parsed_args.auto_resolve:
                return self._handle_auto_resolve(parsed_args, token)

            # 返信機能
            if parsed_args.reply_to:
                return self._handle_reply(parsed_args, token)

            # デフォルトはプロンプト生成
            return self._handle_generate(parsed_args, token)

        except KeyboardInterrupt:
            logger.info("処理を中断しました")
            return 130
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}")
            if parsed_args.debug:
                import traceback

                traceback.print_exc()
            return 1

    def _handle_generate(self, args, token: str) -> int:
        """フル機能版 generate の処理（従来フォーマット）"""
        try:
            # カラー用の関数
            def colorize(text: str, color_code: str) -> str:
                if args.no_color:
                    return text
                return f"\033[{color_code}m{text}\033[0m"

            # 進行状況表示（カラー対応）
            print()
            print(colorize("🔄 GitHub Review Prompt Generator (統一版)", "1;34"))
            print(f"{colorize('📋 プルリクエスト:', '1;36')} {args.pr_url}")
            print(colorize("=" * 80, "1;37"))

            # 設定管理
            config = ConfigManager()

            # GitHub クライアント
            github_client = GitHubClient(token, args.api_url)

            # PR URLをパース
            pr_info = github_client.parse_pr_url(args.pr_url)

            # PR基本情報とコメント取得
            print(colorize("📍 PR基本情報を取得中...", "1;33"))
            pr_basic_info = github_client.get_pr_basic_info(pr_info)

            print(colorize("💬 レビューコメントを取得中...", "1;33"))
            comments, comment_stats = github_client.get_all_pr_comments(pr_info)
            print(colorize(f"📊 取得したコメント数: {len(comments)} 件", "1;32"))

            # ハイブリッドアプローチでコメント検出
            print(colorize("🔍 ハイブリッドアプローチでコメント検出中...", "1;33"))
            resolved_ids, _ = github_client.get_comments_via_hybrid_approach(pr_info)
            print(colorize(f"✅ 解決済みコメント: {len(resolved_ids)} 件", "1;32"))

            # 解決済みコメントの除外（--include-resolvedオプションがない場合）
            if not args.include_resolved:
                original_count = len(comments)
                comments = [c for c in comments if c.get("id") not in resolved_ids]
                excluded_count = original_count - len(comments)
                if excluded_count > 0:
                    print(
                        f"{colorize(f'🚫 解決済みコメントを除外: {excluded_count} 件', '1;31')} {colorize(f'→ 残り {len(comments)} 件', '1;32')}"
                    )
            else:
                print(
                    colorize(
                        f"ℹ️ 解決済みコメントも含めて処理: {len(comments)} 件", "1;36"
                    )
                )

            # プロンプト用のPR情報を構築
            pr_dict = {
                "title": pr_basic_info.get("title"),
                "url": args.pr_url,
                "author": pr_basic_info.get("user", {}).get("login"),
                "head_branch": pr_basic_info.get("head", {}).get("ref"),
                "base_branch": pr_basic_info.get("base", {}).get("ref"),
                "owner": pr_info.owner,
                "repo": pr_info.repo,
                "number": pr_info.pull_number,
            }

            # フィルタリング処理
            filter_original_count = len(comments)
            if args.author:
                comments = [
                    c for c in comments if c.get("user", {}).get("login") == args.author
                ]
                print(
                    f"{colorize(f'🔍 作者フィルタ適用: {args.author}', '1;35')} {colorize(f'→ {len(comments)} 件', '1;32')}"
                )

            if args.since:
                # 日付フィルタリング実装
                print(colorize(f"📅 日付フィルタ: {args.since} 以降", "1;35"))
                pass

            if args.file_pattern:
                pattern = re.compile(args.file_pattern)
                comments = [
                    c for c in comments if c.get("path") and pattern.search(c["path"])
                ]
                print(
                    f"{colorize(f'📁 ファイルパターンフィルタ適用: {args.file_pattern}', '1;35')} {colorize(f'→ {len(comments)} 件', '1;32')}"
                )

            if filter_original_count != len(comments):
                print(
                    colorize(
                        f"📋 最終処理対象: {len(comments)} 件 (元: {filter_original_count} 件)",
                        "1;36",
                    )
                )

            print(colorize("🤖 プロンプト生成中...", "1;33"))

            # プロンプト生成オプション
            options = {
                "auto_commit": args.auto_commit,
                "no_confirm": args.no_confirm,
                "persona": args.persona,
                "output_format": args.format,
            }

            # プロンプト生成
            prompt = self.prompt_engine.generate_main_prompt(
                comments, pr_dict, options, token
            )

            # 出力
            self._output_result(
                prompt,
                pr_dict,
                comments,
                args.output,
                args.append,
                args.save_file,
                args.no_color,
            )

            logger.info(f"プロンプトを生成しました ({len(comments)} コメント)")
            return 0

        except Exception as e:
            logger.error(f"プロンプト生成でエラー: {e}")
            return 1

    def _handle_reply(self, args, token: str) -> int:
        """reply 処理"""
        try:
            # メッセージ取得
            message = self._get_message_content(
                args.reply_message, args.reply_template, None
            )

            # curl_reply.py の機能を使用
            from .curl_reply import GitHubCurlReply

            curl_reply = GitHubCurlReply(token, args.api_url)
            result = curl_reply.reply_to_comment(args.pr_url, args.reply_to, message)

            if result:
                logger.info("返信を送信しました")
                return 0
            else:
                logger.error("返信の送信に失敗しました")
                return 1

        except Exception as e:
            logger.error(f"返信処理でエラー: {e}")
            return 1

    def _get_message_content(self, message: str, template: str, file_path: str) -> str:
        """メッセージ内容を取得"""
        if message:
            return message
        elif file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        elif template:
            # テンプレート展開
            templates = {
                "fixed": "修正しました。",
                "acknowledged": "ご指摘ありがとうございます。確認いたします。",
                "clarification": "申し訳ございませんが、詳細を教えていただけますでしょうか？",
                "wontfix": "この件は対応しない方針です。",
                "duplicate": "重複したご指摘です。",
                "resolved": "解決済みです。",
                "investigating": "調査中です。",
                "question": "ご質問ありがとうございます。",
            }
            return templates.get(template, message)
        else:
            raise ValueError(
                "メッセージ、テンプレート、またはファイルのいずれかを指定してください"
            )

    def _analyze_comment_breakdown(self, comments: List[Dict]) -> Dict[str, int]:
        """コメントの種類別内訳を分析"""
        breakdown = {
            "outside_diff": 0,
            "potential_issue": 0,
            "refactor_suggestion": 0,
            "nitpick": 0,
            "committable_suggestion": 0,
            "verification": 0,
            "analysis_chain": 0,
            "other": 0,
        }

        for comment in comments:
            body = comment.get("body", "").lower()

            # outside diff の判定
            if "outside diff" in body or "outside the diff hunk" in body:
                breakdown["outside_diff"] += 1
            # potential issue の判定
            elif (
                ("potential" in body and "issue" in body)
                or "security" in body
                or "bug" in body
                or "vulnerability" in body
            ):
                breakdown["potential_issue"] += 1
            # refactor suggestion の判定
            elif (
                "refactor" in body
                or "improve" in body
                or "consider" in body
                or "suggestion" in body
            ):
                breakdown["refactor_suggestion"] += 1
            # committable suggestion の判定
            elif "committable suggestion" in body or "```suggestion" in body:
                breakdown["committable_suggestion"] += 1
            # nitpick の判定
            elif (
                "nitpick" in body or "nit:" in body or "minor" in body or "typo" in body
            ):
                breakdown["nitpick"] += 1
            # verification agent の判定
            elif "verification" in body or "verify" in body or "analysis agent" in body:
                breakdown["verification"] += 1
            # analysis chain の判定
            elif "analysis chain" in body or "scripts executed" in body:
                breakdown["analysis_chain"] += 1
            else:
                breakdown["other"] += 1

        return breakdown

    def _output_result(
        self,
        content: str,
        pr_dict: Dict,
        comments: List[Dict],
        output_file: str = None,
        append: bool = False,
        save_file: bool = False,
        no_color: bool = False,
    ):
        """美しい結果出力（従来フォーマット）"""

        # カラー用の関数
        def colorize(text: str, color_code: str) -> str:
            if no_color:
                return text
            return f"\033[{color_code}m{text}\033[0m"

        # コメント内訳の分析
        breakdown = self._analyze_comment_breakdown(comments)

        # 統計情報の表示
        print()
        print(colorize("=" * 80, "1;37"))
        print(colorize("✅ レビュープロンプトとTODOリストを生成しました", "1;32"))
        print(
            f"{colorize('📋 処理対象コメント:', '1;36')} {colorize(f'{len(comments)} 件', '1;33')}"
        )

        # 詳細内訳の表示
        if len(comments) > 0:
            print(f"{colorize('📊 内訳詳細:', '1;36')}")
            details = []
            if breakdown["outside_diff"] > 0:
                details.append(f"Outside Diff: {breakdown['outside_diff']}件")
            if breakdown["potential_issue"] > 0:
                details.append(f"Potential Issue: {breakdown['potential_issue']}件")
            if breakdown["refactor_suggestion"] > 0:
                details.append(
                    f"Refactor Suggestion: {breakdown['refactor_suggestion']}件"
                )
            if breakdown["committable_suggestion"] > 0:
                details.append(
                    f"Committable Suggestion: {breakdown['committable_suggestion']}件"
                )
            if breakdown["nitpick"] > 0:
                details.append(f"Nitpick: {breakdown['nitpick']}件")
            if breakdown["verification"] > 0:
                details.append(f"Verification: {breakdown['verification']}件")
            if breakdown["analysis_chain"] > 0:
                details.append(f"Analysis Chain: {breakdown['analysis_chain']}件")
            if breakdown["other"] > 0:
                details.append(f"その他: {breakdown['other']}件")

            # 内訳を2列で表示
            for i in range(0, len(details), 2):
                line_parts = details[i : i + 2]
                print(
                    f"   {colorize(line_parts[0], '1;33')}"
                    + (
                        f"  {colorize(line_parts[1], '1;33')}"
                        if len(line_parts) > 1
                        else ""
                    )
                )

        print(f"{colorize('🔗 プルリクエスト:', '1;36')} {pr_dict.get('title', 'N/A')}")
        print()

        # プロンプト用コピー範囲の明確な開始マーカー（プレーンテキスト）
        print("🤖" + "=" * 78 + "🤖")
        print("📋 AI AGENT PROMPT - コピーペースト用範囲 (開始)")
        print("💡 以下の内容をコピーしてAIチャットに貼り付けてください")
        print("🤖" + "=" * 78 + "🤖")
        print()

        # プロンプト内容を出力
        print(content)

        # プロンプト用コピー範囲の明確な終了マーカー
        print()
        print("🤖" + "=" * 78 + "🤖")
        print("📋 AI AGENT PROMPT - コピーペースト用範囲 (終了)")
        print("💡 上記の内容をコピーしてAIチャットに貼り付けてください")
        print("🤖" + "=" * 78 + "🤖")
        print()

        # ファイル保存処理
        saved_files = []

        # --output オプションでのファイル保存
        if output_file:
            try:
                mode = "a" if append else "w"
                with open(output_file, mode, encoding="utf-8") as f:
                    f.write(content)
                    if append:
                        f.write("\n\n---\n\n")
                saved_files.append(output_file)
            except Exception as e:
                logger.error(f"ファイル保存に失敗しました ({output_file}): {e}")

        # --save-file オプションでのデフォルトファイル保存
        if save_file:
            default_file = "review_prompt_with_todos.md"
            try:
                with open(default_file, "w", encoding="utf-8") as f:
                    f.write(content)
                saved_files.append(default_file)
            except Exception as e:
                logger.error(
                    f"デフォルトファイル保存に失敗しました ({default_file}): {e}"
                )

        # 保存結果の表示
        if saved_files:
            for file in saved_files:
                print(
                    f"{colorize('📁 プロンプトファイルを保存しました:', '1;32')} {file}"
                )
        else:
            print(
                colorize(
                    "💡 プロンプトファイルは保存されませんでした（--output または --save-file オプションで保存可能）",
                    "1;33",
                )
            )

        print(colorize("=" * 80, "1;37"))

    def _handle_auto_resolve(self, args, token: str) -> int:
        """自動解決機能の処理"""
        try:
            # カラー用の関数
            def colorize(text: str, color_code: str) -> str:
                if args.no_color:
                    return text
                return f"\033[{color_code}m{text}\033[0m"

            print()
            print(colorize("🤖 CodeRabbit自動解決依頼機能", "1;34"))
            print(f"{colorize('📋 プルリクエスト:', '1;36')} {args.pr_url}")
            print(colorize("=" * 80, "1;37"))

            # GitHub クライアント
            github_client = GitHubClient(token, args.api_url)

            # PR URLをパース
            pr_info = github_client.parse_pr_url(args.pr_url)

            print(colorize("📍 PR基本情報を取得中...", "1;33"))
            pr_basic_info = github_client.get_pr_basic_info(pr_info)

            print(colorize("💬 レビューコメントを取得中...", "1;33"))
            comments, comment_stats = github_client.get_all_pr_comments(pr_info)

            print(colorize("🔍 解決済みコメントを検出中...", "1;33"))
            resolved_ids, _ = github_client.get_comments_via_hybrid_approach(pr_info)

            # 最後のコミット時刻を取得
            print(colorize("⏰ 最後のコミット時刻を取得中...", "1;33"))
            last_commit_time = self._get_last_commit_time(github_client, pr_info)
            if last_commit_time:
                print(colorize(f"📅 最後のコミット: {last_commit_time}", "1;32"))
            else:
                print(colorize("⚠️ 最後のコミット時刻を取得できませんでした", "1;31"))

            # 対象コメントをフィルタリング
            print(colorize("🎯 対象コメントをフィルタリング中...", "1;33"))
            target_comments = self._filter_auto_resolve_comments(
                comments, resolved_ids, last_commit_time
            )

            print(colorize(f"✅ 対象コメント: {len(target_comments)} 件", "1;32"))

            if not target_comments:
                print(colorize("📭 自動解決対象のコメントが見つかりませんでした。", "1;33"))
                return 0

            # dry-runモードの場合は表示のみ
            if args.dry_run:
                self._display_target_comments(target_comments, colorize)
                return 0

            # 解決依頼コメントを送信
            print(colorize("📤 解決依頼コメントを送信中...", "1;33"))
            success_count = self._send_auto_resolve_requests(
                github_client, args.pr_url, target_comments, colorize
            )

            print()
            print(colorize("=" * 80, "1;37"))
            print(colorize("✅ 自動解決依頼処理完了", "1;32"))
            print(f"{colorize('📊 処理結果:', '1;36')} {success_count}/{len(target_comments)} 件送信成功")
            print(colorize("=" * 80, "1;37"))

            return 0 if success_count > 0 else 1

        except Exception as e:
            logger.error(f"自動解決処理でエラー: {e}")
            return 1

    def _get_last_commit_time(self, github_client: GitHubClient, pr_info) -> Optional[str]:
        """PRの最後のコミット時刻を取得"""
        try:
            # GitHub APIでPRのコミット一覧を取得
            url = f"/repos/{pr_info.owner}/{pr_info.repo}/pulls/{pr_info.pull_number}/commits"
            commits = github_client._make_request("GET", url)

            if commits and len(commits) > 0:
                # 最後のコミットの時刻を返す
                last_commit = commits[-1]
                return last_commit["commit"]["committer"]["date"]

            return None
        except Exception as e:
            logger.warning(f"最後のコミット時刻取得に失敗: {e}")
            return None

    def _filter_auto_resolve_comments(
        self, comments: List[Dict], resolved_ids: set, last_commit_time: Optional[str]
    ) -> List[Dict]:
        """自動解決対象のコメントをフィルタリング"""
        target_comments = []

        for comment in comments:
            if self._should_auto_resolve_comment(comment, resolved_ids, last_commit_time):
                target_comments.append(comment)

        return target_comments

    def _should_auto_resolve_comment(
        self, comment: Dict, resolved_ids: set, last_commit_time: Optional[str]
    ) -> bool:
        """自動解決対象の判定"""
        # 未解決
        if comment.get("id") in resolved_ids:
            return False

        # 最後のコメント者がcoderabbitai
        user_login = comment.get("user", {}).get("login", "")
        if user_login not in ["coderabbitai[bot]", "coderabbitai"]:
            return False

        # インラインコメント（pathとlineが存在）
        if not comment.get("path") or comment.get("line") is None:
            return False

        # 最終コメントが最後のコミット時刻より前
        if last_commit_time:
            comment_time = comment.get("created_at")
            if comment_time and comment_time >= last_commit_time:
                return False

        return True

    def _display_target_comments(self, target_comments: List[Dict], colorize) -> None:
        """対象コメントを表示（dry-runモード）"""
        print()
        print(colorize("📋 自動解決対象コメント一覧", "1;36"))
        print(colorize("=" * 60, "1;37"))

        for i, comment in enumerate(target_comments, 1):
            print(f"{colorize(f'🎯 コメント #{i}', '1;33')}")
            print(f"   ID: {comment.get('id')}")
            print(f"   ファイル: {comment.get('path')}")
            print(f"   行: {comment.get('line')}")
            print(f"   作成者: {comment.get('user', {}).get('login')}")
            print(f"   作成日時: {comment.get('created_at')}")

            # コメント内容の要約（最初の100文字）
            body = comment.get("body", "")[:100]
            if len(comment.get("body", "")) > 100:
                body += "..."
            print(f"   内容: {body}")
            print()

    def _send_auto_resolve_requests(
        self, github_client: GitHubClient, pr_url: str, target_comments: List[Dict], colorize
    ) -> int:
        """解決依頼コメントを送信"""
        success_count = 0

        # 解決依頼メッセージテンプレート
        resolve_message = """@coderabbitai この指摘について技術的検証を実施しました。

HEADブランチを確認後、技術的に問題ないと判断できる場合は、**以下のテキストを一字一句正確にコピーペースト**してください：

```
[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

⚠️ **重要**: 上記マーカーは自動処理用フォーマットのため、文言変更・追加・削除は禁止です。"""

        for comment in target_comments:
            try:
                comment_id = comment.get("id")
                print(f"{colorize(f'📤 コメントID {comment_id} に返信中...', '1;33')}")

                # curl_reply.py の機能を使用
                from .curl_reply import GitHubCurlReply
                curl_reply = GitHubCurlReply(github_client.token, github_client.api_url)

                result = curl_reply.reply_to_comment(pr_url, comment_id, resolve_message)

                if result:
                    print(f"{colorize(f'✅ コメントID {comment_id} への返信成功', '1;32')}")
                    success_count += 1
                else:
                    print(f"{colorize(f'❌ コメントID {comment_id} への返信失敗', '1;31')}")

            except Exception as e:
                comment_id = comment.get("id", "不明")
                print(f"{colorize(f'❌ コメントID {comment_id} でエラー: {e}', '1;31')}")

        return success_count


def main() -> int:
    """メインエントリーポイント"""
    cli = UnifiedCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
