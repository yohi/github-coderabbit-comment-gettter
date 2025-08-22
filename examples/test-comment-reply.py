#!/usr/bin/env python3
"""
GitHub Comment Reply Tool のテストスクリプト

実際のGitHub APIを呼び出さずに、主要な機能をテストします。
"""

import json
import os
import sys
import tempfile
from unittest.mock import Mock, patch

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from github_review_prompts.github_client import GitHubClient
from github_review_prompts.models import GitHubPRInfo


def test_comment_reply_functionality():
    """コメント返信機能のテスト"""
    print("🧪 Testing GitHub Comment Reply functionality...")
    
    # モックデータ
    pr_info = GitHubPRInfo(
        owner="test-owner",
        repo="test-repo", 
        pull_number=123,
        url="https://github.com/test-owner/test-repo/pull/123"
    )
    
    # GitHubクライアントのモック
    with patch('github_review_prompts.github_client.requests.Session') as mock_session:
        # モックレスポンス
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "id": 987654,
            "body": "Test reply",
            "html_url": "https://github.com/test-owner/test-repo/pull/123#issuecomment-987654",
            "path": "src/test.py",
            "line": 42,
            "side": "RIGHT"
        }
        
        mock_session.return_value.request.return_value = mock_response
        
        # トークンバリデーションをスキップしてテスト用クライアントを作成
        client = GitHubClient(token=None)  # トークンなしで初期化
        client.token = "test-token"  # 後でトークンを設定
        
        # 1. 元コメントの取得のモック
        original_comment = {
            "id": 456789,
            "body": "Original comment",
            "path": "src/test.py",
            "line": 42,
            "side": "RIGHT"
        }
        
        with patch.object(client, 'get_single_comment_detail', return_value=original_comment):
            # 2. 返信コメントの作成テスト
            print("  ✅ Testing reply_to_comment...")
            result = client.reply_to_comment(pr_info, 456789, "Test reply")
            assert result["id"] == 987654
            print(f"     返信コメント作成成功: ID {result['id']}")
        
        # 3. 新規コメント作成テスト
        print("  ✅ Testing create_comment...")
        result = client.create_comment(pr_info, "New comment", "src/test.py", 42)
        assert result["id"] == 987654
        print(f"     新規コメント作成成功: ID {result['id']}")
        
        # 4. コメント更新テスト
        print("  ✅ Testing update_comment...")
        result = client.update_comment(pr_info, 456789, "Updated comment")
        assert result["id"] == 987654
        print(f"     コメント更新成功: ID {result['id']}")
        
        # 5. curlコマンド生成テスト
        print("  ✅ Testing generate_curl_command...")
        
        with patch.object(client, 'get_single_comment_detail', return_value=original_comment):
            curl_command = client.generate_curl_command(
                pr_info, "reply", 
                comment_id=456789, 
                reply_body="Test reply"
            )
            assert "curl -X POST" in curl_command
            assert "test-token" in curl_command
            print("     curlコマンド生成成功")
        
        # 6. 一括返信テスト
        print("  ✅ Testing batch_reply_to_comments...")
        replies = [
            {"comment_id": 456789, "reply_body": "Reply 1"},
            {"comment_id": 456790, "reply_body": "Reply 2"}
        ]
        
        with patch.object(client, 'reply_to_comment', return_value={"id": 987654}):
            results = client.batch_reply_to_comments(pr_info, replies)
            assert len(results) == 2
            print(f"     一括返信成功: {len(results)} 件")


def test_cli_argument_parsing():
    """CLI引数解析のテスト"""
    print("🧪 Testing CLI argument parsing...")
    
    from github_review_prompts.comment_reply_cli import create_argument_parser, load_reply_template
    
    # 1. 引数パーサーの作成
    parser = create_argument_parser()
    
    # 2. reply コマンドのテスト
    args = parser.parse_args([
        "reply", 
        "https://github.com/test/repo/pull/123",
        "--comment-id", "456789",
        "--message", "Test message"
    ])
    
    assert args.command == "reply"
    assert args.comment_id == 456789
    assert args.message == "Test message"
    print("  ✅ reply command parsing OK")
    
    # 3. template 使用のテスト
    args = parser.parse_args([
        "reply",
        "https://github.com/test/repo/pull/123", 
        "--comment-id", "456789",
        "--template", "fixed"
    ])
    
    template_content = load_reply_template("fixed")
    assert "Fixed!" in template_content
    print("  ✅ template loading OK")
    
    # 4. batch-reply コマンドのテスト
    args = parser.parse_args([
        "batch-reply",
        "https://github.com/test/repo/pull/123",
        "--replies-file", "test.json"
    ])
    
    assert args.command == "batch-reply"
    assert args.replies_file == "test.json"
    print("  ✅ batch-reply command parsing OK")
    
    # 5. generate-curl コマンドのテスト
    args = parser.parse_args([
        "generate-curl",
        "https://github.com/test/repo/pull/123",
        "--action", "reply",
        "--comment-id", "456789",
        "--message", "Test"
    ])
    
    assert args.command == "generate-curl"
    assert args.action == "reply"
    print("  ✅ generate-curl command parsing OK")


def test_json_file_processing():
    """JSONファイル処理のテスト"""
    print("🧪 Testing JSON file processing...")
    
    from github_review_prompts.comment_reply_cli import load_batch_replies
    
    # テスト用JSONファイルの作成
    test_data = [
        {"comment_id": 123456, "reply_body": "Test reply 1"},
        {"comment_id": 123457, "template": "fixed"},
        {"comment_id": 123458, "reply_body": "Test reply 2"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f)
        temp_file = f.name
    
    try:
        # JSONファイルの読み込みテスト
        replies = load_batch_replies(temp_file)
        assert len(replies) == 3
        assert replies[0]["comment_id"] == 123456
        assert replies[1]["reply_body"] == "✅ Fixed! Thanks for the feedback."  # テンプレート展開
        print("  ✅ JSON file loading OK")
        
    finally:
        os.unlink(temp_file)


def test_curl_command_generation():
    """curlコマンド生成の詳細テスト"""
    print("🧪 Testing curl command generation...")
    
    pr_info = GitHubPRInfo(
        owner="test-owner",
        repo="test-repo",
        pull_number=123,
        url="https://github.com/test-owner/test-repo/pull/123"
    )
    
    with patch('github_review_prompts.github_client.requests.Session'):
        # トークンバリデーションをスキップしてテスト用クライアントを作成
        client = GitHubClient(token=None)  # トークンなしで初期化
        client.token = "test-token"  # 後でトークンを設定
        
        # 元コメントのモック
        original_comment = {
            "path": "src/test.py",
            "line": 42,
            "side": "RIGHT"
        }
        
        with patch.object(client, 'get_single_comment_detail', return_value=original_comment):
            # 1. reply アクション
            curl_cmd = client.generate_curl_command(
                pr_info, "reply",
                comment_id=456789,
                reply_body="Test reply"
            )
            assert "POST" in curl_cmd
            assert "Authorization: token test-token" in curl_cmd
            assert "Test reply" in curl_cmd
            print("  ✅ reply curl command OK")
            
            # 2. create アクション
            curl_cmd = client.generate_curl_command(
                pr_info, "create",
                body="New comment",
                path="src/test.py",
                line=42
            )
            assert "POST" in curl_cmd
            assert "New comment" in curl_cmd
            print("  ✅ create curl command OK")
            
            # 3. update アクション
            curl_cmd = client.generate_curl_command(
                pr_info, "update",
                comment_id=456789,
                new_body="Updated"
            )
            assert "PATCH" in curl_cmd
            assert "Updated" in curl_cmd
            print("  ✅ update curl command OK")
            
            # 4. delete アクション
            curl_cmd = client.generate_curl_command(
                pr_info, "delete",
                comment_id=456789
            )
            assert "DELETE" in curl_cmd
            print("  ✅ delete curl command OK")


def run_all_tests():
    """全テストの実行"""
    print("🚀 Starting GitHub Comment Reply Tool Tests\n")
    
    try:
        test_comment_reply_functionality()
        print()
        
        test_cli_argument_parsing()
        print()
        
        test_json_file_processing() 
        print()
        
        test_curl_command_generation()
        print()
        
        print("🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)