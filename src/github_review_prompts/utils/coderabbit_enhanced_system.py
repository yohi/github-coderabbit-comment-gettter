"""CodeRabbitアドバイスに基づく統合システム"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from .enhanced_config import EnhancedConfigManager
from .priority_classifier import EnhancedPriorityClassifier
from .rate_limit_handler import GitHubRateLimitHandler
from .database_tracker import DatabaseProgressTracker
from .enhanced_github_manager import EnhancedGitHubIssueManager
from .outside_diff_parser import OutsideDiffParser
from .resolution_master import ResolutionMasterController

logger = logging.getLogger(__name__)


class CodeRabbitEnhancedSystem:
    """CodeRabbitアドバイスに基づく統合システム"""

    def __init__(
        self, config_path: Optional[str] = None, environment: Optional[str] = None
    ):
        """
        Args:
            config_path: 設定ファイルパス
            environment: 環境名 (development, staging, production)
        """
        self.logger = logging.getLogger(__name__)

        try:
            # 1. 設定管理システム
            self.config_manager = EnhancedConfigManager(config_path, environment)
            self.config = self.config_manager.config

            # 2. データベース進捗追跡システム
            self.db_tracker = DatabaseProgressTracker()

            # 3. 優先度分類システム
            self.priority_classifier = EnhancedPriorityClassifier()

            # 4. GitHub Issue管理システム
            self.github_manager = EnhancedGitHubIssueManager(
                self.config_manager, self.db_tracker
            )

            # 5. 範囲外コメント解析システム
            self.outside_diff_parser = OutsideDiffParser()

            # 6. 解決状態追跡システム
            self.resolution_master = ResolutionMasterController(
                project_root=".", github_token=self.config.github.token
            )

            self.logger.info("CodeRabbit統合システム初期化完了")

        except Exception as e:
            self.logger.error(f"システム初期化エラー: {e}")
            raise

    def process_coderabbit_review(
        self, pr_number: int, pr_url: str, comment_body: str
    ) -> Dict[str, Any]:
        """CodeRabbitレビューコメントを包括的に処理

        Args:
            pr_number: プルリクエスト番号
            pr_url: プルリクエストURL
            comment_body: CodeRabbitのコメント本文

        Returns:
            処理結果の詳細情報
        """
        try:
            self.logger.info(f"CodeRabbitレビュー処理開始: PR#{pr_number}")

            # 1. 範囲外コメントの解析
            outside_comments = self.outside_diff_parser.parse_outside_diff_comments(
                comment_body
            )

            if not outside_comments:
                return {
                    "success": True,
                    "message": "範囲外コメントは見つかりませんでした",
                    "outside_comments_count": 0,
                    "processed_at": datetime.now().isoformat(),
                }

            # 2. 優先度分類
            classified_comments = []
            for comment in outside_comments:
                classification = self.priority_classifier.classify_comment(
                    comment=comment.body,
                    file_path=comment.file_path,
                    line_number=self._parse_line_number(comment.line_range),
                    comment_metadata={
                        "category": (
                            comment.category.value if comment.category else "actionable"
                        )
                    },
                )

                classified_comments.append(
                    {"comment": comment, "classification": classification}
                )

            # 3. データベースへの記録
            tracked_comments = []
            for item in classified_comments:
                comment = item["comment"]
                classification = item["classification"]

                comment_id = self.db_tracker.track_comment(
                    pr_number=pr_number,
                    pr_url=pr_url,
                    file_path=comment.file_path,
                    line_number=self._parse_line_number(comment.line_range),
                    comment_body=comment.body,
                    priority=classification["priority"].value,
                    category=(
                        comment.category.value if comment.category else "actionable"
                    ),
                    severity=comment.severity.value if comment.severity else "warning",
                    estimated_hours=classification.get("estimated_effort", {}).get(
                        "estimated_hours", 2.0
                    ),
                )

                tracked_comments.append(
                    {
                        "comment_id": comment_id,
                        "comment": comment,
                        "classification": classification,
                    }
                )

            # 4. Issue自動作成
            issue_results = []
            if self.config.processing_rules.auto_create_threshold:
                for item in tracked_comments:
                    comment = item["comment"]
                    classification = item["classification"]

                    comment_data = {
                        "pr_number": pr_number,
                        "pr_url": pr_url,
                        "file_path": comment.file_path,
                        "line_number": self._parse_line_number(comment.line_range),
                        "comment_body": comment.body,
                        "priority": classification["priority"].value,
                        "category": (
                            comment.category.value if comment.category else "actionable"
                        ),
                        "severity": (
                            comment.severity.value if comment.severity else "warning"
                        ),
                        "estimated_hours": classification.get(
                            "estimated_effort", {}
                        ).get("estimated_hours", 2.0),
                    }

                    issue_result = self.github_manager.create_issue_if_not_exists(
                        comment_data
                    )
                    issue_results.append(issue_result)

            # 5. 進捗スナップショット記録
            self.db_tracker.record_progress_snapshot(pr_number)

            # 6. 結果サマリー生成
            result_summary = self._generate_processing_summary(
                outside_comments, classified_comments, tracked_comments, issue_results
            )

            self.logger.info(
                f"CodeRabbitレビュー処理完了: PR#{pr_number}, {len(outside_comments)}件処理"
            )

            return result_summary

        except Exception as e:
            self.logger.error(f"CodeRabbitレビュー処理エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed_at": datetime.now().isoformat(),
            }

    def _parse_line_number(self, line_range: str) -> Optional[int]:
        """行範囲から行番号を抽出"""
        try:
            if "-" in line_range:
                start_line = line_range.split("-")[0]
                return int(start_line)
            else:
                return int(line_range)
        except (ValueError, AttributeError):
            return None

    def _generate_processing_summary(
        self,
        outside_comments: List,
        classified_comments: List,
        tracked_comments: List,
        issue_results: List,
    ) -> Dict[str, Any]:
        """処理サマリーを生成"""

        # 優先度別統計
        priority_stats = {}
        for item in classified_comments:
            priority = item["classification"]["priority"].value
            priority_stats[priority] = priority_stats.get(priority, 0) + 1

        # Issue作成統計
        issue_stats = {
            "created": sum(1 for r in issue_results if r.action_taken == "created"),
            "updated": sum(1 for r in issue_results if r.action_taken == "updated"),
            "skipped": sum(1 for r in issue_results if r.action_taken == "skipped"),
            "errors": sum(1 for r in issue_results if r.action_taken == "error"),
        }

        # 推定工数
        total_estimated_hours = sum(
            item["classification"].get("estimated_effort", {}).get("estimated_hours", 0)
            for item in classified_comments
        )

        return {
            "success": True,
            "outside_comments_count": len(outside_comments),
            "classified_comments_count": len(classified_comments),
            "tracked_comments_count": len(tracked_comments),
            "priority_distribution": priority_stats,
            "issue_creation_stats": issue_stats,
            "total_estimated_hours": total_estimated_hours,
            "estimated_days": round(total_estimated_hours / 8, 1),
            "processing_recommendations": self._generate_processing_recommendations(
                priority_stats, total_estimated_hours
            ),
            "processed_at": datetime.now().isoformat(),
        }

    def _generate_processing_recommendations(
        self, priority_stats: Dict[str, int], total_hours: float
    ) -> List[str]:
        """処理推奨事項を生成"""
        recommendations = []

        # 緊急対応
        critical_count = priority_stats.get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"🚨 {critical_count}件のクリティカルな問題があります - 即座に対応してください"
            )

        # 高優先度
        high_count = priority_stats.get("high", 0)
        if high_count > 5:
            recommendations.append(
                f"⚠️ {high_count}件の高優先度問題があります - 24時間以内の対応を推奨します"
            )

        # 工数に基づく推奨
        if total_hours > 40:
            recommendations.append(
                "⏰ 大規模な作業量です - チーム分担を検討してください"
            )
        elif total_hours > 16:
            recommendations.append(
                "📅 中規模の作業量です - スプリント計画に含めてください"
            )

        # 自動化推奨
        total_comments = sum(priority_stats.values())
        if total_comments > 20:
            recommendations.append(
                "🤖 大量のコメントです - バッチ処理や自動化を検討してください"
            )

        return recommendations

    def generate_enhanced_prompt(self, pr_number: int, pr_url: str = "") -> str:
        """強化されたプロンプトを生成"""
        try:
            # データベースからコメントを取得
            comments = self.db_tracker.get_comments_by_pr(pr_number)

            if not comments:
                return "このPRには追跡対象のコメントがありません。"

            # 未解決コメントのみを抽出
            from .database_tracker import CommentStatus

            unresolved_comments = [
                c
                for c in comments
                if c.status in [CommentStatus.PENDING, CommentStatus.IN_PROGRESS]
            ]

            if not unresolved_comments:
                return "🎉 このPRのすべてのコメントが解決済みです！"

            # 進捗統計を取得
            progress_stats = self.db_tracker.get_progress_stats(pr_number)

            # プロンプト生成
            prompt_parts = []

            # ヘッダー
            prompt_parts.append("# 🚨 CodeRabbit統合レビュー対応プロンプト")
            prompt_parts.append("")

            # 進捗サマリー
            prompt_parts.append("## 📊 進捗サマリー")
            prompt_parts.append(f"- **総コメント数**: {progress_stats.total_comments}")
            prompt_parts.append(f"- **解決済み**: {progress_stats.resolved_comments}")
            prompt_parts.append(f"- **未解決**: {len(unresolved_comments)}")
            prompt_parts.append(f"- **完了率**: {progress_stats.completion_rate:.1f}%")
            prompt_parts.append(
                f"- **推定残り時間**: {progress_stats.total_estimated_hours:.1f}時間"
            )
            prompt_parts.append("")

            # 未解決コメント
            prompt_parts.append("## 🎯 対応が必要なコメント")
            prompt_parts.append("")

            # 優先度順にソート
            sorted_comments = sorted(
                unresolved_comments,
                key=lambda c: (
                    (
                        0
                        if c.priority == "critical"
                        else (
                            1
                            if c.priority == "high"
                            else 2 if c.priority == "medium" else 3
                        )
                    ),
                    c.created_at,
                ),
            )

            for i, comment in enumerate(sorted_comments, 1):
                priority_emoji = {
                    "critical": "🚨",
                    "high": "⚠️",
                    "medium": "📋",
                    "low": "📝",
                }.get(comment.priority, "📋")

                prompt_parts.append(
                    f"### {priority_emoji} TODO #{i}: {comment.file_path}"
                )
                prompt_parts.append(f"**優先度**: {comment.priority}")
                prompt_parts.append(f"**カテゴリ**: {comment.category}")
                prompt_parts.append(f"**推定時間**: {comment.estimated_hours}時間")
                if comment.line_number:
                    prompt_parts.append(f"**行番号**: {comment.line_number}")
                prompt_parts.append("")
                prompt_parts.append("**問題内容**:")
                prompt_parts.append(
                    comment.comment_body[:500]
                    + ("..." if len(comment.comment_body) > 500 else "")
                )
                prompt_parts.append("")
                prompt_parts.append("---")
                prompt_parts.append("")

            # フッター
            prompt_parts.append("## 📝 対応完了時の報告")
            prompt_parts.append(
                "各コメントの対応完了時は、以下の形式で報告してください："
            )
            prompt_parts.append("")
            prompt_parts.append("```")
            prompt_parts.append("✅ TODO #X 対応完了")
            prompt_parts.append("- ファイル: [ファイル名]")
            prompt_parts.append("- 対応方法: [具体的な対応内容]")
            prompt_parts.append("- 実際の作業時間: [時間]")
            prompt_parts.append("```")

            return "\n".join(prompt_parts)

        except Exception as e:
            self.logger.error(f"強化プロンプト生成エラー: {e}")
            return f"プロンプト生成中にエラーが発生しました: {e}"

    def update_comment_resolution(
        self,
        comment_id: int,
        resolved: bool,
        method: str = "manual",
        actual_hours: Optional[float] = None,
        notes: str = "",
    ) -> bool:
        """コメントの解決状態を更新"""
        try:
            from .database_tracker import CommentStatus, ResolutionMethod

            status = CommentStatus.RESOLVED if resolved else CommentStatus.PENDING
            resolution_method = ResolutionMethod(method) if method else None

            return self.db_tracker.update_comment_status(
                comment_id=comment_id,
                status=status,
                resolution_method=resolution_method,
                actual_hours=actual_hours,
                notes=notes,
            )

        except Exception as e:
            self.logger.error(f"コメント解決状態更新エラー: {e}")
            return False

    def generate_comprehensive_report(
        self, pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """包括的なレポートを生成"""
        try:
            # 進捗統計
            progress_stats = self.db_tracker.get_progress_stats(pr_number)

            # 優先度分類レポート
            comments = (
                self.db_tracker.get_comments_by_pr(pr_number) if pr_number else []
            )
            classifications = []
            for comment in comments:
                classifications.append(
                    {
                        "priority": comment.priority,
                        "security_risk": "none",  # 簡略化
                        "estimated_effort": {
                            "estimated_hours": comment.estimated_hours
                        },
                    }
                )

            priority_report = self.priority_classifier.generate_priority_report(
                classifications
            )

            # GitHub Issue統計
            issue_stats = self.github_manager.generate_creation_report([])  # 簡略化

            # 速度トレンド
            velocity_trend = []
            if pr_number:
                velocity_trend = self.db_tracker.get_velocity_trend(pr_number)

            return {
                "report_type": "comprehensive",
                "pr_number": pr_number,
                "generated_at": datetime.now().isoformat(),
                "progress_statistics": {
                    "total_comments": progress_stats.total_comments,
                    "resolved_comments": progress_stats.resolved_comments,
                    "completion_rate": progress_stats.completion_rate,
                    "average_resolution_time": progress_stats.average_resolution_time,
                    "efficiency_ratio": progress_stats.efficiency_ratio,
                },
                "priority_analysis": priority_report,
                "github_integration": issue_stats,
                "velocity_trend": velocity_trend,
                "system_recommendations": self._generate_system_recommendations(
                    progress_stats, priority_report
                ),
            }

        except Exception as e:
            self.logger.error(f"包括的レポート生成エラー: {e}")
            return {"error": str(e)}

    def _generate_system_recommendations(
        self, progress_stats, priority_report
    ) -> List[str]:
        """システム推奨事項を生成"""
        recommendations = []

        # 完了率に基づく推奨
        if progress_stats.completion_rate < 50:
            recommendations.append(
                "📈 完了率が低いです - 作業の優先順位を見直してください"
            )
        elif progress_stats.completion_rate > 90:
            recommendations.append("🎯 完了率が高いです - 残りの作業を完了させましょう")

        # 効率性に基づく推奨
        if progress_stats.efficiency_ratio and progress_stats.efficiency_ratio < 0.8:
            recommendations.append(
                "⏱️ 作業効率が予想より低いです - プロセスの見直しを検討してください"
            )

        # 優先度分布に基づく推奨
        if priority_report.get("total_comments", 0) > 50:
            recommendations.append(
                "📊 大量のコメントがあります - 自動化ツールの活用を検討してください"
            )

        return recommendations

    def cleanup_and_maintenance(self, days: int = 30) -> Dict[str, Any]:
        """システムのクリーンアップとメンテナンス"""
        try:
            # データベースクリーンアップ
            db_cleaned = self.db_tracker.cleanup_old_data(days)

            # 解決状態追跡システムのクリーンアップ
            resolution_cleaned = self.resolution_master.cleanup_old_data(days)

            return {
                "cleanup_completed": True,
                "database_records_cleaned": db_cleaned,
                "resolution_records_cleaned": resolution_cleaned.get(
                    "storage_records_cleaned", 0
                ),
                "cleanup_date": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"クリーンアップエラー: {e}")
            return {"error": str(e)}

    def get_system_status(self) -> Dict[str, Any]:
        """システム状態を取得"""
        try:
            # データベース情報
            db_info = self.db_tracker.get_database_info()

            # 設定サマリー
            config_summary = self.config_manager.get_config_summary()

            # GitHub API制限状況
            rate_limit_status = {}
            if (
                hasattr(self.github_manager, "rate_limiter")
                and self.github_manager.rate_limiter
            ):
                rate_limit_status = (
                    self.github_manager.rate_limiter.get_rate_limit_status()
                )

            return {
                "system_status": "operational",
                "database_info": db_info,
                "configuration": config_summary,
                "github_rate_limits": rate_limit_status,
                "features_enabled": {
                    "priority_classification": True,
                    "database_tracking": True,
                    "github_integration": bool(self.config.github.token),
                    "issue_auto_creation": bool(
                        self.config.processing_rules.auto_create_threshold
                    ),
                    "duplicate_detection": self.config.processing_rules.enable_duplicate_detection,
                    "security_analysis": self.config.processing_rules.enable_security_analysis,
                    "terraform_analysis": self.config.processing_rules.enable_terraform_analysis,
                },
                "status_checked_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"システム状態取得エラー: {e}")
            return {
                "system_status": "error",
                "error": str(e),
                "status_checked_at": datetime.now().isoformat(),
            }
