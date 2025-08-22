"""
[非推奨] CLI インターフェース
このファイルは非推奨です。main.py の統一CLIを使用してください。

互換性のため一時的に残されています。
新しいコマンド: python -m github_review_prompts.main generate [OPTIONS]
"""

import warnings
warnings.warn(
    "このCLIは非推奨です。main.py の統一CLIを使用してください。",
    DeprecationWarning,
    stacklevel=2
)

import argparse
import logging
import os
import sys
from typing import Optional, Dict, Any
from pathlib import Path

from .config import ConfigManager
from .github_client import GitHubClient
from .comment_processor import CommentProcessor
from .prompt_generator import AIPromptGenerator
from .output_formatter import OutputFormatter
from .models import APIError, AuthenticationError, RateLimitError, PERSONAS
from .utils.validators import validate_pr_url, validate_persona, validate_output_format


class CLIInterface:
    """コマンドラインインターフェース"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = None  # setup_logging後に初期化

    def create_parser(self) -> argparse.ArgumentParser:
        """引数パーサーを作成"""
        parser = argparse.ArgumentParser(
            prog="github-review-prompts",
            description="GitHub PR review comments からAIエージェント用プロンプトを抽出",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  # 基本的な使用法
  github-review-prompts https://github.com/owner/repo/pull/123

  # ファイルに出力
  github-review-prompts -o prompts.md https://github.com/owner/repo/pull/123
  
  # マークダウンファイルを自動生成
  github-review-prompts --save-file https://github.com/owner/repo/pull/123

  # セキュリティアナリストのペルソナで分析
  github-review-prompts --persona security-analyst https://github.com/owner/repo/pull/123

  # 解決済みコメントも含める
  github-review-prompts --include-resolved https://github.com/owner/repo/pull/123

  # JSON形式で出力
  github-review-prompts --format json https://github.com/owner/repo/pull/123

  # 確認スキップモードで実行
  github-review-prompts --no-confirm https://github.com/owner/repo/pull/123

  # 自動コミット・プッシュ機能付きで実行
  github-review-prompts --auto-commit https://github.com/owner/repo/pull/123

  # 両方のオプションを組み合わせ
  github-review-prompts --no-confirm --auto-commit https://github.com/owner/repo/pull/123

  # コピーペースト最適化（カラー無効）
  github-review-prompts --no-color https://github.com/owner/repo/pull/123

ファイル生成オプション:
  デフォルトではコンソール出力のみ。以下のオプションでファイル生成可能：
  
  # 指定ファイル名で保存
  github-review-prompts -o custom_name.md [PR_URL]
  
  # 自動ファイル名で保存（coderabbit_review_[repo]_pr[number].md）
  github-review-prompts --save-file [PR_URL]

環境変数:
  GITHUB_TOKEN                 GitHub APIトークン（必須）
  DEFAULT_OUTPUT_FORMAT        デフォルトの出力形式 (markdown/json)
  DEFAULT_PERSONA              デフォルトのペルソナ
  LOG_LEVEL                    ログレベル (DEBUG/INFO/WARNING/ERROR)
            """
        )

        # プルリクエストURL（一部のオプションでは任意）
        parser.add_argument(
            "pr_url",
            nargs="?",
            help="GitHub プルリクエストURL"
        )

        # 出力オプション
        output_group = parser.add_argument_group("出力オプション")
        output_group.add_argument(
            "-o", "--output",
            type=str,
            help="出力ファイルパス（未指定時はコンソールに出力）"
        )
        output_group.add_argument(
            "--format",
            choices=["markdown", "json"],
            default="markdown",
            help="出力形式 (デフォルト: markdown)"
        )
        output_group.add_argument(
            "--save-file",
            action="store_true",
            help="マークダウンファイルを自動生成する（デフォルトはコンソール出力のみ）"
        )

        # AIペルソナオプション
        persona_group = parser.add_argument_group("AIペルソナオプション")
        persona_group.add_argument(
            "--persona",
            choices=list(PERSONAS.keys()),
            default="code-reviewer",
            help="AIエージェントのペルソナ (デフォルト: code-reviewer)"
        )
        persona_group.add_argument(
            "--list-personas",
            action="store_true",
            help="利用可能なペルソナの一覧を表示"
        )

        # フィルタリングオプション
        filter_group = parser.add_argument_group("フィルタリングオプション")
        filter_group.add_argument(
            "--include-resolved",
            action="store_true",
            help="解決済みコメントも含める"
        )
        filter_group.add_argument(
            "--categories",
            nargs="+",
            choices=["security", "performance", "style", "logic", "general"],
            help="含めるカテゴリを指定"
        )
        filter_group.add_argument(
            "--priorities",
            nargs="+",
            choices=["high", "medium", "low"],
            help="含める優先度を指定"
        )
        filter_group.add_argument(
            "--file-patterns",
            nargs="+",
            help="含めるファイルパターンを指定（ワイルドカード対応）"
        )

        # デバッグ・開発オプション
        debug_group = parser.add_argument_group("デバッグ・開発オプション")
        debug_group.add_argument(
            "--debug",
            action="store_true",
            help="デバッグモードを有効にする"
        )
        debug_group.add_argument(
            "--debug-comment",
            type=int,
            help="特定のコメントIDをデバッグ"
        )
        debug_group.add_argument(
            "--analyze-all",
            action="store_true",
            help="全コメントの解決状況を分析（詳細ログ）"
        )
        debug_group.add_argument(
            "--dry-run",
            action="store_true",
            help="実際の処理を行わずに設定を確認"
        )

        # その他のオプション
        misc_group = parser.add_argument_group("その他")
        misc_group.add_argument(
            "--config",
            type=str,
            help="設定ファイルパス"
        )
        misc_group.add_argument(
            "--summary-only",
            action="store_true",
            help="サマリーレポートのみを出力"
        )
        misc_group.add_argument(
            "--no-confirm",
            action="store_true",
            help="各コメント処理後の確認をスキップする"
        )
        misc_group.add_argument(
            "--auto-commit",
            action="store_true",
            help="作業完了後に自動的にgit commit & pushを実行する"
        )
        misc_group.add_argument(
            "--no-color",
            action="store_true",
            help="カラー出力を無効にする（コピーペースト最適化）"
        )
        misc_group.add_argument(
            "--version",
            action="version",
            version="%(prog)s 1.0.0"
        )

        return parser

    def setup_logging(self, debug: bool = False) -> None:
        """ログ設定をセットアップ"""
        level = "DEBUG" if debug else None
        self.config_manager.setup_logging(level)
        self.logger = logging.getLogger(__name__)

    def validate_arguments(self, args: argparse.Namespace) -> Optional[str]:
        """引数の検証"""
        errors = []

        # PR URL検証（pr_urlが提供されている場合のみ）
        if args.pr_url and not validate_pr_url(args.pr_url):
            errors.append(f"無効なプルリクエストURL: {args.pr_url}")

        # ペルソナ検証
        if not validate_persona(args.persona):
            errors.append(f"無効なペルソナ: {args.persona}")

        # 出力形式検証
        if not validate_output_format(args.format):
            errors.append(f"無効な出力形式: {args.format}")

        # ファイルパス検証
        if args.output:
            from .utils.validators import validate_file_path
            if not validate_file_path(args.output, allow_create=True):
                errors.append(f"無効な出力ファイルパス: {args.output}")

        # デバッグコメントID検証
        if args.debug_comment and args.debug_comment <= 0:
            errors.append("デバッグコメントIDは正の整数である必要があります")

        return "; ".join(errors) if errors else None

    def display_personas(self) -> None:
        """利用可能なペルソナの一覧を表示"""
        print("\n利用可能なAIペルソナ:\n")

        for persona_id, config in PERSONAS.items():
            print(f"🤖 {persona_id}")
            print(f"   役割: {config.role}")
            print(f"   専門: {config.expertise}")
            print(f"   特徴: {config.approach}")
            print(f"   口調: {config.tone}")
            print()

    def run(self, args: Optional[list] = None) -> int:
        """メイン実行関数"""
        try:
            # 引数パース
            parser = self.create_parser()
            parsed_args = parser.parse_args(args)

            # ペルソナ一覧表示
            if parsed_args.list_personas:
                self.display_personas()
                return 0

            # ログ設定
            self.setup_logging(parsed_args.debug)

            # 引数検証
            validation_error = self.validate_arguments(parsed_args)
            if validation_error:
                self.logger.error(f"引数検証エラー: {validation_error}")
                parser.print_help()
                return 1

            # カラー出力設定
            if parsed_args.no_color:
                os.environ['NO_COLOR'] = '1'
            
            # 設定読み込み
            if parsed_args.config:
                self.config_manager.config_file = parsed_args.config

            config = self.config_manager.load_config()

            # コマンドライン引数で設定を上書き
            if parsed_args.output:
                config.output_file = parsed_args.output
            if parsed_args.format:
                config.output_format = parsed_args.format
            if parsed_args.persona:
                config.persona = parsed_args.persona
            config.include_resolved = parsed_args.include_resolved
            config.debug_mode = parsed_args.debug

            # Dry run モード
            if parsed_args.dry_run:
                self._display_config(config, parsed_args)
                return 0

            # PR URLが必要な処理の場合にチェック
            if not parsed_args.pr_url:
                self.logger.error("プルリクエストURLが必要です")
                parser.print_help()
                return 1

            # メイン処理実行
            return self._execute_main_process(config, parsed_args)

        except KeyboardInterrupt:
            print("\n\n⚠️  処理がユーザーによって中断されました。")
            return 130
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"予期しないエラー: {str(e)}", exc_info=True)
            else:
                print(f"予期しないエラー: {str(e)}", file=sys.stderr)
            return 1

    def _display_config(self, config, args: argparse.Namespace) -> None:
        """設定確認用の表示（Dry runモード）"""
        print("\n🔧 設定確認 (Dry Run Mode)\n")
        print(f"プルリクエストURL: {args.pr_url}")
        print(f"出力形式: {config.output_format}")
        print(f"ペルソナ: {config.persona}")
        output_description = config.output_file or ('自動生成ファイル' if args.save_file else 'コンソール出力のみ')
        print(f"出力ファイル: {output_description}")
        print(f"解決済み含む: {config.include_resolved}")
        print(f"デバッグモード: {config.debug_mode}")
        print(f"ファイル自動生成: {'有効' if args.save_file else '無効'}")

        if config.github_token:
            print("GitHubトークン: 設定済み（マスク済み）")
        else:
            print("⚠️  GitHubトークン: 未設定")

        if args.categories:
            print(f"カテゴリフィルター: {', '.join(args.categories)}")

        if args.priorities:
            print(f"優先度フィルター: {', '.join(args.priorities)}")

        if args.file_patterns:
            print(f"ファイルパターン: {', '.join(args.file_patterns)}")

    def _execute_main_process(self, config, args: argparse.Namespace) -> int:
        """メイン処理を実行"""
        try:
            self.logger.info("GitHub Review Prompts AI Agent 開始")

            # GitHub クライアント初期化
            github_client = GitHubClient(token=config.github_token)

            # 認証テスト
            if config.github_token:
                try:
                    auth_info = github_client.test_authentication()
                    self.logger.info(f"GitHub認証成功: {auth_info['user']['login']}")
                except (AuthenticationError, APIError) as e:
                    self.logger.error(f"GitHub認証失敗: {str(e)}")
                    return 1

            # PR情報解析
            pr_info = github_client.parse_pr_url(args.pr_url)
            self.logger.info(f"PR情報: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")

            # PR基本情報取得
            pr_basic_info = github_client.get_pr_basic_info(pr_info)
            self.logger.info(f"タイトル: {pr_basic_info.get('title', 'N/A')}")
            if pr_basic_info.get('head_branch') and pr_basic_info.get('base_branch'):
                head_repo = pr_basic_info.get('head_repo', 'N/A')
                head_branch = pr_basic_info.get('head_branch', 'N/A')
                base_repo = pr_basic_info.get('base_repo', 'N/A')
                base_branch = pr_basic_info.get('base_branch', 'N/A')
                self.logger.info(f"ソースブランチ: {head_repo}:{head_branch}")
                self.logger.info(f"ターゲットブランチ: {base_repo}:{base_branch}")

            # レビューコメント取得
            self.logger.info("レビューコメント取得開始...")
            review_comments = github_client.get_pr_review_comments(pr_info)

            # GraphQL APIで解決済みコメント検出
            self.logger.info("解決済みコメント検出開始...")
            resolved_ids, graphql_bodies = github_client.get_resolved_comments_via_graphql(pr_info)

            # コメント処理
            self.logger.info("コメント処理開始...")
            processor = CommentProcessor(github_client)
            prompts, stats = processor.process_comments(
                review_comments, resolved_ids, graphql_bodies, config.include_resolved, pr_basic_info
            )

            # フィルタリング適用
            if args.categories or args.priorities or args.file_patterns:
                prompts = processor.filter_prompts_by_criteria(
                    prompts, args.categories, args.priorities,
                    file_patterns=args.file_patterns
                )

            # プロンプト生成
            self.logger.info("AIプロンプト生成開始...")
            prompt_generator = AIPromptGenerator(config.persona, config.github_token)

            # メタデータ準備
            metadata = {
                "pr_info": {
                    "owner": pr_info.owner,
                    "repo": pr_info.repo,
                    "pull_number": pr_info.pull_number,
                    "url": pr_info.url,
                    **pr_basic_info
                },
                "persona": config.persona,
                "include_resolved": config.include_resolved,
                "filters": {
                    "categories": args.categories,
                    "priorities": args.priorities,
                    "file_patterns": args.file_patterns
                }
            }

            # 出力内容生成
            if args.summary_only:
                output_formatter = OutputFormatter(config.output_format)
                content = output_formatter.create_summary_report(prompts, stats, metadata)
            else:
                # レビュープロンプトとTODOリストを生成
                content = self._generate_review_prompt_with_todos(prompts, pr_basic_info, pr_info, args.no_confirm, args.auto_commit)

            # 出力処理
            output_formatter = OutputFormatter(config.output_format)
            formatted_content = output_formatter.format_output(content, metadata, stats)

            # ファイル出力の判定: --outputオプションまたは--save-fileオプションが指定された場合
            should_save_file = config.output_file or args.save_file
            
            if should_save_file:
                # 出力ファイル名の決定
                if config.output_file:
                    output_file = config.output_file
                else:
                    # --save-fileオプションの場合、自動でファイル名を生成
                    pr_number = pr_info.pull_number
                    repo_name = pr_info.repo
                    output_file = f"coderabbit_review_{repo_name}_pr{pr_number}.md"
                
                # ファイル出力
                success = output_formatter.save_to_file(formatted_content, output_file)
                if success:
                    self.logger.info(f"結果を {output_file} に保存しました")
                    # 簡潔なサマリーをコンソールに表示
                    print(f"\\n✅ 処理完了: {stats.prompts_extracted} 件のプロンプトを抽出")
                    print(f"📄 出力ファイル: {output_file}")
                else:
                    self.logger.error("ファイル保存に失敗しました")
                    return 1
            else:
                # コンソール出力のみ
                output_formatter.display_to_console(formatted_content, metadata, stats)

            # 分析モード（デバッグ用）
            if args.analyze_all:
                self._display_analysis_summary(processor, stats)

            self.logger.info("処理完了")
            return 0

        except (AuthenticationError, RateLimitError, APIError) as e:
            self.logger.error(f"GitHub API エラー: {str(e)}")
            return 1
        except Exception as e:
            self.logger.error(f"処理中にエラーが発生: {str(e)}", exc_info=True)
            return 1

    def _display_analysis_summary(self, processor: CommentProcessor, stats) -> None:
        """分析サマリーを表示（デバッグ用）"""
        summary = processor.get_processing_summary()

        print("\\n" + "="*50)
        print("📊 詳細分析サマリー")
        print("="*50)
        print(f"総コメント数: {summary['total_comments']}")
        print(f"解決済み: {summary['resolved_comments']}")
        print(f"未解決: {summary['unresolved_comments']}")
        print(f"プロンプト抽出: {summary['prompts_extracted']}")
        print(f"成功率: {summary['success_rate']:.1%}")
        print(f"処理時間: {summary['processing_time']:.2f}秒")

        if summary['errors']:
            print(f"\\n⚠️ エラー ({len(summary['errors'])} 件):")
            for error in summary['errors']:
                print(f"  - {error}")

    def _generate_review_prompt_with_todos(self, prompts, pr_basic_info, pr_info, no_confirm: bool = False, auto_commit: bool = False) -> str:
        """レビュープロンプトとTODOリストを生成"""

        # レビュープロンプトの内容を読み込み（相対パス）
        current_dir = Path(__file__).parent  # src/github_review_prompts/cli.py -> src/github_review_prompts/
        prompt_file = current_dir / "coderabbit_review_prompt.md"

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                review_prompt = f.read()
        except FileNotFoundError:
            # フォールバック: デフォルトプロンプト
            review_prompt = self._get_default_review_prompt(no_confirm, auto_commit)
        
        # オプション固有の指示を追加（ファイルから読み込んだプロンプトにも適用）
        if no_confirm or auto_commit:
            review_prompt += self._get_option_specific_instructions(no_confirm, auto_commit)

        # TODOリストを生成（PR基本情報も含める）
        todos_section = self._generate_todos_section(prompts, pr_info, pr_basic_info)

        # プロンプトとTODOを結合
        combined_content = f"""{review_prompt}

{todos_section}"""

        return combined_content

    def _get_default_review_prompt(self, no_confirm: bool = False, auto_commit: bool = False) -> str:
        """デフォルトのレビュープロンプト"""
        base_prompt = """# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## 対応方針
1. **一つずつ順番に処理**: 複数のコメントがある場合、必ず一つずつ順番に対応してください
2. **批判的評価**: レビューコメントが技術的に正しいかどうかを必ず検証してください
3. **対応判断**: 各コメントに対して以下のいずれかの対応を決定してください：
   - ✅ 対応実施（修正が必要で技術的に正しい）
   - ❌ 対応不要（技術的に間違っているか不適切）
   - 🤔 要確認（追加情報が必要）

## 作業手順
1. コメントの技術的妥当性を評価
2. 対応要否を判断し、理由を明記
3. **対応する場合**: 具体的な修正を実施
4. **対応しない場合**: GitHub APIを使って@coderabbitaiに技術的根拠を含む返信コメントを作成

## 出力フォーマット
各コメントに対して以下の形式で回答してください：

**コメント [番号]: [要約]**
- 判断: [✅/❌/🤔]
- 理由: [技術的根拠]
- 対応: [具体的な行動]"""
        
        # 確認オプションに応じた指示を追加
        if no_confirm:
            base_prompt += """

## ⚡ 作業モード設定
**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。"""
        else:
            base_prompt += """

次のコメントに進む前に、必ず確認を求めてください。"""
        
        # Git自動コミットオプションに応じた指示を追加
        if auto_commit:
            base_prompt += """

## 🔄 Git自動操作設定
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

### Git操作手順
1. **ステージング**: 変更したファイルのみを個別に `git add <ファイル名>` でステージング
2. **コミット**: `git commit -m "CodeRabbitレビューコメント対応 - [PR番号]"` でコミット
3. **プッシュ**: `git push` でリモートリポジトリに反映

⚠️ **注意**: `git add .` は使用しないでください。関係のないファイルまでコミットされる危険があります。

### コミットメッセージ例
```
CodeRabbitレビューコメント対応 - #123

- 認証モジュールの潜在的セキュリティ問題を修正
- データベース接続処理をリファクタリング
- 提案に従いエラーハンドリングを更新
```

**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。"""
        
        base_prompt += """

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。"""
        
        return base_prompt

    def _get_option_specific_instructions(self, no_confirm: bool = False, auto_commit: bool = False) -> str:
        """オプション固有の指示を生成"""
        instructions = ""
        
        if no_confirm or auto_commit:
            instructions += "\n\n## ⚡ 作業モード設定"
            
            if no_confirm:
                instructions += "\n**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。"
            
            if auto_commit:
                instructions += """
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

### Git操作手順
1. **ステージング**: 変更したファイルのみを個別に `git add <ファイル名>` でステージング
2. **コミット**: `git commit -m "CodeRabbitレビューコメント対応 - [PR番号]"` でコミット
3. **プッシュ**: `git push` でリモートリポジトリに反映

⚠️ **注意**: `git add .` は使用しないでください。関係のないファイルまでコミットされる危険があります。

### コミットメッセージ例
```
CodeRabbitレビューコメント対応 - #123

- 認証モジュールの潜在的セキュリティ問題を修正
- データベース接続処理をリファクタリング
- 提案に従いエラーハンドリングを更新
```

**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。"""
        
        return instructions

    def _generate_todos_section(self, prompts, pr_info, pr_basic_info = None) -> str:
        """TODOセクションを生成"""
        if not prompts:
            return "\\n## レビューコメント一覧\\n\\n対象となるレビューコメントが見つかりませんでした。"

        # PR基本情報のセクションを追加
        todos_content = f"""\\n## レビューコメント一覧

**プルリクエスト**: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}
**URL**: {pr_info.url}"""

        # PR基本情報からタイトルと作成者を追加
        if pr_basic_info:
            todos_content += f"""
**タイトル**: {pr_basic_info.get('title', 'タイトル不明')}
**作成者**: @{pr_basic_info.get('author', '不明')}"""
            
            # ブランチ情報を追加
            head_branch = pr_basic_info.get('head_branch')
            base_branch = pr_basic_info.get('base_branch')
            head_repo = pr_basic_info.get('head_repo')
            base_repo = pr_basic_info.get('base_repo')
            
            if head_branch or base_branch:
                todos_content += f"""

### 📂 ブランチ情報
**ソースブランチ**: `{head_repo or 'N/A'}:{head_branch or 'N/A'}`
**ターゲットブランチ**: `{base_repo or 'N/A'}:{base_branch or 'N/A'}`

### 🔄 作業開始コマンド
```bash"""
                
                # 同じリポジトリかフォークかで分岐
                if head_repo and head_branch:
                    if head_repo == base_repo:
                        todos_content += f"""
# ローカルでソースブランチにチェックアウト
git checkout {head_branch}
git pull origin {head_branch}"""
                    else:
                        todos_content += f"""
# フォークからのPRの場合
git remote add fork https://github.com/{head_repo}.git
git fetch fork {head_branch}
git checkout -b {head_branch} fork/{head_branch}"""
                
                todos_content += """
```"""
        
        todos_content += "\\n\\n"

        for i, prompt in enumerate(prompts, 1):
            # プロンプトから基本情報を抽出
            file_path = getattr(prompt, 'file_path', 'Unknown')
            line_number = getattr(prompt, 'line_number', 'Unknown')

            # コメント本体から情報を抽出
            comment_body = getattr(prompt, 'content', '')

            # レビュー種類を判定
            review_type = self._extract_review_type(comment_body)

            # タイトルを生成（最初の行または要約）
            title = self._extract_title_from_comment(comment_body)

            # 問題の説明を抽出
            problem_description = self._extract_problem_description(comment_body)

            todos_content += f"""### TODO #{i}: {title}
**ID**: {getattr(prompt, 'comment_id', 'Unknown')}
**ファイル**: `{file_path}`
**行**: {line_number}
**種類**: {review_type}
**問題**: {problem_description}

**元のコメント**:
```
{comment_body.strip()}
```

---

"""

        return todos_content

    def _extract_review_type(self, comment_body: str) -> str:
        """コメント本体からレビュー種類を抽出"""
        review_types = {
            '⚠️ Potential issue': 'Potential issue',
            '🛠️ Refactor suggestion': 'Refactor suggestion',
            '💡 Nitpick comments': 'Nitpick comments',
            '📝 Committable suggestion': 'Committable suggestion',
            '🔍 Verification agent': 'Verification agent',
            '📊 Analysis chain': 'Analysis chain'
        }

        for pattern, review_type in review_types.items():
            if pattern in comment_body:
                return review_type

        return 'General comment'

    def _extract_title_from_comment(self, comment_body: str) -> str:
        """コメントからタイトルを抽出"""
        lines = comment_body.strip().split('\\n')

        # **太字のタイトル**を探す
        for line in lines:
            line = line.strip()
            if line.startswith('**') and line.endswith('**') and len(line) > 4:
                return line[2:-2]  # **を除去

        # 最初の非空行を使用
        for line in lines:
            line = line.strip()
            if line and not line.startswith('_') and not line.startswith('`'):
                # 最大80文字に制限
                return line[:80] + '...' if len(line) > 80 else line

        return 'レビューコメント'

    def _extract_problem_description(self, comment_body: str) -> str:
        """コメントから問題の説明を抽出"""
        lines = comment_body.strip().split('\\n')

        # **タイトル**の後の説明文を探す
        found_title = False
        description_lines = []

        for line in lines:
            line = line.strip()

            if line.startswith('**') and line.endswith('**'):
                found_title = True
                continue

            if found_title and line and not line.startswith('```') and not line.startswith('<details>'):
                description_lines.append(line)
                # 最初の段落で十分
                if len(description_lines) >= 3:
                    break

        if description_lines:
            description = ' '.join(description_lines)
            # 最大200文字に制限
            return description[:200] + '...' if len(description) > 200 else description

        # フォールバック: 最初の数行
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if len(non_empty_lines) > 1:
            return non_empty_lines[1][:100] + '...' if len(non_empty_lines[1]) > 100 else non_empty_lines[1]

        return 'レビューコメントの内容を確認してください'


def main() -> int:
    """CLI エントリーポイント"""
    cli = CLIInterface()
    return cli.run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
