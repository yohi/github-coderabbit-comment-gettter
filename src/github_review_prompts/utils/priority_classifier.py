"""CodeRabbitアドバイスに基づく高度な重要度分類システム"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """優先度レベル"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SecurityRiskLevel(Enum):
    """セキュリティリスクレベル"""

    SEVERE = "severe"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class EnhancedPriorityClassifier:
    """CodeRabbitアドバイスに基づく高度な優先度分類器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # CodeRabbitアドバイスに基づく優先度キーワード
        self.priority_keywords = {
            "critical": [
                # セキュリティ関連
                "クリティカル",
                "セキュリティ.*リスク",
                "セキュリティ.*脆弱性",
                "security.*vulnerability",
                "security.*risk",
                "critical.*security",
                # 構文・実行エラー
                "必ず",
                "エラー",
                "構文エラー",
                "syntax.*error",
                "plan.*失敗",
                "apply.*失敗",
                "terraform.*error",
                "未定義.*参照",
                "undefined.*reference",
                "resource.*not.*found",
                # 破壊的変更
                "破壊的",
                "destructive",
                "data.*loss",
                "irreversible",
                "production.*impact",
                "本番.*影響",
            ],
            "high": [
                # 修正必須
                "修正",
                "対応",
                "必要",
                "required",
                "must.*fix",
                "should.*fix",
                "needs.*attention",
                "対応必須",
                # 機能・パフォーマンス問題
                "パフォーマンス.*問題",
                "performance.*issue",
                "機能.*不具合",
                "functional.*issue",
                "logic.*error",
                "設定.*ミス",
                "configuration.*error",
                "resource.*conflict",
                # コンプライアンス
                "コンプライアンス",
                "compliance",
                "policy.*violation",
                "best.*practice.*violation",
            ],
            "medium": [
                # 推奨改善
                "推奨",
                "検討",
                "改善",
                "recommended",
                "consider",
                "improve",
                "enhancement",
                "optimization",
                "最適化",
                # コード品質
                "リファクタリング",
                "refactor",
                "code.*quality",
                "maintainability",
                "保守性",
                "readability",
                "可読性",
                "documentation",
                "ドキュメント",
                "comment.*missing",
            ],
            "low": [
                # 軽微な指摘
                "Nitpick",
                "任意",
                "考慮",
                "optional",
                "nice.*to.*have",
                "minor",
                "cosmetic",
                "style",
                "formatting",
                "フォーマット",
                "スタイル",
                "naming.*convention",
                "命名規則",
                "whitespace",
                "indentation",
            ],
        }

        # ファイルパス別の重要度調整
        self.file_priority_modifiers = {
            # セキュリティ関連ファイル（優先度アップ）
            "security/": 2,
            "iam/": 2,
            "kms/": 2,
            "secrets/": 2,
            "auth/": 2,
            "firewall/": 2,
            "network-security/": 2,
            "zero-trust/": 2,
            # インフラ基盤（優先度アップ）
            "vpc/": 1,
            "network/": 1,
            "database/": 1,
            "storage/": 1,
            "backup/": 1,
            # 本番環境（優先度アップ）
            "prod/": 2,
            "production/": 2,
            "main.tf": 1,
            "variables.tf": 1,
            # テスト・開発環境（優先度ダウン）
            "test/": -1,
            "dev/": -1,
            "development/": -1,
            "examples/": -1,
            "docs/": -1,
            "README": -1,
        }

        # セキュリティリスクパターン
        self.security_risk_patterns = {
            "severe": [
                r"public.*access.*enabled",
                r"encryption.*disabled",
                r"暗号化.*無効",
                r"パブリック.*アクセス.*許可",
                r"root.*access.*allowed",
                r"admin.*privileges.*granted",
                r"password.*hardcoded",
                r"api.*key.*exposed",
                r"secret.*in.*code",
            ],
            "high": [
                r"insecure.*protocol",
                r"weak.*encryption",
                r"弱い.*暗号化",
                r"不安全.*プロトコル",
                r"default.*credentials",
                r"デフォルト.*認証情報",
                r"unrestricted.*access",
                r"制限なし.*アクセス",
                r"missing.*authentication",
            ],
            "medium": [
                r"security.*group.*too.*permissive",
                r"セキュリティ.*グループ.*緩い",
                r"logging.*disabled",
                r"ログ.*無効",
                r"monitoring.*missing",
                r"監視.*設定なし",
                r"backup.*not.*configured",
            ],
            "low": [
                r"security.*header.*missing",
                r"セキュリティ.*ヘッダー.*なし",
                r"version.*not.*specified",
                r"バージョン.*未指定",
                r"tag.*missing",
                r"タグ.*なし",
            ],
        }

        # Terraform固有のパターン
        self.terraform_specific_patterns = {
            "critical": [
                r"resource.*dependency.*cycle",
                r"リソース.*依存.*循環",
                r"state.*corruption",
                r"ステート.*破損",
                r"provider.*version.*conflict",
                r"プロバイダー.*バージョン.*競合",
            ],
            "high": [
                r"resource.*recreation",
                r"リソース.*再作成",
                r"data.*source.*not.*found",
                r"データソース.*見つからない",
                r"variable.*not.*defined",
                r"変数.*未定義",
                r"output.*reference.*invalid",
            ],
            "medium": [
                r"deprecated.*resource",
                r"非推奨.*リソース",
                r"inefficient.*configuration",
                r"非効率.*設定",
                r"resource.*naming.*inconsistent",
                r"リソース.*命名.*不統一",
            ],
        }

    def classify_comment(
        self,
        comment: str,
        file_path: str = "",
        line_number: Optional[int] = None,
        comment_metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """コメントの優先度を包括的に分類

        Args:
            comment: コメント内容
            file_path: ファイルパス
            line_number: 行番号
            comment_metadata: 追加のメタデータ

        Returns:
            分類結果の詳細情報
        """
        try:
            # 基本的な優先度分類
            base_priority = self._classify_by_keywords(comment)

            # セキュリティリスク評価
            security_risk = self._assess_security_risk(comment, file_path)

            # Terraform固有の問題評価
            terraform_severity = self._assess_terraform_severity(comment)

            # ファイルパスによる調整
            file_modifier = self._get_file_priority_modifier(file_path)

            # 最終優先度の決定
            final_priority = self._calculate_final_priority(
                base_priority, security_risk, terraform_severity, file_modifier
            )

            # 詳細な分析結果
            analysis_result = {
                "priority": final_priority,
                "base_priority": base_priority,
                "security_risk": security_risk,
                "terraform_severity": terraform_severity,
                "file_modifier": file_modifier,
                "file_path": file_path,
                "line_number": line_number,
                "reasoning": self._generate_reasoning(
                    comment,
                    base_priority,
                    security_risk,
                    terraform_severity,
                    file_modifier,
                ),
                "recommended_actions": self._generate_recommended_actions(
                    final_priority, security_risk, terraform_severity
                ),
                "estimated_effort": self._estimate_effort(final_priority, comment),
                "classified_at": datetime.now().isoformat(),
            }

            return analysis_result

        except Exception as e:
            self.logger.error(f"優先度分類エラー: {e}")
            return {
                "priority": PriorityLevel.MEDIUM,
                "error": str(e),
                "classified_at": datetime.now().isoformat(),
            }

    def _classify_by_keywords(self, comment: str) -> PriorityLevel:
        """キーワードベースの基本分類"""
        comment_lower = comment.lower()

        # 優先度の高い順にチェック
        for priority_level in ["critical", "high", "medium", "low"]:
            keywords = self.priority_keywords[priority_level]
            for keyword in keywords:
                if re.search(keyword, comment_lower, re.IGNORECASE):
                    return PriorityLevel(priority_level)

        # デフォルトは medium
        return PriorityLevel.MEDIUM

    def _assess_security_risk(self, comment: str, file_path: str) -> SecurityRiskLevel:
        """セキュリティリスクの評価"""
        comment_lower = comment.lower()

        # セキュリティ関連ファイルの場合はリスクレベルを上げる
        is_security_file = any(
            sec_path in file_path.lower()
            for sec_path in ["security/", "iam/", "kms/", "secrets/", "auth/"]
        )

        # パターンマッチング
        for risk_level in ["severe", "high", "medium", "low"]:
            patterns = self.security_risk_patterns[risk_level]
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    # セキュリティファイルの場合は1レベル上げる
                    if is_security_file and risk_level != "severe":
                        risk_levels = ["low", "medium", "high", "severe"]
                        current_index = risk_levels.index(risk_level)
                        return SecurityRiskLevel(risk_levels[min(current_index + 1, 3)])
                    return SecurityRiskLevel(risk_level)

        return SecurityRiskLevel.NONE

    def _assess_terraform_severity(self, comment: str) -> PriorityLevel:
        """Terraform固有の問題の重要度評価"""
        comment_lower = comment.lower()

        for severity_level in ["critical", "high", "medium"]:
            patterns = self.terraform_specific_patterns[severity_level]
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    return PriorityLevel(severity_level)

        return PriorityLevel.LOW

    def _get_file_priority_modifier(self, file_path: str) -> int:
        """ファイルパスによる優先度修正値を取得"""
        file_path_lower = file_path.lower()

        for path_pattern, modifier in self.file_priority_modifiers.items():
            if path_pattern in file_path_lower:
                return modifier

        return 0

    def _calculate_final_priority(
        self,
        base_priority: PriorityLevel,
        security_risk: SecurityRiskLevel,
        terraform_severity: PriorityLevel,
        file_modifier: int,
    ) -> PriorityLevel:
        """最終優先度を計算"""

        # 優先度を数値に変換（高いほど重要）
        priority_scores = {
            PriorityLevel.LOW: 1,
            PriorityLevel.MEDIUM: 2,
            PriorityLevel.HIGH: 3,
            PriorityLevel.CRITICAL: 4,
        }

        security_scores = {
            SecurityRiskLevel.NONE: 0,
            SecurityRiskLevel.LOW: 1,
            SecurityRiskLevel.MEDIUM: 2,
            SecurityRiskLevel.HIGH: 3,
            SecurityRiskLevel.SEVERE: 4,
        }

        # スコア計算
        base_score = priority_scores[base_priority]
        security_score = security_scores[security_risk]
        terraform_score = priority_scores[terraform_severity]

        # 重み付き合計
        final_score = (
            base_score * 0.4  # 基本優先度: 40%
            + security_score * 0.4  # セキュリティリスク: 40%
            + terraform_score * 0.2  # Terraform固有: 20%
            + file_modifier  # ファイル修正値
        )

        # スコアを優先度レベルに変換
        if final_score >= 4.0:
            return PriorityLevel.CRITICAL
        elif final_score >= 3.0:
            return PriorityLevel.HIGH
        elif final_score >= 2.0:
            return PriorityLevel.MEDIUM
        else:
            return PriorityLevel.LOW

    def _generate_reasoning(
        self,
        comment: str,
        base_priority: PriorityLevel,
        security_risk: SecurityRiskLevel,
        terraform_severity: PriorityLevel,
        file_modifier: int,
    ) -> str:
        """分類理由を生成"""
        reasons = []

        # 基本優先度の理由
        reasons.append(f"基本優先度: {base_priority.value}")

        # セキュリティリスクの理由
        if security_risk != SecurityRiskLevel.NONE:
            reasons.append(f"セキュリティリスク: {security_risk.value}")

        # Terraform固有の理由
        if terraform_severity != PriorityLevel.LOW:
            reasons.append(f"Terraform固有の問題: {terraform_severity.value}")

        # ファイル修正の理由
        if file_modifier > 0:
            reasons.append(f"重要ファイル (+{file_modifier})")
        elif file_modifier < 0:
            reasons.append(f"低優先度ファイル ({file_modifier})")

        return " | ".join(reasons)

    def _generate_recommended_actions(
        self,
        priority: PriorityLevel,
        security_risk: SecurityRiskLevel,
        terraform_severity: PriorityLevel,
    ) -> List[str]:
        """推奨アクションを生成"""
        actions = []

        if priority == PriorityLevel.CRITICAL:
            actions.extend(
                [
                    "🚨 即座に対応が必要",
                    "本番環境への影響を確認",
                    "チームリーダーに報告",
                ]
            )
        elif priority == PriorityLevel.HIGH:
            actions.extend(["⚠️ 24時間以内に対応", "影響範囲を調査", "対応計画を作成"])
        elif priority == PriorityLevel.MEDIUM:
            actions.extend(["📋 1週間以内に対応", "次回スプリントに含める"])
        else:
            actions.extend(["📝 時間があるときに対応", "リファクタリング時に検討"])

        # セキュリティ固有のアクション
        if security_risk in [SecurityRiskLevel.SEVERE, SecurityRiskLevel.HIGH]:
            actions.extend(
                [
                    "🔒 セキュリティチームに相談",
                    "脆弱性スキャンを実行",
                    "セキュリティポリシーを確認",
                ]
            )

        # Terraform固有のアクション
        if terraform_severity in [PriorityLevel.CRITICAL, PriorityLevel.HIGH]:
            actions.extend(
                [
                    "🏗️ terraform plan で影響を確認",
                    "ステートファイルのバックアップ",
                    "段階的な適用を検討",
                ]
            )

        return actions

    def _estimate_effort(self, priority: PriorityLevel, comment: str) -> Dict[str, Any]:
        """作業工数を推定"""

        # 基本工数（時間）
        base_efforts = {
            PriorityLevel.CRITICAL: 8.0,  # 1日
            PriorityLevel.HIGH: 4.0,  # 半日
            PriorityLevel.MEDIUM: 2.0,  # 2時間
            PriorityLevel.LOW: 0.5,  # 30分
        }

        base_effort = base_efforts[priority]

        # コメント内容による調整
        complexity_multipliers = {
            "refactor": 2.0,
            "リファクタリング": 2.0,
            "migration": 3.0,
            "マイグレーション": 3.0,
            "security": 1.5,
            "セキュリティ": 1.5,
            "performance": 1.5,
            "パフォーマンス": 1.5,
            "testing": 1.2,
            "テスト": 1.2,
        }

        multiplier = 1.0
        comment_lower = comment.lower()
        for keyword, mult in complexity_multipliers.items():
            if keyword in comment_lower:
                multiplier = max(multiplier, mult)

        final_effort = base_effort * multiplier

        return {
            "estimated_hours": round(final_effort, 1),
            "estimated_days": round(final_effort / 8, 1),
            "complexity_multiplier": multiplier,
            "confidence": 0.7,  # 推定の信頼度
        }

    def batch_classify(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """複数コメントの一括分類"""
        results = []

        for comment_data in comments:
            try:
                classification = self.classify_comment(
                    comment=comment_data.get("body", ""),
                    file_path=comment_data.get("file_path", ""),
                    line_number=comment_data.get("line_number"),
                    comment_metadata=comment_data.get("metadata", {}),
                )

                classification["comment_id"] = comment_data.get("id")
                results.append(classification)

            except Exception as e:
                self.logger.error(
                    f"コメント分類エラー (ID: {comment_data.get('id')}): {e}"
                )
                results.append(
                    {
                        "comment_id": comment_data.get("id"),
                        "priority": PriorityLevel.MEDIUM,
                        "error": str(e),
                    }
                )

        return results

    def generate_priority_report(
        self, classifications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """優先度分類レポートを生成"""
        try:
            total_count = len(classifications)
            if total_count == 0:
                return {"total_comments": 0, "priority_distribution": {}}

            # 優先度別集計
            priority_counts = {}
            security_risk_counts = {}
            total_effort = 0.0

            for classification in classifications:
                priority = classification.get("priority", PriorityLevel.MEDIUM)
                if hasattr(priority, "value"):
                    priority_key = priority.value
                else:
                    priority_key = str(priority)

                priority_counts[priority_key] = priority_counts.get(priority_key, 0) + 1

                # セキュリティリスク集計
                security_risk = classification.get(
                    "security_risk", SecurityRiskLevel.NONE
                )
                if hasattr(security_risk, "value"):
                    risk_key = security_risk.value
                else:
                    risk_key = str(security_risk)

                security_risk_counts[risk_key] = (
                    security_risk_counts.get(risk_key, 0) + 1
                )

                # 工数集計
                effort_info = classification.get("estimated_effort", {})
                total_effort += effort_info.get("estimated_hours", 0)

            # パーセンテージ計算
            priority_percentages = {
                priority: round((count / total_count) * 100, 1)
                for priority, count in priority_counts.items()
            }

            return {
                "total_comments": total_count,
                "priority_distribution": {
                    "counts": priority_counts,
                    "percentages": priority_percentages,
                },
                "security_risk_distribution": security_risk_counts,
                "effort_estimation": {
                    "total_hours": round(total_effort, 1),
                    "total_days": round(total_effort / 8, 1),
                    "average_hours_per_comment": round(total_effort / total_count, 1),
                },
                "recommendations": self._generate_report_recommendations(
                    priority_counts, security_risk_counts, total_effort
                ),
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"優先度レポート生成エラー: {e}")
            return {"error": str(e)}

    def _generate_report_recommendations(
        self, priority_counts: Dict, security_risk_counts: Dict, total_effort: float
    ) -> List[str]:
        """レポート用推奨事項を生成"""
        recommendations = []

        # 緊急対応が必要な場合
        critical_count = priority_counts.get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"🚨 {critical_count}件のクリティカルな問題があります - 即座に対応してください"
            )

        # セキュリティリスクの警告
        severe_security = security_risk_counts.get("severe", 0)
        high_security = security_risk_counts.get("high", 0)
        if severe_security > 0 or high_security > 0:
            recommendations.append(
                f"🔒 高リスクのセキュリティ問題が{severe_security + high_security}件あります"
            )

        # 工数に基づく推奨事項
        if total_effort > 40:  # 5日以上
            recommendations.append(
                "⏰ 大規模な作業量です - チーム分担を検討してください"
            )
        elif total_effort > 16:  # 2日以上
            recommendations.append(
                "📅 中規模の作業量です - スプリント計画に含めてください"
            )

        # 優先度分布に基づく推奨事項
        high_priority_count = priority_counts.get("high", 0) + critical_count
        total_count = sum(priority_counts.values())
        if high_priority_count / total_count > 0.3:
            recommendations.append(
                "⚡ 高優先度の問題が多いです - 段階的な対応計画を立ててください"
            )

        return recommendations
