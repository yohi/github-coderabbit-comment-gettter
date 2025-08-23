"""AIエージェント向けの作業指示最適化ユーティリティ"""

import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from ..models import (
    OutsideDiffComment,
    OutsideDiffCommentCategory,
    OutsideDiffCommentSeverity,
)

logger = logging.getLogger(__name__)


class AIAgentOptimizer:
    """AIエージェント向けの作業指示最適化クラス"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def optimize_work_instructions(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, Any]:
        """AIエージェント向けの作業指示を最適化

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            最適化された作業指示
        """
        optimization_result = {
            "total_comments": len(comments),
            "estimated_time_minutes": 0,
            "complexity_score": 0,
            "recommended_approach": "sequential",
            "batch_groups": [],
            "priority_order": [],
            "risk_assessment": {},
            "automation_opportunities": [],
            "manual_review_required": [],
        }

        if not comments:
            return optimization_result

        # 複雑度スコアの計算
        complexity_score = self._calculate_complexity_score(comments)
        optimization_result["complexity_score"] = complexity_score

        # 推定作業時間の計算
        estimated_time = self._estimate_work_time(comments)
        optimization_result["estimated_time_minutes"] = estimated_time

        # 最適なアプローチの決定
        approach = self._determine_optimal_approach(comments, complexity_score)
        optimization_result["recommended_approach"] = approach

        # バッチグループの作成
        batch_groups = self._create_batch_groups(comments)
        optimization_result["batch_groups"] = batch_groups

        # 優先順序の決定
        priority_order = self._determine_priority_order(comments)
        optimization_result["priority_order"] = priority_order

        # リスク評価
        risk_assessment = self._assess_risks(comments)
        optimization_result["risk_assessment"] = risk_assessment

        # 自動化機会の特定
        automation_opportunities = self._identify_automation_opportunities(comments)
        optimization_result["automation_opportunities"] = automation_opportunities

        # 手動レビュー必須項目の特定
        manual_review_required = self._identify_manual_review_items(comments)
        optimization_result["manual_review_required"] = manual_review_required

        return optimization_result

    def _calculate_complexity_score(self, comments: List[OutsideDiffComment]) -> float:
        """複雑度スコアを計算

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            複雑度スコア（0-100）
        """
        if not comments:
            return 0.0

        total_score = 0.0

        for comment in comments:
            score = 0.0

            # 重要度による重み付け
            severity_weights = {
                OutsideDiffCommentSeverity.CAUTION: 10.0,
                OutsideDiffCommentSeverity.WARNING: 5.0,
                OutsideDiffCommentSeverity.INFO: 2.0,
            }
            score += severity_weights.get(comment.severity, 2.0)

            # 行範囲による重み付け
            if comment.line_details and comment.line_details.get("line_count"):
                line_count = comment.line_details["line_count"]
                if line_count > 50:
                    score += 8.0
                elif line_count > 20:
                    score += 5.0
                elif line_count > 10:
                    score += 3.0
                else:
                    score += 1.0

            # コード修正案の複雑度による重み付け
            if comment.suggestion_details:
                complexity = comment.suggestion_details.get("complexity", "low")
                complexity_weights = {"high": 8.0, "medium": 4.0, "low": 1.0}
                score += complexity_weights.get(complexity, 1.0)

            # ファイルタイプによる重み付け
            if comment.file_details:
                if comment.file_details.get("is_config"):
                    score += 3.0  # 設定ファイルは慎重に
                if comment.file_details.get("language") in [
                    "terraform",
                    "yaml",
                    "json",
                ]:
                    score += 2.0  # インフラ系は重要

            total_score += score

        # 正規化（0-100の範囲）
        max_possible_score = len(comments) * 30.0  # 理論的最大値
        normalized_score = min(100.0, (total_score / max_possible_score) * 100.0)

        return round(normalized_score, 2)

    def _estimate_work_time(self, comments: List[OutsideDiffComment]) -> int:
        """作業時間を推定

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            推定作業時間（分）
        """
        if not comments:
            return 0

        total_minutes = 0

        # 基本時間（コメント理解・ファイル確認）
        base_time_per_comment = 3  # 分
        total_minutes += len(comments) * base_time_per_comment

        for comment in comments:
            additional_time = 0

            # 重要度による追加時間
            severity_time = {
                OutsideDiffCommentSeverity.CAUTION: 15,  # 緊急対応
                OutsideDiffCommentSeverity.WARNING: 8,  # 重要対応
                OutsideDiffCommentSeverity.INFO: 3,  # 低優先対応
            }
            additional_time += severity_time.get(comment.severity, 3)

            # 行範囲による追加時間
            if comment.line_details and comment.line_details.get("line_count"):
                line_count = comment.line_details["line_count"]
                if line_count > 50:
                    additional_time += 20
                elif line_count > 20:
                    additional_time += 10
                elif line_count > 10:
                    additional_time += 5

            # コード修正案の複雑度による追加時間
            if comment.suggestion_details:
                complexity = comment.suggestion_details.get("complexity", "low")
                complexity_time = {"high": 25, "medium": 12, "low": 5}
                additional_time += complexity_time.get(complexity, 5)

            total_minutes += additional_time

        return total_minutes

    def _determine_optimal_approach(
        self, comments: List[OutsideDiffComment], complexity_score: float
    ) -> str:
        """最適なアプローチを決定

        Args:
            comments: 範囲外コメントのリスト
            complexity_score: 複雑度スコア

        Returns:
            推奨アプローチ
        """
        comment_count = len(comments)

        # 複雑度とコメント数に基づく判定
        if complexity_score > 70 or comment_count > 15:
            return "phased"  # 段階的実行
        elif complexity_score > 40 or comment_count > 8:
            return "batched"  # バッチ処理
        else:
            return "sequential"  # 順次処理

    def _create_batch_groups(
        self, comments: List[OutsideDiffComment]
    ) -> List[Dict[str, Any]]:
        """バッチグループを作成

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            バッチグループのリスト
        """
        groups = []

        # ファイル別グループ化
        file_groups = {}
        for comment in comments:
            file_path = comment.file_path
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(comment)

        # 各ファイルグループをバッチとして作成
        for file_path, file_comments in file_groups.items():
            if len(file_comments) > 1:
                # 重要度でソート
                sorted_comments = sorted(
                    file_comments,
                    key=lambda x: (
                        0
                        if x.severity == OutsideDiffCommentSeverity.CAUTION
                        else (
                            1 if x.severity == OutsideDiffCommentSeverity.WARNING else 2
                        )
                    ),
                )

                groups.append(
                    {
                        "type": "file_batch",
                        "file_path": file_path,
                        "comment_count": len(sorted_comments),
                        "comments": [c.id for c in sorted_comments],
                        "estimated_time_minutes": self._estimate_work_time(
                            sorted_comments
                        ),
                        "complexity_score": self._calculate_complexity_score(
                            sorted_comments
                        ),
                    }
                )

        return groups

    def _determine_priority_order(
        self, comments: List[OutsideDiffComment]
    ) -> List[Dict[str, Any]]:
        """優先順序を決定

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            優先順序付きコメントリスト
        """
        priority_list = []

        # 多次元ソート
        complexity_order = {"low": 0, "medium": 1, "high": 2}
        sorted_comments = sorted(
            comments,
            key=lambda x: (
                # 1. 重要度（数値が小さいほど高優先）
                (
                    0
                    if x.severity == OutsideDiffCommentSeverity.CAUTION
                    else 1 if x.severity == OutsideDiffCommentSeverity.WARNING else 2
                ),
                # 2. セキュリティ関連かどうか
                (
                    0
                    if any(
                        keyword in x.title.lower() or keyword in x.description.lower()
                        for keyword in ["security", "token", "credential", "auth"]
                    )
                    else 1
                ),
                # 3. 設定ファイルかどうか
                0 if x.file_details and x.file_details.get("is_config") else 1,
                # 4. 複雑度（簡単なものから）
                complexity_order.get(
                    (
                        x.suggestion_details.get("complexity", "low")
                        if x.suggestion_details
                        else "low"
                    ),
                    0,
                ),
                # 5. ファイルパス（アルファベット順）
                x.file_path,
            ),
        )

        for i, comment in enumerate(sorted_comments, 1):
            priority_item = {
                "rank": i,
                "comment_id": comment.id,
                "title": comment.title,
                "file_path": comment.file_path,
                "line_range": comment.line_range,
                "severity": comment.severity.value,
                "estimated_time_minutes": self._estimate_work_time([comment]),
                "dependencies": self._find_dependencies(comment, comments),
                "risk_level": self._assess_comment_risk(comment),
            }
            priority_list.append(priority_item)

        return priority_list

    def _assess_risks(self, comments: List[OutsideDiffComment]) -> Dict[str, Any]:
        """リスク評価を実行

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            リスク評価結果
        """
        risks = {
            "overall_risk_level": "low",
            "security_risks": [],
            "breaking_change_risks": [],
            "performance_risks": [],
            "compatibility_risks": [],
            "mitigation_strategies": [],
        }

        security_count = 0
        breaking_count = 0
        performance_count = 0

        for comment in comments:
            # セキュリティリスク
            security_keywords = [
                "security",
                "token",
                "credential",
                "auth",
                "permission",
                "access",
            ]
            if any(
                keyword in comment.title.lower()
                or keyword in comment.description.lower()
                for keyword in security_keywords
            ):
                security_count += 1
                risks["security_risks"].append(
                    {
                        "comment_id": comment.id,
                        "title": comment.title,
                        "risk_description": "セキュリティ関連の変更が必要",
                    }
                )

            # 破壊的変更リスク
            breaking_keywords = [
                "breaking",
                "incompatible",
                "deprecated",
                "remove",
                "delete",
            ]
            if any(
                keyword in comment.title.lower()
                or keyword in comment.description.lower()
                for keyword in breaking_keywords
            ):
                breaking_count += 1
                risks["breaking_change_risks"].append(
                    {
                        "comment_id": comment.id,
                        "title": comment.title,
                        "risk_description": "破壊的変更の可能性",
                    }
                )

            # パフォーマンスリスク
            performance_keywords = [
                "performance",
                "slow",
                "timeout",
                "memory",
                "cpu",
                "optimization",
            ]
            if any(
                keyword in comment.title.lower()
                or keyword in comment.description.lower()
                for keyword in performance_keywords
            ):
                performance_count += 1
                risks["performance_risks"].append(
                    {
                        "comment_id": comment.id,
                        "title": comment.title,
                        "risk_description": "パフォーマンスへの影響の可能性",
                    }
                )

        # 全体的なリスクレベルの決定
        total_high_risk = security_count + breaking_count
        if total_high_risk > 3 or security_count > 1:
            risks["overall_risk_level"] = "high"
        elif total_high_risk > 1 or performance_count > 2:
            risks["overall_risk_level"] = "medium"

        # 軽減戦略の提案
        if security_count > 0:
            risks["mitigation_strategies"].append(
                "セキュリティ関連の変更は段階的に実装し、各段階で動作確認を実施"
            )
        if breaking_count > 0:
            risks["mitigation_strategies"].append(
                "破壊的変更は別ブランチで実装し、十分なテストを実施後にマージ"
            )
        if performance_count > 0:
            risks["mitigation_strategies"].append(
                "パフォーマンス関連の変更は事前・事後でベンチマークを取得"
            )

        return risks

    def _identify_automation_opportunities(
        self, comments: List[OutsideDiffComment]
    ) -> List[Dict[str, Any]]:
        """自動化機会を特定

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            自動化機会のリスト
        """
        opportunities = []

        # パターン別の自動化機会
        patterns = {
            "formatting": {
                "keywords": ["format", "indent", "spacing", "style", "lint"],
                "automation_type": "code_formatter",
                "confidence": "high",
            },
            "import_sorting": {
                "keywords": ["import", "sort", "order", "organize"],
                "automation_type": "import_organizer",
                "confidence": "high",
            },
            "variable_rename": {
                "keywords": ["rename", "variable", "consistent", "naming"],
                "automation_type": "refactoring_tool",
                "confidence": "medium",
            },
            "documentation": {
                "keywords": ["comment", "document", "readme", "description"],
                "automation_type": "doc_generator",
                "confidence": "medium",
            },
        }

        for comment in comments:
            text = f"{comment.title} {comment.description}".lower()

            for pattern_name, pattern_info in patterns.items():
                if any(keyword in text for keyword in pattern_info["keywords"]):
                    opportunities.append(
                        {
                            "comment_id": comment.id,
                            "pattern": pattern_name,
                            "automation_type": pattern_info["automation_type"],
                            "confidence": pattern_info["confidence"],
                            "description": f"{pattern_name}の自動化が可能",
                            "estimated_time_saved_minutes": (
                                5 if pattern_info["confidence"] == "high" else 3
                            ),
                        }
                    )

        return opportunities

    def _identify_manual_review_items(
        self, comments: List[OutsideDiffComment]
    ) -> List[Dict[str, Any]]:
        """手動レビュー必須項目を特定

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            手動レビュー必須項目のリスト
        """
        manual_items = []

        for comment in comments:
            requires_manual = False
            reasons = []

            # セキュリティ関連は手動レビュー必須
            security_keywords = [
                "security",
                "token",
                "credential",
                "auth",
                "permission",
            ]
            if any(
                keyword in comment.title.lower()
                or keyword in comment.description.lower()
                for keyword in security_keywords
            ):
                requires_manual = True
                reasons.append("セキュリティ関連の変更")

            # 複雑な変更は手動レビュー必須
            if (
                comment.suggestion_details
                and comment.suggestion_details.get("complexity") == "high"
            ):
                requires_manual = True
                reasons.append("高複雑度の変更")

            # 大きな行範囲は手動レビュー必須
            if comment.line_details and comment.line_details.get("line_count", 0) > 30:
                requires_manual = True
                reasons.append("大規模な変更範囲")

            # 設定ファイルは手動レビュー推奨
            if comment.file_details and comment.file_details.get("is_config"):
                requires_manual = True
                reasons.append("設定ファイルの変更")

            if requires_manual:
                manual_items.append(
                    {
                        "comment_id": comment.id,
                        "title": comment.title,
                        "file_path": comment.file_path,
                        "reasons": reasons,
                        "review_priority": (
                            "high" if "セキュリティ関連の変更" in reasons else "medium"
                        ),
                    }
                )

        return manual_items

    def _find_dependencies(
        self, comment: OutsideDiffComment, all_comments: List[OutsideDiffComment]
    ) -> List[int]:
        """コメント間の依存関係を特定

        Args:
            comment: 対象コメント
            all_comments: 全コメントのリスト

        Returns:
            依存するコメントIDのリスト
        """
        dependencies = []

        # 同じファイル内の他のコメントとの依存関係をチェック
        for other_comment in all_comments:
            if other_comment.id == comment.id:
                continue

            # 同じファイルで行範囲が重複している場合
            if other_comment.file_path == comment.file_path:
                if self._check_line_range_overlap(
                    comment.line_range, other_comment.line_range
                ):
                    dependencies.append(other_comment.id)

        return dependencies

    def _check_line_range_overlap(self, range1: str, range2: str) -> bool:
        """行範囲の重複をチェック

        Args:
            range1: 行範囲1
            range2: 行範囲2

        Returns:
            重複している場合True
        """

        def parse_range(range_str: str) -> Tuple[int, int]:
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
                return start, end
            else:
                line = int(range_str)
                return line, line

        try:
            start1, end1 = parse_range(range1)
            start2, end2 = parse_range(range2)

            # 重複チェック
            return not (end1 < start2 or end2 < start1)
        except (ValueError, AttributeError):
            return False

    def _assess_comment_risk(self, comment: OutsideDiffComment) -> str:
        """個別コメントのリスクレベルを評価

        Args:
            comment: 対象コメント

        Returns:
            リスクレベル（high/medium/low）
        """
        risk_score = 0

        # 重要度による基本スコア
        if comment.severity == OutsideDiffCommentSeverity.CAUTION:
            risk_score += 3
        elif comment.severity == OutsideDiffCommentSeverity.WARNING:
            risk_score += 2
        else:
            risk_score += 1

        # セキュリティ関連
        security_keywords = ["security", "token", "credential", "auth"]
        if any(
            keyword in comment.title.lower() or keyword in comment.description.lower()
            for keyword in security_keywords
        ):
            risk_score += 3

        # 設定ファイル
        if comment.file_details and comment.file_details.get("is_config"):
            risk_score += 2

        # 大きな変更範囲
        if comment.line_details and comment.line_details.get("line_count", 0) > 30:
            risk_score += 2

        # 高複雑度
        if (
            comment.suggestion_details
            and comment.suggestion_details.get("complexity") == "high"
        ):
            risk_score += 2

        if risk_score >= 6:
            return "high"
        elif risk_score >= 3:
            return "medium"
        else:
            return "low"
