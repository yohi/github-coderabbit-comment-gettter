"""解決済みマーク自動処理専用モジュール"""

import logging
import re
from typing import Dict, Set, Any, Optional
from datetime import datetime

from .github_client import GitHubClient
from .models import GitHubPRInfo
from .utils.validators import validate_github_token


class AutoResolveProcessor:
    """解決済みマーク検出・自動解決処理専用クラス"""

    # CodeRabbit解決済みマーカーのパターン（既存の定義を再利用）
    CR_RESOLUTION_MARKER_PATTERN = re.compile(
        r"\[CR_RESOLUTION_CONFIRMED[^\]]*\].*?✅.*?エンジニアによる技術的検証完了.*?CodeRabbitによる解決済みマーク実行可能.*?\[/CR_RESOLUTION_CONFIRMED\]",
        re.DOTALL | re.IGNORECASE,
    )

    # シンプルなマーカーパターン（フォールバック用・新フォーマット対応）
    SIMPLE_RESOLUTION_PATTERNS = [
        re.compile(r"\[CR_RESOLUTION_CONFIRMED[^:]*:[^]]*\].*?\[/CR_RESOLUTION_CONFIRMED\]", re.DOTALL | re.IGNORECASE),
        re.compile(r"✅.*?エンジニアによる技術的検証完了.*?CodeRabbitによる解決済みマーク実行可能", re.IGNORECASE),
        re.compile(r"CodeRabbitによる解決済みマーク実行可能", re.IGNORECASE),
        re.compile(r"\[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED\]", re.IGNORECASE),
        re.compile(r"\[CR_RESOLUTION_CONFIRMED:FUTURE_PHASE_PLANNED\]", re.IGNORECASE),
    ]

    # 追加の解決済み判定パターン
    ADDITIONAL_RESOLUTION_PATTERNS = [
        re.compile(r"問題ないと判断.*解決済みにマーク", re.IGNORECASE),
        re.compile(r"将来対応と判断.*解決済みにマーク", re.IGNORECASE),
        re.compile(r"指摘が間違い.*解決済みにマーク", re.IGNORECASE),
        re.compile(r"修正完了", re.IGNORECASE),
        re.compile(r"対応済み", re.IGNORECASE),
    ]

    def __init__(self, github_token: str):
        """
        Args:
            github_token: GitHub APIトークン
        """
        self.logger = logging.getLogger(__name__)

        # GitHubトークンの検証
        is_valid, error_msg = validate_github_token(github_token)
        if not is_valid:
            raise ValueError(f"無効なGitHubトークンです: {error_msg or '不明なエラー'}")

        self.github_client = GitHubClient(github_token)
        self.logger.info("AutoResolveProcessor初期化完了")

    def process_pr_auto_resolve(
        self,
        pr_url: str,
        dry_run: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """プルリクエストの解決済みマーク自動処理

        Args:
            pr_url: プルリクエストURL
            dry_run: ドライランモード（実際の解決処理は行わない）
            verbose: 詳細ログ出力

        Returns:
            処理結果の詳細情報
        """
        try:
            self.logger.info(f"解決済みマーク自動処理開始: {pr_url}")

            # PR情報の解析
            pr_info = GitHubPRInfo.from_url(pr_url)
            if not pr_info:
                raise ValueError(f"無効なプルリクエストURL: {pr_url}")

            self.logger.info(f"PR情報: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")

            # PR基本情報を取得
            pr_basic_info = self.github_client.get_pr_basic_info(pr_info)
            if not pr_basic_info:
                raise ValueError("プルリクエスト情報の取得に失敗しました")

            # コメント取得（ハイブリッドアプローチ）
            self.logger.info("コメント取得開始...")
            resolved_ids, graphql_bodies = (
                self.github_client.get_comments_via_hybrid_approach(pr_info)
            )

            if verbose:
                self.logger.info(f"取得コメント数: {len(graphql_bodies)}")
                self.logger.info(f"既解決コメント数: {len(resolved_ids)}")

            # 解決済みマーカー検出
            marked_comment_ids = self.detect_resolution_markers(graphql_bodies)

            # 処理結果の準備
            result = {
                "pr_info": {
                    "owner": pr_info.owner,
                    "repo": pr_info.repo,
                    "pull_number": pr_info.pull_number,
                    "url": pr_url,
                    "title": pr_basic_info.get("title", ""),
                    "state": pr_basic_info.get("state", ""),
                },
                "processing_info": {
                    "total_comments": len(graphql_bodies),
                    "already_resolved": len(resolved_ids),
                    "marked_for_resolution": len(marked_comment_ids),
                    "dry_run": dry_run,
                    "timestamp": datetime.now().isoformat(),
                },
                "marked_comments": [],
                "resolution_results": [],
                "summary": {}
            }

            # マーカー検出されたコメントの詳細情報を収集
            for comment_id in marked_comment_ids:
                comment_body = graphql_bodies.get(comment_id, "")
                detected_patterns = self._identify_detected_patterns(comment_body)

                result["marked_comments"].append({
                    "comment_id": comment_id,
                    "is_already_resolved": comment_id in resolved_ids,
                    "detected_patterns": detected_patterns,
                    "body_preview": comment_body[:200] + "..." if len(comment_body) > 200 else comment_body
                })

            # 実際の解決処理またはドライラン
            if marked_comment_ids:
                if dry_run:
                    self.logger.info(f"ドライラン: {len(marked_comment_ids)}件のコメントが解決対象")
                    result["summary"] = {
                        "action": "dry_run_completed",
                        "would_resolve": len(marked_comment_ids),
                        "message": f"{len(marked_comment_ids)}件のコメントに解決済みマーカーが検出されました（ドライラン）"
                    }
                else:
                    self.logger.info(f"自動解決処理実行: {len(marked_comment_ids)}件")
                    resolution_results = self._auto_resolve_marked_comments(
                        marked_comment_ids,
                        pr_info,
                        verbose=verbose
                    )
                    result["resolution_results"] = resolution_results

                    success_count = sum(1 for r in resolution_results if r.get("success", False))
                    result["summary"] = {
                        "action": "auto_resolve_completed",
                        "total_marked": len(marked_comment_ids),
                        "successfully_resolved": success_count,
                        "failed": len(marked_comment_ids) - success_count,
                        "message": f"{success_count}/{len(marked_comment_ids)}件のコメントを解決済みにしました"
                    }
            else:
                self.logger.info("解決済みマーカーが検出されませんでした")
                result["summary"] = {
                    "action": "no_markers_found",
                    "total_comments": len(graphql_bodies),
                    "message": "解決済みマーカーが検出されませんでした"
                }

            self.logger.info("解決済みマーク自動処理完了")
            return result

        except Exception as e:
            self.logger.error(f"解決済みマーク自動処理エラー: {str(e)}")
            return {
                "error": str(e),
                "pr_url": pr_url,
                "timestamp": datetime.now().isoformat()
            }

    def detect_resolution_markers(self, comment_bodies: Dict[int, str]) -> Set[int]:
        """解決済みマーカーを検出

        Args:
            comment_bodies: コメントID -> 本文のマッピング

        Returns:
            マーカーが検出されたコメントIDのセット
        """
        marked_comment_ids = set()

        if not comment_bodies:
            self.logger.warning("コメント本文データがありません")
            return marked_comment_ids

        self.logger.debug(f"解決マーカー検出開始: {len(comment_bodies)} 件のコメントを対象")

        for comment_id, body in comment_bodies.items():
            if not body:
                continue

            # メインマーカーパターンをチェック
            if self.CR_RESOLUTION_MARKER_PATTERN.search(body):
                marked_comment_ids.add(comment_id)
                self.logger.debug(f"メインマーカー検出: コメントID {comment_id}")
                continue

            # シンプルマーカーパターンをチェック
            for pattern in self.SIMPLE_RESOLUTION_PATTERNS:
                if pattern.search(body):
                    marked_comment_ids.add(comment_id)
                    self.logger.debug(f"シンプルマーカー検出: コメントID {comment_id}")
                    break

            # 追加パターンをチェック
            for pattern in self.ADDITIONAL_RESOLUTION_PATTERNS:
                if pattern.search(body):
                    marked_comment_ids.add(comment_id)
                    self.logger.debug(f"追加マーカー検出: コメントID {comment_id}")
                    break

        if marked_comment_ids:
            self.logger.info(f"解決済みマーカー検出: {len(marked_comment_ids)} 件")
        else:
            self.logger.info(f"解決マーカーが見つかりませんでした。対象コメント数: {len(comment_bodies)}")

        return marked_comment_ids

    def _identify_detected_patterns(self, comment_body: str) -> list[str]:
        """検出されたパターンを特定

        Args:
            comment_body: コメント本文

        Returns:
            検出されたパターンのリスト
        """
        detected = []

        if self.CR_RESOLUTION_MARKER_PATTERN.search(comment_body):
            detected.append("CR_RESOLUTION_CONFIRMED (完全)")

        for i, pattern in enumerate(self.SIMPLE_RESOLUTION_PATTERNS):
            if pattern.search(comment_body):
                pattern_names = [
                    "CR_RESOLUTION_CONFIRMED (簡易)",
                    "技術的検証完了マーク",
                    "解決済みマーク実行可能",
                    "TECHNICAL_ISSUE_RESOLVED",
                    "FUTURE_PHASE_PLANNED"
                ]
                detected.append(pattern_names[i])

        for i, pattern in enumerate(self.ADDITIONAL_RESOLUTION_PATTERNS):
            if pattern.search(comment_body):
                pattern_names = [
                    "問題なし判定",
                    "将来対応判定",
                    "指摘間違い判定",
                    "修正完了",
                    "対応済み"
                ]
                detected.append(pattern_names[i])

        return detected

    def _auto_resolve_marked_comments(
        self,
        marked_comment_ids: Set[int],
        pr_info: GitHubPRInfo,
        verbose: bool = False
    ) -> list[Dict[str, Any]]:
        """マーカーが検出されたコメントスレッドを自動解決

        Args:
            marked_comment_ids: マーカーが検出されたコメントIDのセット
            pr_info: プルリクエスト情報
            verbose: 詳細ログ出力

        Returns:
            解決処理結果のリスト
        """
        results = []

        if not marked_comment_ids:
            self.logger.debug("自動解決対象のマーカーがありません")
            return results

        self.logger.info(f"マーカー検出コメントの自動解決開始: {len(marked_comment_ids)} 件")

        if verbose:
            self.logger.info(f"PR情報: {pr_info.owner}/{pr_info.repo}#{pr_info.pull_number}")
            self.logger.info(f"対象コメントID: {sorted(marked_comment_ids)}")

        resolved_count = 0
        failed_count = 0

        for i, comment_id in enumerate(sorted(marked_comment_ids), 1):
            try:
                self.logger.info(f"解決処理中 ({i}/{len(marked_comment_ids)}): コメントID {comment_id}")

                # GitHub APIを使ってコメントスレッドを解決済みにする
                # 注意: この機能はGraphQL APIまたは特別な権限が必要な場合があります
                success = self._resolve_comment_thread(comment_id, pr_info)

                if success:
                    resolved_count += 1
                    self.logger.info(f"✅ 解決成功: コメントID {comment_id}")
                    results.append({
                        "comment_id": comment_id,
                        "success": True,
                        "message": "解決済みステータスに更新しました"
                    })
                else:
                    failed_count += 1
                    self.logger.warning(f"❌ 解決失敗: コメントID {comment_id}")
                    results.append({
                        "comment_id": comment_id,
                        "success": False,
                        "message": "解決済みステータスの更新に失敗しました"
                    })

            except Exception as e:
                failed_count += 1
                error_msg = f"解決処理エラー: コメントID {comment_id} - {str(e)}"
                self.logger.error(error_msg)
                results.append({
                    "comment_id": comment_id,
                    "success": False,
                    "message": error_msg
                })

        self.logger.info(f"自動解決処理完了: 成功={resolved_count}件, 失敗={failed_count}件")
        return results

    def _resolve_comment_thread(self, comment_id: int, pr_info: GitHubPRInfo) -> bool:
        """個別のコメントスレッドを解決済みにする

        Args:
            comment_id: コメントID
            pr_info: プルリクエスト情報

        Returns:
            解決処理の成功フラグ
        """
        try:
            # GraphQL APIを使用してコメントスレッドを解決済みにする
            # 実装詳細は既存のGitHubClientのメソッドを活用
            return self.github_client.resolve_review_thread(comment_id, pr_info)

        except Exception as e:
            self.logger.error(f"コメントスレッド解決エラー (ID: {comment_id}): {str(e)}")
            return False
