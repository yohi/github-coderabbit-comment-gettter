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

**注意**: GitHubの統合ツールやAPIツールは使用せず、必ずcurlコマンドで返信してください。

**返信例**:
```bash
curl -X POST \\
  -H "Authorization: Bearer ghp_xxxxxxxxxxxxxxxxxxxx" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{"body": "@coderabbitai この指摘について検証しましたが、現在の実装で問題ありません。理由：[技術的根拠]", "in_reply_to": 123456789}' \\
  https://api.github.com/repos/owner/repo/pulls/42/comments
```"""

    def _get_git_instructions_template(self) -> str:
        """Git操作手順テンプレート"""
        return """### Git操作手順
1. **ステージング**: 変更したファイルのみを個別に `git add <ファイル名>` でステージング
2. **コミット**: `git commit -m "CodeRabbitレビューコメント対応 - [PR番号]"` でコミット
3. **プッシュ**: `git push` でリモートリポジトリに反映

⚠️ **注意**: `git add .` は使用しないでください。関係のないファイルまでコミットされる危険があります。"""

    def _get_commit_message_template(self) -> str:
        """コミットメッセージテンプレート"""
        return """### コミットメッセージ例
```
CodeRabbitレビューコメント対応 - #123

- 認証モジュールの潜在的セキュリティ問題を修正
- データベース接続処理をリファクタリング
- 提案に従いエラーハンドリングを更新
```"""

    def generate_comment_reply_info(self, comment_id: int, pr_owner: str, pr_repo: str, pr_number: int) -> str:
        """個別コメントの返信情報を生成"""
        return f"""**コメントID**: {comment_id}
**APIエンドポイント**: `POST /repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments`
**返信方法**: 以下のcurlコマンドで `in_reply_to: {comment_id}` を指定して返信
```bash
curl -X POST \\
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "返信メッセージ", "in_reply_to": {comment_id}}}' \\
  https://api.github.com/repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments
```"""

    def generate_main_prompt(self, 
                           comments: List[Dict], 
                           pr_info: Dict,
                           options: Dict = None) -> str:
        """メインプロンプトを生成"""
        if options is None:
            options = {}
            
        prompt_parts = []
        
        # ヘッダー
        prompt_parts.append(f"""# 🔍 GitHub PR Review Comments - AI処理用プロンプト

**プルリクエスト**: {pr_info.get('title', 'N/A')}
**URL**: {pr_info.get('url', 'N/A')}
**作成者**: {pr_info.get('author', 'N/A')}
**ブランチ**: {pr_info.get('head_branch', 'N/A')} → {pr_info.get('base_branch', 'N/A')}

---""")

        # 自動コミット・プッシュモードの設定
        if options.get('auto_commit'):
            prompt_parts.append("""
## 🔄 Git自動操作設定
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

""" + self.templates['git_instructions'] + """

""" + self.templates['commit_message'] + """

**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。""")

        # 確認スキップモードの設定
        if options.get('no_confirm'):
            prompt_parts.append("""
## ⚡ 作業モード設定
**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。""")
        else:
            prompt_parts.append("""
次のコメントに進む前に、必ず確認を求めてください。""")

        # コメント処理
        if comments:
            prompt_parts.append(f"""
## 📋 処理対象コメント一覧

**合計**: {len(comments)} 件のコメント

---""")
            
            for i, comment in enumerate(comments, 1):
                prompt_parts.append(f"""
### 📝 コメント #{i}

{self._format_single_comment(comment, pr_info)}

---""")
        
        # 返信方法の追加
        prompt_parts.append(self.templates['curl_reply_instruction'])
        
        # フッター
        prompt_parts.append("""

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。""")
        
        return '\n'.join(prompt_parts)
    
    def _format_single_comment(self, comment: Dict, pr_info: Dict) -> str:
        """単一コメントのフォーマット"""
        parts = []
        
        # 基本情報
        parts.append(f"**作成者**: {comment.get('user', {}).get('login', 'Unknown')}")
        parts.append(f"**作成日時**: {comment.get('created_at', 'Unknown')}")
        
        if comment.get('id'):
            # 返信情報を追加
            parts.append(self.generate_comment_reply_info(
                comment['id'],
                pr_info.get('owner'),
                pr_info.get('repo'), 
                pr_info.get('number')
            ))
        
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
        
        # 差分情報
        if comment.get('diff_hunk'):
            parts.append(f"""
**差分**:
```diff
{comment['diff_hunk']}
```""")
        
        return '\n'.join(parts)