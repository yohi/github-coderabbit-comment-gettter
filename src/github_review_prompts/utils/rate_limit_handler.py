"""GitHub API制限対策システム"""

import time
import logging
from functools import wraps
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta
import requests
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """レート制限対策戦略"""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    ADAPTIVE = "adaptive"
    BATCH_PROCESSING = "batch_processing"


class GitHubRateLimitHandler:
    """GitHub API制限対策ハンドラー"""

    def __init__(
        self,
        strategy: RateLimitStrategy = RateLimitStrategy.ADAPTIVE,
        cache_file: Optional[str] = None,
    ):
        self.strategy = strategy
        self.logger = logging.getLogger(__name__)

        # レート制限情報のキャッシュ
        self.cache_file = (
            Path(cache_file) if cache_file else Path(".github_rate_limit_cache.json")
        )
        self.rate_limit_info = self._load_rate_limit_cache()

        # 戦略別設定
        self.config = {
            RateLimitStrategy.EXPONENTIAL_BACKOFF: {
                "base_delay": 1,
                "max_delay": 300,  # 5分
                "backoff_factor": 2,
            },
            RateLimitStrategy.FIXED_DELAY: {"delay": 1.2},  # 1.2秒固定
            RateLimitStrategy.ADAPTIVE: {
                "target_remaining_ratio": 0.1,  # 残り10%で制限開始
                "min_delay": 0.5,
                "max_delay": 60,
            },
            RateLimitStrategy.BATCH_PROCESSING: {
                "batch_size": 10,
                "batch_delay": 60,  # バッチ間の待機時間
            },
        }

        # 統計情報
        self.stats = {
            "total_requests": 0,  # 総試行回数
            "successful_requests": 0,  # 成功回数
            "rate_limited_requests": 0,
            "total_wait_time": 0.0,
            "last_reset_time": None,
        }

    def _load_rate_limit_cache(self) -> Dict[str, Any]:
        """レート制限情報のキャッシュを読み込み"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"レート制限キャッシュの読み込みエラー: {e}")

        return {
            "core": {"remaining": 5000, "reset": 0, "limit": 5000},
            "search": {"remaining": 30, "reset": 0, "limit": 30},
            "graphql": {"remaining": 5000, "reset": 0, "limit": 5000},
        }

    def _save_rate_limit_cache(self):
        """レート制限情報をキャッシュに保存"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.rate_limit_info, f, indent=2)
        except Exception as e:
            self.logger.warning(f"レート制限キャッシュの保存エラー: {e}")

    def rate_limit_handler(self, api_type: str = "core"):
        """レート制限対策デコレータ

        Args:
            api_type: APIタイプ ('core', 'search', 'graphql')
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self._execute_with_rate_limit(func, api_type, *args, **kwargs)

            return wrapper

        return decorator

    def _execute_with_rate_limit(self, func: Callable, api_type: str, *args, **kwargs):
        """レート制限を考慮した関数実行"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 事前チェック：レート制限に近づいている場合は待機
                self._pre_request_check(api_type)

                # 関数実行
                start_time = time.time()
                response = func(*args, **kwargs)

                # レスポンスからレート制限情報を更新
                if hasattr(response, "headers"):
                    self._update_rate_limit_info(response.headers, api_type)

                # ステータスコードによるレート制限・過負荷の検出（raise_for_status前にチェック）
                status = getattr(response, "status_code", None)
                if status in (403, 429):
                    wait_time = self._handle_rate_limit_error(
                        response, api_type, retry_count=retry_count
                    )
                    self.logger.warning(
                        f"レート制限/過負荷応答({status})。{wait_time}秒待機します..."
                    )
                    time.sleep(wait_time)
                    self.stats["rate_limited_requests"] += 1
                    self.stats["total_wait_time"] += wait_time
                    retry_count += 1
                    continue

                # 統計更新（成功）- レート制限でない場合のみ
                self.stats["total_requests"] += 1
                self.stats["successful_requests"] += 1

                return response

            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code in (403, 429):
                    # レート制限エラーの処理
                    wait_time = self._handle_rate_limit_error(
                        e.response, api_type, retry_count=retry_count
                    )

                    self.logger.warning(
                        f"レート制限に達しました(ステータス: {e.response.status_code})。{wait_time}秒待機します..."
                    )
                    time.sleep(wait_time)

                    # 統計更新
                    self.stats["rate_limited_requests"] += 1
                    self.stats["total_wait_time"] += wait_time

                    retry_count += 1
                    continue
                else:
                    raise

            except Exception as e:
                self.logger.error(f"API実行エラー: {e}")
                raise

        raise Exception(f"レート制限により{max_retries}回のリトライ後も失敗しました")

    def _pre_request_check(self, api_type: str):
        """リクエスト前のレート制限チェック"""
        rate_info = self.rate_limit_info.get(api_type, {})
        remaining = rate_info.get("remaining", 5000)
        reset_time = rate_info.get("reset", 0)
        limit = rate_info.get("limit", 5000)

        current_time = time.time()

        # リセット時刻を過ぎている場合は情報をリセット
        if current_time > reset_time:
            rate_info["remaining"] = limit
            rate_info["reset"] = current_time + 3600  # 1時間後
            self._save_rate_limit_cache()
            return

        # 戦略に応じた制限チェック
        if self.strategy == RateLimitStrategy.ADAPTIVE:
            config = self.config[RateLimitStrategy.ADAPTIVE]
            target_remaining = limit * config["target_remaining_ratio"]

            if remaining <= target_remaining:
                # 残りリクエスト数に応じた待機時間計算
                time_until_reset = reset_time - current_time
                if time_until_reset > 0:
                    if remaining <= 0:
                        delay = min(
                            max(time_until_reset, config["min_delay"]),
                            config["max_delay"],
                        )
                    else:
                        delay = min(
                            max(
                                time_until_reset / max(remaining, 1),
                                config["min_delay"],
                            ),
                            config["max_delay"],
                        )
                    self.logger.info(f"レート制限予防待機: {delay:.1f}秒")
                    time.sleep(delay)

        elif self.strategy == RateLimitStrategy.FIXED_DELAY:
            config = self.config[RateLimitStrategy.FIXED_DELAY]
            time.sleep(config["delay"])

    def _handle_rate_limit_error(
        self, response: requests.Response, api_type: str, retry_count: int = 0
    ) -> float:
        """レート制限エラーの処理"""
        headers = response.headers

        # Retry-After 優先（abuse/secondary rate limit対策）
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                delay = max(float(retry_after), 0.0)
                return delay
            except ValueError:
                # 数値以外（HTTP-date等）の場合はリセット時刻ベースにフォールバック
                pass

        # GitHub APIのレート制限ヘッダーから情報取得
        reset_time = int(headers.get("X-RateLimit-Reset", time.time() + 3600))
        remaining = int(headers.get("X-RateLimit-Remaining", 0))

        # レート制限情報を更新
        self.rate_limit_info[api_type] = {
            "remaining": remaining,
            "reset": reset_time,
            "limit": int(headers.get("X-RateLimit-Limit", 5000)),
        }
        self._save_rate_limit_cache()

        # 待機時間の計算
        current_time = time.time()
        time_until_reset = max(reset_time - current_time, 0)

        if self.strategy == RateLimitStrategy.EXPONENTIAL_BACKOFF:
            config = self.config[RateLimitStrategy.EXPONENTIAL_BACKOFF]
            delay = min(
                config["base_delay"] * (config["backoff_factor"] ** retry_count),
                config["max_delay"],
            )

        elif self.strategy == RateLimitStrategy.FIXED_DELAY:
            delay = time_until_reset + 10  # 少し余裕を持たせる

        else:  # ADAPTIVE
            # リセット時刻まで待機（少し余裕を持たせる）
            delay = time_until_reset + 5

        return delay

    def _update_rate_limit_info(self, headers: Dict[str, str], api_type: str):
        """レスポンスヘッダーからレート制限情報を更新"""
        try:
            if "X-RateLimit-Remaining" in headers:
                self.rate_limit_info[api_type] = {
                    "remaining": int(headers["X-RateLimit-Remaining"]),
                    "reset": int(headers["X-RateLimit-Reset"]),
                    "limit": int(headers["X-RateLimit-Limit"]),
                }
                self._save_rate_limit_cache()
        except (ValueError, KeyError) as e:
            self.logger.warning(f"レート制限情報の更新エラー: {e}")

    def get_rate_limit_status(self, api_type: str = "core") -> Dict[str, Any]:
        """現在のレート制限状況を取得"""
        rate_info = self.rate_limit_info.get(api_type, {})
        current_time = time.time()
        reset_time = rate_info.get("reset", 0)

        return {
            "api_type": api_type,
            "remaining": rate_info.get("remaining", 0),
            "limit": rate_info.get("limit", 5000),
            "reset_time": reset_time,
            "time_until_reset": max(reset_time - current_time, 0),
            "usage_percentage": (
                (rate_info.get("limit", 5000) - rate_info.get("remaining", 0))
                / rate_info.get("limit", 5000)
                * 100
            ),
            "is_rate_limited": rate_info.get("remaining", 5000) == 0,
            "stats": self.stats.copy(),
        }

    def batch_execute(self, functions: list, api_type: str = "core") -> list:
        """バッチ処理でのAPI実行"""
        if self.strategy != RateLimitStrategy.BATCH_PROCESSING:
            # 通常の実行
            return [self._execute_with_rate_limit(func, api_type) for func in functions]

        config = self.config[RateLimitStrategy.BATCH_PROCESSING]
        batch_size = config["batch_size"]
        batch_delay = config["batch_delay"]

        results = []

        for i in range(0, len(functions), batch_size):
            batch = functions[i : i + batch_size]

            # バッチ内の関数を実行
            batch_results = []
            for func in batch:
                try:
                    result = self._execute_with_rate_limit(func, api_type)
                    batch_results.append(result)
                except Exception as e:
                    self.logger.error(f"バッチ処理エラー: {e}")
                    batch_results.append(None)

            results.extend(batch_results)

            # 次のバッチまで待機（最後のバッチでない場合）
            if i + batch_size < len(functions):
                self.logger.info(f"バッチ処理待機: {batch_delay}秒")
                time.sleep(batch_delay)

        return results

    def estimate_completion_time(
        self, request_count: int, api_type: str = "core"
    ) -> Dict[str, Any]:
        """完了予想時間を推定"""
        rate_info = self.rate_limit_info.get(api_type, {})
        remaining = rate_info.get("remaining", 5000)
        reset_time = rate_info.get("reset", time.time() + 3600)
        current_time = time.time()

        if request_count <= remaining:
            # 現在の制限内で完了可能
            if self.strategy == RateLimitStrategy.FIXED_DELAY:
                estimated_seconds = (
                    request_count * self.config[RateLimitStrategy.FIXED_DELAY]["delay"]
                )
            else:
                estimated_seconds = request_count * 0.5  # 平均0.5秒/リクエスト
        else:
            # 制限を超える場合
            time_until_reset = max(reset_time - current_time, 0)
            requests_after_reset = request_count - remaining

            # リセット後の時間を推定
            additional_resets = requests_after_reset // rate_info.get("limit", 5000)
            additional_time = additional_resets * 3600  # 1時間/リセット

            estimated_seconds = time_until_reset + additional_time

        return {
            "estimated_seconds": estimated_seconds,
            "estimated_minutes": estimated_seconds / 60,
            "estimated_hours": estimated_seconds / 3600,
            "completion_time": datetime.now() + timedelta(seconds=estimated_seconds),
            "requests_per_hour": min(rate_info.get("limit", 5000), request_count),
            "resets_required": max(
                0, (request_count - remaining) // rate_info.get("limit", 5000)
            ),
        }

    def generate_usage_report(self) -> Dict[str, Any]:
        """使用状況レポートを生成"""
        report = {
            "rate_limit_status": {},
            "statistics": self.stats.copy(),
            "strategy": self.strategy.value,
            "generated_at": datetime.now().isoformat(),
        }

        # 各APIタイプの状況
        for api_type in ["core", "search", "graphql"]:
            report["rate_limit_status"][api_type] = self.get_rate_limit_status(api_type)

        # 効率性の計算
        total_requests = self.stats["total_requests"]
        if total_requests > 0:
            report["efficiency"] = {
                "rate_limit_ratio": self.stats["rate_limited_requests"]
                / total_requests,
                "average_wait_time": self.stats["total_wait_time"] / total_requests,
                "successful_ratio": (
                    total_requests - self.stats["rate_limited_requests"]
                )
                / total_requests,
            }

        # 推奨事項
        report["recommendations"] = self._generate_usage_recommendations()

        return report

    def _generate_usage_recommendations(self) -> list:
        """使用状況に基づく推奨事項を生成"""
        recommendations = []

        # レート制限の頻度チェック
        total_requests = self.stats["total_requests"]
        rate_limited = self.stats["rate_limited_requests"]

        if total_requests > 0:
            rate_limit_ratio = rate_limited / total_requests

            if rate_limit_ratio > 0.2:  # 20%以上がレート制限
                recommendations.append(
                    "🚨 レート制限の頻度が高いです。バッチ処理戦略を検討してください"
                )
            elif rate_limit_ratio > 0.1:  # 10%以上がレート制限
                recommendations.append(
                    "⚠️ レート制限が発生しています。適応的戦略への変更を検討してください"
                )

        # 待機時間チェック
        avg_wait_time = self.stats["total_wait_time"] / max(total_requests, 1)
        if avg_wait_time > 10:  # 平均10秒以上の待機
            recommendations.append(
                "⏰ 平均待機時間が長いです。リクエスト頻度の調整を検討してください"
            )

        # 現在の制限状況チェック
        core_status = self.get_rate_limit_status("core")
        if core_status["usage_percentage"] > 80:
            recommendations.append(
                "📊 API使用量が80%を超えています。リクエスト計画を見直してください"
            )

        return recommendations


# 便利なデコレータ関数
def github_rate_limit(
    api_type: str = "core", strategy: RateLimitStrategy = RateLimitStrategy.ADAPTIVE
):
    """GitHub APIレート制限対策デコレータ（簡易版）"""
    handler = GitHubRateLimitHandler(strategy=strategy)
    return handler.rate_limit_handler(api_type)


# 使用例
if __name__ == "__main__":
    # デモ用の使用例
    handler = GitHubRateLimitHandler(strategy=RateLimitStrategy.ADAPTIVE)

    @handler.rate_limit_handler("core")
    def sample_github_api_call():
        # 実際のGitHub API呼び出しをシミュレート
        import requests

        response = requests.get("https://api.github.com/rate_limit")
        return response

    # 使用状況の確認
    status = handler.get_rate_limit_status("core")
    print(f"レート制限状況: {status}")

    # 完了時間の推定
    estimation = handler.estimate_completion_time(100, "core")
    print(f"100リクエストの完了予想: {estimation}")
