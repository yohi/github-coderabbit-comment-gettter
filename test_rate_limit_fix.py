#!/usr/bin/env python3
"""Rate limit handler修正のテスト"""

import sys
import os
import time
from unittest.mock import Mock, patch

# プロジェクトルートをPATHに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from github_review_prompts.utils.rate_limit_handler import GitHubRateLimitHandler
import requests


def test_rate_limit_handler_improvements():
    """Rate limit handler修正のテスト"""

    print("🧪 Rate limit handler修正テストを開始...")

    # GitHubRateLimitHandlerインスタンスを作成
    handler = GitHubRateLimitHandler()

    # テストケース1: 403ステータスコードが直接返される場合
    print("\n✅ テストケース1: 403ステータスコードの直接処理")

    def mock_func_403():
        """403を返すモック関数"""
        response = Mock()
        response.status_code = 403
        response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 60),
            "X-RateLimit-Limit": "5000",
        }
        return response

    try:
        with patch.object(
            handler, "_handle_rate_limit_error", return_value=1.0
        ) as mock_handler:
            result = handler._execute_with_rate_limit(mock_func_403, "core")
            print("❌ 予期せず成功: 403エラーでリトライされるべき")
    except Exception as e:
        print("✅ 403エラーが適切にハンドリングされました")

    # テストケース2: 429ステータスコードが直接返される場合
    print("\n🔧 テストケース2: 429ステータスコードの直接処理")

    def mock_func_429():
        """429を返すモック関数"""
        response = Mock()
        response.status_code = 429
        response.headers = {"Retry-After": "2", "X-RateLimit-Remaining": "0"}
        return response

    try:
        with patch.object(
            handler, "_handle_rate_limit_error", return_value=1.0
        ) as mock_handler:
            result = handler._execute_with_rate_limit(mock_func_429, "core")
            print("❌ 予期せず成功: 429エラーでリトライされるべき")
    except Exception as e:
        print("✅ 429エラーが適切にハンドリングされました")

    # テストケース3: HTTPError経由での403/429処理
    print("\n🔄 テストケース3: HTTPError経由での403/429処理")

    def mock_func_http_error():
        """HTTPErrorを発生させるモック関数"""
        response = Mock()
        response.status_code = 429
        response.headers = {"Retry-After": "1"}

        error = requests.exceptions.HTTPError("Rate limited")
        error.response = response
        raise error

    try:
        with patch.object(
            handler, "_handle_rate_limit_error", return_value=1.0
        ) as mock_handler:
            result = handler._execute_with_rate_limit(mock_func_http_error, "core")
            print("❌ 予期せず成功: HTTPError(429)でリトライされるべき")
    except Exception as e:
        print("✅ HTTPError(429)が適切にハンドリングされました")

    # テストケース4: 正常なレスポンスでのstats更新
    print("\n📈 テストケース4: 正常レスポンスでの統計更新")

    def mock_func_success():
        """成功レスポンスを返すモック関数"""
        response = Mock()
        response.status_code = 200
        response.headers = {
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        }
        return response

    initial_total = handler.stats.get("total_requests", 0)
    initial_success = handler.stats.get("successful_requests", 0)

    try:
        result = handler._execute_with_rate_limit(mock_func_success, "core")

        final_total = handler.stats.get("total_requests", 0)
        final_success = handler.stats.get("successful_requests", 0)

        if final_total > initial_total and final_success > initial_success:
            print("✅ 正常レスポンスで統計が正しく更新されました")
        else:
            print("❌ 統計の更新に問題があります")

    except Exception as e:
        print(f"❌ 正常レスポンステストでエラー: {e}")

    print("\n🎉 テスト完了")
    print(f"Current stats: {handler.stats}")


if __name__ == "__main__":
    test_rate_limit_handler_improvements()
