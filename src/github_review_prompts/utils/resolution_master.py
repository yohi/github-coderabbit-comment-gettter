"""範囲外コメント解決システムのマスターコントローラー"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from ..models import OutsideDiffComment
from .resolution_detector import OutsideDiffResolutionDetector
from .resolution_storage import HierarchicalResolutionStorage
from .ai_response_analyzer import AIResponseAnalyzer
from .enhanced_github_manager import EnhancedGitHubIssueManager
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class ResolutionMasterController:
    """範囲外コメント解決システムの統合コントローラー"""

    def __init__(
        self,
        project_root: str,
        github_token: Optional[str] = None,
        storage_config: Optional[Dict] = None,
    ):
        """
        Args:
            project_root: プロジェクトルートディレクトリ
            github_token: GitHub API トークン
            storage_config: ストレージ設定
        """
        self.project_root = Path(project_root)
        self.github_token = github_token
        self.logger = logging.getLogger(__name__)

        # コンポーネント初期化
        try:
            # ストレージシステム
            self.storage = HierarchicalResolutionStorage(
                project_root=str(self.project_root), config=storage_config or {}
            )

            # 解決検出器
            self.detector = OutsideDiffResolutionDetector()

            # AI応答解析器
            self.ai_analyzer = AIResponseAnalyzer()

            # GitHub統合マネージャー
            self.github_manager = (
                EnhancedGitHubIssueManager(github_token=github_token)
                if github_token
                else None
            )

            # 進捗追跡器
            self.progress_tracker = ProgressTracker(self.storage)

            self.logger.info("ResolutionMasterController 初期化完了")

        except Exception as e:
            self.logger.error(f"ResolutionMasterController 初期化エラー: {e}")
            raise

    def process_comments_with_resolution_tracking(
        self,
        comments: List[OutsideDiffComment],
        pr_url: str = "",
        enable_github_integration: bool = True,
    ) -> Dict[str, Any]:
        """コメントの解決状態追跡付き処理

        Args:
            comments: 範囲外コメントのリスト
            pr_url: プルリクエストURL
            enable_github_integration: GitHub統合を有効にするか

        Returns:
            処理結果の詳細情報
        """
        try:
            self.logger.info(f"解決状態追跡付きコメント処理開始: {len(comments)}件")

            # 1. 既存の解決状態を確認
            resolution_states = {}
            for comment in comments:
                state = self.storage.get_resolution_status(comment.id)
                resolution_states[comment.id] = state
                comment.is_resolved = state.get("is_resolved", False)
                comment.resolution_method = state.get("method")
                comment.resolution_notes = state.get("notes", "")

            # 2. 未解決コメントを抽出
            unresolved_comments = [
                comment
                for comment in comments
                if not resolution_states[comment.id].get("is_resolved", False)
            ]

            # 3. GitHub統合（有効な場合）
            github_insights = {}
            if enable_github_integration and self.github_manager and pr_url:
                try:
                    github_insights = self.github_manager.analyze_pr_resolution_context(
                        pr_url, unresolved_comments
                    )
                except Exception as e:
                    self.logger.warning(f"GitHub統合エラー: {e}")
                    github_insights = {"error": str(e)}

            # 4. 進捗分析
            progress_report = self.progress_tracker.generate_progress_report(
                comments, include_detailed_analysis=True
            )

            # 5. 推奨アクション生成
            recommended_actions = self._generate_recommended_actions(
                unresolved_comments, progress_report, github_insights
            )

            # 6. 結果をまとめて返す
            result = {
                "total_comments": len(comments),
                "resolved_comments": len(comments) - len(unresolved_comments),
                "unresolved_comments": len(unresolved_comments),
                "resolution_states": resolution_states,
                "progress_report": progress_report,
                "github_insights": github_insights,
                "recommended_actions": recommended_actions,
                "processed_at": datetime.now().isoformat(),
            }

            self.logger.info(
                f"解決状態追跡付きコメント処理完了: {result['resolved_comments']}/{result['total_comments']} 解決済み"
            )
            return result

        except Exception as e:
            self.logger.error(f"解決状態追跡付きコメント処理エラー: {e}")
            return {
                "total_comments": len(comments),
                "resolved_comments": 0,
                "unresolved_comments": len(comments),
                "error": str(e),
                "processed_at": datetime.now().isoformat(),
            }

    def analyze_ai_response_and_update_status(
        self, ai_response: str, comment_ids: List[int]
    ) -> Dict[str, Any]:
        """AI応答を解析して解決状態を更新

        Args:
            ai_response: AIからの応答テキスト
            comment_ids: 対象コメントIDのリスト

        Returns:
            解析・更新結果
        """
        try:
            self.logger.info(f"AI応答解析開始: {len(comment_ids)}件のコメント")

            # AI応答を解析
            analysis_result = self.ai_analyzer.analyze_response(ai_response)

            # 更新結果を記録
            update_results = []

            for comment_id in comment_ids:
                try:
                    # コメント固有の解析
                    comment_analysis = (
                        self.ai_analyzer.analyze_comment_specific_response(
                            ai_response, comment_id
                        )
                    )

                    # 解決状態の判定
                    if comment_analysis.get("is_resolved", False):
                        # 解決済みとしてマーク
                        self.storage.mark_resolved(
                            comment_id=comment_id,
                            method=comment_analysis.get("method", "ai_automated"),
                            notes=comment_analysis.get("summary", ""),
                            metadata={
                                "ai_confidence": comment_analysis.get(
                                    "confidence", 0.0
                                ),
                                "analysis_timestamp": datetime.now().isoformat(),
                                "response_snippet": (
                                    ai_response[:200] + "..."
                                    if len(ai_response) > 200
                                    else ai_response
                                ),
                            },
                        )

                        update_results.append(
                            {
                                "comment_id": comment_id,
                                "status": "resolved",
                                "method": comment_analysis.get("method"),
                                "confidence": comment_analysis.get("confidence", 0.0),
                            }
                        )
                    else:
                        update_results.append(
                            {
                                "comment_id": comment_id,
                                "status": "unresolved",
                                "reason": comment_analysis.get(
                                    "reason", "AI分析で未解決と判定"
                                ),
                            }
                        )

                except Exception as e:
                    self.logger.error(f"コメント{comment_id}の解析エラー: {e}")
                    update_results.append(
                        {"comment_id": comment_id, "status": "error", "error": str(e)}
                    )

            # 全体の統計
            resolved_count = sum(1 for r in update_results if r["status"] == "resolved")
            error_count = sum(1 for r in update_results if r["status"] == "error")

            result = {
                "analysis_summary": analysis_result,
                "update_results": update_results,
                "statistics": {
                    "total_processed": len(comment_ids),
                    "resolved": resolved_count,
                    "unresolved": len(comment_ids) - resolved_count - error_count,
                    "errors": error_count,
                },
                "analyzed_at": datetime.now().isoformat(),
            }

            self.logger.info(
                f"AI応答解析完了: {resolved_count}/{len(comment_ids)} 件解決"
            )
            return result

        except Exception as e:
            self.logger.error(f"AI応答解析エラー: {e}")
            return {"error": str(e), "analyzed_at": datetime.now().isoformat()}

    def generate_enhanced_prompt_with_resolution_context(
        self,
        comments: List[OutsideDiffComment],
        pr_info: Dict,
        include_progress_info: bool = True,
    ) -> str:
        """解決コンテキスト付きの強化プロンプトを生成

        Args:
            comments: 範囲外コメントのリスト
            pr_info: プルリクエスト情報
            include_progress_info: 進捗情報を含むかどうか

        Returns:
            強化されたプロンプトテキスト
        """
        try:
            # 未解決コメントのみを抽出
            unresolved_comments = []
            resolved_summary = []

            for comment in comments:
                resolution_state = self.storage.get_resolution_status(comment.id)
                if resolution_state.get("is_resolved", False):
                    resolved_summary.append(
                        {
                            "id": comment.id,
                            "file": comment.file_path,
                            "method": resolution_state.get("method", "unknown"),
                            "resolved_at": resolution_state.get("resolved_at", ""),
                        }
                    )
                else:
                    unresolved_comments.append(comment)

            # 進捗情報を取得
            progress_info = ""
            if include_progress_info:
                progress_report = self.progress_tracker.generate_progress_report(
                    comments
                )
                progress_info = progress_report.get("summary_text", "")

            # プロンプト構築
            prompt_parts = []

            # ヘッダー
            prompt_parts.append("# 🚨 範囲外コメント対応プロンプト（解決状態追跡付き）")
            prompt_parts.append("")

            # 進捗サマリー
            if progress_info:
                prompt_parts.append("## 📊 現在の進捗状況")
                prompt_parts.append(progress_info)
                prompt_parts.append("")

            # 解決済みコメントサマリー
            if resolved_summary:
                prompt_parts.append("## ✅ 解決済みコメント")
                prompt_parts.append(
                    f"以下の {len(resolved_summary)} 件は既に対応完了済みです："
                )
                prompt_parts.append("")

                for resolved in resolved_summary[:10]:  # 最大10件表示
                    prompt_parts.append(
                        f"- `{resolved['file']}` (ID: {resolved['id']}) - {resolved['method']}"
                    )

                if len(resolved_summary) > 10:
                    prompt_parts.append(f"- ... 他 {len(resolved_summary) - 10} 件")

                prompt_parts.append("")

            # 未解決コメント
            if unresolved_comments:
                prompt_parts.append("## 🎯 対応が必要なコメント")
                prompt_parts.append(
                    f"以下の {len(unresolved_comments)} 件の対応をお願いします："
                )
                prompt_parts.append("")

                # 重要度順にソート
                sorted_comments = sorted(
                    unresolved_comments,
                    key=lambda c: (
                        (
                            0
                            if c.severity and c.severity.value == "caution"
                            else (
                                1 if c.severity and c.severity.value == "warning" else 2
                            )
                        ),
                        (
                            0
                            if c.category and c.category.value == "actionable"
                            else (
                                1
                                if c.category and c.category.value == "duplicate"
                                else 2
                            )
                        ),
                    ),
                )

                for i, comment in enumerate(sorted_comments, 1):
                    severity_emoji = {"caution": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(
                        comment.severity.value if comment.severity else "warning", "⚠️"
                    )

                    category_emoji = {
                        "actionable": "🔴",
                        "duplicate": "🟡",
                        "nitpick": "🟢",
                    }.get(
                        comment.category.value if comment.category else "actionable",
                        "🔴",
                    )

                    prompt_parts.append(
                        f"### {severity_emoji} TODO #{i}: {comment.file_path} (行 {comment.line_range})"
                    )
                    prompt_parts.append(
                        f"**カテゴリ**: {category_emoji} {comment.category.value if comment.category else 'actionable'}"
                    )
                    prompt_parts.append(f"**ID**: {comment.id}")
                    prompt_parts.append("")
                    prompt_parts.append("**問題内容**:")
                    prompt_parts.append(
                        comment.body[:500] + ("..." if len(comment.body) > 500 else "")
                    )
                    prompt_parts.append("")

                    if comment.suggestion_details:
                        prompt_parts.append("**推奨修正**:")
                        prompt_parts.append(
                            comment.suggestion_details[:300]
                            + ("..." if len(comment.suggestion_details) > 300 else "")
                        )
                        prompt_parts.append("")

                    prompt_parts.append("---")
                    prompt_parts.append("")

            # フッター（対応完了時の報告指示）
            prompt_parts.append("## 📝 対応完了時の報告")
            prompt_parts.append(
                "各コメントの対応完了時は、以下の形式で報告してください："
            )
            prompt_parts.append("")
            prompt_parts.append("```")
            prompt_parts.append("✅ TODO #X 対応完了")
            prompt_parts.append("- ファイル: [ファイル名]")
            prompt_parts.append("- 対応方法: [具体的な対応内容]")
            prompt_parts.append("- 変更内容: [主な変更点]")
            prompt_parts.append("```")
            prompt_parts.append("")
            prompt_parts.append(
                "この形式で報告いただくことで、自動的に解決状態が更新されます。"
            )

            return "\n".join(prompt_parts)

        except Exception as e:
            self.logger.error(f"強化プロンプト生成エラー: {e}")
            return f"プロンプト生成中にエラーが発生しました: {e}"

    def _generate_recommended_actions(
        self,
        unresolved_comments: List[OutsideDiffComment],
        progress_report: Dict,
        github_insights: Dict,
    ) -> List[Dict[str, Any]]:
        """推奨アクションを生成"""
        actions = []

        try:
            # 緊急度の高いコメントがある場合
            critical_comments = [
                c
                for c in unresolved_comments
                if c.severity and c.severity.value == "caution"
            ]

            if critical_comments:
                actions.append(
                    {
                        "priority": "high",
                        "action": "immediate_attention",
                        "title": f"🚨 緊急対応が必要 ({len(critical_comments)}件)",
                        "description": "CAUTION レベルのコメントを最優先で対応してください",
                        "comment_ids": [c.id for c in critical_comments],
                    }
                )

            # 大量のコメントがある場合
            if len(unresolved_comments) > 20:
                actions.append(
                    {
                        "priority": "medium",
                        "action": "batch_processing",
                        "title": f"📊 バッチ処理推奨 ({len(unresolved_comments)}件)",
                        "description": "コメント数が多いため、カテゴリ別の段階的対応を推奨します",
                        "estimated_time": progress_report.get(
                            "remaining_work_analysis", {}
                        ).get("estimated_hours", 0),
                    }
                )

            # GitHub統合からの推奨事項
            if github_insights.get("recommendations"):
                for rec in github_insights["recommendations"][:3]:
                    actions.append(
                        {
                            "priority": "medium",
                            "action": "github_integration",
                            "title": f"🔗 GitHub統合推奨",
                            "description": rec,
                            "source": "github_analysis",
                        }
                    )

            # 進捗に基づく推奨事項
            completion_rate = progress_report.get("summary", {}).get(
                "completion_rate", 0
            )
            if completion_rate > 80:
                actions.append(
                    {
                        "priority": "low",
                        "action": "final_review",
                        "title": "🎯 最終レビュー段階",
                        "description": "残り少数のコメントを完了させて100%達成を目指しましょう",
                        "completion_rate": completion_rate,
                    }
                )

            return actions

        except Exception as e:
            self.logger.error(f"推奨アクション生成エラー: {e}")
            return [
                {
                    "priority": "low",
                    "action": "error",
                    "title": "エラー",
                    "description": f"推奨アクション生成中にエラーが発生しました: {e}",
                }
            ]

    def export_comprehensive_report(
        self,
        comments: List[OutsideDiffComment],
        pr_url: str = "",
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """包括的なレポートをエクスポート

        Args:
            comments: 範囲外コメントのリスト
            pr_url: プルリクエストURL
            output_dir: 出力ディレクトリ

        Returns:
            エクスポートされたファイルのパス辞書
        """
        try:
            if output_dir is None:
                output_dir = (
                    self.project_root / ".github-review-resolutions" / "reports"
                )

            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            exported_files = {}

            # 1. 進捗レポート
            progress_file = output_dir / f"progress_report_{timestamp}.json"
            exported_files["progress"] = self.progress_tracker.export_progress_data(
                comments, progress_file
            )

            # 2. 解決状態詳細
            resolution_file = output_dir / f"resolution_states_{timestamp}.json"
            resolution_data = {}
            for comment in comments:
                resolution_data[comment.id] = self.storage.get_resolution_status(
                    comment.id
                )

            with open(resolution_file, "w", encoding="utf-8") as f:
                import json

                json.dump(resolution_data, f, ensure_ascii=False, indent=2)
            exported_files["resolutions"] = resolution_file

            # 3. GitHub統合レポート（可能な場合）
            if self.github_manager and pr_url:
                try:
                    github_file = output_dir / f"github_analysis_{timestamp}.json"
                    github_data = self.github_manager.generate_comprehensive_report(
                        pr_url, comments
                    )

                    with open(github_file, "w", encoding="utf-8") as f:
                        import json

                        json.dump(github_data, f, ensure_ascii=False, indent=2)
                    exported_files["github"] = github_file
                except Exception as e:
                    self.logger.warning(f"GitHub統合レポートエクスポートエラー: {e}")

            self.logger.info(
                f"包括的レポートエクスポート完了: {len(exported_files)}ファイル"
            )
            return exported_files

        except Exception as e:
            self.logger.error(f"包括的レポートエクスポートエラー: {e}")
            return {}

    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """古いデータをクリーンアップ

        Args:
            days: 保持期間（日数）

        Returns:
            クリーンアップ統計
        """
        try:
            # ストレージのクリーンアップ
            storage_cleaned = self.storage.cleanup_old_resolutions(days)

            # レポートファイルのクリーンアップ
            reports_dir = self.project_root / ".github-review-resolutions" / "reports"
            reports_cleaned = 0

            if reports_dir.exists():
                cutoff_date = datetime.now() - timedelta(days=days)
                for file_path in reports_dir.glob("*.json"):
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        file_path.unlink()
                        reports_cleaned += 1

            result = {
                "storage_records_cleaned": storage_cleaned,
                "report_files_cleaned": reports_cleaned,
                "cleanup_date": datetime.now().isoformat(),
            }

            self.logger.info(f"データクリーンアップ完了: {result}")
            return result

        except Exception as e:
            self.logger.error(f"データクリーンアップエラー: {e}")
            return {"error": str(e)}
