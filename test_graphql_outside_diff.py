#!/usr/bin/env python3
"""GraphQL APIからOutside diff commentsを取得して分析"""

import os
import json
import requests
from typing import Dict, Any, List


def get_pr_review_comments_graphql(
    owner: str, repo: str, pr_number: int
) -> Dict[str, Any]:
    """GraphQL APIでPRのレビューコメントを取得"""

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN環境変数が設定されていません")

    # GraphQLクエリ - PRのレビューコメントを取得
    query = """
    query GetPRReviewComments($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          title
          number
          reviews(first: 20, states: [SUBMITTED]) {
            nodes {
              id
              author {
                login
              }
              body
              submittedAt
              state
              comments(first: 100) {
                nodes {
                  id
                  author {
                    login
                  }
                  body
                  createdAt
                  position
                  line
                  path
                  diffHunk
                  outdated
                  pullRequestReview {
                    id
                  }
                }
              }
            }
          }
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              comments(first: 50) {
                nodes {
                  id
                  author {
                    login
                  }
                  body
                  createdAt
                  line
                  path
                  diffHunk
                  outdated
                  position
                  pullRequestReview {
                    id
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {"owner": owner, "repo": repo, "number": pr_number}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=10,
    )

    if response.status_code != 200:
        raise Exception(f"GraphQL API error: {response.status_code} - {response.text}")

    return response.json()


def analyze_outside_diff_comments(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Outside diff commentsを分析して抽出"""

    outside_diff_comments = []

    # PRデータを取得
    pr_data = data.get("data", {}).get("repository", {}).get("pullRequest", {})
    if not pr_data:
        return outside_diff_comments

    print(f"📋 PR情報: #{pr_data.get('number')} - {pr_data.get('title')}")

    # レビューコメントを分析
    reviews = pr_data.get("reviews", {}).get("nodes", [])
    print(f"📊 総レビュー数: {len(reviews)}")

    for review in reviews:
        author = review.get("author", {}).get("login", "")
        body = review.get("body", "")
        state = review.get("state", "")
        submitted_at = review.get("submittedAt", "")

        print(f"\n🔍 レビュー分析:")
        print(f"  作成者: {author}")
        print(f"  状態: {state}")
        print(f"  投稿日時: {submitted_at}")
        print(f"  本文の長さ: {len(body)}文字")

        # Outside diff range commentsが含まれているかチェック
        if "Outside diff range comments" in body:
            print(f"  ✅ Outside diff range commentsセクション発見!")

            # 件数を抽出
            import re

            count_match = re.search(r"Outside diff range comments \((\d+)\)", body)
            if count_match:
                expected_count = int(count_match.group(1))
                print(f"  📊 期待件数: {expected_count}")

            outside_diff_comments.append(
                {
                    "review_id": review.get("id"),
                    "author": author,
                    "body": body,
                    "submitted_at": submitted_at,
                    "expected_count": expected_count if count_match else 0,
                    "body_length": len(body),
                }
            )

        # 個別コメントも確認
        comments = review.get("comments", {}).get("nodes", [])
        print(f"  💬 個別コメント数: {len(comments)}")

        for comment in comments:
            comment_author = comment.get("author", {}).get("login", "")
            comment_body = comment.get("body", "")
            position = comment.get("position")
            line = comment.get("line")
            path = comment.get("path", "")

            # Outside diff関連の個別コメントをチェック
            if position is None and line is None:
                print(
                    f"    🔍 位置情報なしコメント発見: {comment_author} - {len(comment_body)}文字"
                )

    # ReviewThreadsも確認
    review_threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    print(f"\n📊 総レビュースレッド数: {len(review_threads)}")

    for thread in review_threads:
        is_resolved = thread.get("isResolved", False)
        thread_comments = thread.get("comments", {}).get("nodes", [])

        for comment in thread_comments:
            comment_author = comment.get("author", {}).get("login", "")
            comment_body = comment.get("body", "")
            position = comment.get("position")
            line = comment.get("line")
            path = comment.get("path", "")
            outdated = comment.get("outdated", False)

            # Outside diff関連コメントを特定
            if position is None and line is None and path == "":
                print(f"🔍 Outside diff候補コメント:")
                print(f"  作成者: {comment_author}")
                print(f"  解決済み: {is_resolved}")
                print(f"  古いコメント: {outdated}")
                print(f"  本文プレビュー: {comment_body[:100]}...")

    return outside_diff_comments


def main():
    """メイン実行"""

    # GITHUB_TOKEN確認
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN環境変数が設定されていません")
        print("以下のコマンドで設定してください:")
        print('export GITHUB_TOKEN="your_github_token_here"')
        return

    print("✅ GITHUB_TOKEN確認: 設定済み")

    # PR情報
    owner = "yohi"
    repo = "CursorCLI-Extensions"
    pr_number = 12

    print(f"🎯 対象PR: https://github.com/{owner}/{repo}/pull/{pr_number}")

    try:
        # GraphQL APIでデータ取得
        print("\n📡 GraphQL APIでPRデータを取得中...")
        data = get_pr_review_comments_graphql(owner, repo, pr_number)

        # Outside diff commentsを分析
        print("\n🔍 Outside diff commentsを分析中...")
        outside_diff_comments = analyze_outside_diff_comments(data)

        print(f"\n📊 分析結果:")
        print(f"Outside diff commentsセクション数: {len(outside_diff_comments)}")

        total_expected = 0
        for i, comment in enumerate(outside_diff_comments, 1):
            print(f"\n--- セクション {i} ---")
            print(f"レビューID: {comment['review_id']}")
            print(f"作成者: {comment['author']}")
            print(f"投稿日時: {comment['submitted_at']}")
            print(f"期待件数: {comment['expected_count']}")
            print(f"本文の長さ: {comment['body_length']}文字")
            total_expected += comment["expected_count"]

        print(f"\n📊 総計:")
        print(f"全セクションの期待件数合計: {total_expected}")

        # JSONファイルに詳細データを保存
        output_file = "pr12_outside_diff_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "pr_info": {"owner": owner, "repo": repo, "number": pr_number},
                    "outside_diff_sections": outside_diff_comments,
                    "summary": {
                        "total_sections": len(outside_diff_comments),
                        "total_expected_comments": total_expected,
                    },
                    "raw_data": data,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"\n💾 詳細データを {output_file} に保存しました")

    except Exception as e:
        print(f"❌ エラー発生: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
