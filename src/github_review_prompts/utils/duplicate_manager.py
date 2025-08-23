"""複数PRにまたがる重複コメント管理ユーティリティ"""

import logging
import hashlib
import json
from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from ..models import (
    OutsideDiffComment,
    OutsideDiffCommentCategory,
    OutsideDiffCommentSeverity,
)

logger = logging.getLogger(__name__)


class DuplicateCommentManager:
    """複数PRにまたがる重複コメント管理クラス"""

    def __init__(self, cache_dir: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".github_review_prompts_cache"
        )
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "comment_history.json"
        self.similarity_threshold = 0.8  # 類似度の閾値

    def track_comments(
        self, pr_url: str, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """コメントを追跡・記録

        Args:
            pr_url: プルリクエストURL
            comments: 範囲外コメントのリスト

        Returns:
            追跡結果
        """
        tracking_result = {
            "pr_url": pr_url,
            "timestamp": datetime.now().isoformat(),
            "new_comments": 0,
            "duplicate_comments": 0,
            "similar_comments": 0,
            "tracked_comments": [],
            "duplicates_found": [],
            "similar_patterns": [],
        }

        # 既存の履歴を読み込み
        history = self._load_comment_history()

        for comment in comments:
            comment_signature = self._generate_comment_signature(comment)

            # 重複チェック
            duplicate_info = self._check_for_duplicates(comment, history)
            if duplicate_info:
                tracking_result["duplicate_comments"] += 1
                tracking_result["duplicates_found"].append(duplicate_info)
            else:
                # 類似コメントチェック
                similar_info = self._check_for_similar(comment, history)
                if similar_info:
                    tracking_result["similar_comments"] += 1
                    tracking_result["similar_patterns"].append(similar_info)
                else:
                    tracking_result["new_comments"] += 1

            # 履歴に追加
            comment_record = {
                "signature": comment_signature,
                "pr_url": pr_url,
                "comment_id": comment.id,
                "title": comment.title,
                "file_path": comment.file_path,
                "line_range": comment.line_range,
                "category": comment.category.value,
                "severity": comment.severity.value,
                "timestamp": datetime.now().isoformat(),
                "content_hash": self._hash_content(comment.description),
                "keywords": self._extract_keywords(
                    comment.title + " " + comment.description
                ),
            }

            tracking_result["tracked_comments"].append(comment_record)

            # 履歴に追加（重複を避けるため、signatureで確認）
            if not any(record["signature"] == comment_signature for record in history):
                history.append(comment_record)

        # 履歴を保存
        self._save_comment_history(history)

        return tracking_result

    def find_cross_pr_duplicates(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """複数PR間での重複を検出

        Args:
            comments: 現在のコメントリスト

        Returns:
            重複検出結果
        """
        duplicate_analysis = {
            "total_comments": len(comments),
            "exact_duplicates": [],
            "similar_comments": [],
            "pattern_clusters": {},
            "recommendations": [],
        }

        history = self._load_comment_history()

        # 過去30日間のコメントのみを対象
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_history = [
            record
            for record in history
            if datetime.fromisoformat(record["timestamp"]) > cutoff_date
        ]

        for comment in comments:
            # 完全重複の検出
            exact_matches = self._find_exact_duplicates(comment, recent_history)
            if exact_matches:
                duplicate_analysis["exact_duplicates"].append(
                    {
                        "current_comment": {
                            "id": comment.id,
                            "title": comment.title,
                            "file_path": comment.file_path,
                        },
                        "matches": exact_matches,
                    }
                )

            # 類似コメントの検出
            similar_matches = self._find_similar_comments(comment, recent_history)
            if similar_matches:
                duplicate_analysis["similar_comments"].append(
                    {
                        "current_comment": {
                            "id": comment.id,
                            "title": comment.title,
                            "file_path": comment.file_path,
                        },
                        "similar_matches": similar_matches,
                    }
                )

        # パターンクラスターの分析
        duplicate_analysis["pattern_clusters"] = self._analyze_pattern_clusters(
            recent_history
        )

        # 推奨事項の生成
        duplicate_analysis["recommendations"] = (
            self._generate_duplicate_recommendations(duplicate_analysis)
        )

        return duplicate_analysis

    def generate_deduplication_strategy(
        self, duplicates_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """重複排除戦略を生成

        Args:
            duplicates_info: 重複情報

        Returns:
            重複排除戦略
        """
        strategy = {
            "approach": "prioritized",
            "priority_rules": [],
            "merge_candidates": [],
            "skip_candidates": [],
            "manual_review_required": [],
            "automation_opportunities": [],
        }

        exact_duplicates = duplicates_info.get("exact_duplicates", [])
        similar_comments = duplicates_info.get("similar_comments", [])

        # 完全重複の処理戦略
        for duplicate_group in exact_duplicates:
            current_comment = duplicate_group["current_comment"]
            matches = duplicate_group["matches"]

            # 最も最近のものを優先
            most_recent = max(matches, key=lambda x: x["timestamp"])

            if len(matches) > 2:  # 3回以上の重複
                strategy["skip_candidates"].append(
                    {
                        "comment_id": current_comment["id"],
                        "reason": f"過去{len(matches)}回の重複が検出されました",
                        "most_recent_pr": most_recent["pr_url"],
                        "action": "skip_with_reference",
                    }
                )
            else:
                strategy["merge_candidates"].append(
                    {
                        "comment_id": current_comment["id"],
                        "merge_with": most_recent,
                        "action": "merge_and_update",
                    }
                )

        # 類似コメントの処理戦略
        for similar_group in similar_comments:
            current_comment = similar_group["current_comment"]
            similar_matches = similar_group["similar_matches"]

            if len(similar_matches) > 1:
                strategy["manual_review_required"].append(
                    {
                        "comment_id": current_comment["id"],
                        "reason": "複数の類似コメントが存在",
                        "similar_count": len(similar_matches),
                        "action": "manual_consolidation",
                    }
                )

        # 優先順位ルールの設定
        strategy["priority_rules"] = [
            "セキュリティ関連のコメントは重複でも個別対応",
            "設定ファイルの変更は文脈に依存するため慎重に判断",
            "同一ファイル内の重複は統合を検討",
            "異なるPRの重複は参照リンクで対応",
        ]

        # 自動化機会の特定
        if len(exact_duplicates) > 3:
            strategy["automation_opportunities"].append(
                {
                    "type": "template_creation",
                    "description": "頻繁に重複するコメントのテンプレート化",
                    "estimated_time_saved": len(exact_duplicates) * 5,  # 分
                }
            )

        return strategy

    def _generate_comment_signature(self, comment: OutsideDiffComment) -> str:
        """コメントの署名を生成

        Args:
            comment: 範囲外コメント

        Returns:
            コメント署名
        """
        # ファイルパス、タイトル、重要度を組み合わせて署名を作成
        signature_data = f"{comment.file_path}:{comment.title}:{comment.severity.value}"
        return hashlib.md5(signature_data.encode()).hexdigest()

    def _hash_content(self, content: str) -> str:
        """コンテンツのハッシュを生成

        Args:
            content: コンテンツ文字列

        Returns:
            ハッシュ値
        """
        # 空白や改行を正規化してからハッシュ化
        normalized_content = " ".join(content.split())
        return hashlib.sha256(normalized_content.encode()).hexdigest()

    def _extract_keywords(self, text: str) -> List[str]:
        """テキストからキーワードを抽出

        Args:
            text: 対象テキスト

        Returns:
            キーワードリスト
        """
        # 簡単なキーワード抽出（実際の実装ではより高度な処理が可能）
        import re

        # 英数字の単語を抽出
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]*\b", text.lower())

        # 一般的すぎる単語を除外
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
        }
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]

        # 頻度でソートして上位10個を返す
        from collections import Counter

        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]

    def _check_for_duplicates(
        self, comment: OutsideDiffComment, history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """重複をチェック

        Args:
            comment: チェック対象のコメント
            history: コメント履歴

        Returns:
            重複が見つかった場合の情報
        """
        comment_signature = self._generate_comment_signature(comment)

        for record in history:
            if record["signature"] == comment_signature:
                return {
                    "type": "exact_duplicate",
                    "original_pr": record["pr_url"],
                    "original_timestamp": record["timestamp"],
                    "match_score": 1.0,
                }

        return None

    def _check_for_similar(
        self, comment: OutsideDiffComment, history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """類似コメントをチェック

        Args:
            comment: チェック対象のコメント
            history: コメント履歴

        Returns:
            類似コメントが見つかった場合の情報
        """
        current_keywords = set(
            self._extract_keywords(comment.title + " " + comment.description)
        )

        for record in history:
            # 同じファイルパスの場合のみチェック
            if record["file_path"] == comment.file_path:
                record_keywords = set(record.get("keywords", []))

                if current_keywords and record_keywords:
                    # Jaccard類似度を計算
                    intersection = len(current_keywords & record_keywords)
                    union = len(current_keywords | record_keywords)
                    similarity = intersection / union if union > 0 else 0

                    if similarity >= self.similarity_threshold:
                        return {
                            "type": "similar_comment",
                            "original_pr": record["pr_url"],
                            "original_timestamp": record["timestamp"],
                            "similarity_score": similarity,
                            "common_keywords": list(current_keywords & record_keywords),
                        }

        return None

    def _find_exact_duplicates(
        self, comment: OutsideDiffComment, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """完全重複を検索

        Args:
            comment: 対象コメント
            history: 履歴

        Returns:
            完全重複のリスト
        """
        content_hash = self._hash_content(comment.description)
        matches = []

        for record in history:
            if (
                record.get("content_hash") == content_hash
                and record["file_path"] == comment.file_path
            ):
                matches.append(record)

        return matches

    def _find_similar_comments(
        self, comment: OutsideDiffComment, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """類似コメントを検索

        Args:
            comment: 対象コメント
            history: 履歴

        Returns:
            類似コメントのリスト
        """
        current_keywords = set(
            self._extract_keywords(comment.title + " " + comment.description)
        )
        similar_matches = []

        for record in history:
            record_keywords = set(record.get("keywords", []))

            if current_keywords and record_keywords:
                intersection = len(current_keywords & record_keywords)
                union = len(current_keywords | record_keywords)
                similarity = intersection / union if union > 0 else 0

                if similarity >= self.similarity_threshold:
                    similar_matches.append(
                        {
                            **record,
                            "similarity_score": similarity,
                            "common_keywords": list(current_keywords & record_keywords),
                        }
                    )

        return similar_matches

    def _analyze_pattern_clusters(
        self, history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """パターンクラスターを分析

        Args:
            history: コメント履歴

        Returns:
            クラスター分析結果
        """
        clusters = {}

        # ファイルパス別のクラスター
        file_clusters = {}
        for record in history:
            file_path = record["file_path"]
            if file_path not in file_clusters:
                file_clusters[file_path] = []
            file_clusters[file_path].append(record)

        # 頻出ファイルの特定
        frequent_files = {
            file_path: records
            for file_path, records in file_clusters.items()
            if len(records) >= 3
        }

        clusters["frequent_files"] = frequent_files

        # カテゴリ別のクラスター
        category_clusters = {}
        for record in history:
            category = record["category"]
            if category not in category_clusters:
                category_clusters[category] = []
            category_clusters[category].append(record)

        clusters["category_distribution"] = {
            category: len(records) for category, records in category_clusters.items()
        }

        # キーワードベースのクラスター
        all_keywords = []
        for record in history:
            all_keywords.extend(record.get("keywords", []))

        from collections import Counter

        keyword_frequency = Counter(all_keywords)
        clusters["common_keywords"] = dict(keyword_frequency.most_common(20))

        return clusters

    def _generate_duplicate_recommendations(
        self, duplicate_analysis: Dict[str, Any]
    ) -> List[str]:
        """重複に関する推奨事項を生成

        Args:
            duplicate_analysis: 重複分析結果

        Returns:
            推奨事項のリスト
        """
        recommendations = []

        exact_duplicates_count = len(duplicate_analysis.get("exact_duplicates", []))
        similar_comments_count = len(duplicate_analysis.get("similar_comments", []))

        if exact_duplicates_count > 0:
            recommendations.append(
                f"🔄 {exact_duplicates_count}件の完全重複が検出されました。"
                "過去の対応を参照して効率化を図ってください。"
            )

        if similar_comments_count > 0:
            recommendations.append(
                f"🔍 {similar_comments_count}件の類似コメントが検出されました。"
                "統合可能かどうか確認してください。"
            )

        pattern_clusters = duplicate_analysis.get("pattern_clusters", {})
        frequent_files = pattern_clusters.get("frequent_files", {})

        if frequent_files:
            top_file = max(frequent_files.items(), key=lambda x: len(x[1]))
            recommendations.append(
                f"📁 {top_file[0]} で {len(top_file[1])}件の重複パターンが検出されました。"
                "このファイルの構造的な問題を検討してください。"
            )

        common_keywords = pattern_clusters.get("common_keywords", {})
        if common_keywords:
            top_keywords = list(common_keywords.keys())[:3]
            recommendations.append(
                f'🏷️ 頻出キーワード: {", ".join(top_keywords)}。'
                "これらの問題に対するテンプレート化を検討してください。"
            )

        return recommendations

    def _load_comment_history(self) -> List[Dict[str, Any]]:
        """コメント履歴を読み込み

        Returns:
            コメント履歴のリスト
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"履歴ファイルの読み込みに失敗: {e}")

        return []

    def _save_comment_history(self, history: List[Dict[str, Any]]) -> None:
        """コメント履歴を保存

        Args:
            history: 保存するコメント履歴
        """
        try:
            # 古い履歴を削除（90日以上前）
            cutoff_date = datetime.now() - timedelta(days=90)
            filtered_history = [
                record
                for record in history
                if datetime.fromisoformat(record["timestamp"]) > cutoff_date
            ]

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(filtered_history, f, ensure_ascii=False, indent=2)

        except IOError as e:
            self.logger.error(f"履歴ファイルの保存に失敗: {e}")

    def cleanup_old_cache(self, days: int = 90) -> None:
        """古いキャッシュをクリーンアップ

        Args:
            days: 保持日数
        """
        history = self._load_comment_history()
        cutoff_date = datetime.now() - timedelta(days=days)

        filtered_history = [
            record
            for record in history
            if datetime.fromisoformat(record["timestamp"]) > cutoff_date
        ]

        self.logger.info(
            f"キャッシュクリーンアップ: {len(history) - len(filtered_history)}件の古い記録を削除"
        )
        self._save_comment_history(filtered_history)
