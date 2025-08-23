"""GitHub Issues連携による高度な統合機能"""

import logging
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import urllib.request
import urllib.error

from .resolution_detector import ResolutionStatus, ResolutionMethod
from .resolution_storage import ResolutionRecord

logger = logging.getLogger(__name__)


class GitHubIssuesIntegration:
    """GitHub Issues連携クラス"""

    def __init__(self, github_token: str):
        self.github_token = github_token
        self.logger = logging.getLogger(__name__)
        self.api_base = "https://api.github.com"

    def create_resolution_tracking_issue(
        self,
        pr_url: str,
        outside_diff_comments: List[Any],
        options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """範囲外コメント追跡用のIssueを作成

        Args:
            pr_url: プルリクエストURL
            outside_diff_comments: 範囲外コメントのリスト
            options: 作成オプション

        Returns:
            作成結果
        """
        if options is None:
            options = {}

        try:
            # PR情報を解析
            owner, repo, pr_number = self._parse_pr_url(pr_url)

            # Issue本文を生成
            issue_body = self._generate_tracking_issue_body(
                pr_url, outside_diff_comments, options
            )

            # Issueタイトルを生成
            issue_title = f"[範囲外コメント追跡] PR #{pr_number} - {len(outside_diff_comments)}件の対応状況"

            # Issue作成データ
            issue_data = {
                "title": issue_title,
                "body": issue_body,
                "labels": [
                    "outside-diff-comments",
                    "code-review-tracking",
                    f"pr-{pr_number}",
                ],
                "assignees": options.get("assignees", []),
                "milestone": options.get("milestone"),
            }

            # GitHub API呼び出し
            api_url = f"{self.api_base}/repos/{owner}/{repo}/issues"

            request = urllib.request.Request(
                api_url,
                data=json.dumps(issue_data).encode("utf-8"),
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                self.logger.info(f"追跡Issue作成成功: #{result['number']}")

                return {
                    "success": True,
                    "issue_number": result["number"],
                    "issue_url": result["html_url"],
                    "api_url": result["url"],
                    "created_at": result["created_at"],
                }

        except Exception as e:
            self.logger.error(f"追跡Issue作成に失敗: {e}")
            return {"success": False, "error": str(e)}

    def update_resolution_status_in_issue(
        self,
        issue_number: int,
        owner: str,
        repo: str,
        resolution_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Issue内の解決状況を更新

        Args:
            issue_number: Issue番号
            owner: リポジトリオーナー
            repo: リポジトリ名
            resolution_updates: 解決状況更新のリスト

        Returns:
            更新結果
        """
        try:
            # 現在のIssue本文を取得
            current_issue = self._get_issue(issue_number, owner, repo)
            if not current_issue:
                return {"success": False, "error": "Issue not found"}

            # Issue本文を更新
            updated_body = self._update_issue_body_with_resolutions(
                current_issue["body"], resolution_updates
            )

            # Issue更新データ
            update_data = {"body": updated_body}

            # GitHub API呼び出し
            api_url = f"{self.api_base}/repos/{owner}/{repo}/issues/{issue_number}"

            request = urllib.request.Request(
                api_url,
                data=json.dumps(update_data).encode("utf-8"),
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                method="PATCH",
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                self.logger.info(f"Issue #{issue_number} の解決状況を更新しました")

                return {
                    "success": True,
                    "updated_at": result["updated_at"],
                    "updates_applied": len(resolution_updates),
                }

        except Exception as e:
            self.logger.error(f"Issue更新に失敗: {e}")
            return {"success": False, "error": str(e)}

    def create_resolution_comment(
        self, pr_url: str, comment_id: int, resolution_record: ResolutionRecord
    ) -> Dict[str, Any]:
        """解決報告コメントを作成

        Args:
            pr_url: プルリクエストURL
            comment_id: 対象コメントID
            resolution_record: 解決記録

        Returns:
            コメント作成結果
        """
        try:
            owner, repo, pr_number = self._parse_pr_url(pr_url)

            # コメント本文を生成
            comment_body = self._generate_resolution_comment_body(resolution_record)

            # コメント作成データ
            comment_data = {"body": comment_body}

            # GitHub API呼び出し（PR全体コメント）
            api_url = (
                f"{self.api_base}/repos/{owner}/{repo}/issues/{pr_number}/comments"
            )

            request = urllib.request.Request(
                api_url,
                data=json.dumps(comment_data).encode("utf-8"),
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                self.logger.info(f"解決報告コメント作成成功: {result['html_url']}")

                return {
                    "success": True,
                    "comment_id": result["id"],
                    "comment_url": result["html_url"],
                    "created_at": result["created_at"],
                }

        except Exception as e:
            self.logger.error(f"解決報告コメント作成に失敗: {e}")
            return {"success": False, "error": str(e)}

    def sync_resolution_status_with_github(
        self, pr_url: str, local_resolutions: List[ResolutionRecord]
    ) -> Dict[str, Any]:
        """ローカルの解決状態をGitHubと同期

        Args:
            pr_url: プルリクエストURL
            local_resolutions: ローカルの解決記録

        Returns:
            同期結果
        """
        sync_result = {
            "pr_url": pr_url,
            "sync_timestamp": datetime.now().isoformat(),
            "synced_count": 0,
            "failed_count": 0,
            "errors": [],
            "created_comments": [],
            "updated_issues": [],
        }

        try:
            owner, repo, pr_number = self._parse_pr_url(pr_url)

            # 追跡Issue を探す
            tracking_issue = self._find_tracking_issue(owner, repo, pr_number)

            for resolution in local_resolutions:
                try:
                    # 解決報告コメントを作成
                    if resolution.status == ResolutionStatus.RESOLVED:
                        comment_result = self.create_resolution_comment(
                            pr_url, resolution.comment_id, resolution
                        )
                        if comment_result["success"]:
                            sync_result["synced_count"] += 1
                            sync_result["created_comments"].append(comment_result)
                        else:
                            sync_result["failed_count"] += 1
                            sync_result["errors"].append(
                                f"コメント作成失敗: {comment_result['error']}"
                            )

                    # 追跡Issueがある場合は更新
                    if tracking_issue:
                        # Issue内のチェックボックスを更新
                        self._update_tracking_issue_checkbox(
                            tracking_issue["number"], owner, repo, resolution
                        )

                except Exception as e:
                    sync_result["failed_count"] += 1
                    sync_result["errors"].append(
                        f"コメントID {resolution.comment_id}: {str(e)}"
                    )

            self.logger.info(
                f"GitHub同期完了: {sync_result['synced_count']}件成功, {sync_result['failed_count']}件失敗"
            )

        except Exception as e:
            self.logger.error(f"GitHub同期に失敗: {e}")
            sync_result["errors"].append(str(e))

        return sync_result

    def _parse_pr_url(self, pr_url: str) -> Tuple[str, str, int]:
        """プルリクエストURLを解析"""
        # https://github.com/owner/repo/pull/123
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if not match:
            raise ValueError(f"無効なプルリクエストURL: {pr_url}")

        return match.group(1), match.group(2), int(match.group(3))

    def _generate_tracking_issue_body(
        self, pr_url: str, outside_diff_comments: List[Any], options: Dict[str, Any]
    ) -> str:
        """追跡Issue本文を生成"""
        owner, repo, pr_number = self._parse_pr_url(pr_url)

        body = f"""# 範囲外コメント対応追跡

**対象PR**: [{owner}/{repo}#{pr_number}]({pr_url})
**作成日**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**総コメント数**: {len(outside_diff_comments)}件

## 📊 対応状況サマリー

- [ ] 🔴 緊急対応項目: {len([c for c in outside_diff_comments if c.severity.value == 'caution'])}件
- [ ] 🟡 重要対応項目: {len([c for c in outside_diff_comments if c.severity.value == 'warning'])}件
- [ ] 🟢 低優先対応項目: {len([c for c in outside_diff_comments if c.severity.value == 'info'])}件

## 📋 詳細対応リスト

"""

        # 優先度順にコメントを表示
        sorted_comments = sorted(
            outside_diff_comments,
            key=lambda x: (
                (
                    0
                    if x.severity.value == "caution"
                    else 1 if x.severity.value == "warning" else 2
                ),
                x.file_path,
            ),
        )

        for i, comment in enumerate(sorted_comments, 1):
            severity_icon = (
                "🔴"
                if comment.severity.value == "caution"
                else "🟡" if comment.severity.value == "warning" else "🟢"
            )
            category_icon = (
                "🚨"
                if comment.category.value == "actionable"
                else "♻️" if comment.category.value == "duplicate" else "🧹"
            )

            body += f"""
### {i}. {severity_icon} {comment.title}

- [ ] **対応完了**
- **ファイル**: `{comment.file_path}`
- **行範囲**: {comment.line_range}
- **カテゴリ**: {category_icon} {comment.category.value.title()}
- **コメントID**: {comment.id}

**詳細**: {comment.description[:200]}{'...' if len(comment.description) > 200 else ''}

---
"""

        body += f"""
## 🔧 使用方法

1. 各項目の対応完了後、該当するチェックボックスにチェックを入れてください
2. このIssueは自動的に更新され、全体の進捗を追跡します
3. 対応完了時は自動的にPRにコメントが投稿されます

## 📈 進捗追跡

このIssueは `github-review-prompts-ai-agent` により自動管理されています。

**最終更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        return body

    def _generate_resolution_comment_body(
        self, resolution_record: ResolutionRecord
    ) -> str:
        """解決報告コメント本文を生成"""
        status_icons = {
            ResolutionStatus.RESOLVED: "✅",
            ResolutionStatus.SKIPPED: "❌",
            ResolutionStatus.IN_PROGRESS: "🔄",
            ResolutionStatus.BLOCKED: "🚫",
        }

        method_descriptions = {
            ResolutionMethod.AI_AUTOMATED: "AI自動対応",
            ResolutionMethod.MANUAL: "手動対応",
            ResolutionMethod.SKIPPED: "対応スキップ",
            ResolutionMethod.DUPLICATE: "重複対応",
            ResolutionMethod.WONT_FIX: "修正しない",
            ResolutionMethod.DEFERRED: "延期",
        }

        status_icon = status_icons.get(resolution_record.status, "📝")
        method_desc = (
            method_descriptions.get(resolution_record.method, "不明")
            if resolution_record.method
            else "不明"
        )

        comment_body = f"""## {status_icon} 範囲外コメント対応報告

**コメントID**: {resolution_record.comment_id}
**ファイル**: `{resolution_record.file_path}`
**行範囲**: {resolution_record.line_range}
**対応方法**: {method_desc}
**対応者**: {resolution_record.resolved_by}
**対応日時**: {resolution_record.resolved_at}

"""

        if resolution_record.resolution_notes:
            comment_body += f"""
**対応詳細**:
{resolution_record.resolution_notes}
"""

        if resolution_record.confidence > 0:
            comment_body += f"""
**信頼度**: {resolution_record.confidence:.1%}
"""

        if resolution_record.validation_score > 0:
            comment_body += f"""
**検証スコア**: {resolution_record.validation_score:.1f}/100
"""

        comment_body += f"""

---
*この報告は `github-review-prompts-ai-agent` により自動生成されました*
"""

        return comment_body

    def _get_issue(
        self, issue_number: int, owner: str, repo: str
    ) -> Optional[Dict[str, Any]]:
        """Issueを取得"""
        try:
            api_url = f"{self.api_base}/repos/{owner}/{repo}/issues/{issue_number}"

            request = urllib.request.Request(
                api_url,
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))

        except Exception as e:
            self.logger.error(f"Issue取得に失敗: {e}")
            return None

    def _find_tracking_issue(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[Dict[str, Any]]:
        """追跡Issueを検索"""
        try:
            # ラベルで検索
            search_query = f"repo:{owner}/{repo} label:outside-diff-comments label:pr-{pr_number} is:issue"
            api_url = f"{self.api_base}/search/issues?q={quote_plus(search_query)}"

            request = urllib.request.Request(
                api_url,
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                if result["total_count"] > 0:
                    return result["items"][0]  # 最初のマッチを返す

        except Exception as e:
            self.logger.error(f"追跡Issue検索に失敗: {e}")

        return None

    def _update_issue_body_with_resolutions(
        self, current_body: str, resolution_updates: List[Dict[str, Any]]
    ) -> str:
        """Issue本文の解決状況を更新"""
        updated_body = current_body

        for update in resolution_updates:
            comment_id = update["comment_id"]
            status = update["status"]

            # チェックボックスの更新パターン
            checkbox_patterns = [
                # コメントIDによる特定
                re.compile(
                    f"- \\[ \\] \\*\\*対応完了\\*\\*.*?\\*\\*コメントID\\*\\*: {comment_id}",
                    re.MULTILINE | re.DOTALL,
                ),
                # タイトルによる特定（フォールバック）
                re.compile(
                    f'- \\[ \\] \\*\\*対応完了\\*\\*.*?{re.escape(update.get("title", "")[:50])}',
                    re.MULTILINE | re.DOTALL,
                ),
            ]

            for pattern in checkbox_patterns:
                if status == ResolutionStatus.RESOLVED:
                    # チェックボックスをチェック済みに変更
                    updated_body = pattern.sub(
                        lambda m: m.group(0).replace("- [ ]", "- [x]"), updated_body
                    )
                elif status == ResolutionStatus.SKIPPED:
                    # スキップマークを追加
                    updated_body = pattern.sub(
                        lambda m: m.group(0).replace(
                            "- [ ] **対応完了**", "- [x] **対応スキップ**"
                        ),
                        updated_body,
                    )

        # 最終更新時刻を更新
        timestamp_pattern = re.compile(r"\*\*最終更新\*\*: .+")
        updated_body = timestamp_pattern.sub(
            f"**最終更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            updated_body,
        )

        return updated_body

    def _update_tracking_issue_checkbox(
        self, issue_number: int, owner: str, repo: str, resolution: ResolutionRecord
    ) -> bool:
        """追跡Issue内のチェックボックスを更新"""
        try:
            resolution_updates = [
                {
                    "comment_id": resolution.comment_id,
                    "status": resolution.status,
                    "title": resolution.metadata.get("title", ""),
                }
            ]

            result = self.update_resolution_status_in_issue(
                issue_number, owner, repo, resolution_updates
            )

            return result["success"]

        except Exception as e:
            self.logger.error(f"追跡Issueチェックボックス更新に失敗: {e}")
            return False

    def generate_progress_dashboard_issue(
        self, owner: str, repo: str, stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """進捗ダッシュボードIssueを生成

        Args:
            owner: リポジトリオーナー
            repo: リポジトリ名
            stats: 統計情報

        Returns:
            Issue作成結果
        """
        try:
            # ダッシュボードIssue本文を生成
            dashboard_body = f"""# 🚀 範囲外コメント対応ダッシュボード

**リポジトリ**: {owner}/{repo}
**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**統計期間**: 過去{stats.get('period_days', 30)}日間

## 📊 全体統計

### 解決状況
- **総解決数**: {stats.get('total_resolutions', 0)}件
- **平均信頼度**: {stats.get('average_confidence', 0):.1%}
- **平均検証スコア**: {stats.get('average_validation_score', 0):.1f}/100

### 状態別内訳
"""

            status_breakdown = stats.get("status_breakdown", {})
            for status, count in status_breakdown.items():
                status_icon = {
                    "resolved": "✅",
                    "skipped": "❌",
                    "in_progress": "🔄",
                    "blocked": "🚫",
                }.get(status, "📝")
                dashboard_body += f"- {status_icon} **{status.title()}**: {count}件\n"

            dashboard_body += f"""
### 解決方法別内訳
"""

            method_breakdown = stats.get("method_breakdown", {})
            for method, count in method_breakdown.items():
                method_icon = {
                    "ai_automated": "🤖",
                    "manual": "👨‍💻",
                    "skipped": "⏭️",
                    "duplicate": "🔄",
                }.get(method, "📝")
                dashboard_body += f"- {method_icon} **{method.replace('_', ' ').title()}**: {count}件\n"

            # 最近のアクティビティ
            recent_activity = stats.get("recent_activity", [])
            if recent_activity:
                dashboard_body += f"""
## 📈 最近のアクティビティ

"""
                for activity in recent_activity[:10]:
                    status_icon = {
                        "resolved": "✅",
                        "skipped": "❌",
                        "in_progress": "🔄",
                    }.get(activity["status"], "📝")
                    resolved_at = datetime.fromisoformat(
                        activity["resolved_at"]
                    ).strftime("%m-%d %H:%M")
                    dashboard_body += f"- {status_icon} コメント#{activity['comment_id']} - {activity['resolved_by']} ({resolved_at})\n"

            # トップ解決者
            top_resolvers = stats.get("top_resolvers", {})
            if top_resolvers:
                dashboard_body += f"""
## 🏆 トップ解決者

"""
                sorted_resolvers = sorted(
                    top_resolvers.items(), key=lambda x: x[1], reverse=True
                )
                for resolver, count in sorted_resolvers[:5]:
                    dashboard_body += f"- **{resolver}**: {count}件\n"

            dashboard_body += f"""

---

## 🔧 管理情報

このダッシュボードは `github-review-prompts-ai-agent` により自動生成・更新されます。

**更新頻度**: 毎日自動更新
**データソース**: ローカル解決状態ストレージ
**最終更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            # Issue作成
            issue_data = {
                "title": f"[ダッシュボード] 範囲外コメント対応状況 - {owner}/{repo}",
                "body": dashboard_body,
                "labels": ["outside-diff-comments", "dashboard", "auto-generated"],
            }

            api_url = f"{self.api_base}/repos/{owner}/{repo}/issues"

            request = urllib.request.Request(
                api_url,
                data=json.dumps(issue_data).encode("utf-8"),
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                self.logger.info(f"ダッシュボードIssue作成成功: #{result['number']}")

                return {
                    "success": True,
                    "issue_number": result["number"],
                    "issue_url": result["html_url"],
                }

        except Exception as e:
            self.logger.error(f"ダッシュボードIssue作成に失敗: {e}")
            return {"success": False, "error": str(e)}

    def setup_automated_sync(
        self, pr_url: str, sync_interval_hours: int = 24
    ) -> Dict[str, Any]:
        """自動同期の設定

        Args:
            pr_url: プルリクエストURL
            sync_interval_hours: 同期間隔（時間）

        Returns:
            設定結果
        """
        # GitHub Actionsワークフローファイルを生成
        workflow_content = self._generate_sync_workflow(pr_url, sync_interval_hours)

        setup_result = {
            "pr_url": pr_url,
            "sync_interval_hours": sync_interval_hours,
            "workflow_content": workflow_content,
            "setup_instructions": [
                "1. リポジトリの .github/workflows/ ディレクトリに以下のファイルを作成:",
                "   `outside-diff-resolution-sync.yml`",
                "2. ワークフローファイルの内容を設定",
                "3. GITHUB_TOKEN シークレットを設定",
                "4. ワークフローを有効化",
            ],
        }

        return setup_result

    def _generate_sync_workflow(self, pr_url: str, sync_interval_hours: int) -> str:
        """同期用GitHub Actionsワークフローを生成"""
        owner, repo, pr_number = self._parse_pr_url(pr_url)

        workflow = f"""name: Outside Diff Comments Resolution Sync

on:
  schedule:
    # 毎{sync_interval_hours}時間実行
    - cron: '0 */{sync_interval_hours} * * *'
  workflow_dispatch:
    inputs:
      pr_number:
        description: 'PR Number to sync'
        required: false
        default: '{pr_number}'

jobs:
  sync-resolution-status:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'

    - name: Install uv
      run: |
        curl -LsSf https://astral.sh/uv/install.sh | sh
        echo "$HOME/.cargo/bin" >> $GITHUB_PATH

    - name: Install dependencies
      run: uv sync

    - name: Sync resolution status
      env:
        GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
      run: |
        PR_NUMBER="${{{{ github.event.inputs.pr_number || '{pr_number}' }}}}"
        PR_URL="https://github.com/{owner}/{repo}/pull/$PR_NUMBER"

        # 解決状態の同期
        uv run grp --sync-github-issues "$PR_URL"

    - name: Update dashboard
      env:
        GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
      run: |
        # ダッシュボードの更新
        uv run grp --update-dashboard "{owner}/{repo}"
"""

        return workflow

    def create_resolution_milestone(
        self, owner: str, repo: str, pr_number: int, total_comments: int
    ) -> Dict[str, Any]:
        """解決追跡用のマイルストーンを作成"""
        try:
            milestone_data = {
                "title": f"PR #{pr_number} 範囲外コメント対応",
                "description": f"PR #{pr_number} の {total_comments}件の範囲外コメント対応を追跡するマイルストーン",
                "due_on": (datetime.now() + timedelta(days=14)).isoformat(),  # 2週間後
                "state": "open",
            }

            api_url = f"{self.api_base}/repos/{owner}/{repo}/milestones"

            request = urllib.request.Request(
                api_url,
                data=json.dumps(milestone_data).encode("utf-8"),
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

                self.logger.info(f"解決追跡マイルストーン作成成功: {result['title']}")

                return {
                    "success": True,
                    "milestone_number": result["number"],
                    "milestone_url": result["html_url"],
                }

        except Exception as e:
            self.logger.error(f"マイルストーン作成に失敗: {e}")
            return {"success": False, "error": str(e)}
