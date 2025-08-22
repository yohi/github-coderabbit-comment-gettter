"""AI プロンプト生成（ペルソナ対応）"""

import logging
import time
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
        
        # curlコマンドセクションを生成
        curl_commands_section = "\n".join(self._generate_curl_commands_section(self.github_token))
        
        # 全体を組み合わせ
        output_parts = [
            header,
            "",
            curl_commands_section,
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
                        "# ローカルでソースブランチにチェックアウト",
                        f"git checkout {head_branch}",
                        f"git pull origin {head_branch}"
                    ])
                else:
                    lines.extend([
                        "# フォークからのPRの場合",
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
            "",
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
        
        # CodeRabbit返信用の簡潔な指示を追加
        reply_info = self._generate_coderabbit_reply_info(prompt)
        if reply_info:
            formatted_lines.extend([
                "",
                "**CodeRabbit返信用**:",
                reply_info
            ])
        
        formatted_lines.extend([
            "",
            "---",
            ""
        ])
        
        return "\n".join(formatted_lines)
    
    def _generate_persona_context(self, prompt: AIPrompt) -> Optional[str]:
        """ペルソナ固有のコンテキストを生成（簡潔版）"""
        if self.persona == "security-analyst":
            return "セキュリティリスク・OWASP Top 10・機密性/完全性/可用性を重点評価"
        elif self.persona == "performance-optimizer":
            return "パフォーマンス影響・CPU/メモリ/ネットワーク負荷・スケーラビリティを重点評価"
        elif self.persona == "code-reviewer":
            return "可読性・保守性・拡張性・コーディング規約・開発効率を重点評価"
        
        return None
    
    def _format_context_info(self, context: Dict[str, Any]) -> Optional[str]:
        """コンテキスト情報をフォーマット（簡潔版）"""
        info_parts = []
        
        if context.get("is_resolved"):
            info_parts.append("解決済み")
        
        if context.get("is_coderabbit"):
            info_parts.append("CodeRabbit")
        
        if context.get("was_edited"):
            info_parts.append("編集済み")
        
        if context.get("change_type"):
            change_type_ja = {"addition": "追加", "deletion": "削除", "modification": "変更", "unknown": "不明"}
            info_parts.append(change_type_ja.get(context["change_type"], "不明"))
        
        if context.get("file_extension"):
            info_parts.append(f".{context['file_extension']}")
        
        return " | ".join(info_parts) if info_parts else None
    
    def _generate_coderabbit_reply_info(self, prompt: AIPrompt) -> Optional[str]:
        """CodeRabbit返信用の簡潔な情報を生成"""
        comment_id = prompt.comment_id
        context = prompt.context or {}
        pr_owner = context.get("pr_owner")
        pr_repo = context.get("pr_repo")
        pr_number = context.get("pr_number")
        
        if not all([pr_owner, pr_repo, pr_number, comment_id]):
            return None
        
        # 簡潔な返信情報（curlコマンドへの参照は削除）
        return f"""**コメントID**: {comment_id}
**APIエンドポイント**: `POST /repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments`
**返信方法**: `in_reply_to: {comment_id}` でこのコメントに直接返信可能"""
    
    def _generate_curl_commands_section(self, github_token: str) -> List[str]:
        """CodeRabbit返信用curlコマンドセクションを生成"""
        return [
            "### 🔧 CodeRabbit返信用curlコマンド",
            "",
            "**認証**: 環境変数 GITHUB_TOKEN を使用します（値は出力しません）",
            "",
            "#### ❌ 対応不要（完全に不要）の場合",
            "```bash",
            "curl -X POST \"https://api.github.com/repos/[OWNER]/[REPO]/pulls/[PR_NUMBER]/comments\" \\\\",
            "  -H \"Authorization: token ${GITHUB_TOKEN}\" \\\\",
            "  -H \"Accept: application/vnd.github.v3+json\" \\\\",
            "  -H \"Content-Type: application/json\" \\\\",
            "  -d '{",
            "    \"body\": \"@coderabbitai 対応不要：[技術的根拠を記載]。適切と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。\",",
            "    \"in_reply_to\": [COMMENT_ID]",
            "  }'",
            "```",
            "",
            "#### 📅 将来対応予定（このフェーズでは対応しない）の場合",
            "**重要**: curlコマンド実行と同時に、該当ソースファイルにTODOコメントを追加してください。",
            "```bash",
            "curl -X POST \"https://api.github.com/repos/[OWNER]/[REPO]/pulls/[PR_NUMBER]/comments\" \\\\",
            "  -H \"Authorization: token ${GITHUB_TOKEN}\" \\\\",
            "  -H \"Accept: application/vnd.github.v3+json\" \\\\",
            "  -H \"Content-Type: application/json\" \\\\",
            "  -d '{",
            "    \"body\": \"@coderabbitai この指摘は妥当ですが、現在のPhase/ステップでは対応対象外です。現在: [具体的なPhase名]、対応予定: [具体的な将来Phase名]。**記憶依頼**: 以下を構造化記録し『[将来Phase名]』開始時・[技術領域]作業時に積極的に思い出してください - 指摘:[要約] 対象:[ファイル:行数] 解決方法:[実装案] 優先度:[高/中/低] 思い出し条件:[具体的なトリガー]。適切と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。\",",
            "    \"in_reply_to\": [COMMENT_ID]",
            "  }'",
            "```",
            "**ソースコード修正**: 指摘箇所に以下のTODOコメントを追加",
            "```",
            "// TODO: [次フェーズで対応予定] - [YYYY-MM-DD]",
            "```",
            "",
            "#### 🤔 要確認の場合",
            "```bash",
            "curl -X POST \"https://api.github.com/repos/[OWNER]/[REPO]/pulls/[PR_NUMBER]/comments\" \\\\",
            "  -H \"Authorization: token ${GITHUB_TOKEN}\" \\\\",
            "  -H \"Accept: application/vnd.github.v3+json\" \\\\",
            "  -H \"Content-Type: application/json\" \\\\",
            "  -d '{",
            "    \"body\": \"@coderabbitai [確認したい内容]について詳細説明をお願いします。\",",
            "    \"in_reply_to\": [COMMENT_ID]",
            "  }'",
            "```",
            "",
            "#### ⚠️ 指摘間違いの場合",
            "```bash",
            "curl -X POST \"https://api.github.com/repos/[OWNER]/[REPO]/pulls/[PR_NUMBER]/comments\" \\\\",
            "  -H \"Authorization: token ${GITHUB_TOKEN}\" \\\\",
            "  -H \"Accept: application/vnd.github.v3+json\" \\\\",
            "  -H \"Content-Type: application/json\" \\\\",
            "  -d '{",
            "    \"body\": \"@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。妥当と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。\",",
            "    \"in_reply_to\": [COMMENT_ID]",
            "  }'",
            "```",
            "",
            "**使用方法**:",
            "1. 各TODO項目の「コメントID」を確認",
            "2. 上記テンプレートの `[OWNER]`, `[REPO]`, `[PR_NUMBER]`, `[COMMENT_ID]` を実際の値に置換",
            "3. `[技術的根拠を記載]` 部分に具体的な理由を記入",
            "4. **📅 将来対応予定の場合**: 記憶依頼の各項目（Phase名、技術領域、指摘要約、対象、解決方法、優先度、トリガー条件）を具体的に記入",
            "5. **📅 将来対応予定の場合のみ**: 該当ソースファイルにTODOコメントを追加",
            "6. curlコマンドを実行",
            "",
            "**技術的根拠の例**:",
            "- `型安全性の観点から現在の実装が適切`",
            "- `パフォーマンス要件を満たしており変更不要`",
            "- `セキュリティリスクが存在しないため対応不要`",
            "- `コードの可読性を損なう可能性があるため現状維持`",
            "",
            "**重要**: 修正完了時の@coderabbitaiへの報告は不要です。上記コマンドは対応しない場合のみ使用してください。課題の解決判断はCodeRabbitが行いますが、**一括での課題解決は絶対に行わないでください**。",
            "",
            "## 🚨 返信漏れ防止チェックリスト",
            "**重要**: 以下の対応では必ずcurl返信を実行してください（忘れがちですが必須です）：",
            "",
            "✅ **返信必須の対応**：",
            "- ❌ 対応不要 → curl返信でCodeRabbitに通知",
            "- ⏳ 将来対応 → curl返信 + ソースコードにTODOコメント追加",
            "- ⚠️ 指摘間違い → curl返信でCodeRabbitに反論・説明",
            "- 🤔 要確認 → curl返信でCodeRabbitに質問",
            "",
            "✅ **返信不要の対応**：",
            "- ✅ 修正実施 → コード修正のみ（curl返信不要）",
            "",
            "**処理完了前の最終確認**：",
            "「対応不要/将来対応/指摘間違い/要確認と判断したTODO項目について、すべてcurl返信を実行しましたか？」",
            "",
            "**TODOコメント例**:",
            "```javascript",
            "// TODO: パフォーマンス最適化検討 - 2025-01-15",
            "function processData(data) {",
            "  // 現在のO(n)実装で十分",
            "  return data.map(item => transform(item));",
            "}",
            "```",
            "```python",
            "# TODO: 非同期処理対応 - v2.0で実装予定 - 2025-01-15",
            "def process_data():",
            "    # 現在は同期処理、将来非同期化予定",
            "    return calculate_result()",
            "```",
            ""
        ]
    
    def _generate_footer(self) -> str:
        """フッター部分を生成"""
        return f"""
## 作業手順
1. コメントの技術的妥当性を評価
2. 対応要否を判断し、理由を明記
3. **対応する場合**: 具体的な修正を実施（@coderabbitaiへの完了報告は不要）
4. **対応しない場合**: GitHub APIを使って@coderabbitaiに技術的根拠を含む返信コメントを作成
5. **重要**: 各対応完了後は必ず該当コメントの解決済み指示を含める

**CodeRabbit返信パターン**:
- ✅ **対応完了**: 修正のみ実施、@coderabbitaiへの完了報告は不要
- ❌ **対応不要（完全に不要）**: CodeRabbitに返信のみ
  - 返信: `@coderabbitai 対応不要：[技術的根拠]。適切と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。`
- 📅 **将来対応予定**: 以下の2つのアクションを実行
  1. CodeRabbitに返信: `@coderabbitai 将来対応予定：このフェーズでは対応しませんが、[次のフェーズ/バージョン]で対応予定です。`
  2. **ソースコードにTODOコメント追加**: 該当ファイルの指摘箇所に `// TODO: [次フェーズで対応予定] - [日付]` を追加
- 🤔 **要確認**: `@coderabbitai 確認要望：[確認内容]。詳細説明をお願いします。`
- ⚠️ **指摘間違い**: CodeRabbitに返信のみ
  - 返信: `@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。`

**重要**: 修正完了時の@coderabbitaiへの報告は不要です。課題の解決判断はCodeRabbitに委ねます。**一括での課題解決は禁止**です。

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

**生成情報**: {time.strftime('%Y-%m-%d %H:%M:%S')} | ペルソナ: {self.persona_config.role}
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

**生成情報**: {time.strftime('%Y-%m-%d %H:%M:%S')} | ペルソナ: {self.persona_config.role}
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