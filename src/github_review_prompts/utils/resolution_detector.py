"""範囲外コメントの解決済み検出ユーティリティ"""

import logging
import re
from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime
from enum import Enum

from ..models import OutsideDiffComment

logger = logging.getLogger(__name__)


class ResolutionMethod(Enum):
    """解決方法の種類"""

    MANUAL = "manual"
    AI_AUTOMATED = "ai_automated"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
    WONT_FIX = "wont_fix"
    DEFERRED = "deferred"


class ResolutionStatus(Enum):
    """解決状態"""

    UNRESOLVED = "unresolved"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class OutsideDiffResolutionDetector:
    """範囲外コメントの解決済み検出クラス"""

    # 解決済みマーカーパターン
    RESOLUTION_PATTERNS = {
        ResolutionStatus.RESOLVED: {
            "patterns": [
                # 日本語パターン
                re.compile(
                    r"✅.*?(?:対応完了|修正完了|解決完了|fixed|resolved|done)",
                    re.IGNORECASE,
                ),
                re.compile(r"(?:対応完了|修正完了|解決完了).*?✅", re.IGNORECASE),
                re.compile(
                    r"\[(?:RESOLVED|FIXED|COMPLETED|完了)\].*?範囲外TODO", re.IGNORECASE
                ),
                re.compile(
                    r"範囲外TODO.*?\[(?:RESOLVED|FIXED|COMPLETED|完了)\]", re.IGNORECASE
                ),
                # 英語パターン
                re.compile(
                    r"✅.*?(?:completed|finished|implemented|addressed)", re.IGNORECASE
                ),
                re.compile(
                    r"(?:successfully|properly).*?(?:fixed|resolved|implemented)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"issue.*?(?:has been|is now).*?(?:resolved|fixed)", re.IGNORECASE
                ),
                # 記号パターン
                re.compile(r"✅.*?(?:👍|🎉|💯)", re.IGNORECASE),
                re.compile(r"(?:👍|🎉|💯).*?✅", re.IGNORECASE),
            ],
            "confidence": 0.9,
        },
        ResolutionStatus.SKIPPED: {
            "patterns": [
                # 日本語パターン
                re.compile(
                    r"❌.*?(?:対応不要|スキップ|skip|wont.*?fix)", re.IGNORECASE
                ),
                re.compile(r"(?:対応不要|スキップ).*?❌", re.IGNORECASE),
                re.compile(
                    r"\[(?:SKIPPED|WONT.*?FIX|対応不要)\].*?範囲外TODO", re.IGNORECASE
                ),
                # 英語パターン
                re.compile(
                    r"❌.*?(?:not.*?needed|unnecessary|out.*?of.*?scope)", re.IGNORECASE
                ),
                re.compile(r"(?:decided|choosing).*?(?:not.*?to|skip)", re.IGNORECASE),
                re.compile(r"wont.*?fix.*?because", re.IGNORECASE),
                # 理由付きスキップ
                re.compile(
                    r"(?:intentional|by.*?design|working.*?as.*?intended)",
                    re.IGNORECASE,
                ),
            ],
            "confidence": 0.85,
        },
        ResolutionStatus.IN_PROGRESS: {
            "patterns": [
                # 日本語パターン
                re.compile(
                    r"🔄.*?(?:対応中|作業中|進行中|in.*?progress)", re.IGNORECASE
                ),
                re.compile(r"(?:対応中|作業中|進行中).*?🔄", re.IGNORECASE),
                re.compile(
                    r"\[(?:WIP|作業中|IN.*?PROGRESS)\].*?範囲外TODO", re.IGNORECASE
                ),
                # 英語パターン
                re.compile(
                    r"🔄.*?(?:working.*?on|investigating|in.*?progress)", re.IGNORECASE
                ),
                re.compile(r"(?:started|beginning).*?(?:to|work.*?on)", re.IGNORECASE),
                re.compile(r"currently.*?(?:addressing|fixing|working)", re.IGNORECASE),
            ],
            "confidence": 0.8,
        },
        ResolutionStatus.BLOCKED: {
            "patterns": [
                # 日本語パターン
                re.compile(r"🚫.*?(?:ブロック|阻害|blocked|dependency)", re.IGNORECASE),
                re.compile(r"(?:ブロック|阻害|依存関係).*?🚫", re.IGNORECASE),
                re.compile(
                    r"(?:待機中|pending).*?(?:他の|other).*?(?:作業|work)",
                    re.IGNORECASE,
                ),
                # 英語パターン
                re.compile(
                    r"🚫.*?(?:blocked.*?by|waiting.*?for|depends.*?on)", re.IGNORECASE
                ),
                re.compile(
                    r"(?:cannot.*?proceed|stuck).*?(?:until|because)", re.IGNORECASE
                ),
                re.compile(
                    r"(?:requires|needs).*?(?:other|external).*?(?:changes|work)",
                    re.IGNORECASE,
                ),
            ],
            "confidence": 0.75,
        },
    }

    # 解決方法の検出パターン
    METHOD_PATTERNS = {
        ResolutionMethod.AI_AUTOMATED: [
            re.compile(
                r"(?:AI|assistant|automated).*?(?:fixed|resolved|completed)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:automatically|programmatically).*?(?:addressed|handled)",
                re.IGNORECASE,
            ),
        ],
        ResolutionMethod.MANUAL: [
            re.compile(
                r"(?:manually|hand).*?(?:fixed|resolved|updated)", re.IGNORECASE
            ),
            re.compile(
                r"(?:developer|engineer).*?(?:implemented|changed)", re.IGNORECASE
            ),
        ],
        ResolutionMethod.DUPLICATE: [
            re.compile(r"🔄.*?(?:重複|duplicate|already.*?addressed)", re.IGNORECASE),
            re.compile(r"(?:重複対応|既に対応済み|same.*?as).*?🔄", re.IGNORECASE),
        ],
    }

    # 品質指標パターン
    QUALITY_INDICATORS = {
        "high_quality": [
            re.compile(
                r"(?:tested|verified|validated).*?(?:successfully|properly)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:unit.*?test|integration.*?test).*?(?:pass|success)", re.IGNORECASE
            ),
            re.compile(
                r"(?:code.*?review|peer.*?review).*?(?:approved|passed)", re.IGNORECASE
            ),
        ],
        "medium_quality": [
            re.compile(
                r"(?:implemented|changed|updated).*?(?:as.*?requested|per.*?comment)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:follows|adheres.*?to).*?(?:best.*?practice|guideline)",
                re.IGNORECASE,
            ),
        ],
        "needs_verification": [
            re.compile(
                r"(?:please.*?verify|needs.*?review|require.*?validation)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:untested|not.*?tested|manual.*?testing.*?needed)", re.IGNORECASE
            ),
        ],
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_resolution_status(
        self, comment: OutsideDiffComment, additional_text: str = ""
    ) -> Dict[str, Any]:
        """解決状態を検出

        Args:
            comment: 範囲外コメント
            additional_text: 追加のテキスト（AI応答など）

        Returns:
            解決状態の詳細情報
        """
        # 検索対象テキストを結合
        search_text = f"{comment.body} {comment.description} {additional_text}"

        detection_result = {
            "status": ResolutionStatus.UNRESOLVED,
            "method": None,
            "confidence": 0.0,
            "detected_patterns": [],
            "quality_indicators": [],
            "resolution_notes": "",
            "detected_at": datetime.now().isoformat(),
            "evidence": [],
        }

        # 各状態パターンをチェック
        best_match = None
        highest_confidence = 0.0

        for status, pattern_info in self.RESOLUTION_PATTERNS.items():
            patterns = pattern_info["patterns"]
            base_confidence = pattern_info["confidence"]

            for pattern in patterns:
                match = pattern.search(search_text)
                if match:
                    # マッチした証拠を記録
                    evidence = {
                        "pattern": pattern.pattern,
                        "matched_text": match.group(0),
                        "position": match.span(),
                        "confidence": base_confidence,
                    }

                    detection_result["evidence"].append(evidence)
                    detection_result["detected_patterns"].append(pattern.pattern)

                    # 最高信頼度のマッチを記録
                    if base_confidence > highest_confidence:
                        highest_confidence = base_confidence
                        best_match = {
                            "status": status,
                            "confidence": base_confidence,
                            "evidence": evidence,
                        }

        # 最良のマッチを適用
        if best_match:
            detection_result["status"] = best_match["status"]
            detection_result["confidence"] = best_match["confidence"]

            # 解決方法を検出
            detected_method = self._detect_resolution_method(search_text)
            if detected_method:
                detection_result["method"] = detected_method

            # 品質指標を検出
            quality_indicators = self._detect_quality_indicators(search_text)
            detection_result["quality_indicators"] = quality_indicators

            # 解決ノートを抽出
            resolution_notes = self._extract_resolution_notes(
                search_text, best_match["evidence"]
            )
            detection_result["resolution_notes"] = resolution_notes

        self.logger.debug(
            f"解決状態検出完了: {comment.id} -> {detection_result['status'].value}"
        )
        return detection_result

    def bulk_detect_resolution_status(
        self, comments: List[OutsideDiffComment], ai_responses: Dict[int, str] = None
    ) -> Dict[int, Dict[str, Any]]:
        """複数コメントの解決状態を一括検出

        Args:
            comments: 範囲外コメントのリスト
            ai_responses: コメントIDをキーとするAI応答辞書

        Returns:
            コメントIDをキーとする解決状態辞書
        """
        results = {}

        for comment in comments:
            additional_text = ""
            if ai_responses and comment.id in ai_responses:
                additional_text = ai_responses[comment.id]

            results[comment.id] = self.detect_resolution_status(
                comment, additional_text
            )

        return results

    def _detect_resolution_method(self, text: str) -> Optional[ResolutionMethod]:
        """解決方法を検出"""
        for method, patterns in self.METHOD_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    return method
        return None

    def _detect_quality_indicators(self, text: str) -> List[str]:
        """品質指標を検出"""
        indicators = []

        for quality_level, patterns in self.QUALITY_INDICATORS.items():
            for pattern in patterns:
                if pattern.search(text):
                    indicators.append(quality_level)
                    break  # 同じ品質レベルで複数マッチしても1つだけ記録

        return indicators

    def _extract_resolution_notes(self, text: str, evidence: Dict[str, Any]) -> str:
        """解決ノートを抽出"""
        # マッチした部分の前後のコンテキストを抽出
        matched_text = evidence["matched_text"]
        start_pos = evidence["position"][0]
        end_pos = evidence["position"][1]

        # 前後50文字のコンテキストを取得
        context_start = max(0, start_pos - 50)
        context_end = min(len(text), end_pos + 50)
        context = text[context_start:context_end].strip()

        # 改行で分割して、関連する行のみを抽出
        lines = context.split("\n")
        relevant_lines = []

        for line in lines:
            line = line.strip()
            if line and (
                matched_text.lower() in line.lower()
                or any(
                    keyword in line.lower()
                    for keyword in [
                        "because",
                        "reason",
                        "due to",
                        "により",
                        "理由",
                        "ため",
                    ]
                )
            ):
                relevant_lines.append(line)

        return " ".join(relevant_lines[:3])  # 最大3行まで

    def generate_resolution_summary(
        self, detection_results: Dict[int, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """解決状態の要約を生成

        Args:
            detection_results: 検出結果辞書

        Returns:
            要約統計
        """
        summary = {
            "total_comments": len(detection_results),
            "status_breakdown": {},
            "method_breakdown": {},
            "quality_breakdown": {},
            "average_confidence": 0.0,
            "high_confidence_count": 0,
            "needs_manual_review": [],
        }

        # 統計の集計
        total_confidence = 0.0
        status_counts = {}
        method_counts = {}
        quality_counts = {}

        for comment_id, result in detection_results.items():
            status = result["status"]
            confidence = result["confidence"]
            method = result.get("method")
            quality_indicators = result.get("quality_indicators", [])

            # 状態別カウント
            status_counts[status.value] = status_counts.get(status.value, 0) + 1

            # 方法別カウント
            if method:
                method_counts[method.value] = method_counts.get(method.value, 0) + 1

            # 品質別カウント
            for indicator in quality_indicators:
                quality_counts[indicator] = quality_counts.get(indicator, 0) + 1

            # 信頼度の集計
            total_confidence += confidence
            if confidence >= 0.8:
                summary["high_confidence_count"] += 1

            # 手動レビューが必要な項目
            if confidence < 0.6 or "needs_verification" in quality_indicators:
                summary["needs_manual_review"].append(
                    {
                        "comment_id": comment_id,
                        "confidence": confidence,
                        "reason": (
                            "low_confidence"
                            if confidence < 0.6
                            else "needs_verification"
                        ),
                    }
                )

        # 平均信頼度
        if detection_results:
            summary["average_confidence"] = total_confidence / len(detection_results)

        summary["status_breakdown"] = status_counts
        summary["method_breakdown"] = method_counts
        summary["quality_breakdown"] = quality_counts

        return summary

    def validate_resolution_claim(
        self, comment: OutsideDiffComment, resolution_claim: str
    ) -> Dict[str, Any]:
        """解決主張の妥当性を検証

        Args:
            comment: 対象コメント
            resolution_claim: 解決主張のテキスト

        Returns:
            検証結果
        """
        validation_result = {
            "is_valid": False,
            "confidence": 0.0,
            "validation_score": 0.0,
            "issues": [],
            "recommendations": [],
        }

        # 基本的な解決状態検出
        detection = self.detect_resolution_status(comment, resolution_claim)

        if detection["status"] == ResolutionStatus.UNRESOLVED:
            validation_result["issues"].append("解決状態が検出されませんでした")
            return validation_result

        # 検証スコアの計算
        score = 0.0
        max_score = 100.0

        # 1. 信頼度スコア (40点満点)
        confidence_score = detection["confidence"] * 40
        score += confidence_score

        # 2. 品質指標スコア (30点満点)
        quality_indicators = detection.get("quality_indicators", [])
        if "high_quality" in quality_indicators:
            score += 30
        elif "medium_quality" in quality_indicators:
            score += 20
        elif quality_indicators:
            score += 10

        # 3. 詳細度スコア (20点満点)
        resolution_notes = detection.get("resolution_notes", "")
        if len(resolution_notes) > 50:
            score += 20
        elif len(resolution_notes) > 20:
            score += 15
        elif resolution_notes:
            score += 10

        # 4. 一貫性スコア (10点満点)
        if detection.get("method") and len(detection.get("evidence", [])) > 1:
            score += 10
        elif detection.get("method"):
            score += 5

        validation_result["validation_score"] = score
        validation_result["confidence"] = detection["confidence"]
        validation_result["is_valid"] = score >= 60.0  # 60点以上で有効

        # 問題点と推奨事項の生成
        if score < 60:
            validation_result["issues"].append(
                f"検証スコアが低すぎます: {score:.1f}/100"
            )

        if "needs_verification" in quality_indicators:
            validation_result["recommendations"].append("追加の検証が必要です")

        if not resolution_notes:
            validation_result["recommendations"].append(
                "解決の詳細説明を追加してください"
            )

        return validation_result
