#!/usr/bin/env python3
"""範囲外コメントのフィルタリング詳細テスト"""

from src.github_review_prompts.utils.smart_comment_filter import SmartCommentFilter
from src.github_review_prompts.utils.parsers import extract_outside_diff_comments

def main():
    filter_instance = SmartCommentFilter()

    # 実際のPR #12タイプの範囲外コメントの例（技術的内容を含む）
    sample_outside_diff_comment = {
        'id': 999999,
        'user': {'login': 'coderabbitai'},
        'body': '''
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.

<details>
<summary>⚠️ Outside diff range comments (3)</summary><blockquote>

<details>
<summary>src/domain/services/analysis.ts (143)</summary><blockquote>

`L143`: **undefined変数参照エラーの修正が必要**

`analysisEngine` 変数が未定義のままアクセスされています。

```diff
- const result = analysisEngine.process(data);
+ const result = this.analysisEngine.process(data);
```

このエラーはランタイムで参照エラーを引き起こします。

</blockquote></details>

<details>
<summary>src/infrastructure/database/connection.ts (89)</summary><blockquote>

`L89`: **セキュリティ脆弱性: 認証情報ハードコード**

データベース接続文字列に認証情報が直接記述されています。

```diff
- const connectionString = "mongodb://admin:password123@localhost:27017";
+ const connectionString = `mongodb://${process.env.DB_USER}:${process.env.DB_PASS}@localhost:27017`;
```

セキュリティ上の重要な問題です。

</blockquote></details>

<details>
<summary>src/utils/validation.ts (67)</summary><blockquote>

`L67`: **バリデーション関数の戻り値型修正**

関数の戻り値の型が間違っています。

```diff
- function validateInput(input: string): number {
+ function validateInput(input: string): boolean {
    return input.length > 0;
}
```

</blockquote></details>

</blockquote></details>
        ''',
        'created_at': '2025-01-24T12:00:00Z'
    }

    print('=== 技術的な範囲外コメントのフィルタリングテスト ===')
    print(f'Author: {sample_outside_diff_comment["user"]["login"]}')

    # フィルタリング判定
    should_task, reason, comment_type = filter_instance.should_create_task(sample_outside_diff_comment)
    print(f'\nタスク化判定: {"✅ 必要" if should_task else "❌ 不要"}')
    print(f'判定理由: {reason.value}')
    print(f'コメント種別: {comment_type.value}')

    # 範囲外コメント抽出テスト
    print('\n=== 範囲外コメント抽出テスト ===')
    extracted_comments = extract_outside_diff_comments(sample_outside_diff_comment['body'])
    print(f'抽出された個別コメント数: {len(extracted_comments)}')

    for i, comment in enumerate(extracted_comments, 1):
        print(f'\n--- 抽出コメント {i} ---')
        print(f'ファイル: {comment["file_path"]}')
        print(f'行: {comment["line"]}')
        print(f'タイトル: {comment["title"]}')
        print(f'内容: {comment["content"][:200]}...')
        
    print('\n=== 分析結果 ===')
    body = sample_outside_diff_comment['body']
    technical_indicators = [
        ('undefined変数参照エラー', 'undefined変数参照' in body),
        ('セキュリティ脆弱性', 'セキュリティ脆弱性' in body),
        ('認証情報ハードコード', '認証情報ハードコード' in body),
        ('バリデーション関数', 'バリデーション関数' in body),
        ('```diff', '```diff' in body),
        ('修正が必要', '修正が必要' in body),
        ('エラー', 'エラー' in body),
        ('問題', '問題' in body)
    ]

    print('技術的指標の検出:')
    for indicator, detected in technical_indicators:
        print(f'  {indicator}: {"✅" if detected else "❌"}')

    # 現在のフィルタリング論理の詳細分析
    print('\n=== フィルタリング詳細分析 ===')
    
    # CodeRabbitコメント分析の流れを追跡
    print('1. 除外パターンチェック結果:')
    excluded = False
    for pattern in filter_instance.exclusion_patterns:
        import re
        if re.search(pattern, body, re.IGNORECASE | re.MULTILINE | re.DOTALL):
            print(f'   ❌ 除外パターンマッチ: {pattern}')
            excluded = True
            break
    
    if not excluded:
        print('   ✅ 除外パターンに該当せず')
        
        # CodeRabbit技術的指摘チェック
        print('2. 技術的指摘パターンチェック:')
        technical_indicators_patterns = [
            "_⚠️ Potential issue_",
            "_🛠️ Refactor suggestion_",
            "_💡 Verification agent_",
            "_🔒 Security issue_",
            "_⚡ Performance issue_",
        ]
        
        found_technical = False
        for indicator in technical_indicators_patterns:
            if indicator in body:
                print(f'   ✅ 技術的指摘タイプ発見: {indicator}')
                found_technical = True
                
        if not found_technical:
            print('   ❌ 明確な技術的指摘タイプなし')
            
        # 具体的キーワードチェック
        print('3. 具体的修正キーワードチェック:')
        keywords = [
            "修正", "変更", "エラー", "問題", "脆弱性", "セキュリティ",
            "fix", "change", "error", "issue", "vulnerability", "security",
            "```diff", "```suggestion",
        ]
        
        found_keywords = []
        for keyword in keywords:
            if keyword in body.lower():
                found_keywords.append(keyword)
                
        print(f'   検出されたキーワード: {found_keywords}')
        
        if found_keywords:
            # さらに具体的な修正指示チェック
            print('4. 具体的修正指示チェック:')
            concrete_fixes = [
                "variable", "変数", "未定義", "undefined",
                "参照エラー", "reference error", "validation", "バリデーション",
                "runtime", "ランタイム", "環境変数", "environment",
            ]
            
            found_concrete = []
            for fix in concrete_fixes:
                if fix in body.lower():
                    found_concrete.append(fix)
                    
            print(f'   検出された具体的修正指示: {found_concrete}')
            
            if found_concrete:
                print('   ✅ 具体的修正指示あり -> タスク化対象')
            else:
                print('   ❌ 具体的修正指示なし -> 除外')
        else:
            print('   ❌ 修正関連キーワードなし -> 除外')

if __name__ == '__main__':
    main()