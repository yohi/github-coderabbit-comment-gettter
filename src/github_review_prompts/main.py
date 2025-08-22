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
    from utils.validators import validate_pr_url, validate_persona, validate_output_format
else:
    # モジュールとして実行時
    from .core.prompt_engine import UnifiedPromptEngine
    from .config import ConfigManager
    from .github_client import GitHubClient
    from .comment_processor import CommentProcessor
    from .output_formatter import OutputFormatter
    from .models import APIError, AuthenticationError, RateLimitError, PERSONAS
    from .utils.validators import validate_pr_url, validate_persona, validate_output_format

logger = logging.getLogger(__name__)


class UnifiedCLI:
    """統一CLI（フル機能版）"""
    
    def __init__(self):
        self.prompt_engine = UnifiedPromptEngine()
    
    def create_parser(self) -> argparse.ArgumentParser:
        """引数パーサーを作成（従来フォーマット互換）"""
        parser = argparse.ArgumentParser(
            prog="github-review-prompts",
            description="🔄 GitHub PR Review Comments - 統一AI処理ツール",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  # プロンプト生成
  %(prog)s https://github.com/owner/repo/pull/123
  %(prog)s --no-confirm --auto-commit https://github.com/owner/repo/pull/123
  
  # コメント返信
  %(prog)s --reply-to 456 --reply-message "修正しました" https://github.com/owner/repo/pull/123

環境変数:
  GITHUB_TOKEN    GitHub Personal Access Token (必須)
  GITHUB_API_URL  GitHub API Base URL (デフォルト: https://api.github.com)
"""
        )
        
        # メイン引数（PR URL）
        parser.add_argument("pr_url", help="GitHub プルリクエストURL")
        
        # プロンプト生成オプション
        parser.add_argument("--persona", choices=list(PERSONAS.keys()), 
                           default="engineer", help="AI ペルソナを選択")
        parser.add_argument("--format", choices=["markdown", "json", "text"], 
                           default="markdown", help="出力形式")
        parser.add_argument("--no-confirm", action="store_true", help="確認をスキップして連続処理")
        parser.add_argument("--auto-commit", action="store_true", help="自動コミット・プッシュモード")
        
        # フィルタリングオプション
        parser.add_argument("--include-resolved", action="store_true", help="解決済みコメントも含める")
        parser.add_argument("--author", help="特定作者のコメントのみ抽出")
        parser.add_argument("--since", help="指定日時以降のコメント (YYYY-MM-DD 形式)")
        parser.add_argument("--file-pattern", help="ファイルパスの正規表現フィルタ")
        
        # 返信オプション
        parser.add_argument("--reply-to", type=int, help="指定されたコメントIDに返信")
        parser.add_argument("--reply-message", help="返信メッセージ（--reply-toと組み合わせて使用）")
        parser.add_argument("--reply-template", choices=["fixed", "acknowledged", "clarification", "wontfix", 
                                                        "duplicate", "resolved", "investigating", "question"], 
                           help="返信テンプレート")
        
        # 出力オプション
        parser.add_argument("--output", "-o", help="出力ファイル (指定なしで標準出力)")
        parser.add_argument("--append", action="store_true", help="ファイルに追記 (新規作成ではなく)")
        parser.add_argument("--no-color", action="store_true", help="カラー出力を無効にする")
        
        # システムオプション
        parser.add_argument("--debug", action="store_true", help="デバッグログを有効化")
        parser.add_argument("--token", help="GitHub トークン (環境変数 GITHUB_TOKEN で設定可能)")
        parser.add_argument("--api-url", default="https://api.github.com", help="GitHub API URL")
        
        return parser
    
    def setup_logging(self, debug: bool = False):
        """ログ設定"""
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
                logger.error("GitHub トークンが設定されていません。--token オプションまたは GITHUB_TOKEN 環境変数を設定してください。")
                return 1
            
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
            # 設定管理
            config = ConfigManager()
            
            # GitHub クライアント
            github_client = GitHubClient(token, args.api_url)
            
            # PR URLをパース
            pr_info = github_client.parse_pr_url(args.pr_url)
            
            # PR基本情報とコメント取得
            pr_basic_info = github_client.get_pr_basic_info(pr_info)
            comments = github_client.get_pr_review_comments(pr_info)
            
            # プロンプト用のPR情報を構築
            pr_dict = {
                'title': pr_basic_info.get('title'),
                'url': args.pr_url,
                'author': pr_basic_info.get('user', {}).get('login'),
                'head_branch': pr_basic_info.get('head', {}).get('ref'),
                'base_branch': pr_basic_info.get('base', {}).get('ref'),
                'owner': pr_info.owner,
                'repo': pr_info.repo,
                'number': pr_info.pull_number
            }
            
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
                'output_format': args.format
            }
            
            # プロンプト生成
            prompt = self.prompt_engine.generate_main_prompt(comments, pr_dict, options)
            
            # 出力
            self._output_result(prompt, args.output, args.append)
            
            logger.info(f"プロンプトを生成しました ({len(comments)} コメント)")
            return 0
            
        except Exception as e:
            logger.error(f"プロンプト生成でエラー: {e}")
            return 1
    

    
    def _handle_reply(self, args, token: str) -> int:
        """reply 処理"""
        try:
            # メッセージ取得
            message = self._get_message_content(args.reply_message, args.reply_template, None)
            
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