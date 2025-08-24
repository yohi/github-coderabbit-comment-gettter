"""返信判定マトリックスシステム

コメントに対する対応方針を判定し、返信要否と適切なテンプレートを決定する。
返信漏れを防止し、一貫性のある対応を実現する。
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """対応アクションタイプ"""

    IMPLEMENT = "✅ 実施"  # 修正実装
    REJECT = "❌ 対応不要"  # 技術的根拠で拒否
    FUTURE = "⏳ 将来対応"  # 将来のフェーズで対応
    INCORRECT = "⚠️ 指摘間違い"  # CodeRabbitの誤った指摘
    CLARIFY = "🤔 要確認"  # 追加情報が必要
    AUTO_GENERATED = "🤖 自動生成"  # 自動生成・進捗報告（返信不要）


class ReplyRequirement(Enum):
    """返信要否"""

    REQUIRED = "required"  # 返信必須
    NOT_REQUIRED = "not_required"  # 返信不要
    OPTIONAL = "optional"  # 任意


@dataclass
class ReplyDecision:
    """返信判定結果"""

    action: ActionType
    reply_required: ReplyRequirement
    template_type: Optional[str]
    reason: str
    priority: str  # high, medium, low
    estimated_time: int  # 推定作業時間（分）


class ReplyDecisionMatrix:
    """返信要否を明確に判定するマトリックス"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 返信判定ルール
        self.reply_rules = {
            ActionType.IMPLEMENT: {
                "reply_required": ReplyRequirement.NOT_REQUIRED,
                "template_type": None,
                "reason": "修正実装で対応完了を示す",
                "priority": "high",
                "estimated_time": 15,
            },
            ActionType.REJECT: {
                "reply_required": ReplyRequirement.REQUIRED,
                "template_type": "technical_rejection",
                "reason": "技術的根拠を示して拒否理由を説明",
                "priority": "high",
                "estimated_time": 5,
            },
            ActionType.FUTURE: {
                "reply_required": ReplyRequirement.REQUIRED,
                "template_type": "future_planning",
                "reason": "記憶依頼と解決済みマーク要求",
                "priority": "medium",
                "estimated_time": 8,
            },
            ActionType.INCORRECT: {
                "reply_required": ReplyRequirement.REQUIRED,
                "template_type": "technical_correction",
                "reason": "正しい技術情報で反論・教育",
                "priority": "high",
                "estimated_time": 10,
            },
            ActionType.CLARIFY: {
                "reply_required": ReplyRequirement.REQUIRED,
                "template_type": "clarification_request",
                "reason": "追加情報要求で議論継続",
                "priority": "medium",
                "estimated_time": 3,
            },
            ActionType.AUTO_GENERATED: {
                "reply_required": ReplyRequirement.NOT_REQUIRED,
                "template_type": None,
                "reason": "自動生成・進捗報告のため返信不要",
                "priority": "low",
                "estimated_time": 0,
            },
        }

        # 返信テンプレート（改良版：より具体的で技術的根拠を重視）
        self.reply_templates = {
            "technical_rejection": """@coderabbitai この指摘は以下の技術的理由により対応不要と判断します：

**理由**: {technical_reason}
**詳細**: {detailed_explanation}
**技術的根拠**: {reference_or_documentation}
**代替案**: {alternative_approach}

より適切なアプローチがあれば提案をお願いします。問題ないと判断できれば、このコメントスレッドを解決済みにマークしてください。

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了
[/CR_RESOLUTION_CONFIRMED]""",
            "future_planning": """@coderabbitai 妥当な指摘ですが現在の{current_phase}フェーズでは対応範囲外です。

**現在フェーズ**: {current_phase}
**対応予定フェーズ**: {future_phase}
**影響度**: {impact_level}
**実装工数**: {effort_estimation}

**記憶依頼**: {future_phase}開始時に以下を思い出してください
- **課題**: {issue_summary}
- **対象**: {target_file_and_line}
- **解決方針**: {implementation_approach}
- **優先度**: {priority_level}
- **前提条件**: {prerequisites}
- **思い出し条件**: {trigger_condition}

将来対応として記録して問題なければ、このコメントスレッドを解決済みにマークしてください。

[CR_RESOLUTION_CONFIRMED:FUTURE_PHASE_PLANNED]
✅ 将来フェーズ対応として記録完了
[/CR_RESOLUTION_CONFIRMED]""",
            "technical_correction": """@coderabbitai この指摘は{specific_reason}により技術的に不正確と判断します。

**指摘内容の問題点**: {issue_with_suggestion}
**正しい技術情報**: {correct_technical_info}
**技術的根拠**: {technical_evidence}
**公式ドキュメント**: {documentation_link}
**実証方法**: {verification_method}

技術的な誤りを確認して学習していただけましたら、このコメントスレッドを解決済みにマークしてください。

[CR_RESOLUTION_CONFIRMED:TECHNICAL_CORRECTION_ACCEPTED]
✅ 技術的訂正が受け入れられました
[/CR_RESOLUTION_CONFIRMED]""",
            "clarification_request": """@coderabbitai {clarification_topic}について詳細説明をお願いします。

具体的な確認事項:
- {specific_question_1}
- {specific_question_2}
- {specific_question_3}

この情報により、より適切な対応を検討いたします。""",
        }

    def decide_action_and_reply(
        self, comment: Dict[str, Any], context: Dict[str, Any] = None
    ) -> ReplyDecision:
        """コメントに対する対応アクションと返信要否を判定

        Args:
            comment: GitHub APIから取得したコメント情報
            context: 判定に必要な追加コンテキスト

        Returns:
            ReplyDecision: 判定結果
        """
        if context is None:
            context = {}

        comment_body = comment.get("body", "")
        comment_id = comment.get("id", "unknown")
        author = comment.get("user", {}).get("login", "")

        self.logger.debug(f"返信判定開始: ID={comment_id}, Author={author}")

        # 1. アクションタイプの判定
        action_type = self._determine_action_type(comment_body, context)

        # 2. 返信判定ルールの適用
        rule = self.reply_rules[action_type]

        # 3. ReplyDecision作成
        decision = ReplyDecision(
            action=action_type,
            reply_required=rule["reply_required"],
            template_type=rule["template_type"],
            reason=rule["reason"],
            priority=rule["priority"],
            estimated_time=rule["estimated_time"],
        )

        self.logger.debug(
            f"返信判定完了: Action={action_type.value}, "
            f"Reply={decision.reply_required.value}, "
            f"Template={decision.template_type}"
        )

        return decision

    def _determine_action_type(
        self, comment_body: str, context: Dict[str, Any]
    ) -> ActionType:
        """コメント内容から適切なアクションタイプを判定（改良版）"""

        # まず、自動生成・進捗報告コメントを除外（大幅強化）
        auto_generated_patterns = [
            # CodeRabbit自動生成コメント
            r"<!-- This is an auto-generated",
            r"This is an auto-generated.*reply by CodeRab",
            r"auto-generated.*comment.*summari",
            r"Summary by CodeRabbit",
            r"For best results, initiate chat",
            r"> For best results, initiate chat",
            r"🧩 Analysis chain",
            r"🏁 Script executed:",
            r"Actions performed",
            r"Review triggered",
            r"Workflow.*completed",
            # 開発者の進捗報告
            r"## CodeRabbit.*完了報告",
            r"## .*レビューコメント.*対応完了報告",
            r"## .*レビューコメント.*最終対応完了報告",
            r"## CodeRabbitレビューコメント.*報告",
            r"@coderabbitai.*既に解決済み",
            r"@coderabbitai.*レビューコメント対応完了",
            r"@coderabbitai.*指摘された問題.*既に解決済み",
            r"@coderabbitai.*Analysis Results",
            r"@coderabbitai.*現在のブランチ.*コミット情報",
            r"@coderabbitai.*未解決の課題.*改めて確認",
            r"🎯 現在のブランチ.*コミット情報",
            r"After thoroughly examining.*modules",
            r"✅.*完了した修正項目",
            r"✅.*追加修正完了項目",
            r"✅.*最終修正完了項目",
            # やり取り中間コメント
            r"^@coderabbitai review\s*$",
            r"@coderabbitai review$",
            r"^@coderabbitai\s*$",
            # HTML詳細セクション
            r"<details>.*</details>",
            r"^<details>",
        ]

        if any(
            re.search(pattern, comment_body, re.IGNORECASE | re.MULTILINE)
            for pattern in auto_generated_patterns
        ):
            return ActionType.AUTO_GENERATED

        # 開発者の質問・確認コメント
        developer_question_patterns = [
            r"@coderabbitai.*未解決の課題",
            r"@coderabbitai.*確認",
            r"@coderabbitai.*詳細",
            r"どう思いますか",
            r"いかがでしょう",
        ]

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in developer_question_patterns
        ):
            return ActionType.CLARIFY

        # 明確な技術的指摘（CodeRabbitの指摘タイプ）
        technical_issue_patterns = [
            r"_⚠️ Potential issue_",
            r"_🛠️ Refactor suggestion_",
            r"_💡 Verification agent_",
            r"_🔒 Security issue_",
            r"_⚡ Performance issue_",
        ]

        if any(pattern in comment_body for pattern in technical_issue_patterns):
            # 自動判定ロジックの強化
            return self._classify_technical_issue_priority(comment_body)

        # 明らかな間違い指摘
        incorrect_patterns = [
            r"存在しない.*参照",
            r"undefined.*reference",
            r"不正な.*形式",
            r"invalid.*format",
        ]

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in incorrect_patterns
        ):
            return ActionType.INCORRECT

        # 明らかなコード修正提案の検出
        if any(
            marker in comment_body
            for marker in ["```diff", "```suggestion", "+\t", "-\t"]
        ):
            return self._analyze_code_change_impact(comment_body)

        # デフォルト: 対応不要（フィルタリングで残ったものも基本的に対応不要）
        return ActionType.REJECT

    def _classify_technical_issue_priority(self, comment_body: str) -> ActionType:
        """技術的指摘の優先度を自動判定（新機能）"""
        comment_lower = comment_body.lower()

        # 🔴 Critical - 緊急実施
        critical_keywords = [
            # セキュリティ関連
            "security/detect",
            "prototype pollution",
            "command injection",
            "token",
            "credential",
            "secret",
            "ghp_",
            "github_pat",
            "authorization",
            "bearer",
            "セキュリティ",
            "脆弱性",
            # システム破綻
            "null reference",
            "type error",
            "undefined",
            "infinite loop",
            "deadlock",
            "エラー",
            "バグ",
            "破綻",
            # データ整合性
            "constraint violation",
            "transaction",
            "data integrity",
        ]

        if any(keyword in comment_lower for keyword in critical_keywords):
            return ActionType.IMPLEMENT

        # 🟡 Important - 将来対応
        important_keywords = [
            "performance",
            "memory leak",
            "n+1 query",
            "blocking operation",
            "refactor",
            "maintainability",
            "best practice",
            "パフォーマンス",
            "改善",
            "リファクタリング",
        ]

        if any(keyword in comment_lower for keyword in important_keywords):
            return ActionType.FUTURE

        # 🟢 Low - 基本的に対応不要
        style_keywords = [
            "formatting",
            "naming",
            "import order",
            "comment",
            "style",
            "whitespace",
            "スタイル",
            "フォーマット",
        ]

        if any(keyword in comment_lower for keyword in style_keywords):
            return ActionType.REJECT

        # デフォルト: 要確認
        return ActionType.CLARIFY

    def _analyze_code_change_impact(self, comment_body: str) -> ActionType:
        """コード変更の影響度を分析（新機能）"""
        # 変更範囲の分析
        if "```diff" in comment_body:
            lines_changed = comment_body.count("\n+") + comment_body.count("\n-")

            # 大規模変更は将来対応
            if lines_changed > 10:
                return ActionType.FUTURE

            # 小規模変更は即対応
            return ActionType.IMPLEMENT

        # suggestionブロックの場合
        if "```suggestion" in comment_body:
            return ActionType.IMPLEMENT

        return ActionType.CLARIFY

    def generate_reply_message(
        self, decision: ReplyDecision, context: Dict[str, Any] = None
    ) -> Optional[str]:
        """判定結果に基づいて返信メッセージを生成

        Args:
            decision: 返信判定結果
            context: メッセージ生成に必要なコンテキスト

        Returns:
            返信メッセージ（返信不要の場合はNone）
        """
        if decision.reply_required == ReplyRequirement.NOT_REQUIRED:
            return None

        if not decision.template_type:
            return None

        template = self.reply_templates.get(decision.template_type)
        if not template:
            self.logger.warning(
                f"テンプレートが見つかりません: {decision.template_type}"
            )
            return None

        if context is None:
            context = {}

        # テンプレートのプレースホルダーを埋める
        try:
            if decision.template_type == "technical_rejection":
                return template.format(
                    technical_reason=context.get("technical_reason", "技術的制約"),
                    detailed_explanation=context.get(
                        "detailed_explanation", "詳細な技術的説明が必要"
                    ),
                    reference_or_documentation=context.get(
                        "reference", "公式ドキュメント参照"
                    ),
                    alternative_approach=context.get(
                        "alternative_approach", "代替手法なし"
                    ),
                )
            elif decision.template_type == "future_planning":
                return template.format(
                    current_phase=context.get("current_phase", "現在のフェーズ"),
                    future_phase=context.get("future_phase", "将来のフェーズ"),
                    impact_level=context.get("impact_level", "中程度"),
                    effort_estimation=context.get("effort_estimation", "2-4時間"),
                    issue_summary=context.get("issue_summary", "コメント要約"),
                    target_file_and_line=context.get(
                        "target_location", "ファイル:行数"
                    ),
                    implementation_approach=context.get(
                        "implementation_approach", "実装方針"
                    ),
                    priority_level=context.get("priority_level", "中"),
                    prerequisites=context.get("prerequisites", "特になし"),
                    trigger_condition=context.get(
                        "trigger_condition", "フェーズ開始時"
                    ),
                )
            elif decision.template_type == "technical_correction":
                return template.format(
                    specific_reason=context.get("specific_reason", "技術的理由"),
                    issue_with_suggestion=context.get(
                        "issue_with_suggestion", "指摘内容の問題"
                    ),
                    correct_technical_info=context.get(
                        "correct_info", "正しい技術情報"
                    ),
                    technical_evidence=context.get("evidence", "技術的根拠"),
                    documentation_link=context.get("doc_link", "関連ドキュメント"),
                    verification_method=context.get("verification_method", "実証方法"),
                )
            elif decision.template_type == "clarification_request":
                return template.format(
                    clarification_topic=context.get("topic", "この指摘"),
                    specific_question_1=context.get("question_1", "具体的な確認事項1"),
                    specific_question_2=context.get("question_2", "具体的な確認事項2"),
                    specific_question_3=context.get("question_3", "具体的な確認事項3"),
                )
            else:
                return template

        except KeyError as e:
            self.logger.error(f"テンプレート生成エラー: 不足するコンテキスト {e}")
            return template  # プレースホルダーのまま返す

    def analyze_reply_requirements(
        self, comments: List[Dict[str, Any]], context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """複数コメントの返信要件を分析

        Args:
            comments: GitHub APIから取得したコメントリスト
            context: 判定に必要な追加コンテキスト

        Returns:
            返信要件の分析結果
        """
        results = {
            "total_comments": len(comments),
            "reply_required_count": 0,
            "reply_not_required_count": 0,
            "decisions": [],
            "summary_by_action": {
                "implement": 0,
                "reject": 0,
                "future": 0,
                "incorrect": 0,
                "clarify": 0,
            },
            "estimated_total_time": 0,
        }

        for comment in comments:
            decision = self.decide_action_and_reply(comment, context)
            results["decisions"].append(
                {
                    "comment_id": comment.get("id"),
                    "author": comment.get("user", {}).get("login", ""),
                    "decision": decision,
                }
            )

            # 統計更新
            if decision.reply_required == ReplyRequirement.REQUIRED:
                results["reply_required_count"] += 1
            else:
                results["reply_not_required_count"] += 1

            # アクション別統計
            action_key = (
                decision.action.name.lower()
            )  # implement/reject/future/incorrect/clarify
            if action_key in results["summary_by_action"]:
                results["summary_by_action"][action_key] += 1

            results["estimated_total_time"] += decision.estimated_time

        # 返信効率の計算
        reply_rate = (
            (results["reply_required_count"] / len(comments)) * 100 if comments else 0
        )
        results["reply_efficiency"] = {
            "reply_rate": reply_rate,
            "no_reply_rate": 100 - reply_rate,
            "avg_time_per_comment": (
                results["estimated_total_time"] / len(comments) if comments else 0
            ),
        }

        self.logger.info(
            f"返信要件分析完了: "
            f"総コメント数={len(comments)}, "
            f"返信必要={results['reply_required_count']}, "
            f"返信不要={results['reply_not_required_count']}, "
            f"推定時間={results['estimated_total_time']}分"
        )

        return results

    def get_reply_checklist(self, analysis_results: Dict[str, Any]) -> str:
        """返信チェックリストを生成（最適化版）"""

        reply_required_items = [
            decision
            for decision in analysis_results["decisions"]
            if decision["decision"].reply_required == ReplyRequirement.REQUIRED
        ]

        # 超簡潔版チェックリスト
        checklist = f"""
## 📊 返信サマリー
- **返信必要**: {analysis_results['reply_required_count']}件 / 総{analysis_results['total_comments']}件
- **推定時間**: {analysis_results['estimated_total_time']}分
- **並列実行**: 約{max(1, analysis_results['estimated_total_time'] // 5)}分で完了可能

## ⚡ 高速返信コマンド
```bash
# 並列実行で{analysis_results['reply_required_count']}件を高速処理
{{"""

        # 実際のcurlコマンドを簡潔に生成
        for i, item in enumerate(reply_required_items[:5], 1):  # 最大5件まで表示
            decision = item["decision"]
            comment_id = item["comment_id"]

            # 簡潔な返信メッセージ
            if decision.template_type == "technical_rejection":
                body = "@coderabbitai 技術的制約により対応不要。解決済みマーク依頼。"
            elif decision.template_type == "future_planning":
                body = "@coderabbitai 将来対応予定。記憶依頼。解決済みマーク依頼。"
            elif decision.template_type == "clarification_request":
                body = "@coderabbitai 詳細説明を依頼。"
            else:
                body = "@coderabbitai 対応不要と判断。"

            checklist += f"""
  echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers
  curl -X POST -H @/tmp/github_headers -H "Content-Type: application/json" \\
    -d '{{"body": "@coderabbitai {body}"}}' \\
    "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_ID/replies" &
  rm /tmp/github_headers"""

        if len(reply_required_items) > 5:
            checklist += f"\n  # ... 残り{len(reply_required_items) - 5}件も同様に追加"

        checklist += """
  wait
}
```

## 🎯 成功確認
- [ ] 全curlコマンドが成功ステータスを返した
- [ ] GitHub PRページで返信が表示されている
- [ ] CodeRabbitが解決済みマークを実行した

**注意**: OWNER/REPO/PR_NUMBERを実際の値に置換してください。
"""

        return checklist.strip()

    def _generate_parallel_curl_commands(self, reply_required_items: List[Dict]) -> str:
        """並列curl実行用のコマンドリストを生成"""
        commands = []

        for i, item in enumerate(reply_required_items, 1):
            decision = item["decision"]
            comment_id = item["comment_id"]

            # テンプレートに基づく返信内容を生成
            template_name = decision.template_type or "general"

            if template_name == "technical_rejection":
                reply_body = "@coderabbitai この指摘は技術的制約により対応不要です。\\n\\n問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "future_planning":
                reply_body = "@coderabbitai 技術的に妥当ですが現在のフェーズでは対象外です。\\n\\n将来対応と判断して問題なければ、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "technical_correction":
                reply_body = "@coderabbitai この指摘は技術的に間違いと判断します。\\n\\n指摘が間違いと確認できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "clarification_request":
                reply_body = "@coderabbitai 詳細説明をお願いします。より適切な対応を検討いたします。"
            else:
                reply_body = f"@coderabbitai コメント#{comment_id}への返信"

            # curlコマンドを生成
            curl_cmd = f'echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers && curl -X POST -H @/tmp/github_headers -H "Content-Type: application/json" -d \'{{"body": "@coderabbitai {reply_body}"}}\' "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments/{comment_id}/replies" && rm /tmp/github_headers'
            commands.append(f"# 返信 #{i} (コメント#{comment_id})")
            commands.append(curl_cmd)
            commands.append("")

        return "\\n".join(commands)

    def _generate_parallel_background_commands(
        self, reply_required_items: List[Dict]
    ) -> str:
        """並列バックグラウンド実行用のコマンドを生成"""
        commands = []

        for i, item in enumerate(reply_required_items, 1):
            decision = item["decision"]
            comment_id = item["comment_id"]

            # テンプレートに基づく返信内容を生成
            template_name = decision.template_type or "general"

            if template_name == "technical_rejection":
                reply_body = "@coderabbitai この指摘は技術的制約により対応不要です。\\n\\n問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "future_planning":
                reply_body = "@coderabbitai 技術的に妥当ですが現在のフェーズでは対象外です。\\n\\n将来対応と判断して問題なければ、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "technical_correction":
                reply_body = "@coderabbitai この指摘は技術的に間違いと判断します。\\n\\n指摘が間違いと確認できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：\\n\\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\\n[/CR_RESOLUTION_CONFIRMED]"
            elif template_name == "clarification_request":
                reply_body = "@coderabbitai 詳細説明をお願いします。より適切な対応を検討いたします。"
            else:
                reply_body = f"@coderabbitai コメント#{comment_id}への返信"

            # バックグラウンド実行用のcurlコマンドを生成
            curl_cmd = f'  echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers_{comment_id} && curl -X POST -H @/tmp/github_headers_{comment_id} -H "Content-Type: application/json" -d \'{{"body": "@coderabbitai {reply_body}"}}\' "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments/{comment_id}/replies" && rm /tmp/github_headers_{comment_id} &'
            commands.append(f"  # 返信 #{i} (コメント#{comment_id}) - {template_name}")
            commands.append(curl_cmd)

        return "\\n".join(commands)


def create_reply_decision_matrix() -> ReplyDecisionMatrix:
    """返信判定マトリックスのファクトリー関数"""
    return ReplyDecisionMatrix()


# 使用例とテスト用のサンプルデータ
if __name__ == "__main__":
    # テスト用のサンプルコメント
    sample_comments = [
        {
            "id": 1,
            "user": {"login": "coderabbitai[bot]"},
            "body": "_⚠️ Potential issue_\n\nセキュリティ上の問題があります。パスワードがハードコードされています。",
            "created_at": "2025-01-24T10:00:00Z",
        },
        {
            "id": 2,
            "user": {"login": "coderabbitai[bot]"},
            "body": "_🛠️ Refactor suggestion_\n\nコードの可読性向上のため、リファクタリングを推奨します。",
            "created_at": "2025-01-24T10:01:00Z",
        },
        {
            "id": 3,
            "user": {"login": "coderabbitai[bot]"},
            "body": "_💡 Verification agent_\n\n存在しないリソース参照があります。確認してください。",
            "created_at": "2025-01-24T10:02:00Z",
        },
    ]

    # 返信判定実行
    matrix = create_reply_decision_matrix()

    context = {"current_phase": "mvp", "future_phase": "quality_improvement"}

    analysis = matrix.analyze_reply_requirements(sample_comments, context)

    print("=== 返信判定マトリックス テスト結果 ===")
    print(f"総コメント数: {analysis['total_comments']}")
    print(f"返信必要: {analysis['reply_required_count']}")
    print(f"返信不要: {analysis['reply_not_required_count']}")
    print(f"推定時間: {analysis['estimated_total_time']}分")

    print("\n=== 個別判定結果 ===")
    for decision_info in analysis["decisions"]:
        decision = decision_info["decision"]
        print(
            f"コメント#{decision_info['comment_id']}: {decision.action.value} -> 返信{decision.reply_required.value}"
        )

    print("\n=== 返信チェックリスト ===")
    print(matrix.get_reply_checklist(analysis))
