#!/usr/bin/env python3
"""
GitHub Review Prompts - 統一CLI
全機能を統合したメインエントリーポイント
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# 軽量版用のインポート（依存関係がない場合）
try:
    # 既存モジュールのインポート
    if __name__ == "__main__":
        # 直接実行時は相対インポートを回避
        sys.path.insert(0, str(Path(__file__).parent))
        from core.prompt_engine import UnifiedPromptEngine
        try:
            from config import ConfigManager
            from github_client import GitHubClient
            from comment_processor import CommentProcessor
            from output_formatter import OutputFormatter
            from models import APIError, AuthenticationError, RateLimitError, PERSONAS
            from utils.validators import validate_pr_url, validate_persona, validate_output_format
        except ImportError:
            raise ImportError("フル機能版の依存関係が不足")
    else:
        # モジュールとして実行時
        from .core.prompt_engine import UnifiedPromptEngine
        from .config import ConfigManager
        from .github_client import GitHubClient
        from .comment_processor import CommentProcessor
        from .output_formatter import OutputFormatter
        from .models import APIError, AuthenticationError, RateLimitError, PERSONAS
        from .utils.validators import validate_pr_url, validate_persona, validate_output_format
    FULL_FEATURES_AVAILABLE = True
except ImportError:
    # 軽量版のみ
    if __name__ == "__main__":
        sys.path.insert(0, str(Path(__file__).parent))
        from core.prompt_engine import UnifiedPromptEngine
    else:
        from .core.prompt_engine import UnifiedPromptEngine
    FULL_FEATURES_AVAILABLE = False
    import urllib.request
    import urllib.parse
    import re
    import subprocess
    
    # 軽量版用のダミー定義
    PERSONAS = {"engineer": "Engineer"}
    
    def validate_pr_url(url):
        return bool(re.match(r'https://github\.com/[^/]+/[^/]+/pull/\d+', url))
    
    def validate_persona(persona):
        return persona in PERSONAS
    
    def validate_output_format(fmt):
        return fmt in ["markdown", "json", "text"]

logger = logging.getLogger(__name__)


class UnifiedCLI:
    """統一CLI"""
    
    def __init__(self):
        self.prompt_engine = UnifiedPromptEngine()
        self.full_features = FULL_FEATURES_AVAILABLE
    
    def create_parser(self) -> argparse.ArgumentParser:
        """引数パーサーを作成"""
        parser = argparse.ArgumentParser(
            prog="github-review-prompts",
            description="🔄 GitHub PR Review Comments - 統一AI処理ツール",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  # プロンプト生成
  %(prog)s generate https://github.com/owner/repo/pull/123
  
  # 軽量版
  %(prog)s generate --lightweight https://github.com/owner/repo/pull/123
  
  # コメント返信
  %(prog)s reply https://github.com/owner/repo/pull/123 --comment-id 456 --message "修正しました"
  
  # 一括返信
  %(prog)s batch-reply https://github.com/owner/repo/pull/123 --replies-file replies.json

環境変数:
  GITHUB_TOKEN    GitHub Personal Access Token (必須)
  GITHUB_API_URL  GitHub API Base URL (デフォルト: https://api.github.com)
"""
        )
        
        # 共通オプション
        parser.add_argument("--debug", action="store_true", help="デバッグログを有効化")
        parser.add_argument("--token", help="GitHub トークン (環境変数 GITHUB_TOKEN で設定可能)")
        parser.add_argument("--api-url", default="https://api.github.com", help="GitHub API URL")
        
        # サブコマンド
        subparsers = parser.add_subparsers(dest="command", help="利用可能なコマンド")
        
        # generate サブコマンド
        self._add_generate_parser(subparsers)
        
        # reply サブコマンド  
        self._add_reply_parser(subparsers)
        
        # batch-reply サブコマンド
        self._add_batch_reply_parser(subparsers)
        
        # create サブコマンド
        self._add_create_parser(subparsers)
        
        # update サブコマンド
        self._add_update_parser(subparsers)
        
        # delete サブコマンド
        self._add_delete_parser(subparsers)
        
        # generate-curl サブコマンド
        self._add_generate_curl_parser(subparsers)
        
        # list-templates サブコマンド
        self._add_list_templates_parser(subparsers)
        
        return parser
    
    def _add_generate_parser(self, subparsers):
        """generate サブコマンドの追加"""
        generate_parser = subparsers.add_parser("generate", help="AIプロンプトを生成")
        generate_parser.add_argument("pr_url", help="プルリクエストのURL")
        
        # プロンプト生成オプション
        generate_parser.add_argument("--persona", choices=list(PERSONAS.keys()) if FULL_FEATURES_AVAILABLE else ["engineer"], 
                                   default="engineer", help="AI ペルソナを選択")
        generate_parser.add_argument("--output-format", choices=["markdown", "json", "text"], 
                                   default="markdown", help="出力形式")
        generate_parser.add_argument("--lightweight", action="store_true", help="軽量版プロンプト生成")
        generate_parser.add_argument("--no-confirm", action="store_true", help="確認をスキップして連続処理")
        generate_parser.add_argument("--auto-commit", action="store_true", help="自動コミット・プッシュモード")
        
        # フィルタリングオプション
        generate_parser.add_argument("--include-resolved", action="store_true", help="解決済みコメントも含める")
        generate_parser.add_argument("--author", help="特定作者のコメントのみ抽出")
        generate_parser.add_argument("--since", help="指定日時以降のコメント (YYYY-MM-DD 形式)")
        generate_parser.add_argument("--file-pattern", help="ファイルパスの正規表現フィルタ")
        
        # 出力オプション
        generate_parser.add_argument("--output", "-o", help="出力ファイル (指定なしで標準出力)")
        generate_parser.add_argument("--append", action="store_true", help="ファイルに追記 (新規作成ではなく)")
    
    def _add_reply_parser(self, subparsers):
        """reply サブコマンドの追加"""
        reply_parser = subparsers.add_parser("reply", help="コメントに返信する")
        reply_parser.add_argument("pr_url", help="プルリクエストのURL")
        reply_parser.add_argument("--comment-id", type=int, required=True, help="返信対象のコメントID")
        reply_group = reply_parser.add_mutually_exclusive_group(required=True)
        reply_group.add_argument("--message", help="返信メッセージ")
        reply_group.add_argument("--template", choices=["fixed", "acknowledged", "clarification", "wontfix", 
                                                       "duplicate", "resolved", "investigating", "question"], 
                               help="返信テンプレート")
        reply_parser.add_argument("--file", help="返信メッセージをファイルから読み込む")
    
    def _add_batch_reply_parser(self, subparsers):
        """batch-reply サブコマンドの追加"""
        batch_parser = subparsers.add_parser("batch-reply", help="複数のコメントに一括返信")
        batch_parser.add_argument("pr_url", help="プルリクエストのURL")
        batch_parser.add_argument("--replies-file", required=True, help="返信情報のJSONファイル")
        batch_parser.add_argument("--delay", type=float, default=0.5, help="返信間の遅延秒数")
    
    def _add_create_parser(self, subparsers):
        """create サブコマンドの追加"""
        create_parser = subparsers.add_parser("create", help="新しいコメントを作成")
        create_parser.add_argument("pr_url", help="プルリクエストのURL")
        create_parser.add_argument("--path", required=True, help="ファイルパス")
        create_parser.add_argument("--line", type=int, required=True, help="行番号")
        create_parser.add_argument("--message", help="コメント内容")
        create_parser.add_argument("--file", help="コメント内容をファイルから読み込む")
        create_parser.add_argument("--side", choices=["LEFT", "RIGHT"], default="RIGHT", help="コメント位置")
    
    def _add_update_parser(self, subparsers):
        """update サブコマンドの追加"""
        update_parser = subparsers.add_parser("update", help="既存のコメントを更新")
        update_parser.add_argument("pr_url", help="プルリクエストのURL")
        update_parser.add_argument("--comment-id", type=int, required=True, help="更新対象のコメントID")
        update_parser.add_argument("--message", help="新しいコメント内容")
        update_parser.add_argument("--file", help="コメント内容をファイルから読み込む")
    
    def _add_delete_parser(self, subparsers):
        """delete サブコマンドの追加"""
        delete_parser = subparsers.add_parser("delete", help="コメントを削除")
        delete_parser.add_argument("pr_url", help="プルリクエストのURL")
        delete_parser.add_argument("--comment-id", type=int, required=True, help="削除対象のコメントID")
        delete_parser.add_argument("--confirm", action="store_true", help="削除確認をスキップ")
    
    def _add_generate_curl_parser(self, subparsers):
        """generate-curl サブコマンドの追加"""
        curl_parser = subparsers.add_parser("generate-curl", help="curl コマンドを生成")
        curl_parser.add_argument("pr_url", help="プルリクエストのURL")
        curl_parser.add_argument("--action", choices=["reply", "create", "update", "delete"], 
                               required=True, help="実行するアクション")
        curl_parser.add_argument("--comment-id", type=int, help="コメントID（reply, update, delete で必要）")
        curl_parser.add_argument("--message", help="メッセージ内容")
        curl_parser.add_argument("--template", help="テンプレート名")
        curl_parser.add_argument("--path", help="ファイルパス（create で必要）")
        curl_parser.add_argument("--line", type=int, help="行番号（create で必要）")
        curl_parser.add_argument("--side", choices=["LEFT", "RIGHT"], default="RIGHT", help="コメント位置")
    
    def _add_list_templates_parser(self, subparsers):
        """list-templates サブコマンドの追加"""
        list_parser = subparsers.add_parser("list-templates", help="利用可能なテンプレート一覧を表示")
    
    def setup_logging(self, debug: bool = False):
        """ログ設定"""
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def run(self, args: List[str] = None) -> int:
        """メイン実行"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # ログ設定
        self.setup_logging(parsed_args.debug)
        
        # コマンドが指定されていない場合
        if not parsed_args.command:
            parser.print_help()
            return 1
        
        try:
            # GitHub トークン取得
            token = parsed_args.token or os.getenv("GITHUB_TOKEN")
            if not token:
                logger.error("GitHub トークンが設定されていません。--token オプションまたは GITHUB_TOKEN 環境変数を設定してください。")
                return 1
            
            # コマンド実行
            if parsed_args.command == "generate":
                return self._handle_generate(parsed_args, token)
            elif parsed_args.command == "reply":
                return self._handle_reply(parsed_args, token)
            elif parsed_args.command == "batch-reply":
                return self._handle_batch_reply(parsed_args, token)
            elif parsed_args.command == "create":
                return self._handle_create(parsed_args, token)
            elif parsed_args.command == "update":
                return self._handle_update(parsed_args, token)
            elif parsed_args.command == "delete":
                return self._handle_delete(parsed_args, token)
            elif parsed_args.command == "generate-curl":
                return self._handle_generate_curl(parsed_args, token)
            elif parsed_args.command == "list-templates":
                return self._handle_list_templates(parsed_args)
            else:
                logger.error(f"未知のコマンド: {parsed_args.command}")
                return 1
                
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
        """generate コマンドの処理"""
        # PR URL の検証
        if not validate_pr_url(args.pr_url):
            logger.error("無効なPR URLです")
            return 1
        
        if args.lightweight or not self.full_features:
            return self._handle_lightweight_generate(args, token)
        else:
            return self._handle_full_generate(args, token)
    
    def _handle_lightweight_generate(self, args, token: str) -> int:
        """軽量版 generate の処理"""
        try:
            # 簡易的なPR情報とコメント取得
            pr_info, comments = self._fetch_pr_data_lightweight(args.pr_url, token)
            
            # プロンプト生成
            prompt = self.prompt_engine.generate_lightweight_prompt(comments, pr_info)
            
            # 出力
            self._output_result(prompt, args.output, args.append)
            
            logger.info(f"軽量版プロンプトを生成しました ({len(comments)} コメント)")
            return 0
            
        except Exception as e:
            logger.error(f"軽量版プロンプト生成でエラー: {e}")
            return 1
    
    def _handle_full_generate(self, args, token: str) -> int:
        """フル機能版 generate の処理"""
        try:
            # 設定管理
            config = ConfigManager()
            
            # GitHub クライアント
            github_client = GitHubClient(token, args.api_url)
            
            # PR情報とコメント取得
            pr_info = github_client.get_pr_info(args.pr_url)
            comments = github_client.get_pr_comments(args.pr_url)
            
            # フィルタリング
            if args.author:
                comments = [c for c in comments if c.get('user', {}).get('login') == args.author]
            
            if args.since:
                # 日付フィルタリング実装
                pass
            
            if args.file_pattern:
                pattern = re.compile(args.file_pattern)
                comments = [c for c in comments if c.get('path') and pattern.search(c['path'])]
            
            # プロンプト生成オプション
            options = {
                'auto_commit': args.auto_commit,
                'no_confirm': args.no_confirm,
                'persona': args.persona,
                'output_format': args.output_format
            }
            
            # プロンプト生成
            prompt = self.prompt_engine.generate_main_prompt(comments, pr_info, options)
            
            # 出力
            self._output_result(prompt, args.output, args.append)
            
            logger.info(f"プロンプトを生成しました ({len(comments)} コメント)")
            return 0
            
        except Exception as e:
            logger.error(f"プロンプト生成でエラー: {e}")
            return 1
    
    def _handle_reply(self, args, token: str) -> int:
        """reply コマンドの処理"""
        # curl_reply.py の機能を統合
        from .curl_reply import GitHubCurlReply
        
        try:
            curl_reply = GitHubCurlReply(token, args.api_url)
            
            # メッセージ取得
            message = self._get_message_content(args.message, args.template, args.file)
            
            # 返信実行
            result = curl_reply.reply_to_comment(args.pr_url, args.comment_id, message)
            
            if result:
                logger.info("返信を送信しました")
                return 0
            else:
                logger.error("返信の送信に失敗しました")
                return 1
                
        except Exception as e:
            logger.error(f"返信処理でエラー: {e}")
            return 1
    
    def _handle_batch_reply(self, args, token: str) -> int:
        """batch-reply コマンドの処理"""
        try:
            # 返信ファイル読み込み
            with open(args.replies_file, 'r', encoding='utf-8') as f:
                replies_data = json.load(f)
            
            from .curl_reply import GitHubCurlReply
            curl_reply = GitHubCurlReply(token, args.api_url)
            
            success_count = 0
            for reply in replies_data:
                try:
                    result = curl_reply.reply_to_comment(
                        args.pr_url,
                        reply['comment_id'],
                        reply['message']
                    )
                    if result:
                        success_count += 1
                        logger.info(f"コメント {reply['comment_id']} に返信しました")
                    
                    # 遅延
                    if args.delay > 0:
                        time.sleep(args.delay)
                        
                except Exception as e:
                    logger.error(f"コメント {reply.get('comment_id')} への返信でエラー: {e}")
            
            logger.info(f"一括返信完了: {success_count}/{len(replies_data)} 件成功")
            return 0 if success_count == len(replies_data) else 1
            
        except Exception as e:
            logger.error(f"一括返信処理でエラー: {e}")
            return 1
    
    def _handle_create(self, args, token: str) -> int:
        """create コマンドの処理"""
        # 新規コメント作成機能
        logger.info("create コマンドは未実装です")
        return 1
    
    def _handle_update(self, args, token: str) -> int:
        """update コマンドの処理"""
        # コメント更新機能
        logger.info("update コマンドは未実装です")
        return 1
    
    def _handle_delete(self, args, token: str) -> int:
        """delete コマンドの処理"""
        # コメント削除機能
        logger.info("delete コマンドは未実装です")
        return 1
    
    def _handle_generate_curl(self, args, token: str) -> int:
        """generate-curl コマンドの処理"""
        # curlコマンド生成
        logger.info("generate-curl コマンドは未実装です")
        return 1
    
    def _handle_list_templates(self, args) -> int:
        """list-templates コマンドの処理"""
        templates = ["fixed", "acknowledged", "clarification", "wontfix", 
                    "duplicate", "resolved", "investigating", "question"]
        
        print("利用可能なテンプレート:")
        for template in templates:
            print(f"  - {template}")
        
        return 0
    
    def _fetch_pr_data_lightweight(self, pr_url: str, token: str) -> tuple:
        """軽量版でのPRデータ取得"""
        # URLからPR情報を抽出
        match = re.match(r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
        if not match:
            raise ValueError("無効なPR URL")
        
        owner, repo, pr_number = match.groups()
        
        # GitHub API 呼び出し
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        comments_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # PR情報取得
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            pr_data = json.loads(response.read().decode())
        
        # コメント取得
        req = urllib.request.Request(comments_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            comments_data = json.loads(response.read().decode())
        
        pr_info = {
            'title': pr_data.get('title'),
            'url': pr_url,
            'author': pr_data.get('user', {}).get('login'),
            'head_branch': pr_data.get('head', {}).get('ref'),
            'base_branch': pr_data.get('base', {}).get('ref'),
            'owner': owner,
            'repo': repo,
            'number': int(pr_number)
        }
        
        return pr_info, comments_data
    
    def _get_message_content(self, message: str, template: str, file_path: str) -> str:
        """メッセージ内容を取得"""
        if message:
            return message
        elif file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        elif template:
            # テンプレート展開
            templates = {
                'fixed': '修正しました。',
                'acknowledged': 'ご指摘ありがとうございます。確認いたします。',
                'clarification': '申し訳ございませんが、詳細を教えていただけますでしょうか？',
                'wontfix': 'この件は対応しない方針です。',
                'duplicate': '重複したご指摘です。',
                'resolved': '解決済みです。',
                'investigating': '調査中です。',
                'question': 'ご質問ありがとうございます。'
            }
            return templates.get(template, message)
        else:
            raise ValueError("メッセージ、テンプレート、またはファイルのいずれかを指定してください")
    
    def _output_result(self, content: str, output_file: str = None, append: bool = False):
        """結果を出力"""
        if output_file:
            mode = 'a' if append else 'w'
            with open(output_file, mode, encoding='utf-8') as f:
                f.write(content)
                if append:
                    f.write('\n\n---\n\n')
            logger.info(f"結果を {output_file} に出力しました")
        else:
            print(content)


def main() -> int:
    """メインエントリーポイント"""
    cli = UnifiedCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())