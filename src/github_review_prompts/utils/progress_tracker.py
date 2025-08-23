"""進捗追跡・レポート機能"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
from enum import Enum

from ..models import (
    OutsideDiffComment,
    OutsideDiffCommentCategory,
    OutsideDiffCommentSeverity,
)
from .resolution_detector import ResolutionStatus, ResolutionMethod
from .resolution_storage import HierarchicalResolutionStorage

logger = logging.getLogger(__name__)


class ProgressMetric(Enum):
    """進捗メトリクス"""

    COMPLETION_RATE = "completion_rate"
    RESOLUTION_VELOCITY = "resolution_velocity"
    CATEGORY_DISTRIBUTION = "category_distribution"
    SEVERITY_DISTRIBUTION = "severity_distribution"
    TIME_TO_RESOLUTION = "time_to_resolution"
    RESOLUTION_METHOD_DISTRIBUTION = "resolution_method_distribution"


class ProgressTracker:
    """進捗追跡・レポート生成クラス"""

    def __init__(self, storage: HierarchicalResolutionStorage):
        self.storage = storage
        self.logger = logging.getLogger(__name__)

    def calculate_completion_rate(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """完了率を計算

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            完了率の詳細情報
        """
        try:
            if not comments:
                return {
                    "overall_rate": 0.0,
                    "total_comments": 0,
                    "resolved_comments": 0,
                    "by_category": {},
                    "by_severity": {},
                }

            total_count = len(comments)
            resolved_count = 0
            category_stats = defaultdict(lambda: {"total": 0, "resolved": 0})
            severity_stats = defaultdict(lambda: {"total": 0, "resolved": 0})

            for comment in comments:
                # 解決状態を確認
                resolution_status = self.storage.get_resolution_status(comment.id)
                is_resolved = resolution_status.get("is_resolved", False)

                if is_resolved:
                    resolved_count += 1

                # カテゴリ別統計
                category = comment.category.value if comment.category else "unknown"
                category_stats[category]["total"] += 1
                if is_resolved:
                    category_stats[category]["resolved"] += 1

                # 重要度別統計
                severity = comment.severity.value if comment.severity else "unknown"
                severity_stats[severity]["total"] += 1
                if is_resolved:
                    severity_stats[severity]["resolved"] += 1

            # 完了率計算
            overall_rate = (
                (resolved_count / total_count) * 100 if total_count > 0 else 0.0
            )

            # カテゴリ別完了率
            category_rates = {}
            for category, stats in category_stats.items():
                rate = (
                    (stats["resolved"] / stats["total"]) * 100
                    if stats["total"] > 0
                    else 0.0
                )
                category_rates[category] = {
                    "rate": rate,
                    "resolved": stats["resolved"],
                    "total": stats["total"],
                }

            # 重要度別完了率
            severity_rates = {}
            for severity, stats in severity_stats.items():
                rate = (
                    (stats["resolved"] / stats["total"]) * 100
                    if stats["total"] > 0
                    else 0.0
                )
                severity_rates[severity] = {
                    "rate": rate,
                    "resolved": stats["resolved"],
                    "total": stats["total"],
                }

            return {
                "overall_rate": round(overall_rate, 2),
                "total_comments": total_count,
                "resolved_comments": resolved_count,
                "by_category": category_rates,
                "by_severity": severity_rates,
                "calculated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"完了率計算エラー: {e}")
            return {
                "overall_rate": 0.0,
                "total_comments": 0,
                "resolved_comments": 0,
                "by_category": {},
                "by_severity": {},
                "error": str(e),
            }

    def calculate_resolution_velocity(self, days: int = 7) -> Dict[str, Any]:
        """解決速度を計算

        Args:
            days: 計算対象の日数

        Returns:
            解決速度の詳細情報
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 期間内の解決記録を取得
            resolutions = self.storage.get_resolutions_in_period(start_date, end_date)

            if not resolutions:
                return {
                    "velocity": 0.0,
                    "total_resolutions": 0,
                    "period_days": days,
                    "daily_average": 0.0,
                    "by_method": {},
                    "trend": "stable",
                }

            total_resolutions = len(resolutions)
            daily_average = total_resolutions / days

            # 解決方法別統計
            method_counts = Counter()
            for resolution in resolutions:
                method = resolution.get("method", "unknown")
                method_counts[method] += 1

            method_stats = {}
            for method, count in method_counts.items():
                method_stats[method] = {
                    "count": count,
                    "percentage": round((count / total_resolutions) * 100, 2),
                }

            # トレンド分析（前半と後半の比較）
            mid_date = start_date + timedelta(days=days // 2)
            first_half = [
                r
                for r in resolutions
                if datetime.fromisoformat(r["resolved_at"]) < mid_date
            ]
            second_half = [
                r
                for r in resolutions
                if datetime.fromisoformat(r["resolved_at"]) >= mid_date
            ]

            first_half_rate = len(first_half) / (days // 2)
            second_half_rate = len(second_half) / (days - days // 2)

            if second_half_rate > first_half_rate * 1.1:
                trend = "improving"
            elif second_half_rate < first_half_rate * 0.9:
                trend = "declining"
            else:
                trend = "stable"

            return {
                "velocity": round(daily_average, 2),
                "total_resolutions": total_resolutions,
                "period_days": days,
                "daily_average": round(daily_average, 2),
                "by_method": method_stats,
                "trend": trend,
                "first_half_rate": round(first_half_rate, 2),
                "second_half_rate": round(second_half_rate, 2),
                "calculated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"解決速度計算エラー: {e}")
            return {
                "velocity": 0.0,
                "total_resolutions": 0,
                "period_days": days,
                "daily_average": 0.0,
                "by_method": {},
                "trend": "unknown",
                "error": str(e),
            }

    def estimate_remaining_work(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """残り作業量を推定

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            残り作業量の推定情報
        """
        try:
            # 未解決コメントを抽出
            unresolved_comments = []
            for comment in comments:
                resolution_status = self.storage.get_resolution_status(comment.id)
                if not resolution_status.get("is_resolved", False):
                    unresolved_comments.append(comment)

            if not unresolved_comments:
                return {
                    "remaining_comments": 0,
                    "estimated_hours": 0.0,
                    "estimated_days": 0.0,
                    "by_category": {},
                    "by_severity": {},
                    "recommendations": ["🎉 すべてのコメントが解決済みです！"],
                }

            # 作業時間推定（カテゴリ・重要度別）
            time_estimates = {
                "actionable": {"caution": 4.0, "warning": 2.0, "info": 1.0},
                "duplicate": {"caution": 0.5, "warning": 0.3, "info": 0.2},
                "nitpick": {"caution": 1.0, "warning": 0.5, "info": 0.3},
            }

            total_hours = 0.0
            category_breakdown = defaultdict(lambda: {"count": 0, "hours": 0.0})
            severity_breakdown = defaultdict(lambda: {"count": 0, "hours": 0.0})

            for comment in unresolved_comments:
                category = comment.category.value if comment.category else "actionable"
                severity = comment.severity.value if comment.severity else "warning"

                # 時間推定
                estimated_hours = time_estimates.get(category, {}).get(severity, 2.0)
                total_hours += estimated_hours

                # カテゴリ別集計
                category_breakdown[category]["count"] += 1
                category_breakdown[category]["hours"] += estimated_hours

                # 重要度別集計
                severity_breakdown[severity]["count"] += 1
                severity_breakdown[severity]["hours"] += estimated_hours

            # 作業日数推定（1日8時間として）
            estimated_days = total_hours / 8.0

            # 推奨事項生成
            recommendations = self._generate_work_recommendations(
                unresolved_comments, category_breakdown, severity_breakdown
            )

            return {
                "remaining_comments": len(unresolved_comments),
                "estimated_hours": round(total_hours, 1),
                "estimated_days": round(estimated_days, 1),
                "by_category": dict(category_breakdown),
                "by_severity": dict(severity_breakdown),
                "recommendations": recommendations,
                "calculated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"残り作業量推定エラー: {e}")
            return {
                "remaining_comments": 0,
                "estimated_hours": 0.0,
                "estimated_days": 0.0,
                "by_category": {},
                "by_severity": {},
                "recommendations": ["エラーが発生しました"],
                "error": str(e),
            }

    def generate_progress_report(
        self, comments: List[OutsideDiffComment], include_detailed_analysis: bool = True
    ) -> Dict[str, Any]:
        """総合進捗レポートを生成

        Args:
            comments: 範囲外コメントのリスト
            include_detailed_analysis: 詳細分析を含むかどうか

        Returns:
            総合進捗レポート
        """
        try:
            # 基本統計
            completion_stats = self.calculate_completion_rate(comments)
            velocity_stats = self.calculate_resolution_velocity()
            remaining_work = self.estimate_remaining_work(comments)

            # レポート生成
            report = {
                "summary": {
                    "total_comments": completion_stats["total_comments"],
                    "resolved_comments": completion_stats["resolved_comments"],
                    "completion_rate": completion_stats["overall_rate"],
                    "remaining_comments": remaining_work["remaining_comments"],
                    "estimated_completion_days": remaining_work["estimated_days"],
                },
                "completion_analysis": completion_stats,
                "velocity_analysis": velocity_stats,
                "remaining_work_analysis": remaining_work,
                "generated_at": datetime.now().isoformat(),
            }

            if include_detailed_analysis:
                # 詳細分析を追加
                detailed_analysis = self._generate_detailed_analysis(comments)
                report["detailed_analysis"] = detailed_analysis

            # レポートサマリーテキスト生成
            report["summary_text"] = self._generate_summary_text(report)

            return report

        except Exception as e:
            self.logger.error(f"進捗レポート生成エラー: {e}")
            return {
                "summary": {
                    "total_comments": 0,
                    "resolved_comments": 0,
                    "completion_rate": 0.0,
                    "remaining_comments": 0,
                    "estimated_completion_days": 0.0,
                },
                "error": str(e),
                "generated_at": datetime.now().isoformat(),
            }

    def _generate_work_recommendations(
        self,
        unresolved_comments: List[OutsideDiffComment],
        category_breakdown: Dict,
        severity_breakdown: Dict,
    ) -> List[str]:
        """作業推奨事項を生成"""
        recommendations = []

        # 重要度別推奨事項
        caution_count = severity_breakdown.get("caution", {}).get("count", 0)
        if caution_count > 0:
            recommendations.append(
                f"🚨 CAUTION レベル {caution_count}件を最優先で対応してください"
            )

        # カテゴリ別推奨事項
        actionable_count = category_breakdown.get("actionable", {}).get("count", 0)
        duplicate_count = category_breakdown.get("duplicate", {}).get("count", 0)

        if actionable_count > 10:
            recommendations.append(
                f"⚡ Actionable コメント {actionable_count}件 - バッチ処理を検討してください"
            )

        if duplicate_count > 5:
            recommendations.append(
                f"🔄 重複コメント {duplicate_count}件 - 一括処理で効率化できます"
            )

        # 作業量に応じた推奨事項
        total_count = len(unresolved_comments)
        if total_count > 20:
            recommendations.append("📊 大量のコメント - チーム分担を検討してください")
        elif total_count > 10:
            recommendations.append(
                "📝 中規模のコメント - 優先度順に段階的に対応してください"
            )
        else:
            recommendations.append("✅ 管理可能な量 - 計画的に対応できます")

        return recommendations

    def _generate_detailed_analysis(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """詳細分析を生成"""
        try:
            # ファイル別分析
            file_stats = defaultdict(
                lambda: {"total": 0, "resolved": 0, "categories": defaultdict(int)}
            )

            for comment in comments:
                file_path = comment.file_path
                resolution_status = self.storage.get_resolution_status(comment.id)
                is_resolved = resolution_status.get("is_resolved", False)

                file_stats[file_path]["total"] += 1
                if is_resolved:
                    file_stats[file_path]["resolved"] += 1

                category = comment.category.value if comment.category else "unknown"
                file_stats[file_path]["categories"][category] += 1

            # ファイル別完了率計算
            file_completion_rates = {}
            for file_path, stats in file_stats.items():
                rate = (
                    (stats["resolved"] / stats["total"]) * 100
                    if stats["total"] > 0
                    else 0.0
                )
                file_completion_rates[file_path] = {
                    "completion_rate": round(rate, 2),
                    "total": stats["total"],
                    "resolved": stats["resolved"],
                    "categories": dict(stats["categories"]),
                }

            # 最も問題のあるファイルを特定
            problematic_files = sorted(
                file_completion_rates.items(),
                key=lambda x: (
                    x[1]["total"] - x[1]["resolved"],
                    -x[1]["completion_rate"],
                ),
            )[:5]

            return {
                "file_analysis": file_completion_rates,
                "problematic_files": [
                    {"file": file_path, "stats": stats}
                    for file_path, stats in problematic_files
                ],
                "total_files_affected": len(file_stats),
            }

        except Exception as e:
            self.logger.error(f"詳細分析生成エラー: {e}")
            return {"error": str(e)}

    def _generate_summary_text(self, report: Dict[str, Any]) -> str:
        """レポートサマリーテキストを生成"""
        try:
            summary = report["summary"]
            completion_rate = summary["completion_rate"]
            total = summary["total_comments"]
            resolved = summary["resolved_comments"]
            remaining = summary["remaining_comments"]

            # 進捗状況の評価
            if completion_rate >= 90:
                status_emoji = "🎉"
                status_text = "ほぼ完了"
            elif completion_rate >= 70:
                status_emoji = "🚀"
                status_text = "順調に進行中"
            elif completion_rate >= 50:
                status_emoji = "⚡"
                status_text = "進行中"
            elif completion_rate >= 25:
                status_emoji = "🔄"
                status_text = "開始段階"
            else:
                status_emoji = "📋"
                status_text = "開始前"

            summary_text = f"""
{status_emoji} **範囲外コメント対応状況: {status_text}**

📊 **進捗サマリー**
- 全体進捗: {completion_rate}% ({resolved}/{total} 件完了)
- 残りコメント: {remaining} 件
- 推定完了: {summary.get('estimated_completion_days', 0)} 日

🎯 **次のアクション**
"""

            # 推奨事項を追加
            if "remaining_work_analysis" in report:
                recommendations = report["remaining_work_analysis"].get(
                    "recommendations", []
                )
                for rec in recommendations[:3]:  # 上位3つの推奨事項
                    summary_text += f"- {rec}\n"

            return summary_text.strip()

        except Exception as e:
            self.logger.error(f"サマリーテキスト生成エラー: {e}")
            return "📊 進捗レポート生成中にエラーが発生しました"

    def export_progress_data(
        self, comments: List[OutsideDiffComment], output_path: Optional[Path] = None
    ) -> Path:
        """進捗データをエクスポート

        Args:
            comments: 範囲外コメントのリスト
            output_path: 出力パス（Noneの場合は自動生成）

        Returns:
            エクスポートファイルのパス
        """
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path(f"progress_report_{timestamp}.json")

            # 詳細レポート生成
            report = self.generate_progress_report(
                comments, include_detailed_analysis=True
            )

            # ファイルに保存
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            self.logger.info(f"進捗データをエクスポート: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"進捗データエクスポートエラー: {e}")
            raise
