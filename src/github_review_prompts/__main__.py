#!/usr/bin/env python3
"""
GitHub Review Prompts - メインエントリーポイント
python -m github_review_prompts でのサブコマンド実行
"""

import argparse
import sys
import logging
from typing import List, Optional

# サブコマンドモジュールのインポート
from .main import UnifiedCLI
from .auto_resolve_cli import main as auto_resolve_main


def create_main_parser() -> argparse.ArgumentParser:
    """メインパーサーを作成（サブコマンド対応）"""
    parser = argparse.ArgumentParser(
        prog="github-review-prompts",
        description="🔄 GitHub Review Prompt Generator - 統合ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
サブコマンド:
  generate         プルリクエストからAIプロンプトを生成（デフォルト）
  auto-resolve     解決済みマーク付きコメントを自動で解決済みステータスに更新

使用例:
  # プロンプト生成（デフォルトサブコマンド）
  python -m github_review_prompts https://github.com/owner/repo/pull/123
  python -m github_review_prompts generate https://github.com/owner/repo/pull/123

  # 解決済みマーク自動処理
  python -m github_review_prompts auto-resolve https://github.com/owner/repo/pull/123
  python -m github_review_prompts auto-resolve --dry-run https://github.com/owner/repo/pull/123

環境変数:
  GITHUB_TOKEN - GitHub APIトークン（必須）
        """
    )

    # サブコマンド
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="使用可能なサブコマンド",
        metavar="COMMAND"
    )

    # generateサブコマンド（既存のmain.py機能）
    generate_parser = subparsers.add_parser(
        "generate",
        help="プルリクエストからAIプロンプトを生成",
        description="プルリクエストのレビューコメントからAIプロンプトを生成します"
    )
    # generate用の引数は後でUnifiedCLIのparserから移植

    # auto-resolveサブコマンド
    auto_resolve_parser = subparsers.add_parser(
        "auto-resolve",
        help="解決済みマーク付きコメントを自動解決",
        description="解決済みマーク付きコメントを自動で解決済みステータスに更新します"
    )

    auto_resolve_parser.add_argument(
        "pr_url",
        help="プルリクエストのURL"
    )

    auto_resolve_parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="ドライランモード（実際の解決処理は行わない）"
    )

    auto_resolve_parser.add_argument(
        "--output", "-o",
        choices=["json", "summary", "detailed"],
        default="summary",
        help="出力形式 (default: summary)"
    )

    auto_resolve_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細ログを出力"
    )

    auto_resolve_parser.add_argument(
        "--token",
        help="GitHubトークン（環境変数 GITHUB_TOKEN が優先）"
    )

    return parser


def setup_logging(debug: bool = False, verbose: bool = False):
    """ログ設定"""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def handle_legacy_args(args: List[str]) -> List[str]:
    """レガシー引数形式を処理

    URL引数が最初にある場合は、generateサブコマンドを前置
    """
    if not args:
        return args

    # 最初の引数がサブコマンドかチェック
    known_subcommands = ["generate", "auto-resolve", "help", "--help", "-h"]

    if args[0] in known_subcommands:
        return args

    # URL形式の場合はgenerateサブコマンドを前置
    if args[0].startswith("https://github.com/") and "/pull/" in args[0]:
        return ["generate"] + args

    # その他のオプション引数で始まる場合もgenerateサブコマンドを前置
    if args[0].startswith("-"):
        return ["generate"] + args

    return args


def main(args: Optional[List[str]] = None) -> int:
    """メイン関数"""
    if args is None:
        args = sys.argv[1:]

    # レガシー引数形式の処理
    args = handle_legacy_args(args)

    # メインパーサーの作成
    parser = create_main_parser()

    # 引数が空の場合はヘルプを表示
    if not args:
        parser.print_help()
        return 0

    # 引数解析
    try:
        # サブコマンドが指定されていない場合の処理
        if not any(arg in ["generate", "auto-resolve"] for arg in args):
            # URLが指定されている場合はgenerateサブコマンドを前置
            if any("github.com" in arg and "pull" in arg for arg in args):
                args = ["generate"] + args
            else:
                parser.print_help()
                return 1

        parsed_args = parser.parse_args(args)

    except SystemExit as e:
        return e.code

    # ログ設定
    setup_logging(
        debug=getattr(parsed_args, "debug", False),
        verbose=getattr(parsed_args, "verbose", False)
    )

    logger = logging.getLogger(__name__)

    try:
        # サブコマンド実行
        if parsed_args.subcommand == "auto-resolve":
            # auto-resolve実行
            logger.info("解決済みマーク自動処理サブコマンドを実行")

            # auto_resolve_cliのmain関数を呼び出し
            # 引数を再構築
            auto_resolve_args = [parsed_args.pr_url]

            if parsed_args.dry_run:
                auto_resolve_args.append("--dry-run")
            if parsed_args.output != "summary":
                auto_resolve_args.extend(["--output", parsed_args.output])
            if parsed_args.verbose:
                auto_resolve_args.append("--verbose")
            if getattr(parsed_args, "token", None):
                auto_resolve_args.extend(["--token", parsed_args.token])

            # auto_resolve_cliのmain関数を直接呼び出し
            sys.argv = ["auto-resolve"] + auto_resolve_args
            return auto_resolve_main()

        elif parsed_args.subcommand == "generate" or not parsed_args.subcommand:
            # generate実行（デフォルト）
            logger.info("プロンプト生成サブコマンドを実行")

            # UnifiedCLIで実行
            cli = UnifiedCLI()

            # 引数を再構築（サブコマンド部分を除去）
            generate_args = args[1:] if args[0] == "generate" else args

            return cli.run(generate_args)

        else:
            logger.error(f"不明なサブコマンド: {parsed_args.subcommand}")
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.info("処理が中断されました")
        return 1
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        if getattr(parsed_args, "debug", False):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
