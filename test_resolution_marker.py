#!/usr/bin/env python3
"""解決済みマーカー検出のテスト"""

import re


def test_resolution_marker_detection():
    """解決済みマーカー検出機能のテスト"""

    # テスト用のコメント本文（実際のマーカー形式）
    test_comments = [
        # ケース1: 完全な解決済みマーカー
        """
        修正が完了しました。

        [CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
        ✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
        [/CR_RESOLUTION_CONFIRMED]
        """,
        # ケース2: 部分的なマーカー（不完全）
        """
        修正しました。
        ✅ エンジニアによる技術的検証完了
        """,
        # ケース3: マーカーなし
        """
        普通のコメントです。修正を検討中です。
        """,
        # ケース4: 別の形式の解決済みマーク
        """
        [CR_RESOLUTION_CONFIRMED:SECURITY_ISSUE_RESOLVED]
        ✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
        [/CR_RESOLUTION_CONFIRMED]
        """,
    ]

    def has_coderabbit_resolution_marker(comment_body: str) -> bool:
        """CodeRabbitの解決済みマーカーが含まれているかチェック"""
        if not comment_body:
            return False

        resolution_markers = [
            r"\[CR_RESOLUTION_CONFIRMED:.*?\]",
            r"✅ エンジニアによる技術的検証完了.*CodeRabbitによる解決済みマーク実行可能",
            r"\[/CR_RESOLUTION_CONFIRMED\]",
        ]

        # すべてのマーカーが含まれているかチェック
        for marker in resolution_markers:
            if not re.search(marker, comment_body, re.DOTALL | re.IGNORECASE):
                return False

        return True

    print("📊 解決済みマーカー検出テスト")

    for i, comment in enumerate(test_comments, 1):
        result = has_coderabbit_resolution_marker(comment)
        print(f"\nケース {i}: {'✅ 解決済み' if result else '❌ 未解決'}")
        print(f"コメント: {comment.strip()[:100]}...")

    # 実際のterraform PR#98でのテスト
    print(f"\n{'='*60}")
    print("🔍 terraform PR#98での実際のテスト")
    print(f"{'='*60}")

    import json

    # GraphQLレスポンスを読み込み
    with open("terraform_pr98_response.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    review_threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]

    resolved_by_marker_count = 0
    unresolved_with_inline_count = 0

    for thread in review_threads:
        has_inline_comments = False
        thread_comments = thread["comments"]["nodes"]

        # インラインコメントがあるスレッドかチェック
        for comment in thread_comments:
            if comment.get("path") is not None and (
                comment.get("line") is not None
                or comment.get("originalLine") is not None
            ):
                has_inline_comments = True
                break

        if not has_inline_comments:
            continue

        # スレッドの解決状態チェック
        thread_is_resolved = thread["isResolved"]

        # 最後のコメントで解決済みマーカーチェック
        if thread_comments:
            last_comment = thread_comments[-1]
            if last_comment["author"]["login"] in [
                "coderabbitai",
                "coderabbitai[bot]",
            ] and has_coderabbit_resolution_marker(last_comment["body"]):
                thread_is_resolved = True
                resolved_by_marker_count += 1
                print(f"🎯 マーカーで解決済み判定: thread {thread['id']}")

        if not thread_is_resolved:
            # このスレッドのインラインコメント数をカウント
            for comment in thread_comments:
                if comment.get("path") is not None and (
                    comment.get("line") is not None
                    or comment.get("originalLine") is not None
                ):
                    unresolved_with_inline_count += 1

    print(f"\n📊 結果:")
    print(f"マーカーによる解決済み判定: {resolved_by_marker_count}スレッド")
    print(f"最終的な未解決インラインコメント: {unresolved_with_inline_count}件")


if __name__ == "__main__":
    test_resolution_marker_detection()
