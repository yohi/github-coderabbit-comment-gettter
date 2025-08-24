#!/usr/bin/env python3
"""パーサー修正の検証テスト"""

import re


def extract_outside_diff_comments_fixed(comment_body: str) -> list:
    """修正版: Outside diff range commentsセクションから個別コメントを抽出"""
    if not comment_body or not isinstance(comment_body, str):
        return []

    extracted_comments = []

    # Outside diff range commentsセクションを探す（最後まで取得）
    outside_diff_pattern = (
        r"<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*)"
    )
    outside_match = re.search(
        outside_diff_pattern, comment_body, re.DOTALL | re.IGNORECASE
    )

    if not outside_match:
        return []

    expected_count = int(outside_match.group(1))  # HTML内の数字
    outside_content = outside_match.group(2)

    print(
        f"📊 デバッグ: Outside diff commentsセクション発見 - 期待件数: {expected_count}"
    )  # デバッグ用

    # デバッグ: outside_contentの全体構造を表示
    print(f"📋 outside_content内容（前半500文字）:")
    print(repr(outside_content[:500]))
    print("📋 outside_content内容（可読性版）:")
    print(outside_content[:500])

    # 各ファイルブロックを抽出（改行を考慮）
    file_pattern = r"<details>\s*<summary>([^<]+?)\s*\((\d+)\)</summary><blockquote>(.*?)</blockquote></details>"

    file_matches = list(re.finditer(file_pattern, outside_content, re.DOTALL))
    print(f"📋 ファイルブロック発見数: {len(file_matches)}")

    # デバッグ: パターンマッチしているかチェック
    if len(file_matches) == 0:
        print("📋 デバッグ: ファイルパターンが一致しない、代替パターンを試します")
        # 別パターンを試す
        alt_patterns = [
            r"<details>\s*<summary>([^<]+?)\s*\(\s*(\d+)\s*\)</summary><blockquote>(.*?)</blockquote></details>",
            r"<details>\s*<summary>([^(]+?)\s*\(\s*(\d+)\s*\)</summary><blockquote>(.*?)</blockquote></details>",
            r"<details>[^<]*<summary>([^<]+?)\s*\(\s*(\d+)\s*\)</summary><blockquote>(.*?)</blockquote></details>",
        ]

        for i, pattern in enumerate(alt_patterns):
            matches = list(re.finditer(pattern, outside_content, re.DOTALL))
            print(f"📋 代替パターン{i+1}: {len(matches)}件発見")
            if matches:
                file_matches = matches
                break

    for file_match in file_matches:
        file_path = file_match.group(1).strip()
        file_comment_count = int(file_match.group(2))
        file_content = file_match.group(3).strip()

        print(f"📋 ファイル発見: {file_path} (期待コメント数: {file_comment_count})")
        print(f"📋 ファイル内容プレビュー: {file_content[:150]}...")

        # 各ファイル内の個別コメントを抽出
        # パターン: `行番号`: **タイトル**
        comment_pattern = r"`([^`]+)`:\s*\*\*(.*?)\*\*"

        comment_matches = list(re.finditer(comment_pattern, file_content, re.DOTALL))
        print(f"📋 コメントパターンマッチ数: {len(comment_matches)}")

        file_comments_found = 0
        for comment_match in comment_matches:
            line_info = comment_match.group(1)
            title = comment_match.group(2)

            # タイトル後のコンテンツを取得
            title_end = comment_match.end()
            next_comment_start = len(file_content)

            # 次のコメントの開始位置を探す
            next_matches = list(
                re.finditer(comment_pattern, file_content[title_end:], re.DOTALL)
            )
            if next_matches:
                next_comment_start = title_end + next_matches[0].start()

            content_after_title = file_content[title_end:next_comment_start].strip()

            extracted_comments.append(
                {
                    "file_path": file_path,
                    "line": line_info,
                    "title": title,
                    "content": (
                        content_after_title[:100] + "..."
                        if len(content_after_title) > 100
                        else content_after_title
                    ),
                }
            )
            file_comments_found += 1

        print(
            f"📊 ファイル内抽出完了: {file_path} - 期待{file_comment_count}件, 実際{file_comments_found}件"
        )

    print(
        f"📊 デバッグ: 抽出完了 - 期待件数: {expected_count}, 実際の抽出件数: {len(extracted_comments)}"
    )  # デバッグ用
    return extracted_comments


def main():
    # ユーザーが提供した実際のHTMLフォーマットでテスト（完全版）
    test_html = """
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.

<details>
<summary>⚠️ Outside diff range comments (10)</summary><blockquote>

<details>
<summary>src/domain/services/analysis.ts (2)</summary><blockquote>

`L143`: **undefined変数参照エラーの修正が必要**

`analysisEngine` 変数が未定義のままアクセスされています。

`L200`: **型安全性の改善が必要**

戻り値の型を明確にしてください。

</blockquote></details>

<details>
<summary>src/infrastructure/database/connection.ts (3)</summary><blockquote>

`L89`: **セキュリティ脆弱性: 認証情報ハードコード**

データベース接続文字列に認証情報が直接記述されています。

`L100`: **エラーハンドリングの追加が必要**

接続エラー時の適切な処理を追加してください。

`L120`: **設定値の外部化を推奨**

設定値を環境変数に移行してください。

</blockquote></details>

<details>
<summary>src/utils/validation.ts (5)</summary><blockquote>

`L67`: **バリデーション関数の戻り値型修正**

関数の戻り値の型が間違っています。

`L80`: **入力値チェックの強化**

不正な入力値に対する検証を追加してください。

`L95`: **正規表現パターンの最適化**

正規表現の効率性を改善できます。

`L110`: **例外処理の改善**

より具体的な例外メッセージを追加してください。

`L125`: **パフォーマンス最適化**

計算処理の効率を改善できます。

</blockquote></details>

</blockquote></details>
"""

    print("=== 修正後のパーサーテスト ===")
    extracted = extract_outside_diff_comments_fixed(test_html)
    print(f"抽出されたコメント数: {len(extracted)}")

    for i, comment in enumerate(extracted, 1):
        print(
            f'{i}. ファイル: {comment["file_path"]} | 行: {comment["line"]} | タイトル: {comment["title"]}'
        )


if __name__ == "__main__":
    main()
