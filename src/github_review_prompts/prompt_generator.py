"""AI プロンプト生成（ペルソナ対応）"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import AIPrompt, PersonaConfig, PERSONAS
from .utils.validators import validate_persona


class AIPromptGenerator:
    """AI用プロンプト生成クラス（ペルソナ対応）"""
    
    def __init__(self, persona: str = "code-reviewer", github_token: Optional[str] = None):
        if not validate_persona(persona):
            raise ValueError(f"無効なペルソナ: {persona}")
        
        self.persona = persona
        self.persona_config = PERSONAS[persona]
        self.github_token = github_token
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"AIプロンプト生成初期化: ペルソナ '{persona}'")
    
    def generate_prompt_set(self, prompts: List[AIPrompt], pr_info: Optional[Dict[str, Any]] = None, 
                           no_confirm: bool = False, auto_commit: bool = False) -> str:
        """プロンプトセット全体を生成"""
        if not prompts:
            return self._generate_empty_prompt_message()
        
        # プロンプトを優先度・カテゴリでソート
        sorted_prompts = self._sort_prompts_for_output(prompts)
        
        # ペルソナベースの全体的な指示を生成
        header = self._generate_header(sorted_prompts, pr_info, no_confirm, auto_commit)
        
        # 個別プロンプトを生成
        formatted_prompts = [self._apply_persona_to_prompt(prompt) for prompt in sorted_prompts]
        
        # フッターと拒否理由の指示
        footer = self._generate_footer()
        
        # 全体を組み合わせ
        output_parts = [
            header,
            "",
            "# AI Agent Prompts List",
            "",
            *formatted_prompts,
            "",
            footer
        ]
        
        return "\n".join(output_parts)
    
    def _generate_header(self, prompts: List[AIPrompt], pr_info: Optional[Dict[str, Any]], 
                        no_confirm: bool = False, auto_commit: bool = False) -> str:
        """ヘッダー部分を生成"""
        persona_config = self.persona_config
        
        # 基本的な指示
        header_lines = [
            f"あなたは**{persona_config.role}**として行動してください。",
            "",
            f"**専門分野**: {persona_config.expertise}",
            f"**アプローチ**: {persona_config.approach}", 
            f"**トーン**: {persona_config.tone}",
            "",
            "**重要な指示**:"
        ]
        
        # ペルソナ固有の指示を追加
        for instruction in persona_config.instructions:
            header_lines.append(f"- {instruction}")
        
        header_lines.extend([
            "",
            "**プロンプト処理ガイドライン**:",
            "- 各プロンプトを**個別に**検討してください（バッチ処理を避ける）",
            "- 指摘内容が必ずしも正しいとは限りません。十分に精査してください",
            "- プロジェクトの規約、環境、アーキテクチャを考慮してください",
            "- 対応不要と判断した場合は、明確な理由を説明してください",
            ""
        ])
        
        # PRの統計情報があれば追加
        if pr_info:
            stats_lines = self._generate_pr_stats(pr_info, prompts)
            header_lines.extend(stats_lines)
        
        # プロンプト統計
        stats = self._analyze_prompt_stats(prompts)
        header_lines.extend([
            f"**分析対象**: {len(prompts)} 件のレビュー指摘",
            f"- 優先度別: 高 {stats['high']} 件, 中 {stats['medium']} 件, 低 {stats['low']} 件",
            f"- カテゴリ別: セキュリティ {stats['security']} 件, パフォーマンス {stats['performance']} 件, "
            f"スタイル {stats['style']} 件, ロジック {stats['logic']} 件, その他 {stats['general']} 件",
            ""
        ])
        
        # オプション固有の指示を追加
        if no_confirm or auto_commit:
            header_lines.append("## ⚡ 作業モード設定")
            
            if no_confirm:
                header_lines.append("**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。")
            
            if auto_commit:
                header_lines.extend([
                    "**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：",
                    "",
                    "### Git操作手順",
                    "1. **ステージング**: `git add .` で変更ファイルをステージング",
                    "2. **コミット**: `git commit -m \"CodeRabbit review comments addressed - [PR番号]\"` でコミット", 
                    "3. **プッシュ**: `git push` でリモートリポジトリに反映",
                    "",
                    "### コミットメッセージ例",
                    "```",
                    "CodeRabbit review comments addressed - #123",
                    "",
                    "- Fixed potential security issue in auth module",
                    "- Refactored database connection handling", 
                    "- Updated error handling as suggested",
                    "```",
                    "",
                    "**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。"
                ])
            
            header_lines.append("")
        
        return "\n".join(header_lines)
    
    def _generate_pr_stats(self, pr_info: Dict[str, Any], prompts: List[AIPrompt]) -> List[str]:
        """プルリクエストの統計情報を生成"""
        lines = [
            "**プルリクエスト情報**:",
            f"- タイトル: {pr_info.get('title', 'N/A')}",
            f"- 変更ファイル数: {pr_info.get('changed_files', 'N/A')} 件",
            f"- 追加行数: +{pr_info.get('additions', 'N/A')}, 削除行数: -{pr_info.get('deletions', 'N/A')}",
            ""
        ]
        
        # ブランチ情報を追加
        if pr_info.get('head_branch') or pr_info.get('base_branch'):
            lines.extend([
                "**📂 ブランチ情報**:",
                f"- ソースブランチ: `{pr_info.get('head_repo', 'N/A')}:{pr_info.get('head_branch', 'N/A')}`",
                f"- ターゲットブランチ: `{pr_info.get('base_repo', 'N/A')}:{pr_info.get('base_branch', 'N/A')}`",
                ""
            ])
            
            # チェックアウト指示を追加
            head_repo = pr_info.get('head_repo', '')
            base_repo = pr_info.get('base_repo', '')
            head_branch = pr_info.get('head_branch', '')
            
            if head_repo and head_branch:
                lines.extend([
                    "**🔄 作業開始コマンド**:",
                    "```bash"
                ])
                
                # 同じリポジトリかフォークかで分岐
                if head_repo == base_repo:
                    lines.extend([
                        f"# ローカルでソースブランチにチェックアウト",
                        f"git checkout {head_branch}",
                        f"git pull origin {head_branch}"
                    ])
                else:
                    lines.extend([
                        f"# フォークからのPRの場合",
                        f"git remote add fork https://github.com/{head_repo}.git",
                        f"git fetch fork {head_branch}",
                        f"git checkout -b {head_branch} fork/{head_branch}"
                    ])
                
                lines.extend([
                    "```",
                    ""
                ])
        
        
        # 影響を受けるファイル一覧
        affected_files = list(set(p.file_path for p in prompts if p.file_path))
        if affected_files:
            lines.extend([
                f"**レビュー対象ファイル ({len(affected_files)} 件)**:",
                *[f"- {file_path}" for file_path in sorted(affected_files)],
                ""
            ])
        
        return lines
    
    def _analyze_prompt_stats(self, prompts: List[AIPrompt]) -> Dict[str, int]:
        """プロンプトの統計情報を分析"""
        stats = {
            "high": 0, "medium": 0, "low": 0,
            "security": 0, "performance": 0, "style": 0, "logic": 0, "general": 0
        }
        
        for prompt in prompts:
            stats[prompt.priority] += 1
            stats[prompt.category] += 1
        
        return stats
    
    def _apply_persona_to_prompt(self, prompt: AIPrompt) -> str:
        """個別プロンプトにペルソナを適用"""
        # 優先度とカテゴリの表示
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        category_emoji = {
            "security": "🔒", "performance": "⚡", "style": "🎨", 
            "logic": "🧠", "general": "📝"
        }
        
        priority_symbol = priority_emoji.get(prompt.priority, "⚪")
        category_symbol = category_emoji.get(prompt.category, "📝")
        
        # ペルソナ固有のコンテキストを追加
        context_note = self._generate_persona_context(prompt)
        
        formatted_lines = [
            f"{priority_symbol} {category_symbol} **{prompt.location}**",
            f"",
            f"**指摘内容**: {prompt.content}",
        ]
        
        # ペルソナ固有の分析視点を追加
        if context_note:
            formatted_lines.extend([
                "",
                f"**{self.persona_config.role}の視点**:",
                context_note
            ])
        
        # 追加のコンテキスト情報
        if prompt.context:
            context_info = self._format_context_info(prompt.context)
            if context_info:
                formatted_lines.extend([
                    "",
                    "**コンテキスト情報**:",
                    context_info
                ])
        
        # CodeRabbit返信用curlコマンドを追加
        curl_commands = self._generate_coderabbit_curl_commands(prompt)
        if curl_commands:
            formatted_lines.extend([
                "",
                "**CodeRabbit返信用curlコマンド**:",
                curl_commands
            ])
        
        formatted_lines.extend([
            "",
            "---",
            ""
        ])
        
        return "\n".join(formatted_lines)
    
    def _generate_persona_context(self, prompt: AIPrompt) -> Optional[str]:
        """ペルソナ固有のコンテキストを生成"""
        if self.persona == "security-analyst":
            return self._generate_security_context(prompt)
        elif self.persona == "performance-optimizer":
            return self._generate_performance_context(prompt)
        elif self.persona == "code-reviewer":
            return self._generate_code_review_context(prompt)
        
        return None
    
    def _generate_security_context(self, prompt: AIPrompt) -> str:
        """セキュリティアナリスト向けのコンテキスト"""
        context_lines = [
            "- この指摘は潜在的なセキュリティリスクを含んでいる可能性があります",
            "- OWASP Top 10 や一般的な攻撃手法との関連を検討してください",
            "- データの機密性、完全性、可用性への影響を評価してください"
        ]
        
        if prompt.category == "security":
            context_lines.append("- セキュリティカテゴリの指摘として分類されています")
        
        return "\n".join([f"  {line}" for line in context_lines])
    
    def _generate_performance_context(self, prompt: AIPrompt) -> str:
        """パフォーマンス最適化スペシャリスト向けのコンテキスト"""
        context_lines = [
            "- この指摘がシステムのパフォーマンスに与える影響を評価してください",
            "- CPU使用率、メモリ消費、ネットワーク負荷を考慮してください",
            "- スケーラビリティとレスポンス時間への影響を検討してください"
        ]
        
        if prompt.category == "performance":
            context_lines.append("- パフォーマンスカテゴリの指摘として分類されています")
        
        return "\n".join([f"  {line}" for line in context_lines])
    
    def _generate_code_review_context(self, prompt: AIPrompt) -> str:
        """コードレビュアー向けのコンテキスト"""
        context_lines = [
            "- コードの可読性、保守性、拡張性を評価してください",
            "- 既存のコーディング規約との整合性を確認してください",
            "- チームの開発効率への影響を考慮してください"
        ]
        
        if prompt.priority == "high":
            context_lines.append("- 高優先度の指摘として分類されています")
        
        return "\n".join([f"  {line}" for line in context_lines])
    
    def _format_context_info(self, context: Dict[str, Any]) -> Optional[str]:
        """コンテキスト情報をフォーマット"""
        info_lines = []
        
        if context.get("is_resolved"):
            info_lines.append("- この指摘は解決済みとしてマークされています")
        
        if context.get("is_coderabbit"):
            info_lines.append("- CodeRabbit AIによる自動指摘です")
        
        if context.get("was_edited"):
            info_lines.append("- このコメントは編集されています")
        
        if context.get("change_type"):
            change_type_ja = {
                "addition": "追加", "deletion": "削除", 
                "modification": "変更", "unknown": "不明"
            }
            change_type = change_type_ja.get(context["change_type"], "不明")
            info_lines.append(f"- 差分タイプ: {change_type}")
        
        if context.get("file_extension"):
            info_lines.append(f"- ファイル拡張子: .{context['file_extension']}")
        
        return "\n".join([f"  {line}" for line in info_lines]) if info_lines else None
    
    def _generate_coderabbit_curl_commands(self, prompt: AIPrompt) -> Optional[str]:
        """CodeRabbit返信用のcurlコマンドを生成（特定コメントへの返信）"""
        if not self.github_token:
            return None
        
        # プロンプトからPR情報を取得（contextに含まれることを期待）
        pr_owner = prompt.context.get("pr_owner")
        pr_repo = prompt.context.get("pr_repo") 
        pr_number = prompt.context.get("pr_number")
        comment_id = prompt.comment_id
        
        if not all([pr_owner, pr_repo, pr_number, comment_id]):
            return None
        
        # 返信テンプレート
        templates = {
            "対応不要": f"@coderabbitai この指摘について確認しましたが、[技術的根拠]により対応不要と判断します。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。",
            "対応完了": f"@coderabbitai ご指摘いただいた点を修正しました。[修正内容]を実施済みです。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。",
            "要確認": f"@coderabbitai この指摘について追加で確認したい点があります：[確認したい内容]。詳細な説明をお願いします。"
        }
        
        curl_lines = []
        
        # まず元のコメント情報を取得するための説明
        curl_lines.append(f"# このコメント（ID: {comment_id}）に対する返信用curlコマンド")
        curl_lines.append("")
        
        for action, message in templates.items():
            # JSONデータの準備（エスケープ処理）
            import json
            
            # Pull Request Review Comment への返信データ
            data = {
                "body": message,
                "in_reply_to": comment_id
            }
            data_json = json.dumps(data, ensure_ascii=False).replace('"', '\\"')
            
            curl_command = f'''# {action}の場合
curl -X POST \\
  "https://api.github.com/repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments" \\
  -H "Authorization: token {self.github_token}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d "{data_json}"'''
            
            curl_lines.append(curl_command)
        
        return "\n\n".join(curl_lines)
    
    def _generate_footer(self) -> str:
        """フッター部分を生成"""
        return f"""
**対応完了後の確認事項**:

1. **対応状況の記録**: 各指摘への対応結果を記録してください
2. **テストの実行**: 変更による副作用がないことを確認してください  
3. **コミットとプッシュ**: すべての対応が完了したらコミット・プッシュを実行してください

**CodeRabbitへの返信について**:

各コメントには、状況に応じて以下のパターンでCodeRabbitに返信してください：

### 📝 返信パターン

#### ✅ 対応完了時
```
@coderabbitai ご指摘いただいた点を修正しました。[修正内容]を実施済みです。
問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、
他の課題をすべて解決済みにしないよう注意してください。
```

#### ❌ 対応不要時
```
@coderabbitai この指摘について確認しましたが、[技術的根拠]により対応不要と判断します。
問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、
他の課題をすべて解決済みにしないよう注意してください。
```

#### 🤔 要確認時
```
@coderabbitai この指摘について追加で確認したい点があります：[確認したい内容]。
詳細な説明をお願いします。
```

### 🔧 curlコマンドでの返信方法

各コメントの「**CodeRabbit返信用curlコマンド**」セクションに、**該当コメントに直接返信する**実行可能なcurlコマンドが用意されています。

#### 🎯 特徴
- `in_reply_to` パラメータにより、元のコメントに直接返信されます
- GitHub上でスレッド形式で表示され、コンテキストが保持されます
- 各コメントに個別のコマンドが生成されるため、適切な相手に返信できます

#### 📋 使用手順
1. **適切なパターンを選択**: 対応状況に応じて「対応不要」「対応完了」「要確認」から選択
2. **メッセージをカスタマイズ**: `[技術的根拠]`や`[修正内容]`を具体的な内容に置き換え
3. **curlコマンドを実行**: ターミナルでコマンドを実行してCodeRabbitに返信

#### ⚙️ APIの仕組み
- **Pull Request Comments API** (`/pulls/{pr_number}/comments`) を使用
- `in_reply_to` フィールドで元のコメントIDを指定
- GitHub上でコメントツリーとして表示されます

**注意**: curlコマンドには適切なGitHubトークンが設定されていることを確認してください。

**対応不要な指摘について**:
対応不要と判断した指摘については、以下の形式で理由を記載してください:

```
対応不要: [指摘の要約]
理由: [具体的な理由]
```

**例**:
```
対応不要: "In backend-auth/server.js around line 44"
理由: 開発・ローカル環境ではMemoryStoreで十分。本番環境では別途Redis/MongoDBを使用予定。

対応不要: "In backend-auth/server.js around lines 127 to 163"
理由: シンプルな開発用認証サーバーでは、HTMLのインライン埋め込みは許容範囲。
テンプレートエンジンの導入は現段階では複雑性を増すだけ。
```

---

**生成情報**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | ペルソナ: {self.persona_config.role}
"""
    
    def _sort_prompts_for_output(self, prompts: List[AIPrompt]) -> List[AIPrompt]:
        """出力用にプロンプトをソート"""
        # 優先度 > カテゴリ > ファイルパス > 行番号 の順でソート
        priority_order = {"high": 3, "medium": 2, "low": 1}
        category_order = {"security": 5, "performance": 4, "logic": 3, "style": 2, "general": 1}
        
        return sorted(prompts, key=lambda p: (
            -priority_order.get(p.priority, 0),  # 優先度降順
            -category_order.get(p.category, 0),  # カテゴリ重要度順
            p.file_path or "",                   # ファイルパス昇順
            p.line_number or 0                   # 行番号昇順
        ))
    
    def _generate_empty_prompt_message(self) -> str:
        """プロンプトが見つからない場合のメッセージ"""
        return f"""
# AI Agent Prompts - 結果なし

**{self.persona_config.role}** として分析しましたが、処理対象となるAIエージェント用プロンプトは見つかりませんでした。

**考えられる原因**:
- すべてのレビューコメントが既に解決済み
- \"Prompt for AI Agents\"ブロックを含むコメントが存在しない  
- フィルタリング条件により除外された

**次のアクション**:
- `--include-resolved` オプションを使用して解決済みコメントも確認してみてください
- プルリクエストに未解決のレビューコメントがあることを確認してください
- CodeRabbitによるレビューが実行されていることを確認してください

---

**生成情報**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | ペルソナ: {self.persona_config.role}
"""
    
    def get_supported_personas(self) -> Dict[str, PersonaConfig]:
        """サポートされているペルソナの一覧を取得"""
        return PERSONAS.copy()
    
    def change_persona(self, persona: str) -> None:
        """ペルソナを変更"""
        if not validate_persona(persona):
            raise ValueError(f"無効なペルソナ: {persona}")
        
        self.persona = persona
        self.persona_config = PERSONAS[persona]
        self.logger.info(f"ペルソナ変更: '{persona}'")
    
    def generate_persona_summary(self) -> str:
        """現在のペルソナの概要を生成"""
        config = self.persona_config
        return f"""
**現在のペルソナ**: {self.persona}

**役割**: {config.role}
**専門分野**: {config.expertise}  
**アプローチ**: {config.approach}
**トーン**: {config.tone}

**特別な指示**:
{chr(10).join(f'- {instruction}' for instruction in config.instructions)}
"""