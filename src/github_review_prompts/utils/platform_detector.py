"""プラットフォーム制限の自動検出ユーティリティ"""

import logging
import re
from typing import List, Dict, Optional, Any, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class PlatformLimitationDetector:
    """プラットフォーム制限の自動検出クラス"""

    # GitHub プラットフォーム制限の検出パターン
    PLATFORM_LIMITATION_PATTERNS = {
        "outside_diff_range": {
            "patterns": [
                re.compile(
                    r"outside the diff.*?can\'t be posted inline",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(r"platform limitations", re.IGNORECASE),
                re.compile(r"⚠️ Outside diff range comments", re.IGNORECASE),
            ],
            "severity": "high",
            "description": "diff範囲外のためインライン表示不可",
        },
        "large_file_limitation": {
            "patterns": [
                re.compile(r"file is too large.*?to display", re.IGNORECASE),
                re.compile(r"large files.*?not shown", re.IGNORECASE),
            ],
            "severity": "medium",
            "description": "ファイルサイズが大きすぎて表示不可",
        },
        "binary_file_limitation": {
            "patterns": [
                re.compile(r"binary file.*?not shown", re.IGNORECASE),
                re.compile(r"cannot display.*?binary", re.IGNORECASE),
            ],
            "severity": "medium",
            "description": "バイナリファイルのため表示不可",
        },
        "generated_file_limitation": {
            "patterns": [
                re.compile(r"generated file.*?not shown", re.IGNORECASE),
                re.compile(r"automatically generated", re.IGNORECASE),
            ],
            "severity": "low",
            "description": "自動生成ファイルのため表示制限",
        },
        "line_limit_exceeded": {
            "patterns": [
                re.compile(r"too many lines.*?truncated", re.IGNORECASE),
                re.compile(r"file truncated.*?lines", re.IGNORECASE),
            ],
            "severity": "medium",
            "description": "行数制限により切り詰められた表示",
        },
    }

    # CodeRabbit特有の制限パターン
    CODERABBIT_LIMITATION_PATTERNS = {
        "review_thread_limit": {
            "patterns": [
                re.compile(r"review thread.*?limit", re.IGNORECASE),
                re.compile(r"too many comments.*?thread", re.IGNORECASE),
            ],
            "severity": "medium",
            "description": "レビュースレッドの制限",
        },
        "api_rate_limit": {
            "patterns": [
                re.compile(r"rate limit.*?exceeded", re.IGNORECASE),
                re.compile(r"api.*?quota.*?exceeded", re.IGNORECASE),
            ],
            "severity": "high",
            "description": "APIレート制限",
        },
        "analysis_timeout": {
            "patterns": [
                re.compile(r"analysis.*?timeout", re.IGNORECASE),
                re.compile(r"processing.*?time limit", re.IGNORECASE),
            ],
            "severity": "medium",
            "description": "分析処理のタイムアウト",
        },
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_platform_limitations(self, comment_body: str) -> Dict[str, Any]:
        """プラットフォーム制限を検出

        Args:
            comment_body: コメント本文

        Returns:
            検出された制限情報
        """
        limitations = {
            "has_limitations": False,
            "detected_limitations": [],
            "severity_level": "none",
            "impact_assessment": {},
            "workaround_suggestions": [],
            "metadata": {
                "detection_timestamp": datetime.now().isoformat(),
                "patterns_checked": 0,
                "matches_found": 0,
            },
        }

        all_patterns = {
            **self.PLATFORM_LIMITATION_PATTERNS,
            **self.CODERABBIT_LIMITATION_PATTERNS,
        }
        patterns_checked = 0
        matches_found = 0

        for limitation_type, limitation_info in all_patterns.items():
            patterns_checked += len(limitation_info["patterns"])

            for pattern in limitation_info["patterns"]:
                if pattern.search(comment_body):
                    matches_found += 1
                    limitations["has_limitations"] = True

                    detected_limitation = {
                        "type": limitation_type,
                        "severity": limitation_info["severity"],
                        "description": limitation_info["description"],
                        "detected_text": self._extract_matched_text(
                            pattern, comment_body
                        ),
                        "workarounds": self._get_workarounds(limitation_type),
                    }

                    limitations["detected_limitations"].append(detected_limitation)

                    # 最高の重要度を記録
                    if self._compare_severity(
                        limitation_info["severity"], limitations["severity_level"]
                    ):
                        limitations["severity_level"] = limitation_info["severity"]

        # 影響評価
        if limitations["has_limitations"]:
            limitations["impact_assessment"] = self._assess_impact(
                limitations["detected_limitations"]
            )
            limitations["workaround_suggestions"] = (
                self._generate_workaround_suggestions(
                    limitations["detected_limitations"]
                )
            )

        limitations["metadata"]["patterns_checked"] = patterns_checked
        limitations["metadata"]["matches_found"] = matches_found

        return limitations

    def analyze_comment_accessibility(
        self, comments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """コメントのアクセシビリティを分析

        Args:
            comments: コメントのリスト

        Returns:
            アクセシビリティ分析結果
        """
        analysis = {
            "total_comments": len(comments),
            "accessible_comments": 0,
            "limited_comments": 0,
            "inaccessible_comments": 0,
            "limitation_breakdown": {},
            "accessibility_score": 0.0,
            "recommendations": [],
        }

        limitation_counts = {}

        for comment in comments:
            comment_body = comment.get("body", "")
            limitations = self.detect_platform_limitations(comment_body)

            if not limitations["has_limitations"]:
                analysis["accessible_comments"] += 1
            else:
                has_high_severity = any(
                    lim["severity"] == "high"
                    for lim in limitations["detected_limitations"]
                )

                if has_high_severity:
                    analysis["inaccessible_comments"] += 1
                else:
                    analysis["limited_comments"] += 1

                # 制限タイプの集計
                for limitation in limitations["detected_limitations"]:
                    lim_type = limitation["type"]
                    if lim_type not in limitation_counts:
                        limitation_counts[lim_type] = 0
                    limitation_counts[lim_type] += 1

        analysis["limitation_breakdown"] = limitation_counts

        # アクセシビリティスコアの計算
        if analysis["total_comments"] > 0:
            accessible_weight = 1.0
            limited_weight = 0.5
            inaccessible_weight = 0.0

            weighted_score = (
                analysis["accessible_comments"] * accessible_weight
                + analysis["limited_comments"] * limited_weight
                + analysis["inaccessible_comments"] * inaccessible_weight
            )

            analysis["accessibility_score"] = round(
                (weighted_score / analysis["total_comments"]) * 100, 2
            )

        # 推奨事項の生成
        analysis["recommendations"] = self._generate_accessibility_recommendations(
            analysis
        )

        return analysis

    def _extract_matched_text(self, pattern: re.Pattern, text: str) -> str:
        """マッチしたテキストを抽出

        Args:
            pattern: 正規表現パターン
            text: 対象テキスト

        Returns:
            マッチしたテキスト
        """
        match = pattern.search(text)
        if match:
            # マッチした部分の前後50文字を含めて返す
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            return text[start:end].strip()
        return ""

    def _compare_severity(self, new_severity: str, current_severity: str) -> bool:
        """重要度を比較

        Args:
            new_severity: 新しい重要度
            current_severity: 現在の重要度

        Returns:
            新しい重要度の方が高い場合True
        """
        severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        return severity_order.get(new_severity, 0) > severity_order.get(
            current_severity, 0
        )

    def _get_workarounds(self, limitation_type: str) -> List[str]:
        """制限タイプに応じた回避策を取得

        Args:
            limitation_type: 制限タイプ

        Returns:
            回避策のリスト
        """
        workarounds = {
            "outside_diff_range": [
                "ファイル全体を直接確認して該当箇所を特定",
                "git diffコマンドで変更範囲を確認",
                "IDEの差分表示機能を使用",
            ],
            "large_file_limitation": [
                "ファイルをローカルにダウンロードして確認",
                "部分的な表示機能を使用",
                "ファイルを分割して確認",
            ],
            "binary_file_limitation": [
                "バイナリファイル用のビューアーを使用",
                "ファイルの種類に応じた専用ツールで確認",
                "ハッシュ値での変更確認",
            ],
            "generated_file_limitation": [
                "生成元のソースファイルを確認",
                "ビルドプロセスの確認",
                "自動生成の設定確認",
            ],
            "line_limit_exceeded": [
                "ファイルの部分的な確認",
                "ローカル環境での全体確認",
                "重要な部分のみを抽出して確認",
            ],
            "review_thread_limit": [
                "コメントを複数のスレッドに分割",
                "重要度に応じた優先順位付け",
                "別のレビューツールの併用",
            ],
            "api_rate_limit": [
                "リクエスト間隔の調整",
                "バッチ処理の実装",
                "キャッシュ機能の活用",
            ],
            "analysis_timeout": [
                "ファイルサイズの削減",
                "分析対象の絞り込み",
                "タイムアウト時間の調整",
            ],
        }

        return workarounds.get(limitation_type, ["該当する回避策が見つかりません"])

    def _assess_impact(
        self, detected_limitations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """制限の影響を評価

        Args:
            detected_limitations: 検出された制限のリスト

        Returns:
            影響評価結果
        """
        impact = {
            "overall_impact": "low",
            "affected_workflows": [],
            "user_experience_impact": "minimal",
            "development_impact": "minimal",
            "risk_factors": [],
        }

        high_severity_count = sum(
            1 for lim in detected_limitations if lim["severity"] == "high"
        )
        medium_severity_count = sum(
            1 for lim in detected_limitations if lim["severity"] == "medium"
        )

        # 全体的な影響レベルの決定
        if high_severity_count > 0:
            impact["overall_impact"] = "high"
            impact["user_experience_impact"] = "significant"
            impact["development_impact"] = "significant"
        elif medium_severity_count > 2:
            impact["overall_impact"] = "medium"
            impact["user_experience_impact"] = "moderate"
            impact["development_impact"] = "moderate"

        # 影響を受けるワークフローの特定
        workflow_impacts = {
            "outside_diff_range": "コードレビューワークフロー",
            "large_file_limitation": "ファイル確認ワークフロー",
            "api_rate_limit": "API統合ワークフロー",
            "analysis_timeout": "自動分析ワークフロー",
        }

        for limitation in detected_limitations:
            workflow = workflow_impacts.get(limitation["type"])
            if workflow and workflow not in impact["affected_workflows"]:
                impact["affected_workflows"].append(workflow)

        # リスク要因の特定
        if high_severity_count > 0:
            impact["risk_factors"].append("重要な情報へのアクセス制限")
        if medium_severity_count > 1:
            impact["risk_factors"].append("複数の制限による累積的影響")

        return impact

    def _generate_workaround_suggestions(
        self, detected_limitations: List[Dict[str, Any]]
    ) -> List[str]:
        """回避策の提案を生成

        Args:
            detected_limitations: 検出された制限のリスト

        Returns:
            回避策提案のリスト
        """
        suggestions = []

        # 高優先度の制限に対する提案
        high_priority_limitations = [
            lim for lim in detected_limitations if lim["severity"] == "high"
        ]

        if high_priority_limitations:
            suggestions.append(
                "🚨 高優先度の制限が検出されました。以下の対応を推奨します："
            )
            for limitation in high_priority_limitations:
                suggestions.extend(
                    [
                        f"  - {workaround}"
                        for workaround in limitation["workarounds"][:2]
                    ]
                )

        # 一般的な提案
        if len(detected_limitations) > 1:
            suggestions.append(
                "📋 複数の制限が検出されています。段階的なアプローチを推奨します。"
            )

        # 範囲外コメント特有の提案
        outside_diff_limitations = [
            lim for lim in detected_limitations if lim["type"] == "outside_diff_range"
        ]
        if outside_diff_limitations:
            suggestions.append(
                "📍 範囲外コメントについては、ファイル全体の確認と手動での位置特定が必要です。"
            )

        return suggestions

    def _generate_accessibility_recommendations(
        self, analysis: Dict[str, Any]
    ) -> List[str]:
        """アクセシビリティ改善の推奨事項を生成

        Args:
            analysis: アクセシビリティ分析結果

        Returns:
            推奨事項のリスト
        """
        recommendations = []

        accessibility_score = analysis["accessibility_score"]

        if accessibility_score < 50:
            recommendations.append(
                "🚨 アクセシビリティスコアが低いです。重要な制限への対応が必要です。"
            )
        elif accessibility_score < 80:
            recommendations.append("⚠️ アクセシビリティに改善の余地があります。")
        else:
            recommendations.append("✅ アクセシビリティは良好です。")

        # 制限タイプ別の推奨事項
        limitation_breakdown = analysis["limitation_breakdown"]

        if "outside_diff_range" in limitation_breakdown:
            count = limitation_breakdown["outside_diff_range"]
            recommendations.append(
                f"📍 {count}件の範囲外コメントがあります。特別な対応手順が必要です。"
            )

        if "api_rate_limit" in limitation_breakdown:
            recommendations.append(
                "⏱️ APIレート制限が検出されています。リクエスト頻度の調整を検討してください。"
            )

        if analysis["inaccessible_comments"] > 0:
            recommendations.append(
                f'🔒 {analysis["inaccessible_comments"]}件のコメントがアクセス不可です。代替手段での確認が必要です。'
            )

        return recommendations
