"""使用状況メトリクス収集システム

本番環境での使用状況を監視し、改善効果を測定する。
プライバシーを保護しながら、匿名化された統計情報を収集。
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class UsageMetrics:
    """使用状況メトリクス"""

    session_id: str
    timestamp: str
    version: str

    # 処理統計
    total_comments: int
    filtered_comments: int
    actionable_comments: int

    # 返信統計
    replies_required: int
    replies_not_required: int
    estimated_time_minutes: int

    # パフォーマンス統計
    processing_time_seconds: float
    api_calls_made: int

    # 機能使用状況
    smart_filtering_enabled: bool
    reply_matrix_enabled: bool
    thread_analysis_enabled: bool
    batch_reply_enabled: bool

    # エラー統計
    errors_encountered: int
    error_types: List[str]


class UsageMetricsCollector:
    """使用状況メトリクス収集システム"""

    def __init__(self, enable_collection: bool = True):
        self.enable_collection = enable_collection
        self.logger = logging.getLogger(__name__)

        # メトリクス保存ディレクトリ
        self.metrics_dir = Path.home() / ".github_review_prompts" / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # セッション情報
        self.session_id = self._generate_session_id()
        self.session_start = time.time()

        # 統計情報
        self.stats = {
            "total_comments": 0,
            "filtered_comments": 0,
            "actionable_comments": 0,
            "replies_required": 0,
            "replies_not_required": 0,
            "estimated_time_minutes": 0,
            "api_calls_made": 0,
            "errors_encountered": 0,
            "error_types": [],
        }

        # 機能使用状況
        self.features_used = {
            "smart_filtering_enabled": False,
            "reply_matrix_enabled": False,
            "thread_analysis_enabled": False,
            "batch_reply_enabled": False,
        }

    def _generate_session_id(self) -> str:
        """匿名化されたセッションIDを生成"""
        import hashlib
        import uuid

        # ランダムUUIDをハッシュ化して匿名化
        random_uuid = str(uuid.uuid4())
        session_hash = hashlib.sha256(random_uuid.encode()).hexdigest()[:16]
        return f"session_{session_hash}"

    def record_processing_start(self, total_comments: int):
        """処理開始を記録"""
        if not self.enable_collection:
            return

        self.stats["total_comments"] = total_comments
        self.logger.debug(f"メトリクス記録開始: {total_comments}件のコメント")

    def record_smart_filtering(self, original_count: int, filtered_count: int):
        """スマートフィルタリング結果を記録"""
        if not self.enable_collection:
            return

        self.features_used["smart_filtering_enabled"] = True
        self.stats["filtered_comments"] = original_count - filtered_count
        self.stats["actionable_comments"] = filtered_count

        self.logger.debug(f"フィルタリング記録: {original_count} -> {filtered_count}")

    def record_reply_analysis(
        self, replies_required: int, replies_not_required: int, estimated_time: int
    ):
        """返信分析結果を記録"""
        if not self.enable_collection:
            return

        self.features_used["reply_matrix_enabled"] = True
        self.stats["replies_required"] = replies_required
        self.stats["replies_not_required"] = replies_not_required
        self.stats["estimated_time_minutes"] = estimated_time

        self.logger.debug(
            f"返信分析記録: 必要={replies_required}, 不要={replies_not_required}"
        )

    def record_thread_analysis(self, threads_analyzed: int):
        """スレッド分析を記録"""
        if not self.enable_collection:
            return

        self.features_used["thread_analysis_enabled"] = True
        self.logger.debug(f"スレッド分析記録: {threads_analyzed}スレッド")

    def record_batch_reply(self, batches_created: int):
        """バッチ返信を記録"""
        if not self.enable_collection:
            return

        self.features_used["batch_reply_enabled"] = True
        self.logger.debug(f"バッチ返信記録: {batches_created}バッチ")

    def record_api_call(self):
        """API呼び出しを記録"""
        if not self.enable_collection:
            return

        self.stats["api_calls_made"] += 1

    def record_error(self, error_type: str):
        """エラーを記録"""
        if not self.enable_collection:
            return

        self.stats["errors_encountered"] += 1
        if error_type not in self.stats["error_types"]:
            self.stats["error_types"].append(error_type)

        self.logger.debug(f"エラー記録: {error_type}")

    def finalize_session(self) -> Optional[UsageMetrics]:
        """セッションを終了してメトリクスを保存"""
        if not self.enable_collection:
            return None

        processing_time = time.time() - self.session_start

        # バージョン情報を取得
        version = self._get_version()

        # メトリクス作成
        metrics = UsageMetrics(
            session_id=self.session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=version,
            total_comments=self.stats["total_comments"],
            filtered_comments=self.stats["filtered_comments"],
            actionable_comments=self.stats["actionable_comments"],
            replies_required=self.stats["replies_required"],
            replies_not_required=self.stats["replies_not_required"],
            estimated_time_minutes=self.stats["estimated_time_minutes"],
            processing_time_seconds=round(processing_time, 2),
            api_calls_made=self.stats["api_calls_made"],
            smart_filtering_enabled=self.features_used["smart_filtering_enabled"],
            reply_matrix_enabled=self.features_used["reply_matrix_enabled"],
            thread_analysis_enabled=self.features_used["thread_analysis_enabled"],
            batch_reply_enabled=self.features_used["batch_reply_enabled"],
            errors_encountered=self.stats["errors_encountered"],
            error_types=self.stats["error_types"],
        )

        # メトリクスを保存
        self._save_metrics(metrics)

        self.logger.info(
            f"セッション完了: {processing_time:.2f}秒, {self.stats['total_comments']}件処理"
        )

        return metrics

    def _get_version(self) -> str:
        """バージョン情報を取得"""
        try:
            # pyproject.tomlから取得を試行
            import tomllib

            project_root = Path(__file__).parent.parent.parent.parent
            pyproject_path = project_root / "pyproject.toml"

            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "unknown")
        except Exception:
            pass

        return "2.0.0"  # デフォルトバージョン

    def _save_metrics(self, metrics: UsageMetrics):
        """メトリクスをファイルに保存"""
        try:
            # 日付別ディレクトリ
            date_str = datetime.now().strftime("%Y-%m-%d")
            daily_dir = self.metrics_dir / date_str
            daily_dir.mkdir(exist_ok=True)

            # メトリクスファイル
            metrics_file = daily_dir / f"{metrics.session_id}.json"

            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump(asdict(metrics), f, indent=2, ensure_ascii=False)

            self.logger.debug(f"メトリクス保存: {metrics_file}")

        except Exception as e:
            self.logger.warning(f"メトリクス保存失敗: {e}")

    def get_daily_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """日別サマリーを取得"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        daily_dir = self.metrics_dir / date
        if not daily_dir.exists():
            return {"date": date, "sessions": 0, "error": "No data for this date"}

        summary = {
            "date": date,
            "sessions": 0,
            "total_comments": 0,
            "total_filtering_savings": 0,
            "total_processing_time": 0.0,
            "feature_usage": {
                "smart_filtering": 0,
                "reply_matrix": 0,
                "thread_analysis": 0,
                "batch_reply": 0,
            },
            "average_efficiency": 0.0,
        }

        try:
            for metrics_file in daily_dir.glob("*.json"):
                with open(metrics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                summary["sessions"] += 1
                summary["total_comments"] += data.get("total_comments", 0)
                summary["total_filtering_savings"] += data.get("filtered_comments", 0)
                summary["total_processing_time"] += data.get(
                    "processing_time_seconds", 0.0
                )

                # 機能使用状況
                if data.get("smart_filtering_enabled"):
                    summary["feature_usage"]["smart_filtering"] += 1
                if data.get("reply_matrix_enabled"):
                    summary["feature_usage"]["reply_matrix"] += 1
                if data.get("thread_analysis_enabled"):
                    summary["feature_usage"]["thread_analysis"] += 1
                if data.get("batch_reply_enabled"):
                    summary["feature_usage"]["batch_reply"] += 1

            # 効率性計算
            if summary["total_comments"] > 0:
                summary["average_efficiency"] = (
                    summary["total_filtering_savings"] / summary["total_comments"]
                ) * 100

        except Exception as e:
            summary["error"] = f"Summary generation failed: {e}"

        return summary


def create_usage_metrics_collector(
    enable_collection: bool = None,
) -> UsageMetricsCollector:
    """使用状況メトリクス収集システムのファクトリー関数"""

    # 環境変数で制御可能
    if enable_collection is None:
        enable_collection = os.getenv("GRP_METRICS_ENABLED", "true").lower() == "true"

    return UsageMetricsCollector(enable_collection)


# 使用例
if __name__ == "__main__":
    # テスト用のメトリクス収集
    collector = create_usage_metrics_collector()

    print("=== 使用状況メトリクス収集テスト ===")

    # 処理開始
    collector.record_processing_start(49)

    # スマートフィルタリング
    collector.record_smart_filtering(49, 24)

    # 返信分析
    collector.record_reply_analysis(4, 20, 316)

    # スレッド分析
    collector.record_thread_analysis(5)

    # バッチ返信
    collector.record_batch_reply(2)

    # API呼び出し
    collector.record_api_call()
    collector.record_api_call()

    # セッション終了
    metrics = collector.finalize_session()

    if metrics:
        print(f"セッションID: {metrics.session_id}")
        print(f"処理時間: {metrics.processing_time_seconds}秒")
        print(f"総コメント: {metrics.total_comments}件")
        print(f"フィルタ除外: {metrics.filtered_comments}件")
        print(f"対応必要: {metrics.actionable_comments}件")
        print(f"返信必要: {metrics.replies_required}件")
        print(f"推定時間: {metrics.estimated_time_minutes}分")

        # 日別サマリー
        summary = collector.get_daily_summary()
        print(f"\n日別サマリー:")
        print(f"セッション数: {summary['sessions']}")
        print(f"平均効率性: {summary['average_efficiency']:.1f}%")

    print("\n✅ メトリクス収集テスト完了")
