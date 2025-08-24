"""スマートバッチ返信管理システム

GitHub Pull Request Reviewsの機能を使用して、複数のコメント返信を
1回のAPIリクエストで効率的に送信する。
"""

import json
import logging
import time
from typing import Dict, List, Tuple, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


class ReplyPriority(Enum):
    """返信優先度（改良版：より詳細な分類）"""

    CRITICAL = "critical"  # 🔴緊急（セキュリティ、システム破綻）
    HIGH = "high"  # 🟠高（機能問題、重要な技術指摘）
    MEDIUM = "medium"  # 🟡中（改善提案、将来対応）
    LOW = "low"  # 🟢低（スタイル、軽微な指摘）
    AUTO_REJECT = "auto_reject"  # ❌自動拒否（対応不要）


class ReviewEvent(Enum):
    """レビューイベントタイプ"""

    COMMENT = "COMMENT"  # コメントのみ
    APPROVE = "APPROVE"  # 承認
    REQUEST_CHANGES = "REQUEST_CHANGES"  # 変更要求


@dataclass
class InlineComment:
    """インラインコメント"""

    path: str  # ファイルパス
    body: str  # コメント内容
    line: Optional[int] = None  # 行番号（line/side モード）
    side: str = "RIGHT"  # RIGHT or LEFT
    start_line: Optional[int] = None  # マルチライン開始行
    start_side: Optional[str] = None  # マルチライン開始側
    position: Optional[int] = None  # diff上の位置（positionモード）

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（GitHub API仕様準拠）"""
        result: Dict[str, Any] = {"path": self.path, "body": self.body}

        # 1) 単一行（position モード）
        if self.position is not None:
            result["position"] = self.position
            return result

        # 2) 複数行（range モード）
        if self.start_line is not None or self.start_side is not None:
            if self.start_line is None or self.start_side is None or self.line is None:
                raise ValueError(
                    "Range comments require start_line, start_side, line, and side."
                )
            result.update(
                {
                    "start_line": self.start_line,
                    "start_side": self.start_side,
                    "line": self.line,
                    "side": self.side,
                }
            )
            return result

        # 3) 単一行（line + side モード）
        if self.line is None:
            raise ValueError(
                "Single-line comments require either position or line+side."
            )
        result["line"] = self.line
        result["side"] = self.side
        return result


@dataclass
class BatchReply:
    """バッチ返信データ（改良版：効率性とトラッキングを向上）"""

    comment_id: int  # 元のコメントID
    reply_body: str  # 返信内容
    priority: ReplyPriority  # 優先度
    template_type: str  # テンプレートタイプ
    file_path: Optional[str] = None  # ファイルパス（インライン用）
    line_number: Optional[int] = None  # 行番号（インライン用）
    estimated_time: int = 5  # 推定処理時間（分）
    impact_level: str = "medium"  # 影響レベル（low/medium/high）
    action_type: str = "unknown"  # アクションタイプ（実装/拒否/将来/確認）
    created_at: Optional[datetime] = None  # 作成時刻

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def is_inline_comment(self) -> bool:
        """インラインコメントかどうか"""
        return self.file_path is not None and self.line_number is not None

    def get_efficiency_score(self) -> float:
        """効率性スコアを計算（新機能）"""
        # 優先度ベースのスコア
        priority_scores = {
            ReplyPriority.CRITICAL: 100.0,
            ReplyPriority.HIGH: 80.0,
            ReplyPriority.MEDIUM: 60.0,
            ReplyPriority.LOW: 40.0,
            ReplyPriority.AUTO_REJECT: 20.0,
        }

        base_score = priority_scores.get(self.priority, 50.0)

        # 時間効率性の調整
        if self.estimated_time <= 3:
            time_multiplier = 1.2
        elif self.estimated_time <= 10:
            time_multiplier = 1.0
        else:
            time_multiplier = 0.8

        return base_score * time_multiplier


@dataclass
class ReviewRequest:
    """レビューリクエスト"""

    body: str  # レビュー全体のコメント
    event: ReviewEvent  # レビューイベント
    inline_comments: List[InlineComment]  # インラインコメント
    general_comments: List[str]  # 一般コメント

    def to_api_payload(self) -> Dict[str, Any]:
        """GitHub API用のペイロードに変換"""
        payload = {"body": self.body, "event": self.event.value}

        if self.inline_comments:
            payload["comments"] = [
                comment.to_dict() for comment in self.inline_comments
            ]

        return payload


class SmartBatchReplyManager:
    """効率的なバッチ返信管理システム"""

    def __init__(self, github_token: str, rate_limit_delay: float = 1.0):
        self.github_token = github_token
        self.rate_limit_delay = rate_limit_delay
        self.batch_size = 100  # GitHub APIの制限（最大100コメント/レビュー）
        self.logger = logging.getLogger(__name__)

        # API統計
        self.api_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_comments_sent": 0,
            "rate_limit_hits": 0,
        }

    def optimize_reply_batch(self, replies: List[BatchReply]) -> List[List[BatchReply]]:
        """返信を効率的なバッチに分割

        Args:
            replies: 返信リスト

        Returns:
            最適化されたバッチリスト
        """
        if not replies:
            return []

        # 優先度別に分類
        critical_replies = []  # ❌⚠️ 即座に返信が必要
        normal_replies = []  # ⏳🤔 通常の返信

        for reply in replies:
            if reply.priority == ReplyPriority.CRITICAL:
                critical_replies.append(reply)
            else:
                normal_replies.append(reply)

        batches = []

        # 緊急返信は小さなバッチで優先処理（最大10件）
        critical_batch_size = min(10, self.batch_size)
        for i in range(0, len(critical_replies), critical_batch_size):
            batch = critical_replies[i : i + critical_batch_size]
            batches.append(batch)

        # 通常返信は大きなバッチで効率処理
        normal_batch_size = min(self.batch_size, 50)  # 効率と安全性のバランス
        for i in range(0, len(normal_replies), normal_batch_size):
            batch = normal_replies[i : i + normal_batch_size]
            batches.append(batch)

        self.logger.info(
            f"バッチ最適化完了: "
            f"緊急={len(critical_replies)}件, "
            f"通常={len(normal_replies)}件, "
            f"バッチ数={len(batches)}"
        )

        return batches

    def create_review_request(
        self, batch: List[BatchReply], pr_info: Dict[str, Any]
    ) -> ReviewRequest:
        """バッチからレビューリクエストを作成

        Args:
            batch: 返信バッチ
            pr_info: プルリクエスト情報

        Returns:
            ReviewRequest: レビューリクエスト
        """
        inline_comments = []
        general_comments = []

        # 優先度判定
        has_critical = any(reply.priority == ReplyPriority.CRITICAL for reply in batch)

        # バッチサマリーの生成
        critical_count = sum(
            1 for reply in batch if reply.priority == ReplyPriority.CRITICAL
        )
        normal_count = len(batch) - critical_count

        body_parts = [
            f"## 📝 CodeRabbitレビューコメント一括返信",
            f"",
            f"**返信件数**: {len(batch)}件（緊急: {critical_count}件、通常: {normal_count}件）",
            f"**処理時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
        ]

        # 各返信を処理
        for i, reply in enumerate(batch, 1):
            if reply.is_inline_comment():
                # インラインコメントとして追加
                inline_comment = InlineComment(
                    path=reply.file_path,
                    line=reply.line_number,
                    body=f"**返信 #{i} (コメント#{reply.comment_id})**\n\n{reply.reply_body}",
                )
                inline_comments.append(inline_comment)
            else:
                # 一般コメントとして追加
                comment_text = (
                    f"### 返信 #{i} - コメント#{reply.comment_id}\n{reply.reply_body}"
                )
                general_comments.append(comment_text)

        # 一般コメントを本文に追加
        if general_comments:
            body_parts.extend(["## 💬 一般返信", ""])
            body_parts.extend(general_comments)

        # インラインコメントの説明
        if inline_comments:
            body_parts.extend(
                [
                    "",
                    f"## 📍 インラインコメント返信: {len(inline_comments)}件",
                    "上記に加えて、該当ファイルの特定行にインラインコメントで返信しています。",
                ]
            )

        body = "\n".join(body_parts)

        # レビューイベントの決定
        event = ReviewEvent.REQUEST_CHANGES if has_critical else ReviewEvent.COMMENT

        return ReviewRequest(
            body=body,
            event=event,
            inline_comments=inline_comments,
            general_comments=general_comments,
        )

    def execute_batch_review(
        self, review_request: ReviewRequest, pr_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """バッチレビューを実行

        Args:
            review_request: レビューリクエスト
            pr_info: プルリクエスト情報

        Returns:
            実行結果
        """
        owner = pr_info.get("owner")
        repo = pr_info.get("repo")
        pull_number = pr_info.get("pull_number")

        if not all([owner, repo, pull_number]):
            raise ValueError("PR情報が不完全です")

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        payload = review_request.to_api_payload()

        self.logger.info(
            f"バッチレビュー実行: {len(review_request.inline_comments)}インライン + "
            f"{len(review_request.general_comments)}一般コメント"
        )

        try:
            # curlコマンドを生成（実際の実行用）
            curl_command = self._generate_curl_command(url, payload)

            # 統計更新
            self.api_stats["total_requests"] += 1
            total_comments = len(review_request.inline_comments) + len(
                review_request.general_comments
            )
            self.api_stats["total_comments_sent"] += total_comments

            result = {
                "status": "success",
                "url": url,
                "payload": payload,
                "curl_command": curl_command,
                "comment_count": total_comments,
                "inline_count": len(review_request.inline_comments),
                "general_count": len(review_request.general_comments),
            }

            self.api_stats["successful_requests"] += 1
            self.logger.info(f"バッチレビュー成功: {total_comments}件のコメント送信")

            return result

        except Exception as e:
            self.api_stats["failed_requests"] += 1
            self.logger.error(f"バッチレビュー失敗: {str(e)}")

            return {"status": "error", "error": str(e), "url": url, "payload": payload}

    def _generate_curl_command(self, url: str, payload: Dict[str, Any]) -> str:
        """curlコマンドを生成"""

        # JSONペイロードを整形
        json_payload = json.dumps(payload, indent=2, ensure_ascii=False)

        # ヒアドキュメントで安全にJSONを渡す（変数展開・コマンド置換を抑止）
        curl_command = f"""cat <<'JSON' | curl -sS -X POST \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  -H "Accept: application/vnd.github+json" \\
  -H "Content-Type: application/json" \\
  "{url}" \\
  --data-binary @-
{json_payload}
JSON"""

        return curl_command

    def execute_batch_with_retry(
        self, batch: List[BatchReply], pr_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """エラー耐性のあるバッチ実行

        Args:
            batch: 返信バッチ
            pr_info: プルリクエスト情報

        Returns:
            実行結果
        """
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                # レビューリクエスト作成
                review_request = self.create_review_request(batch, pr_info)

                # バッチレビュー実行
                result = self.execute_batch_review(review_request, pr_info)

                if result["status"] == "success":
                    return result

                # エラーの場合、リトライ判定
                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"バッチ実行失敗（試行 {attempt + 1}/{max_retries}）: {result.get('error', 'Unknown error')}"
                    )
                    time.sleep(retry_delay * (attempt + 1))  # 指数バックオフ
                    continue
                else:
                    return result

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"バッチ実行例外（試行 {attempt + 1}/{max_retries}）: {str(e)}"
                    )
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    return {
                        "status": "error",
                        "error": f"最大リトライ回数到達: {str(e)}",
                        "batch_size": len(batch),
                    }

        return {"status": "error", "error": "予期しないエラー"}

    def process_multiple_batches(
        self, batches: List[List[BatchReply]], pr_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """複数バッチの順次処理

        Args:
            batches: バッチリスト
            pr_info: プルリクエスト情報

        Returns:
            全体の実行結果
        """
        results = {
            "total_batches": len(batches),
            "successful_batches": 0,
            "failed_batches": 0,
            "batch_results": [],
            "total_comments": 0,
            "total_time": 0.0,
        }

        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            self.logger.info(f"バッチ {i}/{len(batches)} 処理開始: {len(batch)}件")

            batch_start = time.time()
            result = self.execute_batch_with_retry(batch, pr_info)
            batch_time = time.time() - batch_start

            result["batch_number"] = i
            result["batch_size"] = len(batch)
            result["execution_time"] = batch_time

            results["batch_results"].append(result)
            results["total_comments"] += len(batch)

            if result["status"] == "success":
                results["successful_batches"] += 1
                self.logger.info(f"バッチ {i} 成功: {len(batch)}件、{batch_time:.1f}秒")
            else:
                results["failed_batches"] += 1
                self.logger.error(
                    f"バッチ {i} 失敗: {result.get('error', 'Unknown error')}"
                )

            # バッチ間の遅延（レート制限対策）
            if i < len(batches):
                time.sleep(self.rate_limit_delay)

        results["total_time"] = time.time() - start_time

        self.logger.info(
            f"全バッチ処理完了: "
            f"成功={results['successful_batches']}, "
            f"失敗={results['failed_batches']}, "
            f"総時間={results['total_time']:.1f}秒"
        )

        return results

    def get_efficiency_report(self, results: Dict[str, Any]) -> str:
        """効率性レポートを生成"""

        success_rate = (
            (results["successful_batches"] / results["total_batches"]) * 100
            if results["total_batches"] > 0
            else 0
        )
        avg_time_per_batch = (
            results["total_time"] / results["total_batches"]
            if results["total_batches"] > 0
            else 0
        )
        avg_comments_per_batch = (
            results["total_comments"] / results["total_batches"]
            if results["total_batches"] > 0
            else 0
        )

        # 従来方式との比較（1コメント1API呼び出し）
        traditional_requests = results["total_comments"]
        actual_requests = results["successful_batches"]
        efficiency_improvement = (
            ((traditional_requests - actual_requests) / traditional_requests * 100)
            if traditional_requests > 0
            else 0
        )

        report = f"""
## ⚡ バッチ返信効率性レポート

### 📊 実行統計
- **総バッチ数**: {results['total_batches']}個
- **成功バッチ**: {results['successful_batches']}個
- **失敗バッチ**: {results['failed_batches']}個
- **成功率**: {success_rate:.1f}%

### 💬 コメント統計
- **総コメント数**: {results['total_comments']}件
- **平均コメント/バッチ**: {avg_comments_per_batch:.1f}件
- **総処理時間**: {results['total_time']:.1f}秒
- **平均時間/バッチ**: {avg_time_per_batch:.1f}秒

### 🚀 効率性改善
- **従来方式**: {traditional_requests}回のAPI呼び出し
- **バッチ方式**: {actual_requests}回のAPI呼び出し
- **効率改善**: {efficiency_improvement:.1f}%削減
- **時間短縮**: 約{efficiency_improvement/100*results['total_time']:.1f}秒短縮

### 📈 API統計
- **総リクエスト数**: {self.api_stats['total_requests']}回
- **成功リクエスト**: {self.api_stats['successful_requests']}回
- **失敗リクエスト**: {self.api_stats['failed_requests']}回
- **送信コメント総数**: {self.api_stats['total_comments_sent']}件
"""

        return report.strip()

    def generate_batch_commands(
        self, batches: List[List[BatchReply]], pr_info: Dict[str, Any]
    ) -> List[str]:
        """実行可能なcurlコマンド群を生成

        Args:
            batches: バッチリスト
            pr_info: プルリクエスト情報

        Returns:
            curlコマンドのリスト
        """
        commands = []

        for i, batch in enumerate(batches, 1):
            review_request = self.create_review_request(batch, pr_info)

            # 副作用なしでcurlコマンドを直接生成
            url = review_request["url"]
            payload = review_request["payload"]
            curl_command = self._generate_curl_command(url, payload)

            command = f"# バッチ {i}: {len(batch)}件のコメント\n{curl_command}\n"
            commands.append(command)

        return commands


def create_smart_batch_reply_manager(github_token: str) -> SmartBatchReplyManager:
    """スマートバッチ返信マネージャーのファクトリー関数"""
    return SmartBatchReplyManager(github_token)


# 使用例とテスト用のサンプルデータ
if __name__ == "__main__":
    # テスト用のサンプル返信
    sample_replies = [
        BatchReply(
            comment_id=123,
            reply_body="@coderabbitai この指摘は技術的根拠により対応不要です。",
            priority=ReplyPriority.CRITICAL,
            template_type="technical_rejection",
        ),
        BatchReply(
            comment_id=456,
            reply_body="@coderabbitai 妥当な指摘ですが現フェーズでは対象外です。",
            priority=ReplyPriority.MEDIUM,
            template_type="future_planning",
        ),
        BatchReply(
            comment_id=789,
            reply_body="@coderabbitai この点について詳細説明をお願いします。",
            priority=ReplyPriority.MEDIUM,
            template_type="clarification_request",
            file_path="src/main.py",
            line_number=42,
        ),
    ]

    # PR情報
    pr_info = {"owner": "test-owner", "repo": "test-repo", "pull_number": 123}

    # バッチ返信管理実行
    manager = create_smart_batch_reply_manager("dummy_token")

    # バッチ最適化
    batches = manager.optimize_reply_batch(sample_replies)

    print("=== スマートバッチ返信管理 テスト結果 ===")
    print(f"総返信数: {len(sample_replies)}")
    print(f"バッチ数: {len(batches)}")

    # 各バッチの処理
    for i, batch in enumerate(batches, 1):
        print(f"\nバッチ {i}: {len(batch)}件")
        for reply in batch:
            print(f"  - コメント#{reply.comment_id}: {reply.priority.value}")

    # レビューリクエスト生成テスト
    if batches:
        review_request = manager.create_review_request(batches[0], pr_info)
        print(f"\nレビューリクエスト例:")
        print(f"- イベント: {review_request.event.value}")
        print(f"- インラインコメント: {len(review_request.inline_comments)}件")
        print(f"- 一般コメント: {len(review_request.general_comments)}件")
        print(f"- 本文長: {len(review_request.body)}文字")
