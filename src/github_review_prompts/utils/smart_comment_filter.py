"""スマートコメントフィルタリングシステム

コメントの性質を分析して、タスク化すべきかどうかを判定する。
不要なノイズを除去し、実際に対応が必要なコメントのみを抽出する。
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CommentType(Enum):
    """コメントタイプの分類"""

    ACTIONABLE = "actionable"  # 対応が必要な技術的指摘
    INFORMATIONAL = "informational"  # 情報提供のみ
    AUTO_GENERATED = "auto_generated"  # 自動生成コメント
    PROGRESS_REPORT = "progress_report"  # 進捗報告
    DISCUSSION = "discussion"  # 議論・質問
    RESOLVED = "resolved"  # 解決済み


class FilterReason(Enum):
    """フィルタリング理由"""

    AUTO_GENERATED = "自動生成・情報提供コメント"
    PROGRESS_REPORT = "進捗報告・サマリー情報"
    SHORT_COMMENT = "短文・簡易コメント"
    RESOLVED_DISCUSSION = "解決済み議論"
    INFORMATIONAL_ONLY = "情報提供のみ"
    TECHNICAL_ISSUE = "技術的指摘・修正提案"
    NEEDS_REVIEW = "要検討コメント"


class SmartCommentFilter:
    """コメントのタスク化適性を判定するフィルター"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 除外パターン（タスク化不要）
        self.exclusion_patterns = [
            # CodeRabbit自動生成コメント（強化版）
            r"<!-- This is an auto-generated",
            r"This is an auto-generated.*reply by CodeRab",
            r"auto-generated.*comment.*summari",
            r"✅ Actions performed",
            r"Summary by CodeRabbit",
            r"## Summary by CodeRabbit",
            r"For best results, initiate chat",
            r"> For best results, initiate chat",
            r"Note: CodeRabbit is an incremental review",
            r"🧩 Analysis chain",
            r"🏁 Script executed:",
            r"Review triggered\.",
            r"Actions performed",
            r"Workflow.*completed",
            r"^<!-- This is an auto-generated comment: summari",
            r"^## Summary by CodeRabbit",
            r"^> For best results",
            # ユーザーコマンド・指示（強化版）
            r"^@coderabbitai review\s*$",
            r"^@coderabbitai\s*$",
            r"^@coderabbitai$",
            r"@coderabbitai review$",
            # 開発者の作業報告・進捗報告（大幅強化）
            r"## CodeRabbit.*完了報告",
            r"## .*レビューコメント.*対応完了報告",
            r"## .*レビューコメント.*最終対応完了報告",
            r"## CodeRabbitレビューコメント.*報告",
            r"@coderabbitai.*指摘された問題.*既に解決済み",
            r"@coderabbitai.*レビューコメント対応完了報告",
            r"@coderabbitai.*Analysis Results",
            r"@coderabbitai.*現在のブランチ.*コミット情報",
            r"@coderabbitai.*未解決の課題.*改めて確認",
            r"🎯 現在のブランチ.*コミット情報",
            r"After thoroughly examining.*modules",
            # 具体的なパターン（実際の出力から）
            r"指摘された問題の大部分は既に解決済みです",
            r"## CodeRabbitレビューコメント追加対応完了報告",
            r"## CodeRabbitレビューコメント最終対応完了報告",
            r"@coderabbitai\s+Analysis Results",
            r"@coderabbitai\s+🎯 現在のブランチ",
            r"@coderabbitai\s+未解決の課題を改めて確認",
            r"@coderabbitai\s+レビューコメント対応完了報告",
            # HTML詳細セクション（強化版）
            r"<details>.*</details>",
            r"^<details>",
            r"<!-- This is an auto-generated reply by CodeRab",
            r"auto-generated comment: summari",
            # 検証スクリプトのみのコメント
            r"#!/bin/bash\n# 参照有無の確認\nrg -nP",
            r"検証スクリプト.*:\n```shell\n#!/bin/bash",
            r"^_💡 Verification agent_\n\n\*\*検証スクリプト\*\*:",
            # 情報提供・確認完了コメント（強化版）
            r"✅.*完了した修正項目",
            r"✅.*追加修正完了項目",
            r"✅.*最終修正完了項目",
            r"指摘された問題の大部分は既に解決済み",
            r"🔴 緊急修正.*完了",
            r"### ✅ 追加修正完了項目",
            r"### ✅ 最終修正完了項目",
        ]

        # 情報提供のみパターン（タスク化不要）
        self.info_only_patterns = [
            r"^## Summary",
            r"^### ✅ 完了した修正項目",
            r"^## CodeRabbit.*完了報告",
            r"^## .*レビューコメント.*対応完了報告",
            r"^### 📊 対応サマリー",
            r"^### 🎯 未対応項目",
            r"検証スクリプトの実行結果を報告します",
            r"バージョン統一に関する指摘について確認しました",
        ]

        # 技術的指摘パターン（タスク化必要） - より厳格な基準
        self.actionable_patterns = [
            # CodeRabbit技術的指摘（明確な指摘タイプのみ）
            r"_⚠️ Potential issue_",
            r"_🛠️ Refactor suggestion_",
            r"_💡 Verification agent_",
            r"_🔒 Security issue_",
            r"_⚡ Performance issue_",
            # 具体的な修正提案
            r"```diff",
            r"```suggestion",
            # 重要度の高い問題のみ（より限定的）
            r"セキュリティ上の問題",
            r"脆弱性",
            r"構文エラー",
            r"参照エラー",
            r"undefined.*reference",
            r"存在しない.*参照",
        ]

        # 解決済みマーカー
        self.resolved_markers = [
            r"CR_RESOLUTION_CONFIRMED",
            r"✅ エンジニアによる技術的検証完了",
            r"問題ないと判断.*解決済みにマーク",
            r"将来対応と判断.*解決済みにマーク",
            r"指摘が間違い.*解決済みにマーク",
            r"修正完了",
            r"対応済み",
            r"解決しました",
            r"Fixed, thanks!",
            r"Addressed in commits?",
        ]

    def should_create_task(
        self, comment: Dict[str, Any]
    ) -> Tuple[bool, FilterReason, CommentType]:
        """コメントをタスク化すべきかを判定

        Args:
            comment: GitHub APIから取得したコメント情報

        Returns:
            Tuple[タスク化すべきか, 理由, コメントタイプ]
        """
        comment_body = comment.get("body", "")
        comment_id = comment.get("id", "unknown")
        author = comment.get("user", {}).get("login", "")

        self.logger.debug(f"コメント分析開始: ID={comment_id}, Author={author}")

        # 1. 除外パターンチェック（強化）
        for pattern in self.exclusion_patterns:
            if re.search(
                pattern, comment_body, re.IGNORECASE | re.MULTILINE | re.DOTALL
            ):
                self.logger.debug(f"除外パターンマッチ: {pattern}")
                return False, FilterReason.AUTO_GENERATED, CommentType.AUTO_GENERATED

        # 2. 情報提供のみパターンチェック
        for pattern in self.info_only_patterns:
            if re.search(pattern, comment_body, re.MULTILINE):
                self.logger.debug(f"情報提供パターンマッチ: {pattern}")
                return False, FilterReason.PROGRESS_REPORT, CommentType.PROGRESS_REPORT

        # 3. 解決済みマーカーチェック
        for marker in self.resolved_markers:
            if re.search(marker, comment_body, re.IGNORECASE):
                self.logger.debug(f"解決済みマーカー検出: {marker}")
                return False, FilterReason.RESOLVED_DISCUSSION, CommentType.RESOLVED

        # 4. CodeRabbitコメントの判定（botありとbotなし両方を対象）
        if author in ["coderabbitai[bot]", "coderabbitai"]:
            # CodeRabbitコメント（outside diff commentsは"coderabbitai"で来る）
            self.logger.debug(f"CodeRabbitコメント分析: {author}")
            return self._analyze_coderabbit_comment(comment_body)

        # 5. 開発者コメントの詳細分析
        # CodeRabbit以外の作者のコメントを分析
        self.logger.debug(f"開発者コメント分析: {author}")
        return self._analyze_developer_comment(comment_body)

        # 6. 短いコメントの判定
        clean_body = re.sub(r"<[^>]+>", "", comment_body)  # HTMLタグ除去
        clean_body = re.sub(
            r"```[^`]*```", "", clean_body, flags=re.DOTALL
        )  # コードブロック除去
        clean_body = clean_body.strip()
        if len(clean_body) < 50:
            self.logger.debug(f"短文コメント: {len(clean_body)}文字")
            return False, FilterReason.SHORT_COMMENT, CommentType.INFORMATIONAL

        # デフォルト: 除外（厳格化）
        self.logger.debug("デフォルト判定: 除外")
        return False, FilterReason.INFORMATIONAL_ONLY, CommentType.INFORMATIONAL

    def _analyze_coderabbit_comment(
        self, comment_body: str
    ) -> Tuple[bool, FilterReason, CommentType]:
        """CodeRabbitコメントの詳細分析（厳格版）"""

        # 明確な技術的指摘タイプのみタスク化
        technical_indicators = [
            "_⚠️ Potential issue_",
            "_🛠️ Refactor suggestion_",
            "_💡 Verification agent_",
            "_🔒 Security issue_",
            "_⚡ Performance issue_",
        ]

        if any(indicator in comment_body for indicator in technical_indicators):
            # さらに、実際に具体的な問題や修正提案があるかチェック
            # ただし、Verification agentの検証スクリプトは除外
            if (
                "検証スクリプト" in comment_body
                or "rg -nP" in comment_body
                or "#!/bin/bash" in comment_body
            ):
                return False, FilterReason.AUTO_GENERATED, CommentType.AUTO_GENERATED

            # 技術的指摘マーカーがある場合はactionable
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # コードブロックや修正提案があるコメントをactionableとする
        code_indicators = [
            "```diff", "```suggestion", "```typescript", "```javascript", "```python",
            "```json", "```yaml", "```yml", "```bash", "```sh"
        ]
        
        if any(indicator in comment_body for indicator in code_indicators):
            self.logger.debug(f"コード関連マーカーを検出")
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE
        
        # コメントの長さでフィルタリング（非常に実質的なコメントのみ）
        clean_body = re.sub(r"<[^>]+>", "", comment_body)  # HTMLタグ除去
        clean_body = clean_body.strip()
        if len(clean_body) > 200:  # 200文字以上の実質的なコメント
            self.logger.debug(f"実質的な長いコメントをactionableと判定: {len(clean_body)}文字")
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # 以下は全て除外
        exclusion_indicators = [
            "🧩 Analysis chain",
            "🏁 Script executed:",
            "Summary by CodeRabbit",
            "For best results",
            "> For best results",
            "検証スクリプト",
            "分析結果",
            "<!-- This is an auto-generated",
            "This is an auto-generated",
            "auto-generated comment: summari",
            "auto-generated.*reply by CodeRab",
            "Review triggered",
            "Actions performed",
            "Note: CodeRabbit is an incremental",
        ]

        if any(indicator in comment_body for indicator in exclusion_indicators):
            return False, FilterReason.AUTO_GENERATED, CommentType.AUTO_GENERATED

        # デフォルト: 技術的指摘マーカーがないCodeRabbitコメントは除外
        # Outside diff commentsでも明確な技術的指摘がないものは情報提供レベル
        self.logger.debug(f"CodeRabbitコメント除外: 明確な技術的指摘マーカーなし")
        return False, FilterReason.INFORMATIONAL_ONLY, CommentType.INFORMATIONAL

    def _analyze_developer_comment(
        self, comment_body: str
    ) -> Tuple[bool, FilterReason, CommentType]:
        """開発者コメントの詳細分析（厳格版）"""

        # 開発者コメントは基本的に除外（99%が進捗報告・やり取り）
        # 進捗報告・完了報告パターン
        progress_indicators = [
            "@coderabbitai",  # CodeRabbitへの指示・質問
            "完了報告",
            "対応完了",
            "修正完了",
            "実装済み",
            "解決済み",
            "確認しました",
            "対応しました",
            "指摘された問題",
            "既に解決済み",
            "Analysis Results",
            "現在のブランチ",
            "コミット情報",
            "未解決の課題",
            "改めて確認",
        ]

        if any(indicator in comment_body for indicator in progress_indicators):
            return False, FilterReason.PROGRESS_REPORT, CommentType.PROGRESS_REPORT

        # 質問・確認・議論パターン（基本的に除外）
        discussion_indicators = [
            "？",
            "?",
            "質問",
            "確認",
            "どう思いますか",
            "意見",
            "提案",
            "検討",
            "相談",
            "どうでしょう",
            "いかがでしょう",
        ]

        if any(indicator in comment_body for indicator in discussion_indicators):
            return False, FilterReason.INFORMATIONAL_ONLY, CommentType.DISCUSSION

        # 短いコメントは除外
        clean_body = comment_body.strip()
        if len(clean_body) < 100:  # 開発者コメントは100文字未満は基本除外
            return False, FilterReason.SHORT_COMMENT, CommentType.INFORMATIONAL

        # 例外的に残すのは、明確な新しい技術的問題の報告のみ
        critical_new_issue_indicators = [
            "新たな問題を発見",
            "重要なバグを発見",
            "セキュリティ問題を発見",
            "クリティカルな問題",
        ]

        if any(
            indicator in comment_body for indicator in critical_new_issue_indicators
        ):
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # デフォルト: 開発者コメントは除外（厳格化）
        return False, FilterReason.PROGRESS_REPORT, CommentType.PROGRESS_REPORT

    def filter_comments(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """コメントリストをフィルタリング

        Args:
            comments: GitHub APIから取得したコメントリスト

        Returns:
            フィルタリング結果の詳細情報
        """
        results = {
            "total_comments": len(comments),
            "actionable_comments": [],
            "filtered_out": [],
            "statistics": {
                "actionable": 0,
                "auto_generated": 0,
                "progress_report": 0,
                "informational": 0,
                "resolved": 0,
                "short_comment": 0,
            },
        }

        for comment in comments:
            should_task, reason, comment_type = self.should_create_task(comment)

            comment_info = {
                "id": comment.get("id"),
                "author": comment.get("user", {}).get("login", ""),
                "created_at": comment.get("created_at"),
                "body_preview": (
                    comment.get("body", "")[:100] + "..."
                    if len(comment.get("body", "")) > 100
                    else comment.get("body", "")
                ),
                "reason": reason.value,
                "type": comment_type.value,
            }

            if should_task:
                results["actionable_comments"].append(comment)
                results["statistics"]["actionable"] += 1
            else:
                results["filtered_out"].append(comment_info)
                # 統計更新
                if comment_type == CommentType.AUTO_GENERATED:
                    results["statistics"]["auto_generated"] += 1
                elif comment_type == CommentType.PROGRESS_REPORT:
                    results["statistics"]["progress_report"] += 1
                elif comment_type == CommentType.INFORMATIONAL:
                    results["statistics"]["informational"] += 1
                elif comment_type == CommentType.RESOLVED:
                    results["statistics"]["resolved"] += 1

                if reason == FilterReason.SHORT_COMMENT:
                    results["statistics"]["short_comment"] += 1

        # フィルタリング効果をログ出力
        filtered_count = len(results["filtered_out"])
        actionable_count = len(results["actionable_comments"])
        filter_rate = (filtered_count / len(comments)) * 100 if comments else 0

        self.logger.info(
            f"スマートフィルタリング完了: "
            f"総コメント数={len(comments)}, "
            f"対応必要={actionable_count}, "
            f"フィルタ除外={filtered_count} ({filter_rate:.1f}%)"
        )

        return results

    def get_filter_summary(self, filter_results: Dict[str, Any]) -> str:
        """フィルタリング結果のサマリーを生成"""
        stats = filter_results["statistics"]
        total = filter_results["total_comments"]
        actionable = stats["actionable"]

        summary = f"""
## 📊 スマートフィルタリング結果

### 全体統計
- **総コメント数**: {total}件
- **対応必要**: {actionable}件 ({(actionable/total*100 if total else 0):.1f}%)
- **フィルタ除外**: {total-actionable}件 ({(((total-actionable)/total*100) if total else 0):.1f}%)

### 除外理由別内訳
- 🤖 **自動生成**: {stats['auto_generated']}件
- 📊 **進捗報告**: {stats['progress_report']}件
- 💬 **情報提供**: {stats['informational']}件
- ✅ **解決済み**: {stats['resolved']}件
- 📝 **短文**: {stats['short_comment']}件

### 🎯 効果
- **ノイズ削減**: {(((total-actionable)/total*100) if total else 0):.1f}%のノイズを除去
- **作業効率**: 実際に対応が必要なコメントのみに集中可能
"""
        return summary.strip()


def create_smart_filter() -> SmartCommentFilter:
    """スマートフィルターのファクトリー関数"""
    return SmartCommentFilter()


# 使用例とテスト用のサンプルデータ
if __name__ == "__main__":
    # テスト用のサンプルコメント
    sample_comments = [
        {
            "id": 1,
            "user": {"login": "coderabbitai[bot]"},
            "body": "<!-- This is an auto-generated reply by CodeRabbit -->\n✅ Actions performed\n\nReview triggered.",
            "created_at": "2025-01-24T10:00:00Z",
        },
        {
            "id": 2,
            "user": {"login": "coderabbitai[bot]"},
            "body": '_⚠️ Potential issue_\n\nセキュリティ上の問題があります。パスワードがハードコードされています。環境変数を使用してください。\n\n```diff\n-var password = "123"\n+var password = process.env.PASSWORD\n```\n\nこの修正により、セキュリティが向上し、設定の柔軟性が増します。',
            "created_at": "2025-01-24T10:01:00Z",
        },
        {
            "id": 3,
            "user": {"login": "developer"},
            "body": "修正完了しました。ご確認ください。",
            "created_at": "2025-01-24T10:02:00Z",
        },
    ]

    # フィルター実行
    filter_instance = create_smart_filter()
    results = filter_instance.filter_comments(sample_comments)

    print("=== テスト結果 ===")
    print(f"総コメント数: {results['total_comments']}")
    print(f"対応必要: {len(results['actionable_comments'])}")
    print(f"フィルタ除外: {len(results['filtered_out'])}")

    print("\n=== 対応必要なコメント ===")
    for comment in results["actionable_comments"]:
        print(f"ID: {comment['id']}, Author: {comment['user']['login']}")

    print("\n=== フィルタ除外されたコメント ===")
    for comment in results["filtered_out"]:
        print(f"ID: {comment['id']}, Reason: {comment['reason']}")
