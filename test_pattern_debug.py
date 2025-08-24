#!/usr/bin/env python3
"""パターンデバッグテスト"""

import json
import re

def debug_outside_diff_extraction():
    """Outside diff range commentsの構造を詳細分析"""
    
    # GraphQLレスポンスを読み込み
    with open('pr12_graphql_response.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    body = data['data']['repository']['pullRequest']['reviews']['nodes'][0]['body']
    
    print("📊 Outside diff range commentsセクション詳細分析")
    
    # 1. セクション全体の抽出テスト
    patterns_to_test = [
        # 現在のパターン（修正前）
        r"<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*)",
        # 修正後パターン
        r"<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*?)</blockquote></details>",
        # 詳細な階層パターン
        r"<details>\s*<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*?)</blockquote></details>",
    ]
    
    for i, pattern in enumerate(patterns_to_test, 1):
        print(f"\n--- パターン {i} テスト ---")
        print(f"パターン: {pattern}")
        
        match = re.search(pattern, body, re.DOTALL | re.IGNORECASE)
        if match:
            expected_count = int(match.group(1))
            content = match.group(2)
            print(f"✅ マッチ成功: 期待件数={expected_count}, コンテンツ長={len(content)}文字")
            
            # コンテンツの最初の500文字を表示
            print(f"コンテンツプレビュー:")
            print(repr(content[:500]))
            
            # ファイルブロック抽出テスト
            file_pattern = r"<details>\s*<summary>([^<]+?)\s*\((\d+)\)</summary><blockquote>(.*?)</blockquote></details>"
            file_matches = list(re.finditer(file_pattern, content, re.DOTALL))
            print(f"ファイルブロック数: {len(file_matches)}")
            
        else:
            print("❌ マッチなし")
    
    # 2. 実際の構造を確認
    print(f"\n{'='*60}")
    print("🔍 実際のHTMLセクション構造確認")
    print(f"{'='*60}")
    
    # Outside diff range commentsが含まれる部分を探す
    outside_start = body.find("⚠️ Outside diff range comments")
    if outside_start != -1:
        # セクションの前後1000文字を表示
        start_pos = max(0, outside_start - 200)
        end_pos = min(len(body), outside_start + 1000)
        section_sample = body[start_pos:end_pos]
        
        print("実際のHTMLセクション（前後含む）:")
        print(section_sample)
        
        # 階層構造を分析
        print(f"\n📊 階層構造分析:")
        print(f"<details>の出現回数: {section_sample.count('<details>')}")
        print(f"</details>の出現回数: {section_sample.count('</details>')}")
        print(f"<summary>の出現回数: {section_sample.count('<summary>')}")
        print(f"</summary>の出現回数: {section_sample.count('</summary>')}")
        print(f"<blockquote>の出現回数: {section_sample.count('<blockquote>')}")
        print(f"</blockquote>の出現回数: {section_sample.count('</blockquote>')}")

if __name__ == "__main__":
    debug_outside_diff_extraction()