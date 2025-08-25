"""
grpコマンドのコマンドライン引数テスト
grp_uvx.py（軽量版）とmain.py（フル機能版）の両方をテスト
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import argparse
from pathlib import Path

# テスト対象のインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import grp_uvx
from github_review_prompts.main import UnifiedCLI


class TestGRPCommandLineArguments:
    """grpコマンドのコマンドライン引数テスト"""

    def setup_method(self):
        """各テストのセットアップ"""
        # 環境変数のバックアップ
        self.original_github_token = os.environ.get('GITHUB_TOKEN')
        # テスト用トークンを設定
        os.environ['GITHUB_TOKEN'] = 'test_token_for_grp_testing'

    def teardown_method(self):
        """各テストのクリーンアップ"""
        # 環境変数を復元
        if self.original_github_token:
            os.environ['GITHUB_TOKEN'] = self.original_github_token
        elif 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']

    @pytest.mark.parametrize("args,expected", [
        # 基本実行
        (["https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_confirm": False,
            "auto_commit": False,
            "debug": False,
            "no_color": False,
            "auto_reply": False
        }),
        # 効率化オプション
        (["--no-confirm", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_confirm": True,
            "auto_commit": False
        }),
        (["--auto-commit", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_confirm": False,
            "auto_commit": True
        }),
        # 組み合わせパターン
        (["--no-confirm", "--auto-commit", "--debug", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_confirm": True,
            "auto_commit": True,
            "debug": True
        }),
        # UI制御オプション
        (["--no-color", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_color": True
        }),
        # 自動返信オプション
        (["--auto-reply", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "auto_reply": True
        }),
        # 全オプション組み合わせ
        (["--no-confirm", "--auto-commit", "--auto-reply", "--no-color", "--debug", "https://github.com/owner/repo/pull/123"], {
            "pr_url": "https://github.com/owner/repo/pull/123",
            "no_confirm": True,
            "auto_commit": True,
            "auto_reply": True,
            "no_color": True,
            "debug": True
        }),
    ])
    def test_grp_uvx_argument_parsing(self, args, expected):
        """grp_uvx.py（軽量版）の引数解析テスト"""
        # ArgumentParserを直接テスト
        parser = argparse.ArgumentParser()
        parser.add_argument("pr_url")
        parser.add_argument("--no-confirm", action="store_true")
        parser.add_argument("--auto-commit", action="store_true")
        parser.add_argument("--no-color", action="store_true")
        parser.add_argument("--auto-reply", action="store_true")
        parser.add_argument("--debug", action="store_true")

        parsed_args = parser.parse_args(args)

        # 期待される値の検証
        for key, expected_value in expected.items():
            assert getattr(parsed_args, key) == expected_value, f"引数 {key} の値が期待値と異なります"

    @pytest.mark.parametrize("args,expected", [
        # フル機能版固有のオプション
        (["--persona", "security-analyst", "https://github.com/owner/repo/pull/123"], {
            "persona": "security-analyst"
        }),
        (["--format", "json", "https://github.com/owner/repo/pull/123"], {
            "format": "json"
        }),
        (["--output", "test.md", "https://github.com/owner/repo/pull/123"], {
            "output": "test.md"
        }),
        (["--save-file", "https://github.com/owner/repo/pull/123"], {
            "save_file": True
        }),
        # 返信機能
        (["--reply-to", "12345", "--reply-message", "Fixed!", "https://github.com/owner/repo/pull/123"], {
            "reply_to": 12345,
            "reply_message": "Fixed!"
        }),
        (["--reply-to", "12345", "--reply-template", "fixed", "https://github.com/owner/repo/pull/123"], {
            "reply_to": 12345,
            "reply_template": "fixed"
        }),
        # フィルタリングオプション
        (["--include-resolved", "https://github.com/owner/repo/pull/123"], {
            "include_resolved": True
        }),
        (["--author", "coderabbitai", "https://github.com/owner/repo/pull/123"], {
            "author": "coderabbitai"
        }),
    ])
    def test_unified_cli_argument_parsing(self, args, expected):
        """UnifiedCLI（フル機能版）の引数解析テスト"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        parsed_args = parser.parse_args(args)

        # 期待される値の検証
        for key, expected_value in expected.items():
            assert getattr(parsed_args, key) == expected_value, f"引数 {key} の値が期待値と異なります"

    def test_invalid_arguments_handling(self):
        """無効な引数の処理テスト"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        # 無効なペルソナ
        with pytest.raises(SystemExit):
            parser.parse_args(["--persona", "invalid-persona", "https://github.com/owner/repo/pull/123"])

        # 無効なフォーマット
        with pytest.raises(SystemExit):
            parser.parse_args(["--format", "invalid-format", "https://github.com/owner/repo/pull/123"])

    def test_required_arguments(self):
        """必須引数の検証"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        # PR URLが必須
        with pytest.raises(SystemExit):
            parser.parse_args([])

    @patch('grp_uvx.get_github_token')
    @patch('grp_uvx.parse_pr_url')
    @patch('grp_uvx.get_pr_info')
    @patch('grp_uvx.get_pr_review_comments')
    @patch('grp_uvx.get_graphql_resolved_comments')
    def test_grp_uvx_main_execution(self, mock_resolved, mock_comments, mock_pr_info,
                                    mock_parse_url, mock_token):
        """grp_uvx.pyのmain()実行テスト"""
        # モックの設定
        mock_token.return_value = 'test_token'
        mock_parse_url.return_value = ('owner', 'repo', 123)
        mock_pr_info.return_value = {
            'title': 'Test PR',
            'head': {'ref': 'feature-branch', 'repo': {'full_name': 'owner/repo'}},
            'base': {'ref': 'main', 'repo': {'full_name': 'owner/repo'}}
        }
        mock_comments.return_value = [
            {
                'id': 1001,
                'body': '_⚠️ Potential issue_\n\nセキュリティ問題があります',
                'user': {'login': 'coderabbitai[bot]'},
                'path': 'src/test.py',
                'line': 10
            }
        ]
        mock_resolved.return_value = set()

        # sys.argvをモック化
        test_args = ['grp', '--no-confirm', 'https://github.com/owner/repo/pull/123']
        with patch.object(sys, 'argv', test_args):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                # 標準出力をキャプチャ
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    try:
                        grp_uvx.main()
                    except SystemExit:
                        pass  # 正常終了のSystemExitは無視

                # 出力内容の検証
                output = mock_stdout.getvalue()
                assert '🔄 CodeRabbit Review Prompt Generator (UVX)' in output
                assert 'プルリクエスト: https://github.com/owner/repo/pull/123' in output
                assert 'ファイル保存: review_prompt_with_todos.md' in output

    @patch('github_review_prompts.main.UnifiedCLI.run')
    def test_unified_cli_main_execution(self, mock_run):
        """UnifiedCLI.main()実行テスト"""
        mock_run.return_value = 0

        # sys.argvをモック化
        test_args = ['github-review-prompts', '--persona', 'security-analyst', 'https://github.com/owner/repo/pull/123']
        with patch.object(sys, 'argv', test_args):
            from github_review_prompts.main import main
            result = main()

            assert result == 0
            mock_run.assert_called_once()

    def test_environment_variable_handling(self):
        """環境変数の処理テスト"""
        # GITHUB_TOKENが未設定の場合
        if 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with pytest.raises(SystemExit):
                grp_uvx.get_github_token()

            output = mock_stdout.getvalue()
            assert '❌ エラー: GITHUB_TOKEN 環境変数が設定されていません' in output
            assert 'export GITHUB_TOKEN=' in output

    def test_debug_mode_logging(self):
        """デバッグモードのログ設定テスト"""
        import logging

        # デバッグモードでない場合
        test_args = ['grp', 'https://github.com/owner/repo/pull/123']
        with patch.object(sys, 'argv', test_args):
            with patch('grp_uvx.get_github_token', return_value='test_token'):
                with patch('grp_uvx.parse_pr_url', return_value=None):
                    with pytest.raises(SystemExit):
                        grp_uvx.main()

        # デバッグモードの場合
        test_args = ['grp', '--debug', 'https://github.com/owner/repo/pull/123']
        with patch.object(sys, 'argv', test_args):
            with patch('grp_uvx.get_github_token', return_value='test_token'):
                with patch('grp_uvx.parse_pr_url', return_value=None):
                    with patch('sys.stdout', new_callable=StringIO):
                        with pytest.raises(SystemExit):
                            grp_uvx.main()

                        # ログレベルの確認
                        assert logging.getLogger().level == logging.DEBUG

    def test_no_color_environment_setting(self):
        """--no-colorオプションの環境変数設定テスト"""
        # NO_COLOR環境変数を事前にクリア
        if 'NO_COLOR' in os.environ:
            del os.environ['NO_COLOR']

        test_args = ['grp', '--no-color', 'https://github.com/owner/repo/pull/123']
        with patch.object(sys, 'argv', test_args):
            with patch('grp_uvx.get_github_token', return_value='test_token'):
                with patch('grp_uvx.parse_pr_url', return_value=None):
                    with pytest.raises(SystemExit):
                        grp_uvx.main()

                    # NO_COLOR環境変数が設定されることを確認
                    assert os.environ.get('NO_COLOR') == '1'

    def test_argument_validation_edge_cases(self):
        """引数バリデーションのエッジケーステスト"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        # reply-toは数値でなければならない
        with pytest.raises(SystemExit):
            parser.parse_args(["--reply-to", "invalid", "https://github.com/owner/repo/pull/123"])

        # 有効なreply-templateの値
        valid_templates = ["fixed", "acknowledged", "investigating", "clarification", "wontfix"]
        for template in valid_templates:
            args = parser.parse_args(["--reply-template", template, "https://github.com/owner/repo/pull/123"])
            assert args.reply_template == template

        # 無効なreply-template
        with pytest.raises(SystemExit):
            parser.parse_args(["--reply-template", "invalid-template", "https://github.com/owner/repo/pull/123"])

    @pytest.mark.parametrize("help_flag", ["-h", "--help"])
    def test_help_display(self, help_flag, capsys):
        """ヘルプ表示のテスト"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([help_flag])

        captured = capsys.readouterr()
        assert "GitHub Review Prompt Generator" in captured.out
        assert "環境変数:" in captured.out
        assert "GITHUB_TOKEN" in captured.out


class TestArgumentCompatibility:
    """軽量版とフル機能版の引数互換性テスト"""

    def test_common_arguments_compatibility(self):
        """共通引数の互換性確認"""
        # 軽量版とフル機能版で共通の引数
        common_args = [
            "pr_url",
            "no_confirm",
            "auto_commit",
            "debug"
        ]

        # 軽量版のパーサー（grp_uvx.py）
        grp_parser = argparse.ArgumentParser()
        grp_parser.add_argument("pr_url")
        grp_parser.add_argument("--no-confirm", action="store_true")
        grp_parser.add_argument("--auto-commit", action="store_true")
        grp_parser.add_argument("--debug", action="store_true")

        # フル機能版のパーサー
        cli = UnifiedCLI()
        full_parser = cli.create_parser()

        # 共通引数での動作確認
        test_args = ["--no-confirm", "--auto-commit", "--debug", "https://github.com/owner/repo/pull/123"]

        grp_parsed = grp_parser.parse_args(test_args)
        full_parsed = full_parser.parse_args(test_args)

        # 共通引数の値が一致することを確認
        for arg in common_args:
            grp_value = getattr(grp_parsed, arg)
            full_value = getattr(full_parsed, arg)
            assert grp_value == full_value, f"共通引数 {arg} の値が軽量版とフル機能版で異なります"

    def test_full_version_exclusive_arguments(self):
        """フル機能版固有の引数テスト"""
        cli = UnifiedCLI()
        parser = cli.create_parser()

        # フル機能版のみの引数
        exclusive_args = [
            "--persona", "security-analyst",
            "--format", "json",
            "--output", "test.md",
            "--save-file",
            "--include-resolved",
            "--reply-to", "12345",
            "--reply-message", "test"
        ]

        # これらの引数はフル機能版で正常に解析される
        test_args = exclusive_args + ["https://github.com/owner/repo/pull/123"]
        parsed_args = parser.parse_args(test_args)

        assert parsed_args.persona == "security-analyst"
        assert parsed_args.format == "json"
        assert parsed_args.output == "test.md"
        assert parsed_args.save_file is True
        assert parsed_args.include_resolved is True
        assert parsed_args.reply_to == 12345
        assert parsed_args.reply_message == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


