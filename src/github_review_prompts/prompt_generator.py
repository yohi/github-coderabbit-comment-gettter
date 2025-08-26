"""AI プロンプト生成（ペルソナ対応）"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import AIPrompt, PersonaConfig, PERSONAS, OutsideDiffComment
from .utils.outside_diff_parser import OutsideDiffParser
from .utils.validators import validate_persona


class AIPromptGenerator:
    """AI用プロンプト生成クラス（ペルソナ対応）"""

    def __init__(
        self, persona: str = "code-reviewer", github_token: Optional[str] = None
    ):
        if not validate_persona(persona):
            raise ValueError(f"無効なペルソナ: {persona}")

        self.persona = persona
        self.persona_config = PERSONAS[persona]
        self.github_token = github_token
        self.logger = logging.getLogger(__name__)
        self.outside_diff_parser = OutsideDiffParser()

        self.logger.info(f"AIプロンプト生成初期化: ペルソナ '{persona}'")

    def generate_prompt_set(
        self,
        prompts: List[AIPrompt],
        pr_info: Optional[Dict[str, Any]] = None,
        no_confirm: bool = False,
        auto_commit: bool = False,
    ) -> str:
        """プロンプトセット全体を生成"""
        if not prompts:
            return self._generate_empty_prompt_message()

        # プロンプトを優先度・カテゴリでソート
        sorted_prompts = self._sort_prompts_for_output(prompts)

        # ペルソナベースの全体的な指示を生成
        header = self._generate_header(sorted_prompts, pr_info, no_confirm, auto_commit)

        # 個別プロンプトを生成
        formatted_prompts = [
            self._apply_persona_to_prompt(prompt) for prompt in sorted_prompts
        ]

        # フッターと拒否理由の指示
        footer = self._generate_footer()

        # curlコマンドセクションを生成（簡潔版）
        # PR情報からowner, repo, pr_numberを抽出
        owner = pr_info.get("owner") if pr_info else None
        repo = pr_info.get("repo") if pr_info else None
        pr_number = pr_info.get("number") if pr_info else None
        curl_commands_section = self._generate_simple_curl_section(owner, repo, pr_number)

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
            footer,
        ]

        return "\n".join(output_parts)

    def _generate_header(
        self,
        prompts: List[AIPrompt],
        pr_info: Optional[Dict[str, Any]],
        no_confirm: bool = False,
        auto_commit: bool = False,
    ) -> str:
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
            "**重要な指示**:",
        ]

        # ペルソナ固有の指示を追加
        for instruction in persona_config.instructions:
            header_lines.append(f"- {instruction}")

        header_lines.extend(
            [
                "",
                "**プロンプト処理ガイドライン**:",
                "- 各プロンプトを**個別に**検討してください（バッチ処理を避ける）",
                "- 指摘内容が必ずしも正しいとは限りません。十分に精査してください",
                "- プロジェクトの規約、環境、アーキテクチャを考慮してください",
                "- 対応不要と判断した場合は、明確な理由を説明してください",
                "",
            ]
        )

        # PRの統計情報があれば追加
        if pr_info:
            stats_lines = self._generate_pr_stats(pr_info, prompts)
            header_lines.extend(stats_lines)

        # プロンプト統計
        stats = self._analyze_prompt_stats(prompts)
        header_lines.extend(
            [
                f"**分析対象**: {len(prompts)} 件のレビュー指摘",
                f"- 優先度別: 高 {stats['high']} 件, 中 {stats['medium']} 件, 低 {stats['low']} 件",
                f"- カテゴリ別: セキュリティ {stats['security']} 件, パフォーマンス {stats['performance']} 件, "
                f"スタイル {stats['style']} 件, ロジック {stats['logic']} 件, その他 {stats['general']} 件",
                "",
            ]
        )

        # オプション固有の指示を追加（簡潔版）
        if no_confirm or auto_commit:
            header_lines.append("## ⚡ 実行モード")

            if no_confirm:
                header_lines.append("- **確認スキップ**: 連続処理モード")

            if auto_commit:
                header_lines.extend(
                    [
                        "- **自動コミット**: 完了後に自動でgit add/commit/push実行",
                        "- コミットメッセージ: `CodeRabbitレビューコメント対応 - #[PR番号]`",
                    ]
                )

            header_lines.append("")

        return "\n".join(header_lines)

    def _generate_pr_stats(
        self, pr_info: Dict[str, Any], prompts: List[AIPrompt]
    ) -> List[str]:
        """プルリクエストの統計情報を生成"""
        lines = [
            "**プルリクエスト情報**:",
            f"- タイトル: {pr_info.get('title', 'N/A')}",
            f"- 変更ファイル数: {pr_info.get('changed_files', 'N/A')} 件",
            f"- 追加行数: +{pr_info.get('additions', 'N/A')}, 削除行数: -{pr_info.get('deletions', 'N/A')}",
            "",
        ]

        # ブランチ情報を追加
        if pr_info.get("head_branch") or pr_info.get("base_branch"):
            lines.extend(
                [
                    "**📂 ブランチ情報**:",
                    f"- ソースブランチ: `{pr_info.get('head_repo', 'N/A')}:{pr_info.get('head_branch', 'N/A')}`",
                    f"- ターゲットブランチ: `{pr_info.get('base_repo', 'N/A')}:{pr_info.get('base_branch', 'N/A')}`",
                    "",
                ]
            )

            # チェックアウト指示を追加
            head_repo = pr_info.get("head_repo", "")
            base_repo = pr_info.get("base_repo", "")
            head_branch = pr_info.get("head_branch", "")

            if head_repo and head_branch:
                lines.extend(["**🔄 作業開始コマンド**:", "```bash"])

                # 同じリポジトリかフォークかで分岐
                if head_repo == base_repo:
                    lines.extend(
                        [
                            "# ローカルでソースブランチにチェックアウト",
                            f"git checkout {head_branch}",
                            f"git pull origin {head_branch}",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            "# フォークからのPRの場合",
                            f"git remote add fork https://github.com/{head_repo}.git",
                            f"git fetch fork {head_branch}",
                            f"git checkout -b {head_branch} fork/{head_branch}",
                        ]
                    )

                lines.extend(["```", ""])

        # 影響を受けるファイル一覧
        affected_files = list(set(p.file_path for p in prompts if p.file_path))
        if affected_files:
            lines.extend(
                [
                    f"**レビュー対象ファイル ({len(affected_files)} 件)**:",
                    *[f"- {file_path}" for file_path in sorted(affected_files)],
                    "",
                ]
            )

        return lines

    def _analyze_prompt_stats(self, prompts: List[AIPrompt]) -> Dict[str, int]:
        """プロンプトの統計情報を分析"""
        stats = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "security": 0,
            "performance": 0,
            "style": 0,
            "logic": 0,
            "general": 0,
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
            "security": "🔒",
            "performance": "⚡",
            "style": "🎨",
            "logic": "🧠",
            "general": "📝",
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
            formatted_lines.extend(
                ["", f"**{self.persona_config.role}の視点**:", context_note]
            )

        # 追加のコンテキスト情報
        if prompt.context:
            context_info = self._format_context_info(prompt.context)
            if context_info:
                formatted_lines.extend(["", "**コンテキスト情報**:", context_info])

        # CodeRabbit返信用の簡潔な指示を追加
        reply_info = self._generate_coderabbit_reply_info(prompt)
        if reply_info:
            formatted_lines.extend(["", "**CodeRabbit返信用**:", reply_info])

        formatted_lines.extend(["", "---", ""])

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
            change_type_ja = {
                "addition": "追加",
                "deletion": "削除",
                "modification": "変更",
                "unknown": "不明",
            }
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

        # 返信情報（curlコマンドでの返信を指示）
        return f"""**コメントID**: {comment_id}
**APIエンドポイント**: `POST /repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments/{comment_id}/replies`
**返信方法**: 以下のcurlコマンドで@coderabbitaiメンションして返信
```bash
curl -X POST \\
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "@coderabbitai 返信メッセージ"}}' \\
  https://api.github.com/repos/{pr_owner}/{pr_repo}/pulls/{pr_number}/comments/{comment_id}/replies
```"""

    def _generate_simple_curl_section(self, owner: str = None, repo: str = None, pr_number: int = None) -> str:
        """簡潔なcurlコマンドセクションを生成"""
        if owner and repo and pr_number:
            url_template = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments/COMMENT_ID/replies"
            replacement_note = "**注意**: COMMENT_IDを実際のコメントIDに置換してください"
        else:
            url_template = "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_ID/replies"
            replacement_note = "**注意**: OWNER/REPO/PR_NUMBER/COMMENT_IDを実際の値に置換してください"

        return f"""## 📤 返信方法

### 基本テンプレート
```bash
echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers
curl -X POST -H @/tmp/github_headers -H "Content-Type: application/json" \\
  -d '{{"body": "@coderabbitai 返信メッセージ"}}' \\
  "{url_template}"
rm /tmp/github_headers
```

### 返信パターン
- **❌ 対応不要**: `@coderabbitai 技術的制約により対応不要。解決済みマーク依頼。`
- **⏳ 将来対応**: `@coderabbitai 将来対応予定。記憶依頼。解決済みマーク依頼。`
- **🤔 要確認**: `@coderabbitai 詳細説明を依頼。`

{replacement_note}"""

    def _generate_footer(self) -> str:
        """フッター部分を生成（簡潔版）"""
        return f"""
## 🎯 作業フロー
1. 各コメントの技術的妥当性を評価
2. 対応判断：✅実施 / ❌不要 / ⏳将来 / 🤔確認
3. **✅実施**: コード修正のみ（返信不要）
4. **❌不要/⏳将来/🤔確認**: curlで@coderabbitaiに返信

## ⚠️ 重要ルール
- 修正完了時は返信不要
- 対応不要時は必ず返信
- 一括解決禁止

---
**生成**: {time.strftime('%Y-%m-%d %H:%M:%S')} | {self.persona_config.role}
"""

    def _sort_prompts_for_output(self, prompts: List[AIPrompt]) -> List[AIPrompt]:
        """出力用にプロンプトをソート"""
        # 優先度 > カテゴリ > ファイルパス > 行番号 の順でソート
        priority_order = {"high": 3, "medium": 2, "low": 1}
        category_order = {
            "security": 5,
            "performance": 4,
            "logic": 3,
            "style": 2,
            "general": 1,
        }

        return sorted(
            prompts,
            key=lambda p: (
                -priority_order.get(p.priority, 0),  # 優先度降順
                -category_order.get(p.category, 0),  # カテゴリ重要度順
                p.file_path or "",  # ファイルパス昇順
                p.line_number or 0,  # 行番号昇順
            ),
        )

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

    def generate_outside_diff_section(
        self, outside_diff_comments: List[OutsideDiffComment]
    ) -> str:
        """範囲外コメント用の特別セクションを生成

        Args:
            outside_diff_comments: 範囲外コメントのリスト

        Returns:
            範囲外コメント用のプロンプトセクション
        """
        if not outside_diff_comments:
            return ""

        # 優先度別に分類
        categorized = self.outside_diff_parser.categorize_by_priority(
            outside_diff_comments
        )
        priority_order = self.outside_diff_parser.get_priority_order()

        section = """
## 🚨 範囲外重要コメント（プラットフォーム制限により別途対応）

**⚠️ 重要**: これらのコメントはGitHubのプラットフォーム制限により、
diffビューでインライン表示されていませんが、対応が必要です。
ファイル全体を確認して該当箇所を特定してください。

### 🔒 セキュリティファースト対応手順
1. **ファイル特定**: 指定されたファイルパスを確認
2. **行範囲確認**: 指定された行範囲を直接確認
3. **コード理解**: 現在の実装を把握
4. **修正適用**: 提案されたdiffを慎重に適用
5. **影響範囲検証**: 関連する他の箇所への影響を確認

"""

        todo_counter = 1

        for priority in priority_order:
            if priority not in categorized:
                continue

            comments = categorized[priority]
            section += f"\n### {priority}対応項目\n\n"

            for comment in comments:
                section += self._format_outside_diff_comment(comment, todo_counter)
                todo_counter += 1

        return section

    def _format_outside_diff_comment(
        self, comment: OutsideDiffComment, todo_number: int
    ) -> str:
        """範囲外コメントを整形

        Args:
            comment: 範囲外コメント
            todo_number: TODO番号

        Returns:
            整形されたコメント文字列
        """
        # カテゴリアイコン/名称
        category_icons = {"actionable": "🚨", "duplicate": "♻️", "nitpick": "🧹"}
        category_names = {
            "actionable": "要対応",
            "duplicate": "重複",
            "nitpick": "指摘（軽微）",
        }

        # 重要度アイコン/名称
        severity_icons = {"caution": "🔴", "warning": "🟡", "info": "🟢"}
        severity_names = {"caution": "重大", "warning": "注意", "info": "情報"}

        category_value = getattr(comment.category, "value", "actionable")
        severity_value = getattr(comment.severity, "value", "warning")
        category_icon = category_icons.get(category_value, "📝")
        severity_icon = severity_icons.get(severity_value, "ℹ️")

        formatted = f"""
### TODO #{todo_number}: {comment.title}
**ID**: {comment.id}
**ファイル**: `{comment.file_path}`
**行範囲**: {comment.line_range}
**カテゴリ**: {category_icon} {category_names.get(category_value, category_value)} ({severity_icon} {severity_names.get(severity_value, severity_value)})
**制限理由**: diff範囲外のためインライン表示不可

**問題**: {comment.title}
**詳細**: {comment.description}
"""

        if comment.suggested_fix:
            formatted += f"""
**🔧 推奨修正**:
```diff
{comment.suggested_fix}
```
"""

        formatted += f"""
**📍 対応方法**:
1. ファイル `{comment.file_path}` を開く
2. 行 {comment.line_range} を確認
3. 上記の修正案を慎重に適用
4. 関連する他の箇所への影響を検証

---
"""

        return formatted
