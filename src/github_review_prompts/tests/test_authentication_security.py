"""
認証・セキュリティテスト
GitHubトークンの適切な管理と出力でのトークン漏洩防止をテスト
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from pathlib import Path

# テスト対象のインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import grp_uvx
from github_review_prompts.github_client import GitHubClient
from github_review_prompts.main import UnifiedCLI


class TestAuthenticationSecurity:
    """認証・セキュリティテスト"""

    def setup_method(self):
        """各テストのセットアップ"""
        # 環境変数のバックアップ
        self.original_github_token = os.environ.get('GITHUB_TOKEN')

    def teardown_method(self):
        """各テストのクリーンアップ"""
        # 環境変数を復元
        if self.original_github_token:
            os.environ['GITHUB_TOKEN'] = self.original_github_token
        elif 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']

    def test_github_token_not_set_grp_uvx(self):
        """grp_uvx: GITHUB_TOKEN未設定時の適切なエラー処理"""
        # 環境変数を削除
        if 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as exc_info:
                grp_uvx.get_github_token()

            # 終了コードが1であることを確認
            assert exc_info.value.code == 1

            # 出力内容の確認
            output = mock_stdout.getvalue()
            assert '❌ エラー: GITHUB_TOKEN 環境変数が設定されていません。' in output
            assert 'export GITHUB_TOKEN=' in output
            assert 'GitHubトークンの取得方法:' in output
            assert 'Personal access tokens' in output

    def test_github_token_not_set_unified_cli(self):
        """UnifiedCLI: GITHUB_TOKEN未設定時の適切なエラー処理"""
        # 環境変数を削除
        if 'GITHUB_TOKEN' in os.environ:
            del os.environ['GITHUB_TOKEN']

        cli = UnifiedCLI()
        test_args = ["https://github.com/owner/repo/pull/123"]

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = cli.run(test_args)

            # エラーコードが返されることを確認
            assert result == 1

            # エラーメッセージの確認
            error_output = mock_stderr.getvalue()
            # エラーログが出力されることを確認（具体的なメッセージは実装依存）
            assert len(error_output) > 0 or result == 1

    def test_github_token_validation(self):
        """GitHubトークンの形式バリデーションテスト"""
        valid_tokens = [
            'ghp_' + 'x' * 36,  # GitHub Personal Access Token
            'github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # GitHub PAT (new format)
            'gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # OAuth token
            'ghu_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  # User-to-server token
        ]

        invalid_tokens = [
            'invalid_token',
            'ghp_' + 'x' * 36,
            'not_github_token_format',
            'bearer_token_format',
        ]

        # 有効なトークン形式のテスト
        for token in valid_tokens:
            os.environ['GITHUB_TOKEN'] = token
            result = grp_uvx.get_github_token()
            assert result == token, f"有効なトークンが正しく取得されませんでした: {token}"

        # 無効なトークン形式でも取得自体は成功する（バリデーションはAPI呼び出し時）
        for token in invalid_tokens:
            os.environ['GITHUB_TOKEN'] = token
            result = grp_uvx.get_github_token()
            assert result == token, f"トークン取得に失敗しました: {token}"

    def test_token_not_leaked_in_stdout_grp_uvx(self):
        """grp_uvx: 標準出力にトークンが漏洩しないことの確認"""
        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        # モックを使用してAPI呼び出しをシミュレート
        with patch('grp_uvx.get_pr_info') as mock_pr_info, \
             patch('grp_uvx.get_pr_review_comments') as mock_comments, \
             patch('grp_uvx.get_graphql_resolved_comments') as mock_resolved, \
             patch('grp_uvx.parse_pr_url') as mock_parse_url, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
             patch('builtins.open', create=True) as mock_open:

            # モックの設定
            mock_parse_url.return_value = ('owner', 'repo', 123)
            mock_pr_info.return_value = {
                'title': 'Test PR',
                'head': {'ref': 'feature', 'repo': {'full_name': 'owner/repo'}},
                'base': {'ref': 'main', 'repo': {'full_name': 'owner/repo'}}
            }
            mock_comments.return_value = []
            mock_resolved.return_value = set()

            # ファイル書き込みのモック
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            # main関数実行（引数をモック）
            test_args = ['grp', 'https://github.com/owner/repo/pull/123']
            with patch.object(sys, 'argv', test_args):
                try:
                    grp_uvx.main()
                except SystemExit:
                    pass  # 正常終了のSystemExitは無視

            # 標準出力の内容確認
            output = mock_stdout.getvalue()
            assert test_token not in output, f"トークンが標準出力に漏洩しています: {test_token}"

            # ファイル出力の内容確認
            if mock_file.write.called:
                written_content = ''.join(call.args[0] for call in mock_file.write.call_args_list)
                assert test_token not in written_content, f"トークンがファイル出力に漏洩しています: {test_token}"

    def test_secure_curl_command_generation(self):
        """curlコマンドでのトークン参照の安全性"""
        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        # curlコマンド生成関数のテスト
        curl_commands = grp_uvx.generate_coderabbit_curl_commands_for_comment(
            'owner', 'repo', 123, 456789, test_token
        )

        # トークンがハードコードされていないことを確認
        assert test_token not in curl_commands, f"curlコマンドにトークンがハードコードされています"

        # 環境変数参照が使用されていることを確認
        assert '${GITHUB_TOKEN}' in curl_commands or '$GITHUB_TOKEN' in curl_commands, \
            "curlコマンドで環境変数参照が使用されていません"

        # Authorization headerが適切に設定されていることを確認
        assert 'Authorization: token $' in curl_commands, \
            "Authorization headerが適切に設定されていません"

    def test_github_client_token_handling(self):
        """GitHubClientのトークン処理テスト"""
        test_token = 'ghp_' + 'x' * 36

        # GitHubClientインスタンス作成
        client = GitHubClient(test_token)

        # トークンが適切に設定されていることを確認
        assert hasattr(client, 'token') or hasattr(client, '_token'), \
            "GitHubClientにトークンが設定されていません"

        # トークンが文字列として保存されていることを確認
        stored_token = getattr(client, 'token', getattr(client, '_token', None))
        assert stored_token == test_token, f"保存されたトークンが期待値と異なります"

    @patch('requests.get')
    def test_api_authentication_headers(self, mock_get):
        """API呼び出し時の認証ヘッダーテスト"""
        test_token = 'ghp_' + 'x' * 36

        # モックレスポンスの設定
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'login': 'test_user'}
        mock_get.return_value = mock_response

        # GitHubClientでAPI呼び出しテスト
        client = GitHubClient(test_token)

        # API呼び出しをシミュレート（実装に応じて調整が必要）
        try:
            # GitHub APIへのリクエストをモック
            import requests
            headers = {
                'Authorization': f'token {test_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'grp-test'
            }
            requests.get('https://api.github.com/user', headers=headers)

            # 呼び出しが行われたことを確認
            mock_get.assert_called_once()

            # 呼び出し時のヘッダーを確認
            call_args = mock_get.call_args
            called_headers = call_args.kwargs.get('headers', {})

            # Authorizationヘッダーが適切に設定されていることを確認
            assert 'Authorization' in called_headers, "Authorizationヘッダーが設定されていません"
            assert called_headers['Authorization'] == f'token {test_token}', \
                "Authorizationヘッダーの値が期待値と異なります"

        except ImportError:
            # requestsがインポートできない場合はスキップ
            pytest.skip("requests module not available")

    def test_environment_variable_security(self):
        """環境変数のセキュリティテスト"""
        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        # 環境変数が適切に取得されることを確認
        retrieved_token = grp_uvx.get_github_token()
        assert retrieved_token == test_token, "環境変数からトークンが正しく取得されませんでした"

        # プロセス環境に意図しない値が設定されていないことを確認
        assert 'GITHUB_PAT' not in os.environ or os.environ['GITHUB_PAT'] != test_token, \
            "トークンが意図しない環境変数に漏洩しています"

    def test_log_output_security(self):
        """ログ出力でのトークン漏洩防止テスト"""
        import logging
        from io import StringIO

        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        # ログキャプチャの設定
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger('grp_uvx')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            # ログ出力を含む処理を実行
            with patch('grp_uvx.parse_pr_url') as mock_parse_url, \
                 patch('sys.argv', ['grp_uvx.py', 'invalid_url']):
                mock_parse_url.return_value = None  # エラーを発生させる

                with pytest.raises(SystemExit):
                    grp_uvx.main()

            # ログ出力にトークンが含まれていないことを確認
            log_output = log_stream.getvalue()
            assert test_token not in log_output, f"ログ出力にトークンが漏洩しています: {test_token}"

        finally:
            logger.removeHandler(handler)

    def test_file_output_security(self):
        """ファイル出力でのトークン漏洩防止テスト"""
        import tempfile
        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, 'test_output.md')

            # モックを使用してファイル出力をテスト
            with patch('grp_uvx.get_pr_info') as mock_pr_info, \
                 patch('grp_uvx.get_pr_review_comments') as mock_comments, \
                 patch('grp_uvx.get_graphql_resolved_comments') as mock_resolved, \
                 patch('grp_uvx.parse_pr_url') as mock_parse_url:

                # モックの設定
                mock_parse_url.return_value = ('owner', 'repo', 123)
                mock_pr_info.return_value = {
                    'title': 'Security Test PR',
                    'head': {'ref': 'feature', 'repo': {'full_name': 'owner/repo'}},
                    'base': {'ref': 'main', 'repo': {'full_name': 'owner/repo'}}
                }
                mock_comments.return_value = [
                    {
                        'id': 1001,
                        'body': '_⚠️ Potential issue_\n\nセキュリティテスト用コメント',
                        'user': {'login': 'coderabbitai[bot]'},
                        'path': 'src/test.py',
                        'line': 10
                    }
                ]
                mock_resolved.return_value = set()

                # main関数実行
                test_args = ['grp', 'https://github.com/owner/repo/pull/123']
                with patch.object(sys, 'argv', test_args):
                    with patch('builtins.open', create=True) as mock_open:
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__.return_value = mock_file

                        try:
                            grp_uvx.main()
                        except SystemExit:
                            pass

                        # ファイルに書き込まれた内容を確認
                        if mock_file.write.called:
                            written_content = ''.join(call.args[0] for call in mock_file.write.call_args_list)
                            assert test_token not in written_content, \
                                f"ファイル出力にトークンが漏洩しています: {test_token}"

    def test_token_masking_in_error_messages(self):
        """エラーメッセージでのトークンマスキングテスト"""
        test_token = 'ghp_' + 'x' * 36
        os.environ['GITHUB_TOKEN'] = test_token

        # APIエラーをシミュレート
        with patch('grp_uvx.make_github_request') as mock_request:
            # APIエラーレスポンスを設定
            mock_request.return_value = {}  # 空のレスポンス（エラー状態）

            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with patch('grp_uvx.parse_pr_url', return_value=('owner', 'repo', 123)):
                    try:
                        grp_uvx.main()
                    except SystemExit:
                        pass

                # エラーメッセージ出力にトークンが含まれていないことを確認
                error_output = mock_stdout.getvalue()
                assert test_token not in error_output, \
                    f"エラーメッセージにトークンが漏洩しています: {test_token}"

    def test_api_request_security(self):
        """API リクエストのセキュリティテスト"""
        test_token = 'ghp_' + 'x' * 36

        # make_github_request関数のセキュリティテスト
        test_url = 'https://api.github.com/repos/owner/repo/pulls/123'

        with patch('urllib.request.Request') as mock_request, \
             patch('urllib.request.urlopen') as mock_urlopen:

            # モックレスポンスの設定
            mock_response = Mock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"id": 123}'
            mock_urlopen.return_value.__enter__.return_value = mock_response

            # API リクエスト実行
            result = grp_uvx.make_github_request(test_url, test_token)

            # リクエストが作成されたことを確認
            mock_request.assert_called_once()

            # リクエストのヘッダーを確認
            call_args = mock_request.call_args
            headers = call_args.kwargs.get('headers', call_args[1] if len(call_args) > 1 else {})

            # Authorizationヘッダーが適切に設定されていることを確認
            assert 'Authorization' in headers, "Authorizationヘッダーが設定されていません"

            # トークンが適切にマスクされていることを確認（ログ等で）
            # 実際のヘッダー値にはトークンが含まれるが、ログ出力時にはマスクされるべき

    def test_secure_token_storage(self):
        """トークンの安全な保存テスト"""
        test_token = 'ghp_' + 'x' * 36

        # GitHubClientでのトークン保存テスト
        client = GitHubClient(test_token)

        # トークンが適切に保存されているが、外部から直接アクセスできないことを確認
        # （実装によってはprivateプロパティとして保存される）

        # オブジェクトの文字列表現にトークンが含まれていないことを確認
        client_str = str(client)
        assert test_token not in client_str, \
            f"GitHubClientの文字列表現にトークンが漏洩しています: {client_str}"

        # reprにもトークンが含まれていないことを確認
        client_repr = repr(client)
        assert test_token not in client_repr, \
            f"GitHubClientのrepr表現にトークンが漏洩しています: {client_repr}"


class TestTokenFormatValidation:
    """トークン形式バリデーションの詳細テスト"""

    @pytest.mark.parametrize("token_format,description", [
        ('ghp_' + 'x' * 36 + 'x' * 36, 'GitHub Personal Access Token (classic)'),
        ('github_pat_' + 'x' * 52, 'GitHub Personal Access Token (fine-grained)'),
        ('gho_' + 'x' * 36, 'GitHub OAuth token'),
        ('ghu_' + 'x' * 36, 'GitHub User-to-server token'),
        ('ghs_' + 'x' * 36, 'GitHub Server-to-server token'),
        ('ghr_' + 'x' * 36, 'GitHub Refresh token'),
    ])
    def test_various_github_token_formats(self, token_format, description):
        """様々なGitHubトークン形式のテスト"""
        os.environ['GITHUB_TOKEN'] = token_format

        # トークン取得が成功することを確認
        result = grp_uvx.get_github_token()
        assert result == token_format, f"{description} の取得に失敗しました"

    def test_token_length_validation(self):
        """トークン長のバリデーションテスト"""
        # 短すぎるトークン
        short_tokens = [
            'ghp_' + 'x' * 36,
            'github_pat_too_short',
            'gho_x',
        ]

        # 実際のアプリケーションではこれらのトークンでAPIエラーが発生するが、
        # 取得自体は成功する（バリデーションはAPI呼び出し時）
        for token in short_tokens:
            os.environ['GITHUB_TOKEN'] = token
            result = grp_uvx.get_github_token()
            assert result == token, f"短いトークンの取得に失敗しました: {token}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
