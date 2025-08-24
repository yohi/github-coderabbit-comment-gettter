#!/usr/bin/env python3
"""GraphQL APIレスポンスからOutside diff comments分析"""

import json
import re

def analyze_outside_diff_from_graphql():
    """GraphQL APIレスポンスからOutside diff commentsを分析"""
    
    # GraphQLレスポンスを読み込み
    with open('pr12_graphql_response.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # PRデータ取得
    pr_data = data['data']['repository']['pullRequest']
    print(f"📋 PR情報: #{pr_data['number']} - {pr_data['title']}")
    
    # レビューデータ取得
    reviews = pr_data['reviews']['nodes']
    print(f"📊 総レビュー数: {len(reviews)}")
    
    for i, review in enumerate(reviews, 1):
        author = review['author']['login']
        body = review['body']
        state = review['state']
        submitted_at = review['submittedAt']
        review_id = review['id']
        
        print(f"\n=== レビュー {i} ===")
        print(f"ID: {review_id}")
        print(f"作成者: {author}")
        print(f"状態: {state}")
        print(f"投稿日時: {submitted_at}")
        print(f"本文の長さ: {len(body):,}文字")
        
        # Outside diff range commentsの確認
        outside_diff_pattern = r"<summary>⚠️ Outside diff range comments \((\d+)\)</summary><blockquote>(.*?)</blockquote></details>"
        outside_matches = list(re.finditer(outside_diff_pattern, body, re.DOTALL))
        
        if outside_matches:
            print(f"✅ Outside diff range commentsセクション発見: {len(outside_matches)}個")
            
            for j, match in enumerate(outside_matches, 1):
                expected_count = int(match.group(1))
                outside_content = match.group(2)
                
                print(f"\n--- Outside diffセクション {j} ---")
                print(f"期待件数: {expected_count}")
                print(f"コンテンツの長さ: {len(outside_content):,}文字")
                
                # 各ファイルブロックを抽出
                file_pattern = r"<details>\s*<summary>([^<]+?)\s*\((\d+)\)</summary><blockquote>(.*?)</blockquote></details>"
                file_matches = list(re.finditer(file_pattern, outside_content, re.DOTALL))
                
                print(f"ファイルブロック数: {len(file_matches)}")
                
                total_extracted = 0
                for file_match in file_matches:
                    file_path = file_match.group(1).strip()
                    file_comment_count = int(file_match.group(2))
                    file_content = file_match.group(3).strip()
                    
                    # 個別コメント抽出
                    comment_pattern = r"`([^`]+)`:\s*\*\*(.*?)\*\*"
                    comment_matches = list(re.finditer(comment_pattern, file_content, re.DOTALL))
                    
                    print(f"  📁 {file_path}: 期待{file_comment_count}件, 実際{len(comment_matches)}件")
                    total_extracted += len(comment_matches)
                
                print(f"✅ セクション{j}の総抽出件数: {total_extracted}/{expected_count}")
        else:
            print("❌ Outside diff range commentsセクションなし")
    
    # 現在のパーサーでテスト
    print(f"\n{'='*60}")
    print("📊 現在のパーサーでの抽出テスト")
    print(f"{'='*60}")
    
    # parsers.pyの関数をインポート
    import sys
    sys.path.append('src/github_review_prompts/utils')
    from parsers import extract_outside_diff_comments
    
    for review in reviews:
        if review['author']['login'] in ['coderabbitai', 'coderabbitai[bot]']:
            body = review['body']
            extracted = extract_outside_diff_comments(body)
            print(f"現在のパーサー抽出結果: {len(extracted)}件")
            
            # 詳細分析
            if extracted:
                print("\n📋 抽出されたコメント詳細:")
                for i, comment in enumerate(extracted[:5], 1):  # 最初の5件のみ表示
                    print(f"{i}. {comment['file_path']} - {comment['line']} - {comment['title']}")
                
                if len(extracted) > 5:
                    print(f"... 他{len(extracted)-5}件")

if __name__ == "__main__":
    analyze_outside_diff_from_graphql()