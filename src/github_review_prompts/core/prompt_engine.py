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
        # 新しいシンプル構造では動的生成を使用
        pass





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

**重要**: エンジニアとしての技術的判断を最優先し、疑問がある場合はCodeRabbitに返信で確認してください。""")

        # 返信方法の追加
        curl_instruction = self._generate_curl_section(pr_info, github_token)
        prompt_parts.append(curl_instruction)

        # 検証チェックリストセクション
        prompt_parts.append("""
## 検証チェックリスト
各重要な修正後に実行：
- [ ] 構文チェック: `python -m py_compile <ファイル名>`
- [ ] Lintチェック: `ruff check <ファイル名>`
- [ ] トークン漏洩チェック: `grep -r "github_pat\\|ghp_" src/`
- [ ] 必要な返信完了

## Git操作方針
**手動確認推奨**: 作業完了後、以下を**段階的に実行**
1. `git status` で変更確認
2. `git add <ファイル名>` で関連ファイルのみ追加
3. `git commit -m "CodeRabbitレビューコメント対応"`
4. 内容確認後 `git push`""")

        # 重要な注意事項
        prompt_parts.append("""

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。

---""")

        # コメント処理
        if comments:
            # セキュリティ関連コメントの自動検出
            security_keywords = ['token', 'credential', 'secret', 'github_pat', 'ghp_', 'authorization', 'bearer']
            security_count = sum(1 for comment in comments 
                               if any(keyword.lower() in comment.get('body', '').lower() 
                                    for keyword in security_keywords))
            
            # ドキュメント関連の低優先コメント検出
            doc_keywords = ['readme', 'md051', 'markdown', 'anchor', 'documentation']
            doc_count = sum(1 for comment in comments 
                          if any(keyword.lower() in comment.get('body', '').lower() 
                               for keyword in doc_keywords))
            
            other_count = len(comments) - security_count - doc_count
            security_percentage = int((security_count / len(comments)) * 100) if comments else 0
            
            prompt_parts.append(f"""
## 🚨 レビューコメント分析（{len(comments)}件）- {security_percentage}%がセキュリティ関連

### 🔴 緊急（セキュリティ・機能破綻）- {security_count}件
**即座対応必須**: トークン漏洩リスク、システム破綻要因

### 🟡 重要（機能改善・品質向上）- {other_count}件  
**PR内対応**: 機能改善、リファクタリング、品質向上

### 🟢 低優先（スタイル・軽微改善）- {doc_count}件
**余裕があれば**: ドキュメント修正、スタイル改善

### ⚡ 推奨対応順序
1. **🔴 セキュリティ関連**: トークン埋め込み・漏洩の完全除去（最優先）
2. **🔴 その他緊急**: システム破綻リスクの修正
3. **🟡 品質改善**: 機能・コード品質の向上
4. **🟢 軽微修正**: ドキュメント・スタイル改善

**🚨 重要**: {security_percentage}%がセキュリティ関連の緊急案件です。トークン漏洩リスクが高いため、🔴項目の完全解決を最優先してください。

### 🔍 根本原因分析
- **設計問題**: トークン値を直接文字列生成に使用
- **移行不完全**: 環境変数参照への移行が部分的
- **整合性不備**: テストコードとの整合性問題

---
## 🔍 対象コメント一覧
""")
            
            for i, comment in enumerate(comments, 1):
                # セキュリティ関連かどうかの自動判定
                is_security = any(keyword.lower() in comment.get('body', '').lower() 
                                for keyword in security_keywords)
                
                # ドキュメント関連の低優先判定
                doc_keywords = ['readme', 'md051', 'markdown', 'anchor', 'documentation']
                is_doc_low_priority = any(keyword.lower() in comment.get('body', '').lower() 
                                        for keyword in doc_keywords)
                
                if is_security:
                    classification = "🔴緊急"
                elif is_doc_low_priority:
                    classification = "🟢低優先"  
                else:
                    classification = "[🔴緊急/🟡重要/🟢低優先] ← 内容確認して分類"
                
                prompt_parts.append(f"""
### TODO #{i}: {self._extract_comment_title(comment)}
**分類**: {classification}

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