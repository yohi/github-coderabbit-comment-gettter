"""
共通テスト設定とフィクスチャ
"""

import pytest
import os
from unittest.mock import Mock


@pytest.fixture(autouse=True)
def mock_github_token():
    """GitHubトークンを自動的にモック化"""
    if not os.getenv('GITHUB_TOKEN'):
        os.environ['GITHUB_TOKEN'] = 'mock_github_token_for_testing'


@pytest.fixture
def sample_pr_info():
    """テスト用の基本PR情報"""
    return {
        "owner": "test-user",
        "repo": "test-repo", 
        "number": 123,
        "title": "Test Pull Request",
        "url": "https://github.com/test-user/test-repo/pull/123"
    }


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