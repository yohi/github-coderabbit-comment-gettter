"""
統一プロンプトエンジン
全てのプロンプト生成ロジックを統合
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UnifiedPromptEngine:
    """統一プロンプト生成エンジン"""
    
    def __init__(self):
        self.templates = {
            'curl_reply_instruction': self._get_curl_reply_template(),
            'git_instructions': self._get_git_instructions_template(),
            'commit_message': self._get_commit_message_template()
        }
    
    def _get_curl_reply_template(self) -> str:
        """curl返信テンプレート"""
        return """### 🔧 返信方法（重要）
プルリクエストコメントに対する返信は、以下の **curlコマンド** を使用して行ってください：

```bash
curl -X POST \\
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{"body": "返信メッセージ", "in_reply_to": COMMENT_ID}' \\
  https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments
```

**返信すべき場面**:
- ❌ 対応不要と判断した場合
- ⏳ 将来対応と判断した場合  
- 🤔 指摘内容が技術的に間違っていると判断した場合
- ❓ 不明な点があり確認が必要な場合

**重要な制約**:
- ⚠️ **返信は指摘コメントに対してのみ行ってください**
- ✅ 修正対応を完了した場合は返信不要です（修正内容の説明も不要）
- 💬 質問や確認のコメントに対しては返信してください
- 🚫 単なる情報提供や説明コメントには返信不要です

**注意**: GitHubの統合ツールやAPIツールは使用せず、必ずcurlコマンドで返信してください。

**返信ガイドライン**:
- 🎯 修正済み → 返信不要、ただちに次のコメントへ
- 🔍 要確認 → 質問や確認事項を返信
- ❌ 対応不要 → 理由を明記して返信
- ⏳ 後で対応 → 対応予定時期を返信

**返信例**:
```bash
curl -X POST \\
  -H "Authorization: Bearer ${{GITHUB_TOKEN}}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{"body": "@coderabbitai この指摘について検証しましたが、現在の実装で問題ありません。理由：[技術的根拠]", "in_reply_to": 123456789}' \\
  https://api.github.com/repos/owner/repo/pulls/42/comments
```"""





    def generate_main_prompt(self, 
                           comments: List[Dict], 
                           pr_info: Dict,
                           options: Dict = None,
                           github_token: str = None) -> str:
        """メインプロンプトを生成（従来版ベース）"""
        if options is None:
            options = {}
            
        prompt_parts = []
        
        # 改善されたシンプルプロンプト
        prompt_parts.append(f"""# 🎯 CodeRabbitレビュー対応プロンプト

## セキュリティ最優先原則
1. **認証情報保護**: `$GITHUB_TOKEN` 環境変数のみ使用
2. **変更範囲限定**: 関連ファイルのみ修正（`git add .` 禁止）

## 優先度判定（3段階）
🔴 **緊急**: セキュリティ・機能破綻
🟡 **重要**: 機能改善・リファクタリング  
🟢 **低優先**: スタイル・軽微改善

## 作業フロー
1. **分析**: 全コメントを🔴🟡🟢で分類
2. **実行**: 🔴→🟡→🟢の順で対応
3. **検証**: 各修正後に構文・Lintチェック
4. **返信**: 判断に応じてCodeRabbitに返信

## 判断基準とアクション
| 判断 | アクション | 返信要否 |
|------|------------|----------|
| ✅ 実施 | 修正実行 | 不要 |
| ❌ 対応不要 | 技術的根拠で拒否 | **必須** |
| ⏳ 将来対応 | TODOコメント追加 | **必須** |
| 🤔 要確認 | 詳細確認要求 | **必須** |

## 返信テンプレート
**❌ 対応不要**: `@coderabbitai [技術的根拠]により対応不要。この課題のみ解決済みにしてください。`
**⏳ 将来対応**: `@coderabbitai 妥当な指摘ですが[現フェーズ]では対応しません。[将来フェーズ]で対応予定。`
**🤔 要確認**: `@coderabbitai [確認内容]について詳細説明をお願いします。`

## 最終確認
- [ ] セキュリティスキャン通過
- [ ] 構文・Lintエラー解消  
- [ ] 必要な返信完了
- [ ] 変更内容確認後、手動コミット検討""")

        # 返信方法の追加
        curl_instruction = self._generate_curl_section(pr_info, github_token)
        prompt_parts.append(curl_instruction)

        # 確認スキップモードの設定
        if options.get('no_confirm'):
            prompt_parts.append("""
## ⚡ 作業モード設定
**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。""")
        else:
            prompt_parts.append("""
次のコメントに進む前に、必ず確認を求めてください。""")

        # 自動コミット・プッシュモードの設定
        if options.get('auto_commit'):
            prompt_parts.append("""
## 🔄 Git自動操作設定
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

""" + self.templates['git_instructions'] + """

""" + self.templates['commit_message'] + """

**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。""")

        # 重要な注意事項
        prompt_parts.append("""

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。

---""")

        # コメント処理
        if comments:
            prompt_parts.append(f"""
## レビューコメント一覧

**合計**: {len(comments)} 件のコメント

---""")
            
            for i, comment in enumerate(comments, 1):
                prompt_parts.append(f"""
### TODO #{i}: {self._extract_comment_title(comment)}

{self._format_single_comment(comment, pr_info, github_token)}

---""")
        
        return '\n'.join(prompt_parts)
    
    def _format_single_comment(self, comment: Dict, pr_info: Dict, github_token: str = None) -> str:
        """単一コメントのフォーマット"""
        parts = []
        
        # 基本情報
        parts.append(f"**作成者**: {comment.get('user', {}).get('login', 'Unknown')}")
        parts.append(f"**作成日時**: {comment.get('created_at', 'Unknown')}")
        
        if comment.get('id'):
            # コメントIDのみ記載（返信時に使用）
            parts.append(f"**コメントID**: {comment['id']}")
        
        # ファイル情報
        if comment.get('path'):
            parts.append(f"**ファイル**: `{comment['path']}`")
            if comment.get('line'):
                parts.append(f"**行番号**: {comment['line']}")
        
        # コメント本文
        if comment.get('body'):
            parts.append(f"""
**コメント内容**:
```
{comment['body']}
```""")
        

        
        return '\n'.join(parts)
    
    def _generate_curl_section(self, pr_info: Dict, github_token: str = None) -> str:
        """curl返信セクションを生成"""
        owner = pr_info.get('owner', 'OWNER')
        repo = pr_info.get('repo', 'REPO')
        pr_number = pr_info.get('number', 'PR_NUMBER')
        
        return f"""
## 返信方法
GitHub UIまたはGitHub CLI推奨。curl使用時は：

```bash
curl -X POST \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "返信内容", "in_reply_to": COMMENT_ID}}' \\
  https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments
```

**重要**: セキュリティのため、実際のトークン値は環境変数から参照してください。"""
    
    def _extract_comment_title(self, comment: Dict) -> str:
        """コメントからタイトルを抽出"""
        body = comment.get('body', '')
        if not body:
            return 'レビューコメント'
        
        # 最初の行または50文字でタイトルを作成
        first_line = body.split('\n')[0].strip()
        if len(first_line) > 50:
            return first_line[:47] + '...'
        return first_line if first_line else 'レビューコメント'