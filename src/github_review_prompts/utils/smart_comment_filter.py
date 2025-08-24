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
            # CodeRabbit自動生成
            r"<!-- This is an auto-generated",
            r"✅ Actions performed",
            r"Summary by CodeRabbit",
            r"For best results, initiate chat",
            r"Note: CodeRabbit is an incremental review",
            r"🧩 Analysis chain",
            r"🏁 Script executed:",
            # ユーザーコマンド
            r"^@coderabbitai review\s*$",
            r"^@coderabbitai\s*$",
            # 処理完了通知
            r"Review triggered\.",
            r"Actions performed",
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

        # 技術的指摘パターン（タスク化必要）
        self.actionable_patterns = [
            # CodeRabbit指摘タイプ
            r"_⚠️ Potential issue_",
            r"_🛠️ Refactor suggestion_",
            r"_💡 Verification agent_",
            r"_🔒 Security issue_",
            r"_⚡ Performance issue_",
            # 修正提案
            r"```diff",
            r"```suggestion",
            # 重要キーワード
            r"セキュリティ",
            r"パフォーマンス",
            r"バグ",
            r"エラー",
            r"脆弱性",
            r"修正",
            r"改善",
            # 英語キーワード
            r"\bsecurity\b",
            r"\bperformance\b",
            r"\bbug\b",
            r"\berror\b",
            r"\bvulnerability\b",
            r"\bfix\b",
            r"\bimprove\b",
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

        # 1. 除外パターンチェック
        for pattern in self.exclusion_patterns:
            if re.search(pattern, comment_body, re.IGNORECASE | re.MULTILINE):
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

        # 4. 技術的指摘パターンチェック（優先）
        for pattern in self.actionable_patterns:
            if re.search(pattern, comment_body, re.IGNORECASE):
                self.logger.debug(f"技術的指摘パターンマッチ: {pattern}")
                return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # 5. 短いコメントの判定（最後に実行）
        clean_body = re.sub(r"<[^>]+>", "", comment_body)  # HTMLタグ除去
        clean_body = re.sub(
            r"```[^`]*```", "", clean_body, flags=re.DOTALL
        )  # コードブロック除去
        clean_body = clean_body.strip()
        if len(clean_body) < 50:
            self.logger.debug(f"短文コメント: {len(clean_body)}文字")
            return False, FilterReason.SHORT_COMMENT, CommentType.INFORMATIONAL

        # 6. CodeRabbitボットの詳細分析
        if author == "coderabbitai[bot]":
            return self._analyze_coderabbit_comment(comment_body)

        # 7. 開発者コメントの分析
        if author != "coderabbitai[bot]":
            return self._analyze_developer_comment(comment_body)

        # デフォルト: 要検討として扱う
        self.logger.debug("デフォルト判定: 要検討コメント")
        return True, FilterReason.NEEDS_REVIEW, CommentType.DISCUSSION

    def _analyze_coderabbit_comment(
        self, comment_body: str
    ) -> Tuple[bool, FilterReason, CommentType]:
        """CodeRabbitコメントの詳細分析"""

        # CodeRabbitの指摘タイプを分析
        if any(
            pattern in comment_body
            for pattern in [
                "_⚠️ Potential issue_",
                "_🛠️ Refactor suggestion_",
                "_💡 Verification agent_",
                "_🔒 Security issue_",
                "_⚡ Performance issue_",
            ]
        ):
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # 検証スクリプトや分析結果
        if any(
            pattern in comment_body
            for pattern in [
                "🧩 Analysis chain",
                "🏁 Script executed:",
                "検証スクリプト",
                "分析結果",
            ]
        ):
            return False, FilterReason.INFORMATIONAL_ONLY, CommentType.INFORMATIONAL

        # 具体的な修正提案があるか
        if "```diff" in comment_body or "```suggestion" in comment_body:
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # その他のCodeRabbitコメントは情報提供として扱う
        return False, FilterReason.INFORMATIONAL_ONLY, CommentType.INFORMATIONAL

    def _analyze_developer_comment(
        self, comment_body: str
    ) -> Tuple[bool, FilterReason, CommentType]:
        """開発者コメントの詳細分析"""

        # 進捗報告パターン
        progress_indicators = [
            "完了報告",
            "対応完了",
            "修正完了",
            "実装済み",
            "解決済み",
            "確認しました",
            "対応しました",
        ]

        if any(indicator in comment_body for indicator in progress_indicators):
            return False, FilterReason.PROGRESS_REPORT, CommentType.PROGRESS_REPORT

        # 質問・議論パターン
        question_indicators = [
            "？",
            "?",
            "質問",
            "確認",
            "どう思いますか",
            "意見",
            "提案",
        ]

        if any(indicator in comment_body for indicator in question_indicators):
            return True, FilterReason.NEEDS_REVIEW, CommentType.DISCUSSION

        # 技術的な指摘・提案
        technical_indicators = [
            "問題",
            "バグ",
            "エラー",
            "修正",
            "改善",
            "最適化",
            "リファクタリング",
        ]

        if any(indicator in comment_body for indicator in technical_indicators):
            return True, FilterReason.TECHNICAL_ISSUE, CommentType.ACTIONABLE

        # デフォルトは議論として扱う
        return True, FilterReason.NEEDS_REVIEW, CommentType.DISCUSSION

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
- **ノイズ削減**: {((total-actionable)/total*100):.1f}%のノイズを除去
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
