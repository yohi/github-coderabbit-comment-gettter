"""SQLiteベースの進捗追跡システム"""

import sqlite3
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import hashlib

logger = logging.getLogger(__name__)


class CommentStatus(Enum):
    """コメントステータス"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"


class ResolutionMethod(Enum):
    """解決方法"""

    MANUAL = "manual"
    AI_AUTOMATED = "ai_automated"
    BATCH_PROCESSED = "batch_processed"
    DUPLICATE_RESOLVED = "duplicate_resolved"
    POLICY_SKIPPED = "policy_skipped"


@dataclass
class CommentRecord:
    """コメントレコード"""

    id: int
    pr_number: int
    pr_url: str
    file_path: str
    line_number: Optional[int]
    comment_body: str
    comment_hash: str
    priority: str
    category: str
    severity: str
    status: CommentStatus
    resolution_method: Optional[ResolutionMethod]
    assignee: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    estimated_hours: float
    actual_hours: Optional[float]
    notes: str
    metadata: Dict[str, Any]


@dataclass
class ProgressStats:
    """進捗統計"""

    total_comments: int
    pending_comments: int
    in_progress_comments: int
    resolved_comments: int
    skipped_comments: int
    completion_rate: float
    average_resolution_time: Optional[float]
    total_estimated_hours: float
    total_actual_hours: float
    efficiency_ratio: Optional[float]


class DatabaseProgressTracker:
    """SQLiteベースの進捗追跡システム"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else Path(".github-review-progress.db")
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()

        # データベースの初期化
        self._init_database()

        self.logger.info(f"データベース進捗追跡システム初期化: {self.db_path}")

    def _init_database(self):
        """データベースの初期化"""
        with self._get_connection() as conn:
            # コメントテーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY,
                    pr_number INTEGER NOT NULL,
                    pr_url TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER,
                    comment_body TEXT NOT NULL,
                    comment_hash TEXT NOT NULL UNIQUE,
                    priority TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolution_method TEXT,
                    assignee TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    estimated_hours REAL NOT NULL DEFAULT 0.0,
                    actual_hours REAL,
                    notes TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """
            )

            # プルリクエストテーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pull_requests (
                    pr_number INTEGER PRIMARY KEY,
                    pr_url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    author TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    total_comments INTEGER DEFAULT 0,
                    resolved_comments INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """
            )

            # 進捗履歴テーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS progress_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_number INTEGER NOT NULL,
                    snapshot_date TIMESTAMP NOT NULL,
                    total_comments INTEGER NOT NULL,
                    resolved_comments INTEGER NOT NULL,
                    completion_rate REAL NOT NULL,
                    velocity REAL NOT NULL DEFAULT 0.0,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (pr_number) REFERENCES pull_requests (pr_number)
                )
            """
            )

            # 解決アクションテーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resolution_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_data TEXT NOT NULL,
                    performed_by TEXT,
                    performed_at TIMESTAMP NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    FOREIGN KEY (comment_id) REFERENCES comments (id)
                )
            """
            )

            # インデックスの作成
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_pr_number ON comments (pr_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_status ON comments (status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_priority ON comments (priority)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comments_hash ON comments (comment_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_progress_history_pr ON progress_history (pr_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resolution_actions_comment ON resolution_actions (comment_id)"
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """データベース接続のコンテキストマネージャー"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def _generate_comment_hash(
        self,
        pr_number: int,
        file_path: str,
        line_number: Optional[int],
        comment_body: str,
    ) -> str:
        """コメントのハッシュを生成"""
        content = f"{pr_number}:{file_path}:{line_number}:{comment_body[:500]}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def track_comment(
        self,
        pr_number: int,
        pr_url: str,
        file_path: str,
        line_number: Optional[int],
        comment_body: str,
        priority: str,
        category: str,
        severity: str,
        estimated_hours: float = 0.0,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """コメントを追跡対象として登録

        Args:
            pr_number: プルリクエスト番号
            pr_url: プルリクエストURL
            file_path: ファイルパス
            line_number: 行番号
            comment_body: コメント内容
            priority: 優先度
            category: カテゴリ
            severity: 重要度
            estimated_hours: 推定作業時間
            assignee: 担当者
            metadata: 追加メタデータ

        Returns:
            コメントID
        """
        try:
            comment_hash = self._generate_comment_hash(
                pr_number, file_path, line_number, comment_body
            )
            now = datetime.now()

            with self._get_connection() as conn:
                # 重複チェック
                existing = conn.execute(
                    "SELECT id FROM comments WHERE comment_hash = ?", (comment_hash,)
                ).fetchone()

                if existing:
                    self.logger.info(f"コメントは既に追跡済みです: {comment_hash}")
                    return existing["id"]

                # コメントを挿入
                cursor = conn.execute(
                    """
                    INSERT INTO comments (
                        pr_number, pr_url, file_path, line_number, comment_body,
                        comment_hash, priority, category, severity, status,
                        created_at, updated_at, estimated_hours, assignee,
                        notes, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pr_number,
                        pr_url,
                        file_path,
                        line_number,
                        comment_body,
                        comment_hash,
                        priority,
                        category,
                        severity,
                        CommentStatus.PENDING.value,
                        now,
                        now,
                        estimated_hours,
                        assignee,
                        "",
                        json.dumps(metadata or {}),
                    ),
                )

                comment_id = cursor.lastrowid

                # PRテーブルも更新
                self._update_pr_stats(conn, pr_number, pr_url)

                conn.commit()

                self.logger.info(
                    f"コメントを追跡対象として登録: ID={comment_id}, Hash={comment_hash}"
                )
                return comment_id

        except Exception as e:
            self.logger.error(f"コメント追跡登録エラー: {e}")
            raise

    def update_comment_status(
        self,
        comment_id: int,
        status: CommentStatus,
        resolution_method: Optional[ResolutionMethod] = None,
        actual_hours: Optional[float] = None,
        notes: str = "",
        performer: Optional[str] = None,
    ) -> bool:
        """コメントのステータスを更新

        Args:
            comment_id: コメントID
            status: 新しいステータス
            resolution_method: 解決方法
            actual_hours: 実際の作業時間
            notes: 備考
            performer: 実行者

        Returns:
            更新成功フラグ
        """
        try:
            now = datetime.now()
            resolved_at = now if status == CommentStatus.RESOLVED else None

            with self._get_connection() as conn:
                # コメントステータス更新
                conn.execute(
                    """
                    UPDATE comments SET
                        status = ?,
                        resolution_method = ?,
                        actual_hours = ?,
                        notes = ?,
                        resolved_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (
                        status.value,
                        resolution_method.value if resolution_method else None,
                        actual_hours,
                        notes,
                        resolved_at,
                        now,
                        comment_id,
                    ),
                )

                if conn.rowcount == 0:
                    self.logger.warning(f"コメントが見つかりません: ID={comment_id}")
                    return False

                # 解決アクションを記録
                conn.execute(
                    """
                    INSERT INTO resolution_actions (
                        comment_id, action_type, action_data, performed_by,
                        performed_at, success
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        comment_id,
                        "status_update",
                        json.dumps(
                            {
                                "old_status": "unknown",  # 実際の実装では前のステータスを取得
                                "new_status": status.value,
                                "resolution_method": (
                                    resolution_method.value
                                    if resolution_method
                                    else None
                                ),
                                "notes": notes,
                            }
                        ),
                        performer,
                        now,
                        True,
                    ),
                )

                # PR統計を更新
                pr_number = conn.execute(
                    "SELECT pr_number FROM comments WHERE id = ?", (comment_id,)
                ).fetchone()["pr_number"]

                self._update_pr_stats(conn, pr_number)

                conn.commit()

                self.logger.info(
                    f"コメントステータス更新: ID={comment_id}, Status={status.value}"
                )
                return True

        except Exception as e:
            self.logger.error(f"コメントステータス更新エラー: {e}")
            return False

    def _update_pr_stats(
        self, conn: sqlite3.Connection, pr_number: int, pr_url: str = ""
    ):
        """PRの統計情報を更新"""
        try:
            # コメント統計を取得
            stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved
                FROM comments
                WHERE pr_number = ?
            """,
                (pr_number,),
            ).fetchone()

            total_comments = stats["total"]
            resolved_comments = stats["resolved"]

            # PRレコードを更新または挿入
            conn.execute(
                """
                INSERT OR REPLACE INTO pull_requests (
                    pr_number, pr_url, title, created_at, updated_at,
                    total_comments, resolved_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    pr_number,
                    pr_url,
                    f"PR #{pr_number}",
                    datetime.now(),
                    datetime.now(),
                    total_comments,
                    resolved_comments,
                ),
            )

        except Exception as e:
            self.logger.error(f"PR統計更新エラー: {e}")

    def get_comment_by_id(self, comment_id: int) -> Optional[CommentRecord]:
        """IDでコメントを取得"""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM comments WHERE id = ?
                """,
                    (comment_id,),
                ).fetchone()

                if not row:
                    return None

                return self._row_to_comment_record(row)

        except Exception as e:
            self.logger.error(f"コメント取得エラー: {e}")
            return None

    def get_comments_by_pr(
        self, pr_number: int, status: Optional[CommentStatus] = None
    ) -> List[CommentRecord]:
        """PRのコメント一覧を取得"""
        try:
            with self._get_connection() as conn:
                if status:
                    rows = conn.execute(
                        """
                        SELECT * FROM comments
                        WHERE pr_number = ? AND status = ?
                        ORDER BY priority DESC, created_at ASC
                    """,
                        (pr_number, status.value),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM comments
                        WHERE pr_number = ?
                        ORDER BY priority DESC, created_at ASC
                    """,
                        (pr_number,),
                    ).fetchall()

                return [self._row_to_comment_record(row) for row in rows]

        except Exception as e:
            self.logger.error(f"PRコメント取得エラー: {e}")
            return []

    def _row_to_comment_record(self, row: sqlite3.Row) -> CommentRecord:
        """データベース行をCommentRecordに変換"""
        return CommentRecord(
            id=row["id"],
            pr_number=row["pr_number"],
            pr_url=row["pr_url"],
            file_path=row["file_path"],
            line_number=row["line_number"],
            comment_body=row["comment_body"],
            comment_hash=row["comment_hash"],
            priority=row["priority"],
            category=row["category"],
            severity=row["severity"],
            status=CommentStatus(row["status"]),
            resolution_method=(
                ResolutionMethod(row["resolution_method"])
                if row["resolution_method"]
                else None
            ),
            assignee=row["assignee"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"])
                if row["resolved_at"]
                else None
            ),
            estimated_hours=row["estimated_hours"],
            actual_hours=row["actual_hours"],
            notes=row["notes"],
            metadata=json.loads(row["metadata"]),
        )

    def get_progress_stats(
        self, pr_number: Optional[int] = None, days: Optional[int] = None
    ) -> ProgressStats:
        """進捗統計を取得"""
        try:
            with self._get_connection() as conn:
                # 基本的なWHERE句
                where_conditions = []
                params = []

                if pr_number:
                    where_conditions.append("pr_number = ?")
                    params.append(pr_number)

                if days:
                    cutoff_date = datetime.now() - timedelta(days=days)
                    where_conditions.append("created_at >= ?")
                    params.append(cutoff_date)

                where_clause = (
                    " WHERE " + " AND ".join(where_conditions)
                    if where_conditions
                    else ""
                )

                # 統計クエリ
                stats_row = conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_comments,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_comments,
                        SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_comments,
                        SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_comments,
                        SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_comments,
                        SUM(estimated_hours) as total_estimated_hours,
                        SUM(actual_hours) as total_actual_hours,
                        AVG(CASE
                            WHEN status = 'resolved' AND resolved_at IS NOT NULL
                            THEN (julianday(resolved_at) - julianday(created_at)) * 24
                            ELSE NULL
                        END) as avg_resolution_time_hours
                    FROM comments{where_clause}
                """,
                    params,
                ).fetchone()

                total = stats_row["total_comments"]
                resolved = stats_row["resolved_comments"]
                completion_rate = (resolved / total * 100) if total > 0 else 0.0

                total_estimated = stats_row["total_estimated_hours"] or 0.0
                total_actual = stats_row["total_actual_hours"] or 0.0
                efficiency_ratio = (
                    (total_estimated / total_actual) if total_actual > 0 else None
                )

                return ProgressStats(
                    total_comments=total,
                    pending_comments=stats_row["pending_comments"],
                    in_progress_comments=stats_row["in_progress_comments"],
                    resolved_comments=resolved,
                    skipped_comments=stats_row["skipped_comments"],
                    completion_rate=completion_rate,
                    average_resolution_time=stats_row["avg_resolution_time_hours"],
                    total_estimated_hours=total_estimated,
                    total_actual_hours=total_actual,
                    efficiency_ratio=efficiency_ratio,
                )

        except Exception as e:
            self.logger.error(f"進捗統計取得エラー: {e}")
            return ProgressStats(0, 0, 0, 0, 0, 0.0, None, 0.0, 0.0, None)

    def record_progress_snapshot(self, pr_number: int) -> bool:
        """進捗のスナップショットを記録"""
        try:
            stats = self.get_progress_stats(pr_number)
            now = datetime.now()

            with self._get_connection() as conn:
                # 前回のスナップショットから速度を計算
                last_snapshot = conn.execute(
                    """
                    SELECT resolved_comments, snapshot_date
                    FROM progress_history
                    WHERE pr_number = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """,
                    (pr_number,),
                ).fetchone()

                velocity = 0.0
                if last_snapshot:
                    time_diff = (
                        now - datetime.fromisoformat(last_snapshot["snapshot_date"])
                    ).total_seconds() / 3600
                    if time_diff > 0:
                        resolved_diff = (
                            stats.resolved_comments - last_snapshot["resolved_comments"]
                        )
                        velocity = resolved_diff / time_diff  # コメント/時間

                # スナップショットを記録
                conn.execute(
                    """
                    INSERT INTO progress_history (
                        pr_number, snapshot_date, total_comments, resolved_comments,
                        completion_rate, velocity, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pr_number,
                        now,
                        stats.total_comments,
                        stats.resolved_comments,
                        stats.completion_rate,
                        velocity,
                        json.dumps(
                            {
                                "pending": stats.pending_comments,
                                "in_progress": stats.in_progress_comments,
                                "skipped": stats.skipped_comments,
                                "avg_resolution_time": stats.average_resolution_time,
                            }
                        ),
                    ),
                )

                conn.commit()

                self.logger.info(
                    f"進捗スナップショット記録: PR#{pr_number}, 完了率={stats.completion_rate:.1f}%"
                )
                return True

        except Exception as e:
            self.logger.error(f"進捗スナップショット記録エラー: {e}")
            return False

    def get_velocity_trend(self, pr_number: int, days: int = 7) -> List[Dict[str, Any]]:
        """速度トレンドを取得"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT snapshot_date, total_comments, resolved_comments,
                           completion_rate, velocity, metadata
                    FROM progress_history
                    WHERE pr_number = ? AND snapshot_date >= ?
                    ORDER BY snapshot_date ASC
                """,
                    (pr_number, cutoff_date),
                ).fetchall()

                return [
                    {
                        "date": row["snapshot_date"],
                        "total_comments": row["total_comments"],
                        "resolved_comments": row["resolved_comments"],
                        "completion_rate": row["completion_rate"],
                        "velocity": row["velocity"],
                        "metadata": json.loads(row["metadata"]),
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"速度トレンド取得エラー: {e}")
            return []

    def cleanup_old_data(self, days: int = 90) -> int:
        """古いデータをクリーンアップ"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                # 古い進捗履歴を削除
                cursor = conn.execute(
                    """
                    DELETE FROM progress_history
                    WHERE snapshot_date < ?
                """,
                    (cutoff_date,),
                )

                deleted_count = cursor.rowcount

                # 古い解決アクションを削除
                conn.execute(
                    """
                    DELETE FROM resolution_actions
                    WHERE performed_at < ?
                """,
                    (cutoff_date,),
                )

                conn.commit()

                self.logger.info(f"古いデータをクリーンアップ: {deleted_count}件削除")
                return deleted_count

        except Exception as e:
            self.logger.error(f"データクリーンアップエラー: {e}")
            return 0

    def export_data(self, output_path: Path, pr_number: Optional[int] = None) -> bool:
        """データをエクスポート"""
        try:
            with self._get_connection() as conn:
                # エクスポートするデータを取得
                if pr_number:
                    comments = conn.execute(
                        """
                        SELECT * FROM comments WHERE pr_number = ?
                        ORDER BY created_at ASC
                    """,
                        (pr_number,),
                    ).fetchall()

                    progress_history = conn.execute(
                        """
                        SELECT * FROM progress_history WHERE pr_number = ?
                        ORDER BY snapshot_date ASC
                    """,
                        (pr_number,),
                    ).fetchall()
                else:
                    comments = conn.execute(
                        """
                        SELECT * FROM comments ORDER BY created_at ASC
                    """
                    ).fetchall()

                    progress_history = conn.execute(
                        """
                        SELECT * FROM progress_history ORDER BY snapshot_date ASC
                    """
                    ).fetchall()

                # データを辞書に変換
                export_data = {
                    "export_date": datetime.now().isoformat(),
                    "pr_number": pr_number,
                    "comments": [dict(row) for row in comments],
                    "progress_history": [dict(row) for row in progress_history],
                }

                # JSONファイルに保存
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

                self.logger.info(f"データをエクスポート: {output_path}")
                return True

        except Exception as e:
            self.logger.error(f"データエクスポートエラー: {e}")
            return False

    def get_database_info(self) -> Dict[str, Any]:
        """データベース情報を取得"""
        try:
            with self._get_connection() as conn:
                # テーブル情報
                tables = conn.execute(
                    """
                    SELECT name FROM sqlite_master WHERE type='table'
                """
                ).fetchall()

                # 各テーブルのレコード数
                table_counts = {}
                for table in tables:
                    table_name = table["name"]
                    count = conn.execute(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    ).fetchone()["count"]
                    table_counts[table_name] = count

                # データベースサイズ
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "database_path": str(self.db_path),
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / (1024 * 1024), 2),
                    "tables": table_counts,
                    "total_records": sum(table_counts.values()),
                }

        except Exception as e:
            self.logger.error(f"データベース情報取得エラー: {e}")
            return {"error": str(e)}
