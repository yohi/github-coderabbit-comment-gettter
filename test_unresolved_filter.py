#!/usr/bin/env python3
"""未解決フィルタのテスト"""

import sys
import os
sys.path.append('src/github_review_prompts')

from github_client import GitHubClient, GitHubPRInfo

def test_unresolved_filter():
    """未解決フィルタの動作確認"""
    
    # GitHub token確認
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN環境変数が設定されていません")
        return
    
    # クライアント初期化
    client = GitHubClient(token)
    pr_info = GitHubPRInfo(
        owner="yohi",
        repo="CursorCLI-Extensions", 
        pull_number=12
    )
    
    print("📊 未解決インラインコメントフィルタテスト")
    print(f"🎯 対象PR: https://github.com/{pr_info.owner}/{pr_info.repo}/pull/{pr_info.pull_number}")
    
    # 1. 全件取得
    print("\n--- 全件取得 ---")
    all_comments = client.get_pr_review_comments(pr_info, unresolved_only=False)
    print(f"全インラインコメント数: {len(all_comments)}件")
    
    # 2. 未解決のみ取得
    print("\n--- 未解決のみ取得 ---")
    unresolved_comments = client.get_pr_review_comments(pr_info, unresolved_only=True)
    print(f"未解決インラインコメント数: {len(unresolved_comments)}件")
    
    # 3. 詳細比較
    print(f"\n📊 比較結果:")
    print(f"全件: {len(all_comments)}件")
    print(f"未解決: {len(unresolved_comments)}件")
    print(f"解決済み: {len(all_comments) - len(unresolved_comments)}件")
    
    # 4. 未解決コメントの詳細
    if unresolved_comments:
        print(f"\n📋 未解決コメント詳細:")
        for i, comment in enumerate(unresolved_comments, 1):
            author = comment.get('user', {}).get('login', 'unknown')
            path = comment.get('path', 'unknown')
            line = comment.get('line', 'unknown')
            is_resolved = comment.get('is_resolved', 'unknown')
            print(f"{i}. {author} - {path}:{line} (解決済み: {is_resolved})")

if __name__ == "__main__":
    test_unresolved_filter()