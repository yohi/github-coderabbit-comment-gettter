#!/usr/bin/env python3
"""Outside diff range commentsセクションの境界を正確に特定"""

import json
import re

def find_section_boundaries():
    """Outside diff range commentsセクションの正確な境界を特定"""
    
    # GraphQLレスポンスを読み込み
    with open('pr12_graphql_response.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    body = data['data']['repository']['pullRequest']['reviews']['nodes'][0]['body']
    
    print("📊 セクション境界の詳細分析")
    
    # 1. Outside diff range commentsの開始位置
    outside_start = body.find("> <summary>⚠️ Outside diff range comments")
    print(f"Outside diff commentsセクション開始位置: {outside_start}")
    
    if outside_start == -1:
        print("❌ Outside diff range commentsセクションが見つかりません")
        return
    
    # 2. セクション内容を分析
    section_part = body[outside_start:outside_start+3000]  # 3000文字程度を確認
    
    # 3. 各種セクションマーカーを探す
    markers_to_find = [
        "🧹 Nitpick comments",
        "🔇 Additional comments", 
        "</blockquote></details>",
        "> </blockquote></details>"
    ]
    
    print(f"\n📊 セクション内のマーカー位置:")
    for marker in markers_to_find:
        pos = section_part.find(marker)
        if pos != -1:
            print(f"{marker}: 位置 {pos} (開始から{pos}文字後)")
        else:
            print(f"{marker}: 見つからない")
    
    # 4. 具体的なセクション終了位置を特定
    potential_ends = []
    
    # パターン1: </blockquote></details>で直接終了
    for match in re.finditer(r"\n>\s*</blockquote></details>", section_part):
        potential_ends.append(("</blockquote></details>", match.end()))
    
    # パターン2: 次のセクション開始
    for match in re.finditer(r"\n>\s*<details>\s*\n>\s*<summary>[🧹🔇]", section_part):
        potential_ends.append(("次セクション開始", match.start()))
    
    print(f"\n📊 潜在的な終了位置:")
    for desc, pos in potential_ends:
        print(f"{desc}: 位置 {pos}")
    
    # 5. 最も適切な終了位置を選択
    if potential_ends:
        # 最も早い位置を終了位置とする
        end_pos = min(potential_ends, key=lambda x: x[1])[1]
        print(f"\n✅ 選択された終了位置: {end_pos}")
        
        # 抽出されるセクションコンテンツ
        extracted_section = section_part[:end_pos]
        print(f"抽出セクション長: {len(extracted_section)}文字")
        
        # ファイルブロック数を確認
        file_pattern = r">\s*<details>\s*\n>\s*<summary>([^<]+?)\s*\((\d+)\)</summary><blockquote>"
        file_matches = list(re.finditer(file_pattern, extracted_section))
        print(f"ファイルブロック数: {len(file_matches)}")
        
        total_expected = 0
        for match in file_matches:
            file_path = match.group(1).strip()
            count = int(match.group(2))
            total_expected += count
            print(f"  📁 {file_path}: {count}件")
        
        print(f"📊 期待件数合計: {total_expected}")
        
        # 実際のコメント抽出をテスト
        print(f"\n🧪 実際のコメント抽出テスト:")
        comment_pattern = r">\s*`([^`]+)`:\s*\*\*(.*?)\*\*"
        comment_matches = list(re.finditer(comment_pattern, extracted_section))
        print(f"実際の抽出コメント数: {len(comment_matches)}")
        
        for i, match in enumerate(comment_matches[:5], 1):
            line = match.group(1)
            title = match.group(2)
            print(f"  {i}. {line}: {title}")

if __name__ == "__main__":
    find_section_boundaries()