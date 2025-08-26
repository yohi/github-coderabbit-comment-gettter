"""AI対応報告の自動解析ユーティリティ"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

from .resolution_detector import ResolutionStatus, ResolutionMethod

logger = logging.getLogger(__name__)


class AIResponseQuality(Enum):
    """AI応答の品質レベル"""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    INVALID = "invalid"


class AIResponseAnalyzer:
    """AI対応報告の自動解析クラス"""

    # AI応答パターンの検出
    AI_RESPONSE_PATTERNS = {
        "completion_report": {
            "patterns": [
                # 完了報告パターン
                re.compile(
                    r"✅.*?範囲外TODO.*?#(\d+).*?(?:完了|completed|fixed|resolved)",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(
                    r"範囲外TODO.*?#(\d+).*?✅.*?(?:対応内容|implementation|solution)",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(
                    r"(?:successfully|properly).*?(?:implemented|fixed|resolved).*?TODO.*?#(\d+)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ],
            "extraction_patterns": [
                re.compile(
                    r"\*\*対応内容\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
                re.compile(
                    r"\*\*検証結果\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
                re.compile(
                    r"\*\*Implementation\*\*:?\s*(.+?)(?=\*\*|$)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ],
        },
        "skip_report": {
            "patterns": [
                # スキップ報告パターン
                re.compile(
                    r"❌.*?範囲外TODO.*?#(\d+).*?(?:対応不要|skip|wont.*?fix)",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(
                    r"範囲外TODO.*?#(\d+).*?❌.*?(?:理由|reason)",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(
                    r"(?:decided|choosing).*?(?:not.*?to|skip).*?TODO.*?#(\d+)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ],
            "extraction_patterns": [
                re.compile(
                    r"\*\*理由\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
                re.compile(
                    r"\*\*判断\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
                re.compile(
                    r"\*\*Reason\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
            ],
        },
        "progress_report": {
            "patterns": [
                # 進捗報告パターン
                re.compile(
                    r"🔄.*?範囲外TODO.*?#(\d+).*?(?:進行中|in.*?progress|working)",
                    re.IGNORECASE | re.DOTALL,
                ),
                re.compile(
                    r"(?:started|beginning|investigating).*?TODO.*?#(\d+)",
                    re.IGNORECASE | re.DOTALL,
                ),
            ],
            "extraction_patterns": [
                re.compile(
                    r"\*\*進捗\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
                re.compile(
                    r"\*\*Progress\*\*:?\s*(.+?)(?=\*\*|$)", re.IGNORECASE | re.DOTALL
                ),
            ],
        },
    }

    # 品質評価パターン
    QUALITY_PATTERNS = {
        AIResponseQuality.EXCELLENT: [
            # 詳細な実装説明 + テスト + 検証
            re.compile(
                r"(?:implemented|fixed).*?(?:tested|verified).*?(?:successfully|properly)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:unit.*?test|integration.*?test).*?(?:pass|success)", re.IGNORECASE
            ),
            re.compile(
                r"(?:before|after).*?(?:comparison|benchmark|measurement)",
                re.IGNORECASE,
            ),
        ],
        AIResponseQuality.GOOD: [
            # 実装説明 + 基本的な検証
            re.compile(
                r"(?:implemented|changed|updated).*?(?:as.*?requested|per.*?comment)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:follows|adheres.*?to).*?(?:best.*?practice|guideline)",
                re.IGNORECASE,
            ),
            re.compile(r"(?:validated|confirmed).*?(?:working|correct)", re.IGNORECASE),
        ],
        AIResponseQuality.ACCEPTABLE: [
            # 基本的な実装報告
            re.compile(r"(?:fixed|resolved|completed|done)", re.IGNORECASE),
            re.compile(
                r"(?:changed|updated|modified).*?(?:code|implementation)", re.IGNORECASE
            ),
        ],
        AIResponseQuality.POOR: [
            # 曖昧な報告
            re.compile(r"(?:looks.*?good|seems.*?fine|should.*?work)", re.IGNORECASE),
            re.compile(
                r"(?:probably|maybe|might.*?be).*?(?:fixed|resolved)", re.IGNORECASE
            ),
        ],
    }

    # コード品質指標
    CODE_QUALITY_INDICATORS = {
        "security_conscious": [
            re.compile(
                r"(?:security|vulnerability).*?(?:addressed|fixed|mitigated)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:input.*?validation|sanitization|authentication)", re.IGNORECASE
            ),
            re.compile(
                r"(?:secure|safety).*?(?:implementation|approach)", re.IGNORECASE
            ),
        ],
        "performance_aware": [
            re.compile(
                r"(?:performance|optimization).*?(?:improved|enhanced)", re.IGNORECASE
            ),
            re.compile(
                r"(?:faster|efficient|optimized).*?(?:implementation|solution)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:reduced|minimized).*?(?:overhead|latency|memory)", re.IGNORECASE
            ),
        ],
        "maintainable": [
            re.compile(
                r"(?:clean|readable|maintainable).*?(?:code|implementation)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:documented|commented|explained).*?(?:changes|implementation)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:refactored|restructured).*?(?:for.*?clarity|readability)",
                re.IGNORECASE,
            ),
        ],
        "tested": [
            re.compile(r"(?:added|created|wrote).*?(?:test|spec)", re.IGNORECASE),
            re.compile(r"(?:test.*?coverage|tested.*?thoroughly)", re.IGNORECASE),
            re.compile(
                r"(?:all.*?tests|test.*?suite).*?(?:pass|passing)", re.IGNORECASE
            ),
        ],
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_ai_response(
        self, response_text: str, comment_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """AI応答を包括的に解析

        Args:
            response_text: AI応答テキスト
            comment_id: 対象コメントID（指定されている場合）

        Returns:
            解析結果
        """
        analysis_result = {
            "comment_id": comment_id,
            "analysis_timestamp": datetime.now().isoformat(),
            "detected_status": ResolutionStatus.UNRESOLVED,
            "detected_method": None,
            "quality_level": AIResponseQuality.INVALID,
            "confidence": 0.0,
            "extracted_info": {},
            "quality_indicators": [],
            "validation_issues": [],
            "recommendations": [],
            "auto_markable": False,
        }

        if not response_text or not response_text.strip():
            analysis_result["validation_issues"].append("空の応答です")
            return analysis_result

        # 1. 基本的な状態検出
        status_detection = self._detect_response_status(response_text, comment_id)
        analysis_result.update(status_detection)

        # 2. 品質レベルの評価
        quality_assessment = self._assess_response_quality(response_text)
        analysis_result.update(quality_assessment)

        # 3. 詳細情報の抽出
        extracted_info = self._extract_detailed_info(
            response_text, analysis_result["detected_status"]
        )
        analysis_result["extracted_info"] = extracted_info

        # 4. 品質指標の検出
        quality_indicators = self._detect_code_quality_indicators(response_text)
        analysis_result["quality_indicators"] = quality_indicators

        # 5. 検証問題の特定
        validation_issues = self._identify_validation_issues(analysis_result)
        analysis_result["validation_issues"] = validation_issues

        # 6. 推奨事項の生成
        recommendations = self._generate_response_recommendations(analysis_result)
        analysis_result["recommendations"] = recommendations

        # 7. 自動マーク可能性の判定
        analysis_result["auto_markable"] = self._is_auto_markable(analysis_result)

        return analysis_result

    def batch_analyze_responses(
        self, responses: Dict[int, str]
    ) -> Dict[int, Dict[str, Any]]:
        """AI応答を一括解析

        Args:
            responses: コメントIDをキーとするAI応答辞書

        Returns:
            コメントIDをキーとする解析結果辞書
        """
        results = {}

        for comment_id, response_text in responses.items():
            results[comment_id] = self.analyze_ai_response(response_text, comment_id)

        # 一括解析の追加統計
        batch_stats = self._generate_batch_statistics(results)

        return {"individual_results": results, "batch_statistics": batch_stats}

    def _detect_response_status(
        self, response_text: str, comment_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """応答から状態を検出"""
        detection = {
            "detected_status": ResolutionStatus.UNRESOLVED,
            "detected_method": None,
            "confidence": 0.0,
            "matched_patterns": [],
        }

        # 優先順位: completion > skip > progress
        for response_type in ["completion_report", "skip_report", "progress_report"]:
            pattern_info = self.AI_RESPONSE_PATTERNS[response_type]
            for pattern in pattern_info["patterns"]:
                match = pattern.search(response_text)
                if not match:
                    continue
                detection["matched_patterns"].append(
                    {
                        "type": response_type,
                        "pattern": pattern.pattern,
                        "matched_text": match.group(0),
                    }
                )
                if response_type == "completion_report":
                    detection["detected_status"] = ResolutionStatus.RESOLVED
                    detection["detected_method"] = ResolutionMethod.AI_AUTOMATED
                    detection["confidence"] = 0.9
                    return detection
                if response_type == "skip_report":
                    detection["detected_status"] = ResolutionStatus.SKIPPED
                    detection["detected_method"] = ResolutionMethod.SKIPPED
                    detection["confidence"] = 0.85
                    return detection
                # progress_report
                detection["detected_status"] = ResolutionStatus.IN_PROGRESS
                detection["detected_method"] = ResolutionMethod.AI_AUTOMATED
                detection["confidence"] = 0.7
                return detection

        return detection

    def _assess_response_quality(self, response_text: str) -> Dict[str, Any]:
        """応答品質を評価"""
        quality_assessment = {
            "quality_level": AIResponseQuality.INVALID,
            "quality_score": 0.0,
            "quality_factors": [],
        }

        # 各品質レベルをチェック
        for quality_level, patterns in self.QUALITY_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(response_text):
                    quality_assessment["quality_level"] = quality_level
                    quality_assessment["quality_factors"].append(pattern.pattern)
                    break

            # より高い品質レベルが見つかったら終了
            if quality_assessment["quality_level"] != AIResponseQuality.INVALID:
                break

        # 品質スコアの計算
        quality_scores = {
            AIResponseQuality.EXCELLENT: 95.0,
            AIResponseQuality.GOOD: 80.0,
            AIResponseQuality.ACCEPTABLE: 65.0,
            AIResponseQuality.POOR: 40.0,
            AIResponseQuality.INVALID: 0.0,
        }

        base_score = quality_scores[quality_assessment["quality_level"]]

        # 追加要素による調整
        bonus_score = 0.0

        # 長さボーナス（詳細な説明）
        if len(response_text) > 200:
            bonus_score += 5.0
        elif len(response_text) > 100:
            bonus_score += 3.0

        # 構造化ボーナス（マークダウン形式）
        if "**" in response_text or "##" in response_text:
            bonus_score += 3.0

        # コードブロックボーナス
        if "```" in response_text:
            bonus_score += 5.0

        quality_assessment["quality_score"] = min(100.0, base_score + bonus_score)

        return quality_assessment

    def _extract_detailed_info(
        self, response_text: str, status: ResolutionStatus
    ) -> Dict[str, Any]:
        """詳細情報を抽出"""
        extracted = {
            "implementation_details": "",
            "verification_results": "",
            "code_changes": [],
            "test_results": "",
            "reasoning": "",
            "impact_assessment": "",
            "follow_up_actions": [],
        }

        # 状態に応じた抽出パターンを選択
        if status == ResolutionStatus.RESOLVED:
            patterns = self.AI_RESPONSE_PATTERNS["completion_report"][
                "extraction_patterns"
            ]
        elif status == ResolutionStatus.SKIPPED:
            patterns = self.AI_RESPONSE_PATTERNS["skip_report"]["extraction_patterns"]
        else:
            patterns = self.AI_RESPONSE_PATTERNS["progress_report"][
                "extraction_patterns"
            ]

        # パターンマッチングで情報抽出
        for pattern in patterns:
            match = pattern.search(response_text)
            if match:
                content = match.group(1).strip()

                # パターンの種類に応じて適切なフィールドに格納
                if (
                    "implementation" in pattern.pattern.lower()
                    or "対応内容" in pattern.pattern
                ):
                    extracted["implementation_details"] = content
                elif (
                    "verification" in pattern.pattern.lower()
                    or "検証結果" in pattern.pattern
                ):
                    extracted["verification_results"] = content
                elif "reason" in pattern.pattern.lower() or "理由" in pattern.pattern:
                    extracted["reasoning"] = content

        # コードブロックの抽出
        code_blocks = re.findall(r"```(?:\w+)?\s*(.*?)\s*```", response_text, re.DOTALL)
        extracted["code_changes"] = [block.strip() for block in code_blocks]

        # テスト結果の抽出
        test_patterns = [
            re.compile(r"(?:test|テスト).*?(?:pass|success|成功|通過)", re.IGNORECASE),
            re.compile(
                r"(?:all.*?tests|全.*?テスト).*?(?:green|ok|正常)", re.IGNORECASE
            ),
        ]

        for pattern in test_patterns:
            match = pattern.search(response_text)
            if match:
                extracted["test_results"] = match.group(0)
                break

        # フォローアップアクションの抽出
        followup_patterns = [
            re.compile(
                r"(?:next|次に|follow.*?up).*?(?:step|action|作業)", re.IGNORECASE
            ),
            re.compile(
                r"(?:todo|要対応|remaining).*?(?:item|task|作業)", re.IGNORECASE
            ),
        ]

        for pattern in followup_patterns:
            matches = pattern.finditer(response_text)
            for match in matches:
                extracted["follow_up_actions"].append(match.group(0))

        return extracted

    def _detect_code_quality_indicators(self, response_text: str) -> List[str]:
        """コード品質指標を検出"""
        indicators = []

        for indicator_type, patterns in self.CODE_QUALITY_INDICATORS.items():
            for pattern in patterns:
                if pattern.search(response_text):
                    indicators.append(indicator_type)
                    break

        return indicators

    def _identify_validation_issues(self, analysis_result: Dict[str, Any]) -> List[str]:
        """検証問題を特定"""
        issues = []

        # 基本的な検証
        if analysis_result["confidence"] < 0.5:
            issues.append("信頼度が低すぎます")

        if analysis_result["quality_level"] == AIResponseQuality.INVALID:
            issues.append("応答形式が無効です")

        if analysis_result["quality_level"] == AIResponseQuality.POOR:
            issues.append("応答品質が低すぎます")

        # 詳細情報の検証
        extracted_info = analysis_result.get("extracted_info", {})

        if analysis_result["detected_status"] == ResolutionStatus.RESOLVED:
            if not extracted_info.get("implementation_details"):
                issues.append("実装詳細が不足しています")

            if not extracted_info.get(
                "verification_results"
            ) and "tested" not in analysis_result.get("quality_indicators", []):
                issues.append("検証結果が不足しています")

        elif analysis_result["detected_status"] == ResolutionStatus.SKIPPED:
            if not extracted_info.get("reasoning"):
                issues.append("スキップ理由が不足しています")

        return issues

    def _generate_response_recommendations(
        self, analysis_result: Dict[str, Any]
    ) -> List[str]:
        """応答に対する推奨事項を生成"""
        recommendations = []

        quality_level = analysis_result["quality_level"]
        confidence = analysis_result["confidence"]
        validation_issues = analysis_result.get("validation_issues", [])

        # 品質レベル別の推奨事項
        if (
            quality_level == AIResponseQuality.POOR
            or quality_level == AIResponseQuality.INVALID
        ):
            recommendations.append("応答の詳細化と構造化が必要です")

        if confidence < 0.7:
            recommendations.append("より明確な状態表示（✅/❌/🔄）を使用してください")

        # 検証問題別の推奨事項
        if "実装詳細が不足" in validation_issues:
            recommendations.append(
                "具体的な実装内容を**対応内容**セクションに記載してください"
            )

        if "検証結果が不足" in validation_issues:
            recommendations.append(
                "動作確認結果を**検証結果**セクションに記載してください"
            )

        if "スキップ理由が不足" in validation_issues:
            recommendations.append(
                "技術的根拠に基づく詳細な理由を**理由**セクションに記載してください"
            )

        # 品質向上の推奨事項
        quality_indicators = analysis_result.get("quality_indicators", [])

        if (
            "security_conscious" not in quality_indicators
            and "security"
            in analysis_result.get("extracted_info", {})
            .get("implementation_details", "")
            .lower()
        ):
            recommendations.append("セキュリティ面での考慮事項を明記してください")

        if (
            "tested" not in quality_indicators
            and analysis_result["detected_status"] == ResolutionStatus.RESOLVED
        ):
            recommendations.append("テスト実行結果を追加してください")

        return recommendations

    def _is_auto_markable(self, analysis_result: Dict[str, Any]) -> bool:
        """自動マーク可能かどうかを判定"""
        # 基本条件
        if analysis_result["confidence"] < 0.8:
            return False

        if analysis_result["quality_level"] in [
            AIResponseQuality.POOR,
            AIResponseQuality.INVALID,
        ]:
            return False

        if analysis_result["validation_issues"]:
            return False

        # 状態別の条件
        status = analysis_result["detected_status"]

        if status == ResolutionStatus.RESOLVED:
            # 完了報告の場合：実装詳細と検証結果が必要
            extracted = analysis_result.get("extracted_info", {})
            return bool(extracted.get("implementation_details")) and (
                bool(extracted.get("verification_results"))
                or "tested" in analysis_result.get("quality_indicators", [])
            )

        elif status == ResolutionStatus.SKIPPED:
            # スキップ報告の場合：理由が必要
            extracted = analysis_result.get("extracted_info", {})
            return bool(extracted.get("reasoning"))

        elif status == ResolutionStatus.IN_PROGRESS:
            # 進捗報告の場合：基本的な情報があればOK
            return True

        return False

    def _generate_batch_statistics(
        self, results: Dict[int, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """一括解析の統計を生成"""
        stats = {
            "total_responses": len(results),
            "status_breakdown": {},
            "quality_breakdown": {},
            "auto_markable_count": 0,
            "average_confidence": 0.0,
            "average_quality_score": 0.0,
            "common_issues": [],
            "overall_assessment": "unknown",
        }

        if not results:
            return stats

        total_confidence = 0.0
        total_quality_score = 0.0
        all_issues = []

        for result in results.values():
            # 状態別集計
            status = result["detected_status"].value
            stats["status_breakdown"][status] = (
                stats["status_breakdown"].get(status, 0) + 1
            )

            # 品質別集計
            quality = result["quality_level"].value
            stats["quality_breakdown"][quality] = (
                stats["quality_breakdown"].get(quality, 0) + 1
            )

            # 自動マーク可能数
            if result["auto_markable"]:
                stats["auto_markable_count"] += 1

            # 平均値計算用
            total_confidence += result["confidence"]
            total_quality_score += result.get("quality_score", 0.0)

            # 問題の収集
            all_issues.extend(result.get("validation_issues", []))

        # 平均値
        stats["average_confidence"] = total_confidence / len(results)
        stats["average_quality_score"] = total_quality_score / len(results)

        # 共通問題の特定
        from collections import Counter

        issue_counts = Counter(all_issues)
        stats["common_issues"] = [
            {"issue": issue, "count": count}
            for issue, count in issue_counts.most_common(5)
        ]

        # 全体評価
        if stats["average_confidence"] >= 0.8 and stats["average_quality_score"] >= 80:
            stats["overall_assessment"] = "excellent"
        elif (
            stats["average_confidence"] >= 0.7 and stats["average_quality_score"] >= 65
        ):
            stats["overall_assessment"] = "good"
        elif (
            stats["average_confidence"] >= 0.5 and stats["average_quality_score"] >= 50
        ):
            stats["overall_assessment"] = "acceptable"
        else:
            stats["overall_assessment"] = "needs_improvement"

        return stats

    def generate_quality_improvement_suggestions(
        self, batch_stats: Dict[str, Any]
    ) -> List[str]:
        """品質改善提案を生成"""
        suggestions = []

        overall_assessment = batch_stats["overall_assessment"]
        average_confidence = batch_stats["average_confidence"]
        common_issues = batch_stats.get("common_issues", [])

        # 全体評価別の提案
        if overall_assessment == "needs_improvement":
            suggestions.append("🚨 応答品質の大幅な改善が必要です")
            suggestions.append(
                "📋 構造化された報告形式（✅/❌ + **詳細**）を使用してください"
            )

        elif overall_assessment == "acceptable":
            suggestions.append("📈 応答品質は許容範囲内ですが、さらなる改善が可能です")

        # 信頼度別の提案
        if average_confidence < 0.6:
            suggestions.append(
                "🎯 明確な状態表示（✅完了/❌スキップ/🔄進行中）を使用してください"
            )

        # 共通問題別の提案
        for issue_info in common_issues:
            issue = issue_info["issue"]
            count = issue_info["count"]

            if count >= 3:  # 3件以上の共通問題
                if "実装詳細が不足" in issue:
                    suggestions.append(
                        f"📝 {count}件で実装詳細が不足しています。**対応内容**セクションを充実させてください"
                    )

                elif "検証結果が不足" in issue:
                    suggestions.append(
                        f"🔍 {count}件で検証結果が不足しています。**検証結果**セクションを追加してください"
                    )

                elif "スキップ理由が不足" in issue:
                    suggestions.append(
                        f"❓ {count}件でスキップ理由が不足しています。技術的根拠を明記してください"
                    )

        # 自動マーク率の提案
        total = batch_stats["total_responses"]
        auto_markable_rate = (
            batch_stats["auto_markable_count"] / total * 100 if total > 0 else 0.0
        )
        if auto_markable_rate < 50:
            suggestions.append(
                f"⚙️ 自動マーク率が{auto_markable_rate:.1f}%と低いです。報告形式の統一化を検討してください"
            )

        return suggestions
