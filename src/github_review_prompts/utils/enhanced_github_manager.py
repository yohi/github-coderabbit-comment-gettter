"""CodeRabbitアドバイスに基づく強化されたGitHub Issue管理システム"""

import logging
import requests
import json
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import hashlib
from dataclasses import dataclass

from .rate_limit_handler import GitHubRateLimitHandler, RateLimitStrategy
from .priority_classifier import EnhancedPriorityClassifier, PriorityLevel
from .enhanced_config import EnhancedConfigManager, IssueTemplateConfig
from .database_tracker import DatabaseProgressTracker, CommentStatus, ResolutionMethod

logger = logging.getLogger(__name__)


@dataclass
class IssueCreationResult:
    """Issue作成結果"""

    success: bool
    issue_number: Optional[int]
    issue_url: Optional[str]
    action_taken: str  # created, updated, skipped, error
    message: str
    existing_issue: Optional[Dict[str, Any]] = None


class EnhancedGitHubIssueManager:
    """CodeRabbitアドバイスに基づく強化されたGitHub Issue管理システム"""

    def __init__(
        self,
        config_manager: EnhancedConfigManager,
        db_tracker: Optional[DatabaseProgressTracker] = None,
    ):
        self.config = config_manager.config
        self.db_tracker = db_tracker
        self.logger = logging.getLogger(__name__)

        # GitHub API設定
        self.api_base_url = self.config.github.api_base_url
        self.repo = self.config.github.repo
        self.headers = {
            "Authorization": f"token {self.config.github.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Review-Prompts/1.0",
        }

        # レート制限ハンドラー
        strategy = RateLimitStrategy(self.config.github.rate_limit_strategy)
        self.rate_limiter = GitHubRateLimitHandler(strategy=strategy)

        # 優先度分類器
        self.priority_classifier = EnhancedPriorityClassifier()

        # 重複検出のためのキャッシュ
        self.issue_cache = {}
        self.cache_ttl = 3600  # 1時間
        self.last_cache_update = 0

        self.logger.info(f"強化されたGitHub Issue管理システム初期化: {self.repo}")

    @property
    def _session(self) -> requests.Session:
        """HTTPセッションを取得"""
        if not hasattr(self, "_http_session"):
            self._http_session = requests.Session()
            self._http_session.headers.update(self.headers)
        return self._http_session

    def create_issue_if_not_exists(
        self, comment_data: Dict[str, Any]
    ) -> IssueCreationResult:
        """重複チェック付きでIssueを作成

        Args:
            comment_data: コメントデータ
                - file_path: ファイルパス
                - line_number: 行番号
                - comment_body: コメント内容
                - priority: 優先度
                - category: カテゴリ
                - severity: 重要度

        Returns:
            Issue作成結果
        """
        try:
            # 優先度に基づく自動作成判定
            priority = comment_data.get("priority", "medium")
            if not self.config.processing_rules.auto_create_threshold:
                return IssueCreationResult(
                    success=False,
                    issue_number=None,
                    issue_url=None,
                    action_taken="skipped",
                    message="自動作成が無効です",
                )

            if not self._should_auto_create_issue(priority):
                return IssueCreationResult(
                    success=False,
                    issue_number=None,
                    issue_url=None,
                    action_taken="skipped",
                    message=f"優先度が閾値未満です: {priority}",
                )

            # 重複チェック
            existing_issue = self.find_existing_issue(comment_data)
            if existing_issue:
                # 既存Issueを更新
                updated_issue = self._update_existing_issue(
                    existing_issue, comment_data
                )
                return IssueCreationResult(
                    success=True,
                    issue_number=existing_issue["number"],
                    issue_url=existing_issue["html_url"],
                    action_taken="updated",
                    message="既存Issueを更新しました",
                    existing_issue=existing_issue,
                )

            # 新しいIssueを作成
            new_issue = self._create_new_issue(comment_data)
            if new_issue:
                # データベースに記録
                if self.db_tracker:
                    self.db_tracker.track_comment(
                        pr_number=comment_data.get("pr_number", 0),
                        pr_url=comment_data.get("pr_url", ""),
                        file_path=comment_data["file_path"],
                        line_number=comment_data.get("line_number"),
                        comment_body=comment_data["comment_body"],
                        priority=priority,
                        category=comment_data.get("category", "actionable"),
                        severity=comment_data.get("severity", "warning"),
                        estimated_hours=comment_data.get("estimated_hours", 2.0),
                        metadata={"issue_number": new_issue["number"]},
                    )

                return IssueCreationResult(
                    success=True,
                    issue_number=new_issue["number"],
                    issue_url=new_issue["html_url"],
                    action_taken="created",
                    message="新しいIssueを作成しました",
                )
            else:
                return IssueCreationResult(
                    success=False,
                    issue_number=None,
                    issue_url=None,
                    action_taken="error",
                    message="Issue作成に失敗しました",
                )

        except Exception as e:
            self.logger.error(f"Issue作成処理エラー: {e}")
            return IssueCreationResult(
                success=False,
                issue_number=None,
                issue_url=None,
                action_taken="error",
                message=f"エラー: {str(e)}",
            )

    def find_existing_issue(
        self, comment_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """既存Issueを検索

        Args:
            comment_data: コメントデータ

        Returns:
            既存Issue情報（見つからない場合はNone）
        """
        try:
            # キャッシュの更新チェック
            self._update_issue_cache_if_needed()

            file_path = comment_data["file_path"]
            line_number = comment_data.get("line_number")
            comment_body = comment_data["comment_body"]

            # 検索パターンを生成
            search_patterns = self._generate_search_patterns(
                file_path, line_number, comment_body
            )

            # キャッシュから検索
            for issue in self.issue_cache.values():
                if self._is_duplicate_issue(issue, search_patterns):
                    self.logger.info(
                        f"既存Issue発見: #{issue['number']} - {issue['title']}"
                    )
                    return issue

            # GitHub APIで検索（キャッシュにない場合）
            return self._search_issues_via_api(search_patterns)

        except Exception as e:
            self.logger.error(f"既存Issue検索エラー: {e}")
            return None

    def _should_auto_create_issue(self, priority: str) -> bool:
        """優先度に基づいてIssueを自動作成すべきかを判定"""
        priority_levels = ["low", "medium", "high", "critical"]
        threshold = self.config.processing_rules.auto_create_threshold

        try:
            threshold_index = priority_levels.index(threshold.lower())
            priority_index = priority_levels.index(priority.lower())
            return priority_index >= threshold_index
        except ValueError:
            return False

    def _generate_search_patterns(
        self, file_path: str, line_number: Optional[int], comment_body: str
    ) -> Dict[str, Any]:
        """検索パターンを生成"""
        # ファイルパスの正規化
        normalized_path = file_path.replace("\\", "/").strip("/")

        # 行番号範囲の計算
        line_ranges = []
        if line_number:
            # ±5行の範囲で検索
            for offset in range(-5, 6):
                line_ranges.append(line_number + offset)

        # コメント内容のキーワード抽出
        keywords = self._extract_keywords(comment_body)

        # コンテンツハッシュ
        content_hash = hashlib.md5(
            f"{normalized_path}:{line_number}:{comment_body[:200]}".encode("utf-8")
        ).hexdigest()[:8]

        return {
            "file_path": normalized_path,
            "line_number": line_number,
            "line_ranges": line_ranges,
            "keywords": keywords,
            "content_hash": content_hash,
            "title_patterns": [
                f"{normalized_path}",
                f"L{line_number}" if line_number else "",
                f"line {line_number}" if line_number else "",
            ],
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """テキストからキーワードを抽出"""
        # 技術的なキーワードを抽出
        keywords = []

        # Terraform固有のキーワード
        terraform_keywords = re.findall(
            r"\b(resource|data|variable|output|module|provider)\b", text, re.IGNORECASE
        )
        keywords.extend(terraform_keywords)

        # セキュリティ関連キーワード
        security_keywords = re.findall(
            r"\b(security|encryption|access|permission|policy|iam|kms)\b",
            text,
            re.IGNORECASE,
        )
        keywords.extend(security_keywords)

        # 一般的な問題キーワード
        problem_keywords = re.findall(
            r"\b(error|warning|issue|problem|bug|fix|deprecated)\b", text, re.IGNORECASE
        )
        keywords.extend(problem_keywords)

        # 重複を除去して返す
        return list(set(keyword.lower() for keyword in keywords))

    def _is_duplicate_issue(
        self, issue: Dict[str, Any], search_patterns: Dict[str, Any]
    ) -> bool:
        """Issueが重複かどうかを判定"""
        issue_title = issue.get("title", "").lower()
        issue_body = issue.get("body", "").lower()

        # ファイルパスの一致チェック
        if (
            search_patterns["file_path"].lower() in issue_title
            or search_patterns["file_path"].lower() in issue_body
        ):
            # 行番号の一致チェック
            if search_patterns["line_number"]:
                for line_num in search_patterns["line_ranges"]:
                    if (
                        f"l{line_num}" in issue_title
                        or f"line {line_num}" in issue_title
                    ):
                        return True
                    if f"l{line_num}" in issue_body or f"line {line_num}" in issue_body:
                        return True

            # キーワードの一致チェック
            keyword_matches = 0
            for keyword in search_patterns["keywords"]:
                if keyword in issue_title or keyword in issue_body:
                    keyword_matches += 1

            # キーワードの一致率が50%以上なら重複と判定
            if len(search_patterns["keywords"]) > 0:
                match_ratio = keyword_matches / len(search_patterns["keywords"])
                if match_ratio >= 0.5:
                    return True

        return False

    def _update_issue_cache_if_needed(self):
        """必要に応じてIssueキャッシュを更新"""
        current_time = time.time()
        if current_time - self.last_cache_update > self.cache_ttl:
            self._refresh_issue_cache()
            self.last_cache_update = current_time

    @GitHubRateLimitHandler().rate_limit_handler("core")
    def _refresh_issue_cache(self):
        """Issueキャッシュを更新"""
        try:
            # 最近のIssueを取得（過去30日間）
            since_date = (datetime.now() - timedelta(days=30)).isoformat()

            url = f"{self.api_base_url}/repos/{self.repo}/issues"
            params = {
                "state": "all",
                "since": since_date,
                "per_page": 100,
                "sort": "updated",
                "direction": "desc",
            }

            response = self._session.get(url, params=params)
            response.raise_for_status()

            issues = response.json()

            # キャッシュを更新
            self.issue_cache = {issue["number"]: issue for issue in issues}

            self.logger.info(f"Issueキャッシュを更新: {len(issues)}件")

        except Exception as e:
            self.logger.error(f"Issueキャッシュ更新エラー: {e}")

    @GitHubRateLimitHandler().rate_limit_handler("search")
    def _search_issues_via_api(
        self, search_patterns: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """GitHub Search APIでIssueを検索"""
        try:
            # 検索クエリを構築
            query_parts = [
                f"repo:{self.repo}",
                f"type:issue",
                f"in:title,body {search_patterns['file_path']}",
            ]

            if search_patterns["line_number"]:
                query_parts.append(f"L{search_patterns['line_number']}")

            # キーワードを追加
            for keyword in search_patterns["keywords"][:3]:  # 最大3つのキーワード
                query_parts.append(keyword)

            query = " ".join(query_parts)

            url = f"{self.api_base_url}/search/issues"
            params = {"q": query, "per_page": 10}

            response = self._session.get(url, params=params)
            response.raise_for_status()

            search_result = response.json()
            issues = search_result.get("items", [])

            # 最も関連性の高いIssueを選択
            for issue in issues:
                if self._is_duplicate_issue(issue, search_patterns):
                    return issue

            return None

        except Exception as e:
            self.logger.error(f"Issue検索エラー: {e}")
            return None

    def _get_issue_template(self, comment_data: Dict[str, Any]) -> IssueTemplateConfig:
        """コメントデータに基づいてIssueテンプレートを選択"""
        priority = comment_data.get("priority", "medium")
        category = comment_data.get("category", "actionable")
        severity = comment_data.get("severity", "warning")

        # セキュリティ関連の判定
        if "security" in comment_data.get("file_path", "").lower() or any(
            keyword in comment_data.get("comment_body", "").lower()
            for keyword in ["security", "vulnerability", "セキュリティ"]
        ):
            return self.config.issue_templates.get("security")

        # 構文エラーの判定
        if any(
            keyword in comment_data.get("comment_body", "").lower()
            for keyword in ["syntax error", "parse error", "構文エラー", "plan failed"]
        ):
            return self.config.issue_templates.get("syntax_error")

        # 優先度に基づく選択
        if priority in ["critical", "high"]:
            return self.config.issue_templates.get(
                "security"
            )  # 高優先度はセキュリティテンプレート
        elif category == "nitpick":
            return self.config.issue_templates.get("nitpick")
        else:
            return self.config.issue_templates.get("improvement")

    @GitHubRateLimitHandler().rate_limit_handler("core")
    def _create_new_issue(
        self, comment_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """新しいIssueを作成"""
        try:
            # テンプレートを取得
            template = self._get_issue_template(comment_data)
            if not template:
                self.logger.error("適切なIssueテンプレートが見つかりません")
                return None

            # タイトルを生成
            title = self._generate_issue_title(comment_data, template)

            # 本文を生成
            body = self._generate_issue_body(comment_data, template)

            # ラベルを決定
            labels = self._determine_labels(comment_data, template)

            # 担当者を決定
            assignee = template.assignee or comment_data.get("assignee")

            # Issue作成データ
            issue_data = {"title": title, "body": body, "labels": labels}

            if assignee:
                issue_data["assignee"] = assignee

            # GitHub APIでIssueを作成
            url = f"{self.api_base_url}/repos/{self.repo}/issues"
            response = self._session.post(url, json=issue_data)
            response.raise_for_status()

            new_issue = response.json()

            self.logger.info(f"新しいIssue作成: #{new_issue['number']} - {title}")

            # キャッシュに追加
            self.issue_cache[new_issue["number"]] = new_issue

            return new_issue

        except Exception as e:
            self.logger.error(f"Issue作成エラー: {e}")
            return None

    def _generate_issue_title(
        self, comment_data: Dict[str, Any], template: IssueTemplateConfig
    ) -> str:
        """Issueタイトルを生成"""
        file_path = comment_data["file_path"]
        line_number = comment_data.get("line_number")
        priority = comment_data.get("priority", "medium")

        # ファイル名を抽出
        file_name = Path(file_path).name

        # 行番号部分
        line_part = f" L{line_number}" if line_number else ""

        # 優先度アイコン
        priority_icons = {"critical": "🚨", "high": "⚠️", "medium": "📋", "low": "📝"}
        icon = priority_icons.get(priority, "📋")

        # コメントから問題の概要を抽出
        comment_body = comment_data.get("comment_body", "")
        summary = self._extract_issue_summary(comment_body)

        title = f"{template.title_prefix} {icon} {file_name}{line_part}: {summary}"

        # タイトルの長さ制限（GitHub制限: 256文字）
        if len(title) > 200:
            title = title[:197] + "..."

        return title

    def _extract_issue_summary(self, comment_body: str) -> str:
        """コメントから問題の概要を抽出"""
        # 最初の文または最初の50文字を使用
        lines = comment_body.split("\n")
        first_line = lines[0].strip()

        # マークダウン記号を除去
        first_line = re.sub(r"[*_`#-]", "", first_line).strip()

        # 長すぎる場合は短縮
        if len(first_line) > 50:
            first_line = first_line[:47] + "..."

        return first_line or "要確認"

    def _generate_issue_body(
        self, comment_data: Dict[str, Any], template: IssueTemplateConfig
    ) -> str:
        """Issue本文を生成"""
        # テンプレート変数を置換
        template_vars = {
            "file_path": comment_data["file_path"],
            "line_number": comment_data.get("line_number", "N/A"),
            "priority": comment_data.get("priority", "medium"),
            "category": comment_data.get("category", "actionable"),
            "severity": comment_data.get("severity", "warning"),
            "comment_body": comment_data.get("comment_body", ""),
            "pr_url": comment_data.get("pr_url", ""),
            "pr_number": comment_data.get("pr_number", "N/A"),
            "recommended_actions": self._generate_recommended_actions(comment_data),
            "impact_assessment": self._generate_impact_assessment(comment_data),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # テンプレートの変数を置換
        body = template.body_template
        for var_name, var_value in template_vars.items():
            body = body.replace(f"{{{var_name}}}", str(var_value))

        return body

    def _generate_recommended_actions(self, comment_data: Dict[str, Any]) -> str:
        """推奨アクションを生成"""
        priority = comment_data.get("priority", "medium")
        category = comment_data.get("category", "actionable")

        actions = []

        if priority == "critical":
            actions.append("🚨 即座に対応が必要です")
            actions.append("本番環境への影響を確認してください")
        elif priority == "high":
            actions.append("⚠️ 24時間以内に対応してください")

        if category == "security":
            actions.append("🔒 セキュリティチームに相談してください")
            actions.append("脆弱性スキャンを実行してください")

        if "terraform" in comment_data.get("file_path", "").lower():
            actions.append("🏗️ terraform plan で影響を確認してください")
            actions.append("ステートファイルのバックアップを取ってください")

        return (
            "\n".join(f"- {action}" for action in actions)
            if actions
            else "適切な対応を検討してください"
        )

    def _generate_impact_assessment(self, comment_data: Dict[str, Any]) -> str:
        """影響評価を生成"""
        file_path = comment_data.get("file_path", "")
        priority = comment_data.get("priority", "medium")

        impact_level = "中"
        if priority == "critical":
            impact_level = "高"
        elif priority == "low":
            impact_level = "低"

        # ファイルタイプに基づく影響評価
        if "security" in file_path.lower():
            return (
                f"**影響レベル**: {impact_level} - セキュリティに関わる重要な設定です"
            )
        elif "main.tf" in file_path.lower():
            return f"**影響レベル**: {impact_level} - メインの設定ファイルです"
        elif "prod" in file_path.lower():
            return (
                f"**影響レベル**: {impact_level} - 本番環境に影響する可能性があります"
            )
        else:
            return f"**影響レベル**: {impact_level}"

    def _determine_labels(
        self, comment_data: Dict[str, Any], template: IssueTemplateConfig
    ) -> List[str]:
        """ラベルを決定"""
        labels = template.labels.copy()

        # 優先度ラベル
        priority = comment_data.get("priority", "medium")
        if priority == "critical":
            labels.append("critical")
        elif priority == "high":
            labels.append("high-priority")

        # ファイルタイプラベル
        file_path = comment_data.get("file_path", "")
        if ".tf" in file_path:
            labels.append("terraform")
        if "security" in file_path.lower():
            labels.append("security")
        if "test" in file_path.lower():
            labels.append("testing")

        # 重複を除去
        return list(set(labels))

    @GitHubRateLimitHandler().rate_limit_handler("core")
    def _update_existing_issue(
        self, existing_issue: Dict[str, Any], comment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """既存Issueを更新"""
        try:
            issue_number = existing_issue["number"]

            # 更新内容を生成
            update_comment = self._generate_update_comment(comment_data)

            # コメントを追加
            url = (
                f"{self.api_base_url}/repos/{self.repo}/issues/{issue_number}/comments"
            )
            comment_data_api = {"body": update_comment}

            response = self._session.post(url, json=comment_data_api)
            response.raise_for_status()

            self.logger.info(f"既存Issue更新: #{issue_number}")

            return existing_issue

        except Exception as e:
            self.logger.error(f"既存Issue更新エラー: {e}")
            return existing_issue

    def _generate_update_comment(self, comment_data: Dict[str, Any]) -> str:
        """更新コメントを生成"""
        return f"""
## 🔄 関連する新しいコメント

**ファイル**: {comment_data['file_path']}
**行番号**: {comment_data.get('line_number', 'N/A')}
**PR**: {comment_data.get('pr_url', 'N/A')}

### コメント内容
{comment_data.get('comment_body', '')}

---
*自動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    def batch_create_issues(
        self, comments_data: List[Dict[str, Any]]
    ) -> List[IssueCreationResult]:
        """複数のIssueを一括作成"""
        results = []
        batch_size = self.config.processing_rules.batch_size

        for i in range(0, len(comments_data), batch_size):
            batch = comments_data[i : i + batch_size]

            for comment_data in batch:
                try:
                    result = self.create_issue_if_not_exists(comment_data)
                    results.append(result)

                    # レート制限対策の待機
                    time.sleep(self.config.processing_rules.rate_limit_delay)

                except Exception as e:
                    self.logger.error(f"バッチIssue作成エラー: {e}")
                    results.append(
                        IssueCreationResult(
                            success=False,
                            issue_number=None,
                            issue_url=None,
                            action_taken="error",
                            message=str(e),
                        )
                    )

            # バッチ間の待機
            if i + batch_size < len(comments_data):
                self.logger.info(f"バッチ処理待機: {batch_size}件処理完了")
                time.sleep(5)  # 5秒待機

        return results

    def generate_creation_report(
        self, results: List[IssueCreationResult]
    ) -> Dict[str, Any]:
        """Issue作成レポートを生成"""
        total = len(results)
        created = sum(1 for r in results if r.action_taken == "created")
        updated = sum(1 for r in results if r.action_taken == "updated")
        skipped = sum(1 for r in results if r.action_taken == "skipped")
        errors = sum(1 for r in results if r.action_taken == "error")

        return {
            "total_processed": total,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "success_rate": (created + updated) / total * 100 if total > 0 else 0,
            "created_issues": [
                {"number": r.issue_number, "url": r.issue_url}
                for r in results
                if r.action_taken == "created"
            ],
            "error_messages": [r.message for r in results if r.action_taken == "error"],
        }
