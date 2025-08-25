"""解決済みマーク自動処理専用CLI"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

from .auto_resolve_processor import AutoResolveProcessor
from .utils.validators import validate_github_token


def setup_logging(verbose: bool = False) -> None:
    """ログ設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_github_token() -> Optional[str]:
    """GitHub トークンを環境変数から取得"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("エラー: GITHUB_TOKEN 環境変数が設定されていません")
        print("export GITHUB_TOKEN=your_token_here を実行してください")
        return None

    if not validate_github_token(token):
        print("エラー: 無効なGitHubトークンです")
        return None

    return token


def format_output(result: dict, output_format: str = "json") -> str:
    """結果の出力フォーマット"""
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    elif output_format == "summary":
        if "error" in result:
            return f"❌ エラー: {result['error']}"

        summary = result.get("summary", {})
        pr_info = result.get("pr_info", {})
        processing_info = result.get("processing_info", {})

        lines = [
            f"🔍 プルリクエスト: {pr_info.get('owner', '')}/{pr_info.get('repo', '')}#{pr_info.get('pull_number', '')}",
            f"📝 タイトル: {pr_info.get('title', '')}",
            f"📊 処理サマリー: {summary.get('message', '')}",
            f"💭 総コメント数: {processing_info.get('total_comments', 0)}",
            f"✅ 既解決コメント数: {processing_info.get('already_resolved', 0)}",
            f"🎯 マーカー検出数: {processing_info.get('marked_for_resolution', 0)}",
        ]

        if "resolution_results" in result and result["resolution_results"]:
            success_count = sum(1 for r in result["resolution_results"] if r.get("success", False))
            total_count = len(result["resolution_results"])
            lines.append(f"🏁 解決処理: {success_count}/{total_count} 件成功")

        return "\n".join(lines)

    elif output_format == "detailed":
        lines = [format_output(result, "summary"), "", "📋 詳細情報:"]

        marked_comments = result.get("marked_comments", [])
        if marked_comments:
            lines.append(f"\n🎯 マーカー検出コメント ({len(marked_comments)}件):")
            for i, comment in enumerate(marked_comments, 1):
                status = "既解決" if comment.get("is_already_resolved") else "未解決"
                patterns = ", ".join(comment.get("detected_patterns", []))
                preview = comment.get("body_preview", "")[:100]
                lines.extend([
                    f"  {i}. コメントID: {comment.get('comment_id')}",
                    f"     ステータス: {status}",
                    f"     検出パターン: {patterns}",
                    f"     内容: {preview}...",
                    ""
                ])

        resolution_results = result.get("resolution_results", [])
        if resolution_results:
            lines.append(f"\n🏁 解決処理結果 ({len(resolution_results)}件):")
            for i, res in enumerate(resolution_results, 1):
                status = "✅ 成功" if res.get("success") else "❌ 失敗"
                message = res.get("message", "")
                lines.extend([
                    f"  {i}. コメントID: {res.get('comment_id')} - {status}",
                    f"     メッセージ: {message}",
                    ""
                ])

        return "\n".join(lines)

    else:
        return json.dumps(result, ensure_ascii=False, indent=2)


def create_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサーを作成"""
    parser = argparse.ArgumentParser(
        description="解決済みマーク自動処理ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ドライラン（実際の解決処理は行わない）
  python -m github_review_prompts.auto_resolve_cli https://github.com/owner/repo/pull/123 --dry-run

  # 実際に解決済みステータスに更新
  python -m github_review_prompts.auto_resolve_cli https://github.com/owner/repo/pull/123

  # 詳細出力
  python -m github_review_prompts.auto_resolve_cli https://github.com/owner/repo/pull/123 --output detailed --verbose

  # JSON形式で出力
  python -m github_review_prompts.auto_resolve_cli https://github.com/owner/repo/pull/123 --output json
        """
    )

    parser.add_argument(
        "pr_url",
        help="プルリクエストのURL"
    )

    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="ドライランモード（実際の解決処理は行わない）"
    )

    parser.add_argument(
        "--output", "-o",
        choices=["json", "summary", "detailed"],
        default="summary",
        help="出力形式 (default: summary)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細ログを出力"
    )

    parser.add_argument(
        "--token",
        help="GitHubトークン（環境変数 GITHUB_TOKEN が優先）"
    )

    return parser


def main() -> int:
    """メイン関数"""
    parser = create_parser()
    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # GitHubトークン取得
        token = args.token or get_github_token()
        if not token:
            return 1

        # 処理実行
        logger.info("解決済みマーク自動処理開始")
        processor = AutoResolveProcessor(token)

        result = processor.process_pr_auto_resolve(
            pr_url=args.pr_url,
            dry_run=args.dry_run,
            verbose=args.verbose
        )

        # 結果出力
        output = format_output(result, args.output)
        print(output)

        # 終了コード決定
        if "error" in result:
            logger.error("処理中にエラーが発生しました")
            return 1

        summary = result.get("summary", {})
        if summary.get("action") == "no_markers_found":
            logger.info("解決済みマーカーが見つかりませんでした（正常終了）")
            return 0
        elif args.dry_run:
            logger.info("ドライラン完了")
            return 0
        elif summary.get("successfully_resolved", 0) > 0:
            logger.info("解決処理が成功しました")
            return 0
        else:
            logger.warning("解決処理で一部または全部が失敗しました")
            return 1

    except KeyboardInterrupt:
        logger.info("処理が中断されました")
        return 1
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
