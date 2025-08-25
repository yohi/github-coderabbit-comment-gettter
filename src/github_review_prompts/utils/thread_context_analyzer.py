"""スレッド文脈分析システム

長いコメントやり取りの文脈を分析し、適切な処理方針を決定する。
重複対応や解決済み議論の再処理を防止する。
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ThreadStatus(Enum):
    """スレッド状況"""

    ACTIVE = "active"  # アクティブな議論
    RESOLVED = "resolved"  # 解決済み
    ONGOING_DISCUSSION = "ongoing"  # 議論継続中
    WAITING_RESPONSE = "waiting"  # 回答待ち
    STALE = "stale"  # 長期間未更新
    DUPLICATE = "duplicate"  # 重複議論


class ThreadPriority(Enum):
    """スレッド優先度"""

    CRITICAL = "critical"  # 緊急対応必要
    HIGH = "high"  # 高優先度
    MEDIUM = "medium"  # 中優先度
    LOW = "low"  # 低優先度
    IGNORE = "ignore"  # 対応不要


@dataclass
class ThreadAnalysis:
    """スレッド分析結果"""

    thread_id: str
    status: ThreadStatus
    priority: ThreadPriority
    participant_count: int
    message_count: int
    last_activity: datetime
    duration_hours: float
    resolution_markers: List[str]
    action_required: bool
    context_summary: str
    recommended_action: str


class ThreadContextAnalyzer:
    """コメントスレッドの文脈を分析するアナライザー"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 解決済みマーカーパターン
        self.resolution_markers = [
            r"CR_RESOLUTION_CONFIRMED",
            r"✅ エンジニアによる技術的検証完了",
            r"問題ないと判断.*解決済みにマーク",
            r"将来対応と判断.*解決済みにマーク",
            r"指摘が間違い.*解決済みにマーク",
            r"修正完了",
            r"対応済み",
            r"解決しました",
            r"Fixed, thanks!",
            r"Addressed in commits?",
            r"完了報告",
            r"対応完了",
            r"実装済み",
        ]

        # 議論継続中マーカー
        self.ongoing_markers = [
            r"@coderabbitai",
            r"確認",
            r"質問",
            r"どう思いますか",
            r"意見",
            r"提案",
            r"検討",
            r"verify",
            r"clarify",
            r"question",
        ]

        # 待機中マーカー
        self.waiting_markers = [
            r"回答待ち",
            r"確認中",
            r"検討中",
            r"調査中",
            r"pending",
            r"investigating",
            r"checking",
        ]

    def analyze_thread_status(
        self, thread_comments: List[Dict[str, Any]]
    ) -> ThreadAnalysis:
        """スレッドの現在状況を分析

        Args:
            thread_comments: スレッド内のコメントリスト（時系列順）

        Returns:
            ThreadAnalysis: 分析結果
        """
        if not thread_comments:
            return self._create_empty_analysis()

        # 基本情報の収集
        participants = set()
        first_comment = thread_comments[0]
        last_comment = thread_comments[-1]

        for comment in thread_comments:
            user = comment.get("user", {}).get("login", "")
            if user:
                participants.add(user)

        # 時間情報の計算
        first_time = self._parse_datetime(first_comment.get("created_at", ""))
        last_time = self._parse_datetime(last_comment.get("created_at", ""))

        duration_hours = 0.0
        if first_time and last_time:
            duration_hours = (last_time - first_time).total_seconds() / 3600

        # 最新コメントの分析
        latest_body = last_comment.get("body", "")

        # 解決状況の判定
        status = self._determine_thread_status(thread_comments)

        # 優先度の判定
        priority = self._determine_thread_priority(thread_comments, status)

        # アクション要否の判定
        action_required = self._is_action_required(status, last_time)

        # 文脈サマリーの生成
        context_summary = self._generate_context_summary(thread_comments)

        # 推奨アクションの決定
        recommended_action = self._determine_recommended_action(
            status, priority, duration_hours
        )

        # スレッドIDの生成（最初のコメントIDベース）
        thread_id = f"thread_{first_comment.get('id', 'unknown')}"

        return ThreadAnalysis(
            thread_id=thread_id,
            status=status,
            priority=priority,
            participant_count=len(participants),
            message_count=len(thread_comments),
            last_activity=last_time or datetime.now(),
            duration_hours=duration_hours,
            resolution_markers=self._find_resolution_markers(thread_comments),
            action_required=action_required,
            context_summary=context_summary,
            recommended_action=recommended_action,
        )

    def _determine_thread_status(
        self, thread_comments: List[Dict[str, Any]]
    ) -> ThreadStatus:
        """スレッドの状況を判定"""

        # 最新のコメントから判定
        latest_comment = thread_comments[-1]
        latest_body = latest_comment.get("body", "")
        latest_time = self._parse_datetime(latest_comment.get("created_at", ""))

        # 解決済み判定
        for marker in self.resolution_markers:
            if re.search(marker, latest_body, re.IGNORECASE):
                return ThreadStatus.RESOLVED

        # 全コメントで解決マーカーをチェック
        for comment in thread_comments:
            body = comment.get("body", "")
            for marker in self.resolution_markers:
                if re.search(marker, body, re.IGNORECASE):
                    return ThreadStatus.RESOLVED

        # 議論継続中判定
        for marker in self.ongoing_markers:
            if re.search(marker, latest_body, re.IGNORECASE):
                return ThreadStatus.ONGOING_DISCUSSION

        # 待機中判定
        for marker in self.waiting_markers:
            if re.search(marker, latest_body, re.IGNORECASE):
                return ThreadStatus.WAITING_RESPONSE

        # 長期間未更新判定（7日以上）
        if latest_time:
            # タイムゾーンを統一
            now = datetime.now()
            if latest_time.tzinfo is not None:
                # latest_timeがタイムゾーン付きの場合、nowもUTCにする
                from datetime import timezone

                now = datetime.now(timezone.utc)
            else:
                # latest_timeがタイムゾーンなしの場合、タイムゾーン情報を削除
                latest_time = latest_time.replace(tzinfo=None)

            days_since_update = (now - latest_time).days
            if days_since_update > 7:
                return ThreadStatus.STALE

        # デフォルトはアクティブ
        return ThreadStatus.ACTIVE

    def _determine_thread_priority(
        self, thread_comments: List[Dict[str, Any]], status: ThreadStatus
    ) -> ThreadPriority:
        """スレッドの優先度を判定"""

        # 解決済みは基本的に低優先度
        if status == ThreadStatus.RESOLVED:
            return ThreadPriority.IGNORE

        # 古いスレッドは低優先度
        if status == ThreadStatus.STALE:
            return ThreadPriority.LOW

        # セキュリティ関連キーワードの検出
        security_keywords = [
            "セキュリティ",
            "security",
            "脆弱性",
            "vulnerability",
            "トークン",
            "token",
            "パスワード",
            "password",
            "認証",
            "authentication",
            "権限",
            "permission",
        ]

        # 緊急キーワードの検出
        critical_keywords = [
            "緊急",
            "urgent",
            "critical",
            "破綻",
            "failure",
            "エラー",
            "error",
            "バグ",
            "bug",
            "クラッシュ",
            "crash",
        ]

        # 全コメントでキーワードチェック（CRITICAL を先）
        for comment in thread_comments:
            body = comment.get("body", "").lower()

            # 緊急キーワードは最高優先度
            if any(keyword.lower() in body for keyword in critical_keywords):
                return ThreadPriority.CRITICAL

            # セキュリティ関連は高優先度
            if any(keyword.lower() in body for keyword in security_keywords):
                return ThreadPriority.HIGH

        # スレッドの長さによる判定
        if len(thread_comments) > 5:
            return ThreadPriority.HIGH  # 長い議論は重要
        elif len(thread_comments) > 2:
            return ThreadPriority.MEDIUM
        else:
            return ThreadPriority.LOW

    def _is_action_required(
        self, status: ThreadStatus, last_activity: Optional[datetime]
    ) -> bool:
        """アクション要否を判定"""

        # 解決済みや待機中は基本的にアクション不要
        if status in [ThreadStatus.RESOLVED, ThreadStatus.WAITING_RESPONSE]:
            return False

        # 古いスレッドもアクション不要
        if status == ThreadStatus.STALE:
            return False

        # アクティブな議論や継続中はアクション必要
        if status in [ThreadStatus.ACTIVE, ThreadStatus.ONGOING_DISCUSSION]:
            return True

        return False

    def _generate_context_summary(self, thread_comments: List[Dict[str, Any]]) -> str:
        """スレッドの文脈サマリーを生成"""

        if not thread_comments:
            return "空のスレッド"

        first_comment = thread_comments[0]
        last_comment = thread_comments[-1]

        # 参加者の分析
        participants = set()
        coderabbit_count = 0
        developer_count = 0

        for comment in thread_comments:
            user = comment.get("user", {}).get("login", "")
            if user:
                participants.add(user)
                if "coderabbit" in user.lower():
                    coderabbit_count += 1
                else:
                    developer_count += 1

        # 主要なトピックの抽出
        topics = []
        for comment in thread_comments:
            body = comment.get("body", "")

            # 技術的なキーワードを抽出
            if "セキュリティ" in body or "security" in body.lower():
                topics.append("セキュリティ")
            if "バージョン" in body or "version" in body.lower():
                topics.append("バージョン管理")
            if "修正" in body or "fix" in body.lower():
                topics.append("修正作業")
            if "確認" in body or "verify" in body.lower():
                topics.append("確認作業")

        # サマリー生成
        summary_parts = []
        summary_parts.append(f"{len(thread_comments)}回のやり取り")
        summary_parts.append(f"{len(participants)}名参加")

        if topics:
            unique_topics = list(set(topics))
            summary_parts.append(f"主要トピック: {', '.join(unique_topics[:3])}")

        if coderabbit_count > 0 and developer_count > 0:
            summary_parts.append("CodeRabbitと開発者の議論")
        elif coderabbit_count > 0:
            summary_parts.append("CodeRabbitによる指摘")
        else:
            summary_parts.append("開発者間の議論")

        return " | ".join(summary_parts)

    def _determine_recommended_action(
        self, status: ThreadStatus, priority: ThreadPriority, duration_hours: float
    ) -> str:
        """推奨アクションを決定"""

        if status == ThreadStatus.RESOLVED:
            return "対応不要（解決済み）"

        if status == ThreadStatus.STALE:
            return "アーカイブ推奨（長期間未更新）"

        if priority == ThreadPriority.CRITICAL:
            return "即座対応（緊急事項）"

        if status == ThreadStatus.WAITING_RESPONSE:
            return "回答待ち（相手の対応待ち）"

        if status == ThreadStatus.ONGOING_DISCUSSION:
            if priority == ThreadPriority.HIGH:
                return "優先対応（重要な議論継続中）"
            else:
                return "通常対応（議論継続中）"

        if duration_hours > 24:
            return "状況確認（長期化している議論）"

        return "通常対応（新しい技術的指摘）"

    def _find_resolution_markers(
        self, thread_comments: List[Dict[str, Any]]
    ) -> List[str]:
        """解決マーカーを検出"""
        markers = []

        for comment in thread_comments:
            body = comment.get("body", "")
            for marker in self.resolution_markers:
                if re.search(marker, body, re.IGNORECASE):
                    markers.append(marker)

        return list(set(markers))  # 重複除去

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """日時文字列をdatetimeオブジェクトに変換"""
        if not datetime_str:
            return None

        try:
            # ISO 8601形式をパース
            return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _create_empty_analysis(self) -> ThreadAnalysis:
        """空のスレッド分析結果を作成"""
        return ThreadAnalysis(
            thread_id="empty",
            status=ThreadStatus.ACTIVE,
            priority=ThreadPriority.LOW,
            participant_count=0,
            message_count=0,
            last_activity=datetime.now(),
            duration_hours=0.0,
            resolution_markers=[],
            action_required=False,
            context_summary="空のスレッド",
            recommended_action="対応不要",
        )

    def analyze_multiple_threads(
        self, threads: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """複数スレッドの一括分析

        Args:
            threads: スレッドID -> コメントリストのマップ

        Returns:
            分析結果のサマリー
        """
        results = {
            "total_threads": len(threads),
            "thread_analyses": [],
            "summary_by_status": {
                "active": 0,
                "resolved": 0,
                "ongoing": 0,
                "waiting": 0,
                "stale": 0,
                "duplicate": 0,
            },
            "summary_by_priority": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "ignore": 0,
            },
            "action_required_count": 0,
            "total_messages": 0,
            "avg_thread_length": 0.0,
        }

        for thread_id, comments in threads.items():
            analysis = self.analyze_thread_status(comments)
            results["thread_analyses"].append(analysis)

            # 統計更新
            results["summary_by_status"][analysis.status.value] += 1
            results["summary_by_priority"][analysis.priority.value] += 1

            if analysis.action_required:
                results["action_required_count"] += 1

            results["total_messages"] += analysis.message_count

        # 平均計算
        if results["total_threads"] > 0:
            results["avg_thread_length"] = (
                results["total_messages"] / results["total_threads"]
            )

        self.logger.info(
            f"スレッド分析完了: "
            f"総スレッド数={results['total_threads']}, "
            f"アクション必要={results['action_required_count']}, "
            f"平均長={results['avg_thread_length']:.1f}メッセージ"
        )

        return results

    def get_thread_processing_guide(self, analysis_results: Dict[str, Any]) -> str:
        """スレッド処理ガイドを生成"""

        action_required_threads = [
            analysis
            for analysis in analysis_results["thread_analyses"]
            if analysis.action_required
        ]

        # 優先度順にソート
        priority_order = {
            ThreadPriority.CRITICAL: 0,
            ThreadPriority.HIGH: 1,
            ThreadPriority.MEDIUM: 2,
            ThreadPriority.LOW: 3,
            ThreadPriority.IGNORE: 4,
        }

        action_required_threads.sort(key=lambda x: priority_order.get(x.priority, 99))

        guide = f"""
## 📝 長期スレッド処理ガイドライン

### 📊 スレッド分析サマリー
- **総スレッド数**: {analysis_results['total_threads']}個
- **アクション必要**: {analysis_results['action_required_count']}個
- **平均メッセージ数**: {analysis_results['avg_thread_length']:.1f}件

### 📈 状況別内訳
- 🟢 **アクティブ**: {analysis_results['summary_by_status']['active']}個
- ✅ **解決済み**: {analysis_results['summary_by_status']['resolved']}個
- 🔄 **議論継続中**: {analysis_results['summary_by_status']['ongoing']}個
- ⏳ **回答待ち**: {analysis_results['summary_by_status']['waiting']}個
- 📦 **長期未更新**: {analysis_results['summary_by_status']['stale']}個

### 🎯 優先度別内訳
- 🔴 **緊急**: {analysis_results['summary_by_priority']['critical']}個
- 🟡 **高**: {analysis_results['summary_by_priority']['high']}個
- 🟢 **中**: {analysis_results['summary_by_priority']['medium']}個
- ⚪ **低**: {analysis_results['summary_by_priority']['low']}個

### ⚡ 対応必要スレッド ({len(action_required_threads)}個)

"""

        for i, analysis in enumerate(action_required_threads, 1):
            priority_icon = {
                ThreadPriority.CRITICAL: "🔴",
                ThreadPriority.HIGH: "🟡",
                ThreadPriority.MEDIUM: "🟢",
                ThreadPriority.LOW: "⚪",
            }.get(analysis.priority, "❓")

            guide += f"""#### {i}. {priority_icon} {analysis.thread_id}
- **状況**: {analysis.status.value}
- **優先度**: {analysis.priority.value}
- **メッセージ数**: {analysis.message_count}件
- **参加者数**: {analysis.participant_count}名
- **継続時間**: {analysis.duration_hours:.1f}時間
- **文脈**: {analysis.context_summary}
- **推奨アクション**: {analysis.recommended_action}

"""

        guide += f"""
### 🔄 処理方針
- **🔴緊急スレッド**: 即座に対応
- **🟡高優先度**: 24時間以内に対応
- **🟢中優先度**: 3日以内に対応
- **⚪低優先度**: 時間があるときに対応
- **✅解決済み**: 対応不要
- **⏳回答待ち**: 相手の回答を待つ

### 📋 長期スレッド対応テンプレート
```
@coderabbitai このスレッドが長期化しています。現在の状況を整理します：
- 当初の指摘: [要約]
- これまでの対応: [実施内容]
- 現在の状況: [未解決点]
- 次のアクション: [提案]
```
"""

        return guide.strip()


def create_thread_context_analyzer() -> ThreadContextAnalyzer:
    """スレッド文脈アナライザーのファクトリー関数"""
    return ThreadContextAnalyzer()


# 使用例とテスト用のサンプルデータ
if __name__ == "__main__":
    # テスト用のサンプルスレッド
    sample_threads = {
        "thread_1": [
            {
                "id": 1,
                "user": {"login": "coderabbitai[bot]"},
                "body": "_⚠️ Potential issue_\n\nセキュリティ上の問題があります。",
                "created_at": "2025-01-24T10:00:00Z",
            },
            {
                "id": 2,
                "user": {"login": "developer"},
                "body": "確認します。どのような対応が必要でしょうか？",
                "created_at": "2025-01-24T10:30:00Z",
            },
            {
                "id": 3,
                "user": {"login": "coderabbitai[bot]"},
                "body": "@developer 環境変数を使用してください。",
                "created_at": "2025-01-24T11:00:00Z",
            },
        ],
        "thread_2": [
            {
                "id": 4,
                "user": {"login": "coderabbitai[bot]"},
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリングを推奨します。",
                "created_at": "2025-01-24T09:00:00Z",
            },
            {
                "id": 5,
                "user": {"login": "developer"},
                "body": "修正完了しました。\n\n問題ないと判断できたら、下記フォーマットの解決済みマークをコメントの末尾に付与してください：\n\n[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]\n✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能\n[/CR_RESOLUTION_CONFIRMED]",
                "created_at": "2025-01-24T09:30:00Z",
            },
        ],
    }

    # スレッド分析実行
    analyzer = create_thread_context_analyzer()
    results = analyzer.analyze_multiple_threads(sample_threads)

    print("=== スレッド文脈分析 テスト結果 ===")
    print(f"総スレッド数: {results['total_threads']}")
    print(f"アクション必要: {results['action_required_count']}")
    print(f"平均メッセージ数: {results['avg_thread_length']:.1f}")

    print("\n=== 個別スレッド分析 ===")
    for analysis in results["thread_analyses"]:
        print(
            f"{analysis.thread_id}: {analysis.status.value} -> {analysis.recommended_action}"
        )

    print("\n=== 処理ガイド ===")
    print(analyzer.get_thread_processing_guide(results))
