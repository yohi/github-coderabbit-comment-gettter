"""範囲外コメント解決状態のハイブリッドストレージシステム"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import fcntl
from contextlib import contextmanager

from .resolution_detector import ResolutionStatus, ResolutionMethod

logger = logging.getLogger(__name__)


class StorageScope(Enum):
    """ストレージスコープ"""

    PERSONAL = "personal"
    SHARED = "shared"
    CACHE = "cache"


class ResolutionRecord:
    """解決記録クラス"""

    def __init__(
        self,
        comment_id: int,
        status: ResolutionStatus,
        method: Optional[ResolutionMethod] = None,
        **kwargs,
    ):
        self.comment_id = comment_id
        self.status = status
        self.method = method
        self.resolved_at = kwargs.get("resolved_at", datetime.now().isoformat())
        self.resolved_by = kwargs.get("resolved_by", os.getenv("USER", "unknown"))
        self.resolution_notes = kwargs.get("resolution_notes", "")
        self.confidence = kwargs.get("confidence", 0.0)
        self.validation_score = kwargs.get("validation_score", 0.0)
        self.pr_url = kwargs.get("pr_url", "")
        self.file_path = kwargs.get("file_path", "")
        self.line_range = kwargs.get("line_range", "")
        self.metadata = kwargs.get("metadata", {})

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "comment_id": self.comment_id,
            "status": (
                self.status.value
                if isinstance(self.status, ResolutionStatus)
                else self.status
            ),
            "method": (
                self.method.value
                if isinstance(self.method, ResolutionMethod)
                else self.method
            ),
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "resolution_notes": self.resolution_notes,
            "confidence": self.confidence,
            "validation_score": self.validation_score,
            "pr_url": self.pr_url,
            "file_path": self.file_path,
            "line_range": self.line_range,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResolutionRecord":
        """辞書から復元"""
        status = (
            ResolutionStatus(data["status"])
            if isinstance(data["status"], str)
            else data["status"]
        )
        method = (
            ResolutionMethod(data["method"])
            if data.get("method") and isinstance(data["method"], str)
            else data.get("method")
        )

        return cls(
            comment_id=data["comment_id"],
            status=status,
            method=method,
            resolved_at=data.get("resolved_at"),
            resolved_by=data.get("resolved_by"),
            resolution_notes=data.get("resolution_notes", ""),
            confidence=data.get("confidence", 0.0),
            validation_score=data.get("validation_score", 0.0),
            pr_url=data.get("pr_url", ""),
            file_path=data.get("file_path", ""),
            line_range=data.get("line_range", ""),
            metadata=data.get("metadata", {}),
        )


class HierarchicalResolutionStorage:
    """階層化解決状態ストレージ"""

    def __init__(
        self,
        project_root: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.logger = logging.getLogger(__name__)

        # プロジェクトルートの決定
        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = self._find_project_root()

        # 設定の読み込み
        self.config = config or self._load_config()

        # ストレージディレクトリの設定
        self.storage_dir = self.project_root / ".github-review-resolutions"
        self.storage_dir.mkdir(exist_ok=True)

        # ストレージファイルパス
        self.shared_file = self.storage_dir / "shared.json"
        self.personal_file = self.storage_dir / f"personal-{self._get_user_id()}.json"
        self.cache_dir = self.storage_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        # .gitignoreの設定
        self._setup_gitignore()

        # README.mdの作成
        self._create_readme()

    def get_resolution_status(self, comment_id: int) -> Optional[ResolutionRecord]:
        """解決状態を階層的に取得

        Args:
            comment_id: コメントID

        Returns:
            解決記録（見つからない場合はNone）
        """
        # 1. 個人ストレージから確認（最優先）
        if self.config.get("personal_storage", {}).get("enabled", True):
            personal_record = self._get_from_storage(self.personal_file, comment_id)
            if personal_record:
                personal_record.metadata["source"] = "personal"
                return personal_record

        # 2. 共有ストレージから確認
        if self.config.get("shared_storage", {}).get("enabled", True):
            shared_record = self._get_from_storage(self.shared_file, comment_id)
            if shared_record:
                shared_record.metadata["source"] = "shared"
                return shared_record

        # 3. キャッシュから確認
        cache_record = self._get_from_cache(comment_id)
        if cache_record:
            cache_record.metadata["source"] = "cache"
            return cache_record

        return None

    def save_resolution(
        self, record: ResolutionRecord, scope: StorageScope = StorageScope.PERSONAL
    ) -> bool:
        """解決状態を保存

        Args:
            record: 解決記録
            scope: 保存スコープ

        Returns:
            保存成功の場合True
        """
        try:
            if scope == StorageScope.PERSONAL:
                if not self.config.get("personal_storage", {}).get("enabled", True):
                    self.logger.warning("個人ストレージが無効です")
                    return False
                return self._save_to_storage(self.personal_file, record)

            elif scope == StorageScope.SHARED:
                if not self.config.get("shared_storage", {}).get("enabled", True):
                    self.logger.warning("共有ストレージが無効です")
                    return False

                # 共有ストレージは検証が必要
                if self.config.get("shared_storage", {}).get(
                    "require_validation", True
                ):
                    if record.validation_score < 60.0:
                        self.logger.warning(
                            f"検証スコアが不十分です: {record.validation_score}"
                        )
                        return False

                return self._save_to_storage(self.shared_file, record)

            elif scope == StorageScope.CACHE:
                return self._save_to_cache(record)

            return False

        except Exception as e:
            self.logger.error(f"解決状態の保存に失敗: {e}")
            return False

    def bulk_save_resolutions(
        self,
        records: List[ResolutionRecord],
        scope: StorageScope = StorageScope.PERSONAL,
    ) -> Dict[str, Any]:
        """解決状態を一括保存

        Args:
            records: 解決記録のリスト
            scope: 保存スコープ

        Returns:
            保存結果の統計
        """
        result = {"total": len(records), "saved": 0, "failed": 0, "errors": []}

        for record in records:
            try:
                if self.save_resolution(record, scope):
                    result["saved"] += 1
                else:
                    result["failed"] += 1
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"コメントID {record.comment_id}: {str(e)}")

        return result

    def promote_to_shared(
        self, comment_id: int, validation_required: bool = True
    ) -> bool:
        """個人状態を共有状態に昇格

        Args:
            comment_id: コメントID
            validation_required: 検証が必要かどうか

        Returns:
            昇格成功の場合True
        """
        # 個人ストレージから取得
        personal_record = self._get_from_storage(self.personal_file, comment_id)
        if not personal_record:
            self.logger.warning(
                f"個人ストレージにコメントID {comment_id} が見つかりません"
            )
            return False

        # 検証が必要な場合
        if validation_required and personal_record.validation_score < 60.0:
            self.logger.warning(
                f"検証スコアが不十分です: {personal_record.validation_score}"
            )
            return False

        # 共有ストレージに保存
        if self.save_resolution(personal_record, StorageScope.SHARED):
            # 個人ストレージから削除
            self._remove_from_storage(self.personal_file, comment_id)
            self.logger.info(f"コメントID {comment_id} を共有ストレージに昇格しました")
            return True

        return False

    def get_resolution_statistics(
        self, pr_url: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """解決統計を取得

        Args:
            pr_url: 特定のPRに限定する場合のURL
            days: 統計期間（日数）

        Returns:
            統計情報
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        stats = {
            "period_days": days,
            "total_resolutions": 0,
            "status_breakdown": {},
            "method_breakdown": {},
            "source_breakdown": {"personal": 0, "shared": 0, "cache": 0},
            "average_confidence": 0.0,
            "average_validation_score": 0.0,
            "recent_activity": [],
            "top_resolvers": {},
            "pr_breakdown": {},
        }

        all_records = []

        # 全ストレージから記録を収集
        for storage_file, source in [
            (self.personal_file, "personal"),
            (self.shared_file, "shared"),
        ]:
            records = self._load_all_from_storage(storage_file)
            for record in records:
                # 期間フィルタ
                if datetime.fromisoformat(record.resolved_at) < cutoff_date:
                    continue

                # PRフィルタ
                if pr_url and record.pr_url != pr_url:
                    continue

                record.metadata["source"] = source
                all_records.append(record)

        # 統計計算
        if all_records:
            stats["total_resolutions"] = len(all_records)

            total_confidence = 0.0
            total_validation_score = 0.0

            for record in all_records:
                # 状態別集計
                status = (
                    record.status.value
                    if isinstance(record.status, ResolutionStatus)
                    else record.status
                )
                stats["status_breakdown"][status] = (
                    stats["status_breakdown"].get(status, 0) + 1
                )

                # 方法別集計
                if record.method:
                    method = (
                        record.method.value
                        if isinstance(record.method, ResolutionMethod)
                        else record.method
                    )
                    stats["method_breakdown"][method] = (
                        stats["method_breakdown"].get(method, 0) + 1
                    )

                # ソース別集計
                source = record.metadata.get("source", "unknown")
                stats["source_breakdown"][source] = (
                    stats["source_breakdown"].get(source, 0) + 1
                )

                # 解決者別集計
                resolver = record.resolved_by
                stats["top_resolvers"][resolver] = (
                    stats["top_resolvers"].get(resolver, 0) + 1
                )

                # PR別集計
                if record.pr_url:
                    stats["pr_breakdown"][record.pr_url] = (
                        stats["pr_breakdown"].get(record.pr_url, 0) + 1
                    )

                # 平均値計算用
                total_confidence += record.confidence
                total_validation_score += record.validation_score

                # 最近のアクティビティ
                if len(stats["recent_activity"]) < 10:
                    stats["recent_activity"].append(
                        {
                            "comment_id": record.comment_id,
                            "status": status,
                            "resolved_at": record.resolved_at,
                            "resolved_by": record.resolved_by,
                        }
                    )

            # 平均値
            stats["average_confidence"] = total_confidence / len(all_records)
            stats["average_validation_score"] = total_validation_score / len(
                all_records
            )

            # 最近のアクティビティをソート
            stats["recent_activity"].sort(key=lambda x: x["resolved_at"], reverse=True)

        return stats

    def cleanup_old_resolutions(self, days: int = 90) -> Dict[str, Any]:
        """古い解決記録をクリーンアップ

        Args:
            days: 保持日数

        Returns:
            クリーンアップ結果
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cleanup_result = {
            "cutoff_date": cutoff_date.isoformat(),
            "personal_cleaned": 0,
            "shared_cleaned": 0,
            "cache_cleaned": 0,
            "total_cleaned": 0,
        }

        # 個人ストレージのクリーンアップ
        if self.personal_file.exists():
            cleaned = self._cleanup_storage_file(self.personal_file, cutoff_date)
            cleanup_result["personal_cleaned"] = cleaned

        # 共有ストレージのクリーンアップ（より長期保持）
        shared_cutoff = datetime.now() - timedelta(days=days * 2)  # 共有は2倍長く保持
        if self.shared_file.exists():
            cleaned = self._cleanup_storage_file(self.shared_file, shared_cutoff)
            cleanup_result["shared_cleaned"] = cleaned

        # キャッシュのクリーンアップ
        cache_cleaned = self._cleanup_cache(cutoff_date)
        cleanup_result["cache_cleaned"] = cache_cleaned

        cleanup_result["total_cleaned"] = (
            cleanup_result["personal_cleaned"]
            + cleanup_result["shared_cleaned"]
            + cleanup_result["cache_cleaned"]
        )

        self.logger.info(
            f"クリーンアップ完了: {cleanup_result['total_cleaned']}件の古い記録を削除"
        )
        return cleanup_result

    def _find_project_root(self) -> Path:
        """プロジェクトルートを探索"""
        current = Path.cwd()

        # .gitディレクトリを探す
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent

        # 見つからない場合は現在のディレクトリ
        return current

    def _load_config(self) -> Dict[str, Any]:
        """設定を読み込み"""
        default_config = {
            "personal_storage": {
                "enabled": True,
                "git_managed": False,
                "auto_cleanup_days": 30,
            },
            "shared_storage": {
                "enabled": True,
                "git_managed": True,
                "require_validation": True,
                "auto_promote": False,
            },
            "conflict_resolution": "personal_priority",
        }

        # プロジェクト設定ファイルを探す
        config_files = [
            self.project_root / ".github-review-prompts.yml",
            self.project_root / ".github-review-prompts.yaml",
            self.project_root / ".github-review-prompts.json",
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    if config_file.suffix in [".yml", ".yaml"]:
                        import yaml

                        with open(config_file, "r", encoding="utf-8") as f:
                            file_config = yaml.safe_load(f)
                    else:
                        with open(config_file, "r", encoding="utf-8") as f:
                            file_config = json.load(f)

                    # デフォルト設定をマージ
                    default_config.update(file_config.get("resolution_storage", {}))
                    break
                except Exception as e:
                    self.logger.warning(
                        f"設定ファイルの読み込みに失敗: {config_file}: {e}"
                    )

        return default_config

    def _get_user_id(self) -> str:
        """ユーザーIDを取得"""
        user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
        # ファイル名に使えない文字を置換
        return user.replace("/", "_").replace("\\", "_")

    def _setup_gitignore(self):
        """.gitignoreを設定"""
        gitignore_file = self.storage_dir / ".gitignore"

        gitignore_content = """# 個人の解決状態管理ファイル
personal-*.json
cache/

# 共有ファイルはGit管理対象
!shared.json
!README.md
!.gitignore
"""

        try:
            with open(gitignore_file, "w", encoding="utf-8") as f:
                f.write(gitignore_content)
        except Exception as e:
            self.logger.warning(f".gitignoreの作成に失敗: {e}")

    def _create_readme(self):
        """README.mdを作成"""
        readme_file = self.storage_dir / "README.md"

        if readme_file.exists():
            return

        readme_content = """# GitHub Review Resolutions

このディレクトリは範囲外コメントの解決状態を管理します。

## ファイル構成

- `shared.json` - チーム共有の解決状態（Git管理対象）
- `personal-*.json` - 個人の解決状態（Git管理対象外）
- `cache/` - 一時キャッシュ（Git管理対象外）

## 使用方法

解決状態は自動的に検出・保存されます。手動での編集は推奨されません。

## 設定

プロジェクトルートに `.github-review-prompts.yml` を作成して設定をカスタマイズできます。

```yaml
resolution_storage:
  personal_storage:
    enabled: true
    auto_cleanup_days: 30
  shared_storage:
    enabled: true
    require_validation: true
```
"""

        try:
            with open(readme_file, "w", encoding="utf-8") as f:
                f.write(readme_content)
        except Exception as e:
            self.logger.warning(f"README.mdの作成に失敗: {e}")

    @contextmanager
    def _file_lock(self, file_path: Path):
        """ファイルロック"""
        lock_file = file_path.with_suffix(file_path.suffix + ".lock")

        try:
            with open(lock_file, "w") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                yield
        except Exception as e:
            self.logger.warning(f"ファイルロックに失敗: {e}")
            yield
        finally:
            try:
                lock_file.unlink(missing_ok=True)
            except:
                pass

    def _get_from_storage(
        self, storage_file: Path, comment_id: int
    ) -> Optional[ResolutionRecord]:
        """ストレージファイルから記録を取得"""
        if not storage_file.exists():
            return None

        try:
            with self._file_lock(storage_file):
                with open(storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for record_data in data.get("resolutions", []):
                    if record_data["comment_id"] == comment_id:
                        return ResolutionRecord.from_dict(record_data)

        except Exception as e:
            self.logger.error(
                f"ストレージファイルの読み込みに失敗: {storage_file}: {e}"
            )

        return None

    def _save_to_storage(self, storage_file: Path, record: ResolutionRecord) -> bool:
        """ストレージファイルに記録を保存"""
        try:
            with self._file_lock(storage_file):
                # 既存データを読み込み
                data = {"resolutions": [], "metadata": {}}
                if storage_file.exists():
                    with open(storage_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                # 既存記録を更新または追加
                resolutions = data.get("resolutions", [])
                updated = False

                for i, existing in enumerate(resolutions):
                    if existing["comment_id"] == record.comment_id:
                        resolutions[i] = record.to_dict()
                        updated = True
                        break

                if not updated:
                    resolutions.append(record.to_dict())

                data["resolutions"] = resolutions
                data["metadata"] = {
                    "last_updated": datetime.now().isoformat(),
                    "total_records": len(resolutions),
                }

                # ファイルに保存
                with open(storage_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                return True

        except Exception as e:
            self.logger.error(f"ストレージファイルの保存に失敗: {storage_file}: {e}")
            return False

    def _load_all_from_storage(self, storage_file: Path) -> List[ResolutionRecord]:
        """ストレージファイルから全記録を読み込み"""
        if not storage_file.exists():
            return []

        try:
            with open(storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            records = []
            for record_data in data.get("resolutions", []):
                records.append(ResolutionRecord.from_dict(record_data))

            return records

        except Exception as e:
            self.logger.error(
                f"ストレージファイルの読み込みに失敗: {storage_file}: {e}"
            )
            return []

    def _remove_from_storage(self, storage_file: Path, comment_id: int) -> bool:
        """ストレージファイルから記録を削除"""
        if not storage_file.exists():
            return False

        try:
            with self._file_lock(storage_file):
                with open(storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                resolutions = data.get("resolutions", [])
                original_count = len(resolutions)

                # 該当記録を削除
                resolutions = [r for r in resolutions if r["comment_id"] != comment_id]

                if len(resolutions) < original_count:
                    data["resolutions"] = resolutions
                    data["metadata"]["last_updated"] = datetime.now().isoformat()
                    data["metadata"]["total_records"] = len(resolutions)

                    with open(storage_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    return True

        except Exception as e:
            self.logger.error(
                f"ストレージファイルからの削除に失敗: {storage_file}: {e}"
            )

        return False

    def _cleanup_storage_file(self, storage_file: Path, cutoff_date: datetime) -> int:
        """ストレージファイルをクリーンアップ"""
        if not storage_file.exists():
            return 0

        try:
            with self._file_lock(storage_file):
                with open(storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                resolutions = data.get("resolutions", [])
                original_count = len(resolutions)

                # 古い記録を削除
                filtered_resolutions = []
                for record_data in resolutions:
                    resolved_at = datetime.fromisoformat(record_data["resolved_at"])
                    if resolved_at >= cutoff_date:
                        filtered_resolutions.append(record_data)

                cleaned_count = original_count - len(filtered_resolutions)

                if cleaned_count > 0:
                    data["resolutions"] = filtered_resolutions
                    data["metadata"]["last_updated"] = datetime.now().isoformat()
                    data["metadata"]["total_records"] = len(filtered_resolutions)

                    with open(storage_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                return cleaned_count

        except Exception as e:
            self.logger.error(
                f"ストレージファイルのクリーンアップに失敗: {storage_file}: {e}"
            )
            return 0

    def _get_from_cache(self, comment_id: int) -> Optional[ResolutionRecord]:
        """キャッシュから記録を取得"""
        cache_file = self.cache_dir / f"{comment_id}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # キャッシュの有効期限チェック（1時間）
            cached_at = datetime.fromisoformat(data["cached_at"])
            if datetime.now() - cached_at > timedelta(hours=1):
                cache_file.unlink()
                return None

            return ResolutionRecord.from_dict(data["record"])

        except Exception as e:
            self.logger.warning(f"キャッシュの読み込みに失敗: {cache_file}: {e}")
            return None

    def _save_to_cache(self, record: ResolutionRecord) -> bool:
        """キャッシュに記録を保存"""
        cache_file = self.cache_dir / f"{record.comment_id}.json"

        try:
            cache_data = {
                "record": record.to_dict(),
                "cached_at": datetime.now().isoformat(),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            self.logger.error(f"キャッシュの保存に失敗: {cache_file}: {e}")
            return False

    def _cleanup_cache(self, cutoff_date: datetime) -> int:
        """キャッシュをクリーンアップ"""
        cleaned_count = 0

        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    cached_at = datetime.fromisoformat(data["cached_at"])
                    if cached_at < cutoff_date:
                        cache_file.unlink()
                        cleaned_count += 1

                except Exception as e:
                    self.logger.warning(
                        f"キャッシュファイルの処理に失敗: {cache_file}: {e}"
                    )
                    # 破損したファイルは削除
                    cache_file.unlink()
                    cleaned_count += 1

        except Exception as e:
            self.logger.error(f"キャッシュクリーンアップに失敗: {e}")

        return cleaned_count
