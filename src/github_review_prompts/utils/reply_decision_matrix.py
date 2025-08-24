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
        }

        # 返信テンプレート
        self.reply_templates = {
            "technical_rejection": """@coderabbitai この指摘は{technical_reason}により対応不要です。

理由: {detailed_explanation}
根拠: {reference_or_documentation}

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]""",
            "future_planning": """@coderabbitai 技術的に妥当ですが現在の{current_phase}では対象外です。

現在フェーズ: {current_phase}
対応予定: {future_phase}

記憶依頼: {future_phase}開始時に以下を思い出してください
- 課題: {issue_summary}
- 対象: {target_file_and_line}
- 解決案: {implementation_approach}
- 優先度: {priority_level}
- 思い出し条件: {trigger_condition}

将来対応と判断して問題なければ、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]""",
            "technical_correction": """@coderabbitai この指摘は{specific_reason}により間違いと判断します。

正しい技術情報: {correct_technical_info}
根拠: {technical_evidence}
参考: {documentation_link}

指摘が間違いと確認できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
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
        """コメント内容から適切なアクションタイプを判定"""

        # セキュリティ関連の緊急指摘
        security_patterns = [
            r"セキュリティ",
            r"security",
            r"脆弱性",
            r"vulnerability",
            r"トークン",
            r"token",
            r"パスワード",
            r"password",
            r"認証",
            r"authentication",
        ]

        # 明らかな間違い指摘パターン
        incorrect_patterns = [
            r"存在しない.*参照",
            r"undefined.*reference",
            r"不正な.*形式",
            r"invalid.*format",
            r"間違った.*設定",
            r"incorrect.*configuration",
        ]

        # 将来対応パターン
        future_patterns = [
            r"リファクタリング",
            r"refactor",
            r"最適化",
            r"optimization",
            r"改善",
            r"improvement",
            r"ベストプラクティス",
            r"best.*practice",
        ]

        # 要確認パターン
        clarify_patterns = [
            r"確認",
            r"verify",
            r"検証",
            r"validation",
            r"どちらか",
            r"which.*one",
            r"意図",
            r"intention",
        ]

        # 対応不要パターン
        reject_patterns = [
            r"自動生成",
            r"auto.*generated",
            r"情報提供",
            r"information.*only",
            r"参考",
            r"reference.*only",
        ]

        # パターンマッチングによる判定
        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in security_patterns
        ):
            # セキュリティ関連は基本的に実施
            return ActionType.IMPLEMENT

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in incorrect_patterns
        ):
            # 明らかな間違いは指摘間違いとして処理
            return ActionType.INCORRECT

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in reject_patterns
        ):
            # 対応不要パターン
            return ActionType.REJECT

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in future_patterns
        ):
            # 将来対応パターン
            return ActionType.FUTURE

        if any(
            re.search(pattern, comment_body, re.IGNORECASE)
            for pattern in clarify_patterns
        ):
            # 要確認パターン
            return ActionType.CLARIFY

        # コンテキストによる判定
        current_phase = context.get("current_phase", "development")
        if current_phase in ["mvp", "prototype"]:
            # MVP/プロトタイプフェーズでは品質改善は将来対応
            quality_patterns = [r"品質", r"quality", r"保守性", r"maintainability"]
            if any(
                re.search(pattern, comment_body, re.IGNORECASE)
                for pattern in quality_patterns
            ):
                return ActionType.FUTURE

        # デフォルトは実施
        return ActionType.IMPLEMENT

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
                )
            elif decision.template_type == "future_planning":
                return template.format(
                    current_phase=context.get("current_phase", "現在のフェーズ"),
                    future_phase=context.get("future_phase", "将来のフェーズ"),
                    issue_summary=context.get("issue_summary", "コメント要約"),
                    target_file_and_line=context.get(
                        "target_location", "ファイル:行数"
                    ),
                    implementation_approach=context.get(
                        "implementation_approach", "実装方針"
                    ),
                    priority_level=context.get("priority_level", "中"),
                    trigger_condition=context.get(
                        "trigger_condition", "フェーズ開始時"
                    ),
                )
            elif decision.template_type == "technical_correction":
                return template.format(
                    specific_reason=context.get("specific_reason", "技術的理由"),
                    correct_technical_info=context.get(
                        "correct_info", "正しい技術情報"
                    ),
                    technical_evidence=context.get("evidence", "技術的根拠"),
                    documentation_link=context.get("doc_link", "関連ドキュメント"),
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
        """返信チェックリストを生成"""

        reply_required_items = [
            decision
            for decision in analysis_results["decisions"]
            if decision["decision"].reply_required == ReplyRequirement.REQUIRED
        ]

        checklist = f"""
## 🔄 返信漏れ防止チェックリスト

### 📊 返信要件サマリー
- **総コメント数**: {analysis_results['total_comments']}件
- **返信必要**: {analysis_results['reply_required_count']}件
- **返信不要**: {analysis_results['reply_not_required_count']}件
- **推定作業時間**: {analysis_results['estimated_total_time']}分

### ✅ 返信必須項目 ({len(reply_required_items)}件)

"""

        for i, item in enumerate(reply_required_items, 1):
            decision = item["decision"]
            checklist += f"""#### {i}. コメント#{item['comment_id']} - {decision.action.value}
- [ ] **返信実行**: curl コマンドで返信送信
- **テンプレート**: {decision.template_type}
- **推定時間**: {decision.estimated_time}分
- **優先度**: {decision.priority}

"""

        # 並列返信の効率的な実行指示を追加
        if len(reply_required_items) > 1:
            checklist += f"""
### ⚡ 効率的な並列返信実行（推奨）

**{len(reply_required_items)}件の返信を並列で高速処理**:

#### 方法1: バックグラウンド並列実行
```bash
# 全ての返信を並列で実行（推奨）
{{
  curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" \\
    -d '{{"body": "返信内容1", "in_reply_to": コメントID1}}' \\
    "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments" &

  curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" \\
    -d '{{"body": "返信内容2", "in_reply_to": コメントID2}}' \\
    "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments" &

  # 全ての並列処理の完了を待機
  wait
}}
```

#### 方法2: xargs並列実行
```bash
# コマンドリストファイルを作成
cat > reply_commands.txt << 'EOF'
{self._generate_parallel_curl_commands(reply_required_items) if hasattr(self, '_generate_parallel_curl_commands') else '# コマンドリストをここに記載'}
EOF

# 並列実行（最大5並列）
cat reply_commands.txt | grep -v '^#' | xargs -I {{}} -P {min(len(reply_required_items), 5)} bash -c "{{}}"
```

#### 方法3: 実行時間測定付き並列処理
```bash
# 実行時間を測定しながら並列実行
time {{
  # 各返信を並列で実行
{self._generate_parallel_background_commands(reply_required_items) if hasattr(self, '_generate_parallel_background_commands') else '  # 並列コマンドをここに記載'}

  # 全ての並列処理の完了を待機
  wait
  echo "✅ {len(reply_required_items)}件の返信を並列処理で完了"
}}
```

**🎯 効果**:
- 実行時間: 最大{len(reply_required_items)}倍高速化（理論値）
- 同時実行数: 最大5件（GitHub API制限考慮）
- 処理効率: 大幅向上
- 推定短縮時間: {max(1, len(reply_required_items) // 5)}分の{len(reply_required_items)}分 → 約{max(1, len(reply_required_items) // 5)}分

"""

        checklist += f"""
### 🚨 最終確認質問
作業完了前に以下を自問してください：

- [ ] **「❌対応不要」と判定したコメントに返信しましたか？**
- [ ] **「⏳将来対応」と判定したコメントに返信しましたか？**
- [ ] **「⚠️指摘間違い」と判定したコメントに返信しましたか？**
- [ ] **「🤔要確認」と判定したコメントに返信しましたか？**

### 📈 返信効率統計
- **返信率**: {analysis_results['reply_efficiency']['reply_rate']:.1f}%
- **返信不要率**: {analysis_results['reply_efficiency']['no_reply_rate']:.1f}%
- **平均時間/コメント**: {analysis_results['reply_efficiency']['avg_time_per_comment']:.1f}分
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
            curl_cmd = f'curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" -d \'{{"body": "{reply_body}", "in_reply_to": {comment_id}}}\' "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments"'
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
            curl_cmd = f'  curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" -d \'{{"body": "{reply_body}", "in_reply_to": {comment_id}}}\' "https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments" &'
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
