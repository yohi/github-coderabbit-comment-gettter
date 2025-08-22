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
5. **確認**: 解決済みマークの適用状況を確認

## 判断基準とアクション
| 判断 | アクション | 返信要否 | 解決済みマーク |
|------|------------|----------|----------------|
| ✅ 実施 | 修正実行 | 不要 | 自動処理 |
| ❌ 対応不要 | 技術的根拠で拒否 | **必須** | **CodeRabbitに依頼** |
| ⏳ 将来対応 | TODOコメント追加 | **必須** | **CodeRabbitに依頼** |
| 🤔 要確認 | 詳細確認要求 | **必須** | 確認完了後 |

## 返信テンプレート
**❌ 対応不要**: `@coderabbitai [技術的根拠]により対応不要と判断します。技術的に妥当であれば、この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。他のコメントには影響しないでください。`
**⏳ 将来対応**: `@coderabbitai 妥当な指摘ですが[現フェーズ]では対応しません。[将来フェーズ]で対応予定です。適切と判断される場合は、この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。`
**🤔 要確認**: `@coderabbitai [確認内容]について詳細説明をお願いします。`

## 📌 重要な解決済みマーク指示

**CodeRabbitに解決済み依頼する場合の注意点：**
- 「この特定のコメントスレッドのみ」を明記
- 他のコメントに影響しないよう強調
- 技術的判断の根拠を具体的に説明
- 間違った指摘であることを明確に伝える

**例文：**
```
@coderabbitai この指摘はXXXの理由により技術的に不適切です。
[具体的な技術的根拠]
妥当と判断される場合は、この特定のコメントスレッドのみを
解決済み（resolved）にマークしてください。
```

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
- [ ] **解決済みマーク確認**: 対応不要・将来対応の判断が適切に反映されているか

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
        """構造化された単一コメントのフォーマット"""
        # 基本情報抽出
        comment_id = comment.get('id', 'unknown')
        author = comment.get('user', {}).get('login', 'Unknown')
        created_at = comment.get('created_at', 'Unknown')
        file_path = comment.get('path', 'Unknown')
        line_number = comment.get('line') or comment.get('original_line', 'Unknown')
        body = comment.get('body', '')
        
        # 自動分類とメタデータ生成
        classification_data = self._analyze_comment(body, file_path)
        
        # 完全機械化YAMLメタデータ
        security_risk = classification_data['issue_type'] == 'security'
        yaml_data = f"""```yaml
id: {comment_id}
priority: {classification_data['classification_emoji']} {classification_data['severity']}
type: {classification_data['issue_type']}
file: {file_path}:{line_number}
author: {author}
created_at: {created_at}
auto_decision: {classification_data['auto_decision']}
security_risk: {str(security_risk).lower()}
```"""

        # パターンベース最適化フォーマット
        optimized_content = self._optimize_comment_format(body)
        
        parts = [
            yaml_data,
            "",
            optimized_content,
            "",
            "**🎯 最終判断**: [ ] ✅実施 [ ] ❌対応不要 [ ] ⏳将来対応 [ ] 🤔要確認"
        ]
        
        return '\n'.join(parts)
    
    def _analyze_comment(self, body: str, file_path: str) -> Dict[str, str]:
        """コメントの自動分析・分類"""
        body_lower = body.lower()
        
        # 分類・重要度マッピングルール
        classification_rules = {
            'security': {'emoji': '🔴', 'priority': 1, 'auto_decision': '✅実施'},
            'functionality': {'emoji': '🔴', 'priority': 2, 'auto_decision': '✅実施'},
            'performance': {'emoji': '🟡', 'priority': 3, 'auto_decision': '✅実施'},
            'maintainability': {'emoji': '🟡', 'priority': 4, 'auto_decision': '🤔要確認'},
            'style': {'emoji': '🟢', 'priority': 5, 'auto_decision': '⏳将来対応'},
            'documentation': {'emoji': '🟢', 'priority': 6, 'auto_decision': '⏳将来対応'}
        }
        
        # セキュリティ関連判定
        security_keywords = ['token', 'credential', 'secret', 'github_pat', 'ghp_', 'authorization', 'bearer', 'security', '漏洩', 'vulnerability']
        if any(keyword in body_lower for keyword in security_keywords):
            return {
                'classification': 'urgent',
                'classification_emoji': '🔴',
                'issue_type': 'security',
                'severity': 'critical',
                'auto_decision': '✅実施',
                'title': self._extract_title(body),
                'tools_detected': self._extract_tools(body)
            }
        
        # ドキュメント関連判定
        if file_path.endswith('.md') or any(keyword in body_lower for keyword in ['readme', 'md051', 'markdown', 'anchor', 'documentation']):
            return {
                'classification': 'low_priority',
                'classification_emoji': '🟢',
                'issue_type': 'documentation',
                'severity': 'low',
                'auto_decision': '⏳将来対応',
                'title': self._extract_title(body),
                'tools_detected': self._extract_tools(body)
            }
        
        # 機能・品質関連（デフォルト）
        return {
            'classification': 'important',
            'classification_emoji': '🟡',
            'issue_type': 'functionality',
            'severity': 'medium',
            'auto_decision': '🤔要確認',
            'title': self._extract_title(body),
            'tools_detected': self._extract_tools(body)
        }
    
    def _extract_title(self, body: str) -> str:
        """コメントからタイトルを抽出"""
        lines = body.split('\n')
        first_line = lines[0].strip()
        
        # ## や ** などのマークダウン記号を除去
        clean_line = first_line.replace('**', '').replace('##', '').replace('*', '').strip()
        
        # 50文字でカット
        if len(clean_line) > 50:
            return clean_line[:47] + '...'
        return clean_line or 'レビューコメント'
    

    
    def _extract_tools(self, body: str) -> str:
        """コメントからツール検出情報を抽出"""
        tools = []
        
        # 一般的なツール
        tool_patterns = ['markdownlint', 'eslint', 'pylint', 'ruff', 'black', 'mypy', 'tsc', 'prettier']
        for tool in tool_patterns:
            if tool.lower() in body.lower():
                tools.append(tool)
        
        # MD051 など特定のルール
        if 'md051' in body.lower():
            tools.append('MD051')
        
        return str(tools) if tools else '[]'
    
    def _optimize_comment_format(self, body: str) -> str:
        """GitHubコメントをパターンベースで最適化"""
        import re
        
        # パターン1: 問題説明 + diffブロック
        problem_diff = self._extract_problem_and_diff(body)
        if problem_diff:
            return self._format_problem_diff_pattern(problem_diff)
        
        # パターン2: 複数ファイル指摘
        file_list = self._extract_file_list_pattern(body)
        if file_list:
            return self._format_file_list_pattern(file_list)
        
        # パターン3: 検証スクリプト提供
        script_pattern = self._extract_script_pattern(body)
        if script_pattern:
            return self._format_script_pattern(script_pattern)
        
        # フォールバック: 未知パターンは要点抽出
        return self._format_fallback_pattern(body)
    
    def _extract_problem_and_diff(self, body: str) -> dict:
        """問題説明とdiffブロックを抽出（改善版）"""
        import re
        
        # より正確な問題説明抽出
        problem = self._extract_clear_problem(body)
        
        # 重複diff除去付きの抽出
        diff_blocks = self._extract_unique_diffs(body)
        
        if problem and diff_blocks:
            return {
                'problem': problem,
                'diffs': diff_blocks
            }
        return None
    
    def _extract_file_list_pattern(self, body: str) -> dict:
        """複数ファイル指摘パターンを抽出（改善版）"""
        import re
        
        # より正確なファイル情報抽出
        file_info = self._extract_structured_files(body)
        
        if len(file_info['files']) >= 2:  # 複数ファイル
            problem = self._extract_clear_problem(body)
            concrete_actions = self._extract_concrete_actions(body)
            
            return {
                'problem': problem,
                'files': file_info['files'],
                'descriptions': file_info['descriptions'],
                'actions': concrete_actions
            }
        return None
    
    def _extract_script_pattern(self, body: str) -> dict:
        """検証スクリプトパターンを抽出"""
        import re
        
        # shellスクリプトブロック
        script_blocks = re.findall(r'```(?:shell|bash)\n(.*?)\n```', body, re.DOTALL)
        
        if script_blocks:
            problem_desc = body.split('\n')[0].strip()
            return {
                'problem': problem_desc,
                'scripts': script_blocks
            }
        return None
    
    def _extract_solution_method(self, body: str) -> str:
        """修正方法を抽出"""
        lines = body.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['対応:', '修正:', 'fix:', 'solution:']):
                return line.strip()
        return "詳細は原文参照"
    
    def _format_problem_diff_pattern(self, data: dict) -> str:
        """問題+diff パターンの整形（改善版）"""
        # 重複除去済みdiffの表示
        diff_text = '\n'.join(f"```diff\n{diff}\n```" for diff in data['diffs'])
        
        return f"""**問題**: {data['problem']}

**修正案**:
{diff_text}"""
    
    def _format_file_list_pattern(self, data: dict) -> str:
        """ファイルリスト パターンの整形（改善版）"""
        file_list = []
        
        # 構造化されたファイル情報の表示
        if data['descriptions']:
            for file_path, description in data['descriptions']:
                file_list.append(f"- `{file_path}`: {description}")
        else:
            # フォールバック: 基本ファイル情報
            for file_info in data['files']:
                if len(file_info) >= 2:
                    file_path, line_num = file_info[0], file_info[1]
                    line_info = f" (行{line_num})" if line_num else ""
                    file_list.append(f"- `{file_path}`{line_info}")
                else:
                    file_list.append(f"- `{file_info[0]}`")
        
        files_text = '\n'.join(file_list)
        
        # 具体的な修正内容
        actions_text = ""
        if data.get('actions'):
            actions_text = f"""
**修正内容**:
{chr(10).join(f"- {action}" for action in data['actions'])}"""
        
        return f"""**問題**: {data['problem']}

**対象ファイル**:
{files_text}{actions_text}"""
    
    def _format_script_pattern(self, data: dict) -> str:
        """スクリプト パターンの整形"""
        script_text = '\n'.join(f"```shell\n{script}\n```" for script in data['scripts'])
        
        return f"""**問題**: {data['problem']}

**検証スクリプト**:
{script_text}"""
    
    def _format_fallback_pattern(self, body: str) -> str:
        """フォールバック: 要点抽出"""
        lines = body.split('\n')
        important_lines = []
        
        # HTMLタグや詳細セクションを除外
        skip_patterns = ['<details>', '<summary>', '<!-- ', '_💡 Verification agent_', '_🧩 Analysis chain_']
        in_details = False
        
        for line in lines[:10]:  # 最初の10行のみ
            line = line.strip()
            
            if '<details>' in line:
                in_details = True
                continue
            if '</details>' in line:
                in_details = False
                continue
            if in_details:
                continue
                
            if line and not any(pattern in line for pattern in skip_patterns):
                # マークダウン記号を除去
                clean_line = line.replace('**', '').replace('*', '').replace('_', '').strip()
                if clean_line and len(clean_line) > 10:
                    important_lines.append(clean_line)
                    
                if len(important_lines) >= 3:  # 最大3行
                    break
        
        summary = '\n'.join(important_lines) if important_lines else "詳細は技術的検証が必要"
        
        return f"""**要点**:
{summary}

**注意**: 複雑なコメントのため、原文確認推奨"""

    def _extract_clear_problem(self, body: str) -> str:
        """明確な問題説明を抽出"""
        import re
        
        # **で囲まれた主要な問題説明
        main_problems = re.findall(r'\*\*(.*?)\*\*', body, re.DOTALL)
        
        # 最初の明確な説明文を採用
        for problem in main_problems:
            problem = problem.strip()
            if len(problem) > 10 and ('が不正' in problem or '重大' in problem or 'セキュリティ' in problem or 'リスク' in problem):
                return problem
        
        # フォールバック: 最初の行から抽出
        first_line = body.split('\n')[0].strip()
        clean_line = re.sub(r'^_.*?_\s*', '', first_line)  # マークダウン記号除去
        clean_line = clean_line.replace('💡', '').replace('🧩', '').strip()
        
        return clean_line or '詳細な問題説明が必要'
    
    def _extract_unique_diffs(self, body: str) -> list:
        """重複除去付きdiffブロック抽出"""
        import re
        
        # diffブロックまたはsuggestionブロック
        diff_blocks = re.findall(r'```(?:diff|suggestion)\n(.*?)\n```', body, re.DOTALL)
        
        # 重複除去（内容ベース）
        unique_diffs = []
        seen_content = set()
        
        for diff in diff_blocks:
            # 空白や改行を正規化して比較
            normalized = re.sub(r'\s+', ' ', diff.strip())
            if normalized and normalized not in seen_content:
                seen_content.add(normalized)
                unique_diffs.append(diff.strip())
        
        return unique_diffs
    
    def _extract_structured_files(self, body: str) -> dict:
        """構造化されたファイル情報抽出"""
        import re
        
        # ファイルパス:行番号 パターン（より正確）
        file_patterns = re.findall(r'([a-zA-Z0-9_/.]+\.py)\s*(?:\（?(?:行)?(\d+(?:[／/,]\d+)*)\）?)?', body)
        
        # 修正対象の詳細説明（改善版）
        target_sections = []
        lines = body.split('\n')
        
        for line in lines:
            # "- filename: description" パターン
            match = re.match(r'[-*]\s*([a-zA-Z0-9_/.]+\.py)\s*(?:\（.*?\）)?\s*[:：]\s*(.+)', line)
            if match:
                target_sections.append((match.group(1), match.group(2).strip()))
        
        return {
            'files': file_patterns,
            'descriptions': target_sections
        }
    
    def _extract_concrete_actions(self, body: str) -> list:
        """具体的な修正アクション抽出"""
        import re
        
        actions = []
        lines = body.split('\n')
        
        # 修正指示パターン
        action_patterns = [
            r'対応[:：]\s*(.+)',
            r'修正[:：]\s*(.+)',
            r'変更[:：]\s*(.+)',
            r'現状[:：]\s*(.+)\s*→\s*(.+)',
            r'-\s*(.+?)\s*\+\s*(.+)'
        ]
        
        for line in lines:
            for pattern in action_patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 2:  # before -> after
                        actions.append(f"{match.group(1).strip()} → {match.group(2).strip()}")
                    else:
                        actions.append(match.group(1).strip())
                    break
        
        return actions[:3]  # 最大3つの具体的アクション

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