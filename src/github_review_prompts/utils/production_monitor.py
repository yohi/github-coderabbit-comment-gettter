"""本番環境監視システム

v2.0.0の本番環境での使用状況をリアルタイムで監視し、
問題の早期発見と継続的改善のためのデータを収集する。
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
import queue

logger = logging.getLogger(__name__)


@dataclass
class ProductionAlert:
    """本番環境アラート"""

    timestamp: str
    severity: str  # critical, warning, info
    category: str  # performance, error, usage, quality
    message: str
    details: Dict[str, Any]
    resolved: bool = False


class ProductionMonitor:
    """本番環境監視システム"""

    def __init__(self, enable_monitoring: bool = True):
        self.enable_monitoring = enable_monitoring
        self.logger = logging.getLogger(__name__)

        # 監視データ保存ディレクトリ
        self.monitor_dir = Path.home() / ".github_review_prompts" / "monitoring"
        self.monitor_dir.mkdir(parents=True, exist_ok=True)

        # アラートキュー
        self.alert_queue = queue.Queue()

        # 監視統計
        self.stats = {
            "session_count": 0,
            "total_processing_time": 0.0,
            "total_comments_processed": 0,
            "error_count": 0,
            "performance_issues": 0,
            "quality_issues": 0,
        }

        # パフォーマンス閾値
        self.thresholds = {
            "max_processing_time": 10.0,  # 10秒以上で警告
            "min_filtering_efficiency": 30.0,  # 30%未満で警告
            "max_error_rate": 5.0,  # 5%以上で警告
            "min_reply_accuracy": 70.0,  # 70%未満で警告
        }

        # 監視開始
        if self.enable_monitoring:
            self._start_monitoring()

    def _start_monitoring(self):
        """監視システム開始"""
        self.logger.info("本番環境監視システム開始")

        # アラート処理スレッド
        self.alert_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.alert_thread.start()

    def _process_alerts(self):
        """アラート処理ループ"""
        while True:
            try:
                alert = self.alert_queue.get(timeout=1.0)
                self._handle_alert(alert)
                self.alert_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"アラート処理エラー: {e}")

    def _handle_alert(self, alert: ProductionAlert):
        """アラート処理"""
        # アラートをファイルに保存
        alert_file = (
            self.monitor_dir / f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        try:
            with open(alert_file, "w", encoding="utf-8") as f:
                json.dump(asdict(alert), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"アラート保存失敗: {e}")

        # ログ出力
        if alert.severity == "critical":
            self.logger.critical(f"🚨 CRITICAL: {alert.message}")
        elif alert.severity == "warning":
            self.logger.warning(f"⚠️ WARNING: {alert.message}")
        else:
            self.logger.info(f"ℹ️ INFO: {alert.message}")

    def record_session_start(self, session_info: Dict[str, Any]):
        """セッション開始記録"""
        if not self.enable_monitoring:
            return

        self.stats["session_count"] += 1
        self.logger.debug(f"セッション開始: {session_info}")

    def record_processing_completed(self, processing_stats: Dict[str, Any]):
        """処理完了記録"""
        if not self.enable_monitoring:
            return

        # 統計更新
        processing_time = processing_stats.get("processing_time", 0.0)
        comments_processed = processing_stats.get("total_comments", 0)

        self.stats["total_processing_time"] += processing_time
        self.stats["total_comments_processed"] += comments_processed

        # パフォーマンス監視
        self._check_performance_thresholds(processing_stats)

        # 品質監視
        self._check_quality_thresholds(processing_stats)

    def record_error(self, error_info: Dict[str, Any]):
        """エラー記録"""
        if not self.enable_monitoring:
            return

        self.stats["error_count"] += 1

        # エラー率チェック
        if self.stats["session_count"] > 0:
            error_rate = (self.stats["error_count"] / self.stats["session_count"]) * 100

            if error_rate > self.thresholds["max_error_rate"]:
                alert = ProductionAlert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    severity="critical",
                    category="error",
                    message=f"エラー率が閾値を超過: {error_rate:.1f}%",
                    details={
                        "error_rate": error_rate,
                        "threshold": self.thresholds["max_error_rate"],
                        "error_info": error_info,
                    },
                )
                self.alert_queue.put(alert)

    def _check_performance_thresholds(self, stats: Dict[str, Any]):
        """パフォーマンス閾値チェック"""
        processing_time = stats.get("processing_time", 0.0)

        # 処理時間チェック
        if processing_time > self.thresholds["max_processing_time"]:
            self.stats["performance_issues"] += 1

            alert = ProductionAlert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="warning",
                category="performance",
                message=f"処理時間が閾値を超過: {processing_time:.2f}秒",
                details={
                    "processing_time": processing_time,
                    "threshold": self.thresholds["max_processing_time"],
                    "stats": stats,
                },
            )
            self.alert_queue.put(alert)

        # フィルタリング効率チェック
        total_comments = stats.get("total_comments", 0)
        filtered_comments = stats.get("filtered_comments", 0)

        if total_comments > 0:
            filtering_efficiency = (filtered_comments / total_comments) * 100

            if filtering_efficiency < self.thresholds["min_filtering_efficiency"]:
                alert = ProductionAlert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    severity="warning",
                    category="performance",
                    message=f"フィルタリング効率が低下: {filtering_efficiency:.1f}%",
                    details={
                        "filtering_efficiency": filtering_efficiency,
                        "threshold": self.thresholds["min_filtering_efficiency"],
                        "total_comments": total_comments,
                        "filtered_comments": filtered_comments,
                    },
                )
                self.alert_queue.put(alert)

    def _check_quality_thresholds(self, stats: Dict[str, Any]):
        """品質閾値チェック"""
        replies_required = stats.get("replies_required", 0)
        replies_not_required = stats.get("replies_not_required", 0)

        # 返信判定精度チェック（仮の計算）
        total_replies = replies_required + replies_not_required
        if total_replies > 0:
            # 実際の精度は手動検証が必要だが、ここでは統計的推定
            estimated_accuracy = min(
                95.0, 80.0 + (replies_not_required / total_replies) * 20.0
            )

            if estimated_accuracy < self.thresholds["min_reply_accuracy"]:
                self.stats["quality_issues"] += 1

                alert = ProductionAlert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    severity="warning",
                    category="quality",
                    message=f"返信判定精度が低下の可能性: {estimated_accuracy:.1f}%",
                    details={
                        "estimated_accuracy": estimated_accuracy,
                        "threshold": self.thresholds["min_reply_accuracy"],
                        "replies_required": replies_required,
                        "replies_not_required": replies_not_required,
                    },
                )
                self.alert_queue.put(alert)

    def get_health_status(self) -> Dict[str, Any]:
        """システム健全性ステータス取得"""
        if self.stats["session_count"] == 0:
            return {"status": "no_data", "message": "使用データなし"}

        # 平均処理時間
        avg_processing_time = (
            self.stats["total_processing_time"] / self.stats["session_count"]
        )

        # エラー率
        error_rate = (self.stats["error_count"] / self.stats["session_count"]) * 100

        # 健全性判定
        health_score = 100.0

        # パフォーマンス減点
        if avg_processing_time > self.thresholds["max_processing_time"]:
            health_score -= 20.0

        # エラー率減点
        if error_rate > self.thresholds["max_error_rate"]:
            health_score -= 30.0

        # 品質問題減点
        if self.stats["quality_issues"] > 0:
            health_score -= 15.0

        # ステータス決定
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 60:
            status = "warning"
        else:
            status = "critical"

        return {
            "status": status,
            "health_score": health_score,
            "stats": {
                "session_count": self.stats["session_count"],
                "avg_processing_time": avg_processing_time,
                "error_rate": error_rate,
                "performance_issues": self.stats["performance_issues"],
                "quality_issues": self.stats["quality_issues"],
            },
            "thresholds": self.thresholds,
        }

    def generate_daily_report(self) -> Dict[str, Any]:
        """日次レポート生成"""
        health_status = self.get_health_status()

        report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "version": "2.0.0",
            "health_status": health_status,
            "summary": {
                "total_sessions": self.stats["session_count"],
                "total_comments_processed": self.stats["total_comments_processed"],
                "total_processing_time": self.stats["total_processing_time"],
                "error_count": self.stats["error_count"],
                "performance_issues": self.stats["performance_issues"],
                "quality_issues": self.stats["quality_issues"],
            },
        }

        # レポート保存
        report_file = (
            self.monitor_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.json"
        )

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"日次レポート保存失敗: {e}")

        return report

    def shutdown(self):
        """監視システム終了"""
        if self.enable_monitoring:
            self.logger.info("本番環境監視システム終了")

            # 最終レポート生成
            final_report = self.generate_daily_report()
            self.logger.info(
                f"最終健全性スコア: {final_report['health_status']['health_score']:.1f}"
            )


# グローバル監視インスタンス
_production_monitor = None


def get_production_monitor() -> ProductionMonitor:
    """本番環境監視インスタンス取得"""
    global _production_monitor

    if _production_monitor is None:
        # 環境変数で制御
        enable_monitoring = (
            os.getenv("GRP_PRODUCTION_MONITORING", "true").lower() == "true"
        )
        _production_monitor = ProductionMonitor(enable_monitoring)

    return _production_monitor


# 使用例
if __name__ == "__main__":
    # テスト用の監視システム
    monitor = get_production_monitor()

    print("=== 本番環境監視システムテスト ===")

    # セッション開始
    monitor.record_session_start({"user": "test_user", "pr_url": "test_pr"})

    # 処理完了（正常）
    monitor.record_processing_completed(
        {
            "processing_time": 3.5,
            "total_comments": 50,
            "filtered_comments": 25,
            "replies_required": 5,
            "replies_not_required": 20,
        }
    )

    # 処理完了（パフォーマンス問題）
    monitor.record_processing_completed(
        {
            "processing_time": 12.0,  # 閾値超過
            "total_comments": 100,
            "filtered_comments": 10,  # 効率低下
            "replies_required": 15,
            "replies_not_required": 5,
        }
    )

    # エラー記録
    monitor.record_error(
        {"error_type": "network_timeout", "details": "GitHub API timeout"}
    )

    # 健全性ステータス確認
    health = monitor.get_health_status()
    print(f"健全性ステータス: {health['status']}")
    print(f"健全性スコア: {health['health_score']:.1f}")

    # 日次レポート生成
    report = monitor.generate_daily_report()
    print(f"セッション数: {report['summary']['total_sessions']}")
    print(f"処理コメント数: {report['summary']['total_comments_processed']}")

    # 監視終了
    time.sleep(1)  # アラート処理待機
    monitor.shutdown()

    print("\n✅ 本番環境監視システムテスト完了")
