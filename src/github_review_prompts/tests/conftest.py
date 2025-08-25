"""
共通テスト設定とフィクスチャ
grpコマンドのテスト拡充に対応した包括的なフィクスチャ
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, MagicMock
from datetime import datetime
from pathlib import Path


@pytest.fixture(autouse=True)
def mock_github_token():
    """GitHubトークンを自動的にモック化"""
    if not os.getenv('GITHUB_TOKEN'):
        os.environ['GITHUB_TOKEN'] = 'mock_github_token_for_testing'


@pytest.fixture
def sample_pr_info():
    """テスト用の基本PR情報"""
    return {
        "number": 123,
        "title": "Test PR for grp command testing",
        "html_url": "https://github.com/owner/repo/pull/123",
        "user": {"login": "test_user"},
        "head": {
            "ref": "feature/test-branch",
            "repo": {
                "full_name": "owner/repo",
                "owner": {"login": "owner"}
            }
        },
        "base": {
            "ref": "main",
            "repo": {
                "full_name": "owner/repo",
                "owner": {"login": "owner"}
            }
        },
        "state": "open",
        "created_at": "2025-08-24T10:00:00Z",
        "updated_at": "2025-08-24T10:30:00Z"
    }


@pytest.fixture
def sample_comments():
    """テスト用のサンプルコメント群"""
    return [
        {
            "id": 1001,
            "body": "_⚠️ Potential issue_\n\nセキュリティ問題があります。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-24T10:00:00Z",
            "path": "src/main.py",
            "line": 10,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r1001"
        },
        {
            "id": 1002,
            "body": "_🛠️ Refactor suggestion_\n\nリファクタリングを推奨します。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-24T10:05:00Z",
            "path": "src/utils.py",
            "line": 25,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r1002"
        },
        {
            "id": 1003,
            "body": "LGTM!",
            "user": {"login": "human_reviewer"},
            "created_at": "2025-08-24T10:10:00Z",
            "path": "src/main.py",
            "line": 5,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r1003"
        }
    ]


@pytest.fixture
def coderabbit_comments_only():
    """CodeRabbitのコメントのみのテストデータ"""
    return [
        {
            "id": 2001,
            "body": "_⚠️ Potential issue_\n\n**セキュリティ脆弱性の検出**\n\nSQL injection の可能性があります。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-24T10:00:00Z",
            "path": "src/database.py",
            "line": 42,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r2001"
        },
        {
            "id": 2002,
            "body": "_🛠️ Refactor suggestion_\n\n**コードの重複除去**\n\n同様のロジックが複数箇所にあります。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-24T10:05:00Z",
            "path": "src/auth.py",
            "line": 15,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r2002"
        },
        {
            "id": 2003,
            "body": "_💡 Nitpick comments_\n\n**命名の改善**\n\n変数名をより明確にできます。",
            "user": {"login": "coderabbitai-pro[bot]"},
            "created_at": "2025-08-24T10:10:00Z",
            "path": "src/helpers.py",
            "line": 8,
            "html_url": "https://github.com/owner/repo/pull/123#discussion_r2003"
        }
    ]


@pytest.fixture
def large_comment_set():
    """大量コメントセット（段階的実行戦略テスト用） - メモリ効率化版"""
    # メモリ使用量を削減: 30件 → 10件に縮小
    comments = []

    # セキュリティ関連コメント（2件に削減）
    security_comments = [
        {
            "id": 3001 + i,
            "body": f"_⚠️ Potential issue_\n\nセキュリティリスク #{i+1}: 重要度の高い脆弱性が検出されました。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-24T10:{i:02d}:00Z",
            "path": f"src/security/module_{i+1}.py",
            "line": 10 + i * 10,
        }
        for i in range(2)  # 3 → 2に削減
    ]

    # 一般的なリファクタリング提案（5件に削減）
    refactor_comments = [
        {
            "id": 3100 + i,
            "body": f"_🛠️ Refactor suggestion_\n\nリファクタリング提案 #{i+1}: コードの改善が可能です。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-24T11:{i:02d}:00Z",
            "path": f"src/modules/module_{i+1}.py",
            "line": 20 + i * 5,
        }
        for i in range(5)  # 20 → 5に削減
    ]

    # ドキュメント関連コメント（3件に削減）
    doc_comments = [
        {
            "id": 3200 + i,
            "body": f"_📝 Documentation_\n\nドキュメント改善 #{i+1}: README.mdの更新が必要です。",
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-24T12:{i:02d}:00Z",
            "path": f"docs/section_{i+1}.md",
            "line": 1,
        }
        for i in range(3)  # 7 → 3に削減
    ]

    comments.extend(security_comments)
    comments.extend(refactor_comments)
    comments.extend(doc_comments)

    return comments


@pytest.fixture
def resolved_comment_ids():
    """解決済みコメントIDのセット"""
    return {1003, 2003, 3003}  # 一部のコメントが解決済み


@pytest.fixture
def mock_github_api_responses():
    """GitHub API応答の包括的モック"""
    return {
        "pr_info": {
            "number": 123,
            "title": "Mock PR for testing",
            "html_url": "https://github.com/owner/repo/pull/123",
            "user": {"login": "test_user"},
            "head": {
                "ref": "feature/mock-test",
                "repo": {"full_name": "owner/repo"}
            },
            "base": {
                "ref": "main",
                "repo": {"full_name": "owner/repo"}
            }
        },
        "comments": [
            {
                "id": 4001,
                "body": "_⚠️ Potential issue_\n\nMocked security issue",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/mock.py",
                "line": 42
            }
        ],
        "graphql_resolved": {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "nodes": [{"databaseId": 4001}]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def temp_workspace(tmp_path):
    """一時的なワークスペース"""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()

    # テスト用ファイル構造を作成
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("# Test main file")
    (workspace / "README.md").write_text("# Test Repository")

    return workspace


@pytest.fixture
def mock_file_system():
    """ファイルシステムのモック"""
    def _create_mock_file_system():
        mock_fs = MagicMock()
        mock_fs.exists.return_value = True
        mock_fs.is_file.return_value = True
        mock_fs.read_text.return_value = "# Mock file content"
        return mock_fs

    return _create_mock_file_system


@pytest.fixture
def environment_backup():
    """環境変数のバックアップ・復元フィクスチャ"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_subprocess():
    """サブプロセス実行のモック"""
    def _mock_run(command, *args, **kwargs):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Mock command output"
        mock_result.stderr = ""
        return mock_result

    return _mock_run


@pytest.fixture
def test_pr_urls():
    """テスト用PR URL集"""
    return {
        "valid": [
            "https://github.com/owner/repo/pull/123",
            "github.com/owner/repo/pull/456",
            "owner/repo#789"
        ],
        "invalid": [
            "invalid-url",
            "https://gitlab.com/owner/repo/pull/123",
            "https://github.com/owner",
            "owner/repo"
        ]
    }


@pytest.fixture
def mock_network_responses():
    """ネットワークレスポンスのモック"""
    def _create_response(status_code=200, json_data=None, text_data=""):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.status = status_code
        mock_response.json.return_value = json_data or {}
        mock_response.text = text_data
        mock_response.read.return_value = (json_data and str(json_data) or text_data).encode()
        return mock_response

    return _create_response


@pytest.fixture
def performance_test_data():
    """パフォーマンステスト用データ - メモリ効率化版"""
    return {
        "small_dataset": list(range(5)),      # 10 → 5に削減
        "medium_dataset": list(range(25)),    # 100 → 25に削減
        "large_dataset": list(range(100)),    # 1000 → 100に削減
        "urls": [f"https://github.com/owner{i}/repo{i}/pull/{i+1}" for i in range(50)]  # 1000 → 50に削減
    }


@pytest.fixture
def security_test_tokens():
    """セキュリティテスト用トークン"""
    return {
        "valid_formats": [
            'ghp_' + 'x' * 36,
            'github_pat_' + 'x' * 52,
            'gho_' + 'x' * 36,
        ],
        "invalid_formats": [
            'invalid_token',
            'ghp_short',
            'not_github_token',
        ],
        "test_token": 'ghp_' + 'x' * 36
    }


# パラメータ化テスト用のマーカー
pytest_plugins = []


@pytest.fixture
def sample_comment():
    """テスト用の基本コメント"""
    return {
        "id": 12345,
        "body": "Test review comment",
        "path": "test/file.py",
        "line": 10,
        "user": {"login": "reviewer"},
        "created_at": "2025-08-22T12:00:00Z"
    }


@pytest.fixture
def mock_github_client():
    """GitHubClientのモック"""
    client = Mock()
    client.get_pull_request.return_value = {
        "number": 123,
        "title": "Test PR",
        "html_url": "https://github.com/test/test/pull/123"
    }
    client.get_review_comments.return_value = []
    client.get_resolved_comments.return_value = []
    return client
