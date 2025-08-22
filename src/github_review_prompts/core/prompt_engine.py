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



    def generate_main_prompt(self, 
                           comments: List[Dict], 
                           pr_info: Dict,
                           options: Dict = None,
                           github_token: str = None) -> str:
        """メインプロンプトを生成（従来版ベース）"""
        if options is None:
            options = {}
            
        prompt_parts = []
        
        # 基本プロンプト（従来版をベース）
        prompt_parts.append(f"""# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## 対応方針
1. **まずコメント分類・優先度判定**: 開始前に必ず全コメントを以下の重要度で分析してください
2. **優先度別TODOリスト作成**: 重要度に基づいてTODOタスクリストを作成してください
3. **体系的な処理**: TODOリスト完成後、高優先度から順番に処理してください
4. **批判的評価**: レビューコメントが技術的に正しいかどうかを必ず検証してください
5. **対応判断**: 各コメントに対して以下のいずれかの対応を決定してください：
   - ✅ 対応実施（修正が必要で技術的に正しい）
   - ⏳ 将来対応（技術的に正しいが現在のPhase/ステップでは対応しない）
   - ❌ 対応不要（技術的に間違っているか不適切）
   - 🤔 要確認（追加情報が必要）

## 🎯 CodeRabbitコメント分類・優先度システム

### 🔥 **最優先対応項目（即座に対応必須）**
- **⚠️ Outside diff range comments**: PR差分範囲外の構造的問題、全体設計影響
- **⚠️ Potential issue**: セキュリティ、バグ、パフォーマンス等の潜在的リスク  
- **📝 Committable suggestion**: diff形式の具体的修正案、ワンクリック適用可能
- **🤖 Prompt for AI Agents**: AI専用の構造化修正指示、最も理解しやすい形式

### 🟡 **高優先対応項目（PR内で対応推奨）**
- **🛠️ Refactor suggestion**: コード構造改善、保守性向上の提案
- **💡 Verification agent**: 自動検証・分析による詳細調査結果
- **🧩 Analysis chain**: 検証プロセスの詳細ログ、分析手法の透明性
- **♻️ Duplicate comments**: 同一問題の複数箇所での指摘、一括修正可能

### 🟢 **補助情報項目（参考程度）**
- **🧰 Tools**: 解析ツール出力（Ruff、markdownlint等）、false positive判別用
- **📜 Review details**: レビュー統計・設定情報、作業規模把握用

### ⚪ **低優先項目（余裕があれば対応）**
- **🧹 Nitpick comments**: 軽微な改善提案、スタイル指摘、機能影響なし
- **🔇 Additional comments**: その他一般的コメント、修正指示が不明確

## 作業手順

### Phase 1: 分類・TODOリスト作成
1. **全コメント分析**: すべてのレビューコメントを最初に確認
2. **分類・優先度判定**: 上記分類システムに基づいて各コメントを🔥🟡🟢⚪で分類
3. **TODOタスクリスト作成**: 分類結果を基に各コメントの対応方針を決定してタスクリストを作成
4. **処理順序決定**: 🔥最優先 → 🟡高優先 → 🟢補助情報 → ⚪低優先の順で処理順序を設定

### Phase 2: 優先度別対応実行  
5. **🔥最優先項目を最初に処理**: Outside diff range、Potential issue、Committable suggestion、AI Agents
6. **🟡高優先項目を続いて処理**: Refactor suggestion、Verification agent、Analysis chain、Duplicate comments
7. **技術的妥当性の再評価**: 各タスク実行時に改めて検証
8. **対応実施**: 修正・返信・記憶依頼を実行
9. **返信必須項目の確認**: ❌⏳⚠️🤔判定した項目はcurl返信必須（忘れやすいので要注意）
10. **進捗管理**: 各タスク完了後にTODOリストを更新
11. **🟢🔇低優先項目**: 時間に余裕がある場合のみ対応検討

## 出力フォーマット

### Phase 1: TODOリスト
```
## 📋 TODO リスト（優先度順）
### 🔴 高優先度
- [ ] TODO-1: [コメント要約] - [対応方針]
### 🟡 中優先度
- [ ] TODO-2: [コメント要約] - [対応方針]
### 🟢 低優先度  
- [ ] TODO-3: [コメント要約] - [対応方針]
```

### Phase 2: 個別対応
**TODO-[番号] 完了: [コメント要約]**
- 判断: [✅修正実施/⏳将来対応/❌対応不要/⚠️指摘間違い/🤔要確認]
- 理由: [技術的根拠]
- 対応: [具体的な行動]
- 返信: [curl返信が必要な場合のみ] ※❌⏳⚠️🤔は必須

### curl返信が必要な4パターン

**⏳ 将来対応**: `@coderabbitai この指摘は妥当ですが、現在のPhase/ステップでは対応対象外です。現在: [具体的なPhase名]、対応予定: [具体的な将来Phase名]。**記憶依頼**: 以下を構造化記録し「[将来Phase名]」開始時・[技術領域]作業時に積極的に思い出してください - 指摘:[要約] 対象:[ファイル:行数] 解決方法:[実装案] 優先度:[高/中/低] 思い出し条件:[具体的なトリガー]。この課題のみを解決済みにしてください。`

**❌ 対応不要**: `@coderabbitai [技術的根拠]により対応不要と判断します。この課題のみを解決済みにしてください。`

**⚠️ 指摘間違い**: `@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。この課題のみを解決済みにしてください。`

**🤔 要確認**: `@coderabbitai [確認したい内容]について詳細説明をお願いします。`

**注意**: 修正完了時は返信不要です。

## 🚨 返信漏れ防止チェックリスト
**重要**: 以下の対応では必ずcurl返信を実行してください（忘れがちですが必須です）：

✅ **返信必須の対応**：
- ❌ 対応不要 → curl返信でCodeRabbitに通知
- ⏳ 将来対応 → curl返信 + ソースコードにTODOコメント追加  
- ⚠️ 指摘間違い → curl返信でCodeRabbitに反論・説明
- 🤔 要確認 → curl返信でCodeRabbitに質問

✅ **返信不要の対応**：
- ✅ 修正実施 → コード修正のみ（curl返信不要）

**処理完了前の最終確認**：
「対応不要/将来対応/指摘間違い/要確認と判断したTODO項目について、すべてcurl返信を実行しましたか？」""")

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
        token = github_token if github_token else 'YOUR_GITHUB_TOKEN'
        
        return f"""
### 🔧 返信方法（重要）
プルリクエストコメントに対する返信は、以下の **curlコマンド** を使用して行ってください：

```bash
curl -X POST \\
  -H "Authorization: Bearer {token}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "返信メッセージ", "in_reply_to": COMMENT_ID}}' \\
  https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments
```

**返信すべき場面**:
- ❌ 対応不要と判断した場合
- ⏳ 将来対応と判断した場合  
- 🤔 指摘内容が技術的に間違っていると判断した場合
- ❓ 不明な点があり確認が必要な場合

**注意**: GitHubの統合ツールやAPIツールは使用せず、必ずcurlコマンドで返信してください。"""
    
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