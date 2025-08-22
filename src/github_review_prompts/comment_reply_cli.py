#!/usr/bin/env python3
"""GitHub PR コメント返信 CLI

CodeRabbitや他のレビューコメントに対する返信を簡単に行うためのコマンドラインツール
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

from .curl_reply import GitHubCurlReply, CurlReplyError, parse_pr_url


def setup_logging(debug: bool = False) -> None:
    """ログ設定をセットアップ"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_reply_template(template_name: str) -> str:
    """返信テンプレートを読み込む"""
    templates = {
        "fixed": "✅ Fixed! Thanks for the feedback.",
        "acknowledged": "👍 Acknowledged. I'll address this in the next update.",
        "clarification": "🤔 Could you provide more details about this issue?",
        "wontfix": "⚠️ I understand the concern, but this is intentional due to [reason].",
        "duplicate": "🔄 This appears to be a duplicate of another comment. See: [reference]",
        "resolved": "✅ This issue has been resolved.",
        "investigating": "🔍 Looking into this issue. Will update soon.",
        "question": "❓ I have a question about this feedback: [question]"
    }
    
    return templates.get(template_name, template_name)


def create_argument_parser() -> argparse.ArgumentParser:
    """コマンドライン引数のパーサーを作成"""
    parser = argparse.ArgumentParser(
        description="GitHub PR コメント返信ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一コメントに返信
  %(prog)s reply https://github.com/owner/repo/pull/123 --comment-id 456789 --message "Fixed!"
  
  # テンプレートを使用した返信
  %(prog)s reply https://github.com/owner/repo/pull/123 --comment-id 456789 --template fixed
  
  # 一括返信（JSONファイルから）
  %(prog)s batch-reply https://github.com/owner/repo/pull/123 --replies-file replies.json
  
  # curlコマンド生成
  %(prog)s generate-curl https://github.com/owner/repo/pull/123 --action reply --comment-id 456789 --message "Fixed!"
  
  # 新しいコメント作成
  %(prog)s create https://github.com/owner/repo/pull/123 --path src/file.py --line 42 --message "Great code!"
  
  # コメント更新
  %(prog)s update https://github.com/owner/repo/pull/123 --comment-id 456789 --message "Updated message"
  
  # コメント削除
  %(prog)s delete https://github.com/owner/repo/pull/123 --comment-id 456789

環境変数:
  GITHUB_TOKEN    GitHub API トークン（必須）
        """
    )
    
    # 共通オプション
    parser.add_argument(
        "--token",
        help="GitHub API トークン（環境変数 GITHUB_TOKEN からも取得可能）"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモードを有効にする"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の API 呼び出しを行わず、実行内容のみ表示"
    )
    
    # サブコマンド
    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")
    
    # reply サブコマンド
    reply_parser = subparsers.add_parser("reply", help="コメントに返信する")
    reply_parser.add_argument("pr_url", help="プルリクエストのURL")
    reply_parser.add_argument("--comment-id", type=int, required=True, help="返信対象のコメントID")
    reply_group = reply_parser.add_mutually_exclusive_group(required=True)
    reply_group.add_argument("--message", help="返信メッセージ")
    reply_group.add_argument("--template", choices=["fixed", "acknowledged", "clarification", "wontfix", "duplicate", "resolved", "investigating", "question"], help="返信テンプレート")
    reply_parser.add_argument("--file", help="返信メッセージをファイルから読み込む")
    
    # batch-reply サブコマンド
    batch_parser = subparsers.add_parser("batch-reply", help="複数のコメントに一括返信")
    batch_parser.add_argument("pr_url", help="プルリクエストのURL")
    batch_parser.add_argument("--replies-file", required=True, help="返信情報のJSONファイル")
    batch_parser.add_argument("--delay", type=float, default=0.5, help="返信間の遅延秒数")
    
    # create サブコマンド
    create_parser = subparsers.add_parser("create", help="新しいコメントを作成")
    create_parser.add_argument("pr_url", help="プルリクエストのURL")
    create_parser.add_argument("--path", required=True, help="ファイルパス")
    create_parser.add_argument("--line", type=int, required=True, help="行番号")
    create_parser.add_argument("--message", help="コメント内容")
    create_parser.add_argument("--file", help="コメント内容をファイルから読み込む")
    create_parser.add_argument("--side", choices=["LEFT", "RIGHT"], default="RIGHT", help="コメント位置")
    
    # update サブコマンド
    update_parser = subparsers.add_parser("update", help="既存のコメントを更新")
    update_parser.add_argument("pr_url", help="プルリクエストのURL")
    update_parser.add_argument("--comment-id", type=int, required=True, help="更新対象のコメントID")
    update_parser.add_argument("--message", help="新しいコメント内容")
    update_parser.add_argument("--file", help="コメント内容をファイルから読み込む")
    
    # delete サブコマンド
    delete_parser = subparsers.add_parser("delete", help="コメントを削除")
    delete_parser.add_argument("pr_url", help="プルリクエストのURL")
    delete_parser.add_argument("--comment-id", type=int, required=True, help="削除対象のコメントID")
    delete_parser.add_argument("--confirm", action="store_true", help="削除確認をスキップ")
    
    # generate-curl サブコマンド
    curl_parser = subparsers.add_parser("generate-curl", help="curl コマンドを生成")
    curl_parser.add_argument("pr_url", help="プルリクエストのURL")
    curl_parser.add_argument("--action", choices=["reply", "create", "update", "delete"], required=True, help="実行するアクション")
    curl_parser.add_argument("--comment-id", type=int, help="コメントID（reply, update, delete で必要）")
    curl_parser.add_argument("--message", help="メッセージ内容")
    curl_parser.add_argument("--template", help="テンプレート名")
    curl_parser.add_argument("--path", help="ファイルパス（create で必要）")
    curl_parser.add_argument("--line", type=int, help="行番号（create で必要）")
    curl_parser.add_argument("--side", choices=["LEFT", "RIGHT"], default="RIGHT", help="コメント位置")
    
    # list-templates サブコマンド
    list_parser = subparsers.add_parser("list-templates", help="利用可能なテンプレート一覧を表示")
    
    return parser


def get_message_content(message: Optional[str], template: Optional[str], file_path: Optional[str]) -> str:
    """メッセージ内容を取得する"""
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            raise ValueError(f"ファイルが見つかりません: {file_path}")
        except Exception as e:
            raise ValueError(f"ファイル読み込みエラー: {e}")
    
    if template:
        return load_reply_template(template)
    
    if message:
        return message
    
    raise ValueError("メッセージ、テンプレート、またはファイルのいずれかを指定してください")


def load_batch_replies(file_path: str) -> List[Dict[str, any]]:
    """一括返信用のJSONファイルを読み込む"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("JSON ファイルは配列形式である必要があります")
        
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"要素 {i} は辞書形式である必要があります")
            
            if "comment_id" not in item:
                raise ValueError(f"要素 {i} に comment_id が含まれていません")
            
            if "reply_body" not in item and "template" not in item:
                raise ValueError(f"要素 {i} に reply_body または template が含まれていません")
            
            # テンプレートがある場合は展開
            if "template" in item:
                item["reply_body"] = load_reply_template(item["template"])
        
        return data
    
    except FileNotFoundError:
        raise ValueError(f"ファイルが見つかりません: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON パースエラー: {e}")
    except Exception as e:
        raise ValueError(f"ファイル読み込みエラー: {e}")


def cmd_reply(args, client: GitHubCurlReply, owner: str, repo: str, pr_number: int) -> None:
    """単一コメント返信コマンド"""
    message = get_message_content(args.message, args.template, args.file)
    
    print(f"📝 コメント {args.comment_id} に返信中...")
    print(f"メッセージ: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    if args.dry_run:
        print("🔍 [DRY RUN] 実際の API 呼び出しはスキップされました")
        return
    
    try:
        result = client.reply_to_review_comment(owner, repo, args.comment_id, message)
        print(f"✅ 返信コメント作成成功!")
        print(f"   コメントID: {result.get('id')}")
        print(f"   URL: {result.get('html_url')}")
    except CurlReplyError as e:
        print(f"❌ 返信失敗: {e}")
        sys.exit(1)


def cmd_batch_reply(args, client: GitHubCurlReply, owner: str, repo: str, pr_number: int) -> None:
    """一括返信コマンド"""
    replies = load_batch_replies(args.replies_file)
    
    print(f"📝 {len(replies)} 件のコメントに一括返信中...")
    
    if args.dry_run:
        print("🔍 [DRY RUN] 実際の API 呼び出しはスキップされました")
        for reply in replies:
            print(f"   コメント {reply['comment_id']}: {reply['reply_body'][:50]}...")
        return
    
    try:
        results = client.batch_reply_to_comments(pr_info, replies)
        print(f"✅ 一括返信完了: {len(results)} 件成功")
        for result in results:
            print(f"   コメントID: {result.get('id')} - URL: {result.get('html_url')}")
    except APIError as e:
        print(f"❌ 一括返信失敗: {e}")
        sys.exit(1)


def cmd_create(args, client: GitHubCurlReply, owner: str, repo: str, pr_number: int) -> None:
    """新規コメント作成コマンド"""
    message = get_message_content(args.message, None, args.file)
    
    print(f"📝 新しいコメントを作成中...")
    print(f"ファイル: {args.path}:{args.line}")
    print(f"メッセージ: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    if args.dry_run:
        print("🔍 [DRY RUN] 実際の API 呼び出しはスキップされました")
        return
    
    try:
        # PRコメントとして作成（ファイル固有のコメントではなく）
        result = client.create_pr_comment(owner, repo, pr_number, message)
        print(f"✅ 新規コメント作成成功!")
        print(f"   コメントID: {result.get('id')}")
        print(f"   URL: {result.get('html_url')}")
    except CurlReplyError as e:
        print(f"❌ コメント作成失敗: {e}")
        sys.exit(1)


def cmd_update(args, client: GitHubCurlReply, owner: str, repo: str, pr_number: int) -> None:
    """コメント更新コマンド"""
    message = get_message_content(args.message, None, args.file)
    
    print(f"📝 コメント {args.comment_id} を更新中...")
    print(f"新しいメッセージ: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    if args.dry_run:
        print("🔍 [DRY RUN] 実際の API 呼び出しはスキップされました")
        return
    
    try:
        result = client.update_comment(pr_info, args.comment_id, message)
        print(f"✅ コメント更新成功!")
        print(f"   コメントID: {result.get('id')}")
        print(f"   URL: {result.get('html_url')}")
    except APIError as e:
        print(f"❌ コメント更新失敗: {e}")
        sys.exit(1)


def cmd_delete(args, client: GitHubClient, pr_info: GitHubPRInfo) -> None:
    """コメント削除コマンド"""
    if not args.confirm and not args.dry_run:
        confirm = input(f"コメント {args.comment_id} を削除しますか? (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("削除をキャンセルしました")
            return
    
    print(f"🗑️ コメント {args.comment_id} を削除中...")
    
    if args.dry_run:
        print("🔍 [DRY RUN] 実際の API 呼び出しはスキップされました")
        return
    
    try:
        success = client.delete_comment(pr_info, args.comment_id)
        if success:
            print(f"✅ コメント削除成功!")
        else:
            print(f"⚠️ コメント削除で予期しない結果")
    except APIError as e:
        print(f"❌ コメント削除失敗: {e}")
        sys.exit(1)


def cmd_generate_curl(args, client: GitHubClient, pr_info: GitHubPRInfo) -> None:
    """curl コマンド生成"""
    kwargs = {}
    
    if args.action == "reply":
        if not args.comment_id:
            print("❌ reply アクションには --comment-id が必要です")
            sys.exit(1)
        message = get_message_content(args.message, args.template, None)
        kwargs = {"comment_id": args.comment_id, "reply_body": message}
    
    elif args.action == "create":
        if not all([args.path, args.line]):
            print("❌ create アクションには --path と --line が必要です")
            sys.exit(1)
        message = get_message_content(args.message, args.template, None)
        kwargs = {"body": message, "path": args.path, "line": args.line, "side": args.side}
    
    elif args.action == "update":
        if not args.comment_id:
            print("❌ update アクションには --comment-id が必要です")
            sys.exit(1)
        message = get_message_content(args.message, args.template, None)
        kwargs = {"comment_id": args.comment_id, "new_body": message}
    
    elif args.action == "delete":
        if not args.comment_id:
            print("❌ delete アクションには --comment-id が必要です")
            sys.exit(1)
        kwargs = {"comment_id": args.comment_id}
    
    try:
        curl_command = client.generate_curl_command(pr_info, args.action, **kwargs)
        print("🔧 生成された curl コマンド:")
        print()
        print(curl_command)
        print()
        print("💡 このコマンドをコピーして実行してください")
    except APIError as e:
        print(f"❌ curl コマンド生成失敗: {e}")
        sys.exit(1)


def cmd_list_templates(args) -> None:
    """テンプレート一覧表示"""
    templates = {
        "fixed": "✅ Fixed! Thanks for the feedback.",
        "acknowledged": "👍 Acknowledged. I'll address this in the next update.",
        "clarification": "🤔 Could you provide more details about this issue?",
        "wontfix": "⚠️ I understand the concern, but this is intentional due to [reason].",
        "duplicate": "🔄 This appears to be a duplicate of another comment. See: [reference]",
        "resolved": "✅ This issue has been resolved.",
        "investigating": "🔍 Looking into this issue. Will update soon.",
        "question": "❓ I have a question about this feedback: [question]"
    }
    
    print("📝 利用可能な返信テンプレート:")
    print()
    for name, content in templates.items():
        print(f"  {name:15} : {content}")
    print()
    print("💡 使用例: --template fixed")


def main() -> None:
    """メイン関数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # デバッグモードの設定
    setup_logging(args.debug)
    
    # コマンドが指定されていない場合はヘルプを表示
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # list-templates は特別処理（GitHub API不要）
    if args.command == "list-templates":
        cmd_list_templates(args)
        return
    
    # GitHub トークンの取得
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ GitHub トークンが必要です。")
        print("   環境変数 GITHUB_TOKEN を設定するか、--token オプションを使用してください。")
        sys.exit(1)
    
    try:
        # GitHub クライアントの初期化
        client = GitHubClient(token)
        
        # プルリクエスト情報の解析
        pr_info = client.parse_pr_url(args.pr_url)
        
        print(f"🔗 プルリクエスト: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")
        
        # 各コマンドの実行
        if args.command == "reply":
            cmd_reply(args, client, pr_info)
        elif args.command == "batch-reply":
            cmd_batch_reply(args, client, pr_info)
        elif args.command == "create":
            cmd_create(args, client, pr_info)
        elif args.command == "update":
            cmd_update(args, client, pr_info)
        elif args.command == "delete":
            cmd_delete(args, client, pr_info)
        elif args.command == "generate-curl":
            cmd_generate_curl(args, client, pr_info)
        else:
            print(f"❌ 未知のコマンド: {args.command}")
            sys.exit(1)
            
    except AuthenticationError as e:
        print(f"❌ 認証エラー: {e}")
        sys.exit(1)
    except APIError as e:
        print(f"❌ API エラー: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ 入力エラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 操作がキャンセルされました")
        sys.exit(1)
    except Exception as e:
        if args.debug:
            import traceback
            traceback.print_exc()
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()