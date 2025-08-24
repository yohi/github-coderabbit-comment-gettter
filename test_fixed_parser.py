#!/usr/bin/env python3
"""修正されたパーサーのテスト"""

import json
import re
import sys
import os

# パスを追加
sys.path.append("src/github_review_prompts/utils")
from parsers import extract_outside_diff_comments


def test_with_graphql_data():
    """GraphQLレスポンスで修正されたパーサーをテスト"""

    # GraphQLレスポンスを読み込み
    with open("pr12_graphql_response.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # レビューデータ取得
    review = data["data"]["repository"]["pullRequest"]["reviews"]["nodes"][0]
    body = review["body"]

    print("📊 GraphQLレスポンスからのOutside diff comments抽出テスト")
    print(f"レビュー作成者: {review['author']['login']}")
    print(f"レビュー本文の長さ: {len(body):,}文字")

    # 修正されたパーサーで抽出
    print("\n🔧 修正されたパーサーでの抽出実行...")
    extracted = extract_outside_diff_comments(body)

    print(f"\n📊 抽出結果:")
    print(f"抽出されたコメント数: {len(extracted)}件")

    if extracted:
        print("\n📋 抽出されたコメント詳細（最初の10件）:")
        for i, comment in enumerate(extracted[:10], 1):
            print(f"{i}. ファイル: {comment['file_path']}")
            print(f"   行: {comment['line']}")
            print(f"   タイトル: {comment['title']}")
            print(f"   カテゴリ: {comment['category']}")
            print(f"   優先度: {comment['priority']}")
            print()

        if len(extracted) > 10:
            print(f"... 他{len(extracted)-10}件")

    # 手動でOutside diff range commentsセクションを確認
    print(f"\n{'='*60}")
    print("🔍 手動セクション確認")
    print(f"{'='*60}")

    # 正確なセクション抽出
    outside_sections = []
    for match in re.finditer(
        r"<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*?)</blockquote></details>",
        body,
        re.DOTALL,
    ):
        count = int(match.group(1))
        content = match.group(2)
        outside_sections.append((count, content))

    print(f"Outside diff range commentsセクション数: {len(outside_sections)}")
    for i, (count, content) in enumerate(outside_sections, 1):
        print(f"セクション{i}: 期待件数={count}, コンテンツ長={len(content)}文字")

        # ファイルブロック数確認
        file_matches = list(
            re.finditer(
                r"<details>\s*<summary>([^<]+?)\s*\((\d+)\)</summary><blockquote>(.*?)</blockquote></details>",
                content,
                re.DOTALL,
            )
        )
        print(f"  ファイルブロック数: {len(file_matches)}")

        # 各ファイルの詳細
        total_comments = 0
        for file_match in file_matches:
            file_path = file_match.group(1).strip()
            file_count = int(file_match.group(2))
            file_content = file_match.group(3)

            # 実際のコメント数を確認
            comment_matches = list(
                re.finditer(r"`([^`]+)`:\s*\*\*(.*?)\*\*", file_content, re.DOTALL)
            )
            actual_count = len(comment_matches)
            total_comments += actual_count

            print(f"    📁 {file_path}: 期待{file_count}件, 実際{actual_count}件")

        print(f"  📊 セクション{i}総計: {total_comments}件")


if __name__ == "__main__":
    test_with_graphql_data()
