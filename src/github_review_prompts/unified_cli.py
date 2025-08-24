#!/usr/bin/env python3
"""
[非推奨] 統一CLI - uvx/uv両環境対応
このファイルは非推奨です。main.py の統一CLIを使用してください。

互換性のため一時的に残されています。
新しいコマンド: python -m github_review_prompts.main generate [OPTIONS]
"""

import warnings

warnings.warn(
    "このCLIは非推奨です。main.py の統一CLIを使用してください。",
    DeprecationWarning,
    stacklevel=2,
)

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Set, Optional, Tuple, Any
from pathlib import Path

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# 実行環境の検出
def detect_execution_environment():
    """実行環境を検出（uvx, uv run, 直接実行等）"""
    import sys

    # uvx実行の検出
    if any("uv" in str(path) and "archive" in str(path) for path in sys.path):
        return "uvx"

    # uv run実行の検出
    if any("uv" in str(path) and ".venv" in str(path) for path in sys.path):
        return "uv_run"

    # 直接実行
    return "direct"


EXECUTION_ENV = detect_execution_environment()

# 依存関係の可用性をチェック
HAS_FULL_DEPENDENCIES = True
IMPORT_ERROR = None

try:
    import requests
    from pydantic import BaseModel, Field, ConfigDict

    # フル機能版のインポート
    from .config import ConfigManager
    from .github_client import GitHubClient
    from .comment_processor import CommentProcessor
    from .prompt_generator import AIPromptGenerator
    from .output_formatter import OutputFormatter
    from .models import APIError, AuthenticationError, RateLimitError, PERSONAS
    from .utils.validators import (
        validate_pr_url,
        validate_persona,
        validate_output_format,
    )
except ImportError as e:
    HAS_FULL_DEPENDENCIES = False
    IMPORT_ERROR = e

    # uvx環境で依存関係が見つからない場合は致命的エラー
    if EXECUTION_ENV == "uvx":
        logger.error(f"❌ uvx環境で依存関係が見つかりません: {e}")
        logger.error("uvxが依存関係を正しくインストールできていない可能性があります。")
        logger.error("以下を試してください:")
        logger.error("  1. uv --version でuvのバージョンを確認")
        logger.error("  2. uvx --help でuvxが利用可能か確認")
        logger.error("  3. 一度 uvx cache clean で キャッシュをクリア")
        sys.exit(1)

    logger.debug(f"フル機能版の依存関係が利用できません: {e}")
    logger.debug("軽量モードで動作します")


def get_reply_templates() -> Dict[str, str]:
    """返信テンプレートを取得"""
    return {
        "fixed": "✅ Fixed! Thanks for the feedback.",
        "acknowledged": "👍 Acknowledged. I'll address this in the next update.",
        "investigating": "🔍 Looking into this issue. Will update soon.",
        "clarification": "🤔 Could you provide more details about this issue?",
        "wontfix": "⚠️ I understand the concern, but this is intentional due to [reason].",
    }


def reply_to_comment_with_curl(
    owner: str, repo: str, pr_number: int, comment_id: int, message: str, token: str
) -> bool:
    """
    curlを使ってコメントに返信

    Args:
        owner: リポジトリオーナー
        repo: リポジトリ名
        pr_number: PR番号
        comment_id: 返信対象のコメントID
        message: 返信メッセージ
        token: GitHub APIトークン

    Returns:
        成功した場合True
    """
    import subprocess
    import json

    # GitHub API URL
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"

    # 返信データ
    reply_data = {"body": message, "in_reply_to": comment_id}

    # curlコマンドを構築
    curl_cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        "-H",
        f"Authorization: Bearer {os.getenv('GITHUB_TOKEN') or token}",
        "-H",
        "Accept: application/vnd.github.v3+json",
        "-H",
        "Content-Type: application/json",
        "-H",
        "User-Agent: github-review-prompts-curl/1.0",
        "-d",
        json.dumps(reply_data),
        "-w",
        "\\n%{http_code}",
        url,
    ]

    try:
        logger.debug(f"Curl command: curl -X POST ... {url}")

        # curlコマンド実行
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Curl command failed: {result.stderr}")
            return False

        # レスポンスを分解（HTTPステータスコードを末尾から分離）
        output = result.stdout.strip()
        if "\n" in output:
            response_body, _, status = output.rpartition("\n")
        else:
            response_body, status = output, ""
        status_code = int(status) if status.isdigit() else 0

        if status_code == 201:
            # 成功
            try:
                response_data = json.loads(response_body)
                logger.info(f"✅ 返信成功: コメントID {response_data.get('id')}")
                logger.info(f"   URL: {response_data.get('html_url')}")
                return True
            except json.JSONDecodeError:
                logger.error("レスポンスのJSONパースに失敗")
                return False
        else:
            # エラー
            logger.error(f"❌ 返信失敗: HTTP {status_code}")
            try:
                error_data = json.loads(response_body)
                logger.error(f"   エラー: {error_data.get('message', 'Unknown error')}")
            except json.JSONDecodeError:
                logger.error(f"   Raw response: {response_body}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Curl command timed out")
        return False
    except Exception as e:
        logger.error(f"Curl execution error: {e}")
        return False


def handle_comment_reply(args) -> int:
    """
    コメント返信を処理

    Args:
        args: コマンドライン引数

    Returns:
        終了コード
    """
    # GitHub トークンを取得
    token = get_github_token()

    # PR URLをパース
    parsed = parse_pr_url(args.pr_url)
    if not parsed:
        print(f"❌ エラー: 無効なプルリクエストURLです: {args.pr_url}")
        return 1
    owner, repo, pr_number = parsed

    # 返信メッセージを決定
    if args.reply_template:
        templates = get_reply_templates()
        message = templates.get(args.reply_template)
        if not message:
            print(f"❌ エラー: 不明なテンプレート '{args.reply_template}'")
            return 1
    elif args.reply_message:
        message = args.reply_message
    else:
        print("❌ エラー: --reply-message または --reply-template が必要です")
        return 1

    print(f"📝 コメント {args.reply_to} に返信中...")
    print(f"メッセージ: {message}")
    print()

    # 確認プロンプト
    if not args.no_confirm:
        response = input("この返信を送信しますか？ [y/N]: ").strip().lower()
        if response not in ["y", "yes"]:
            print("返信がキャンセルされました")
            return 0

    # curlで返信実行
    success = reply_to_comment_with_curl(
        owner, repo, pr_number, args.reply_to, message, token
    )

    if success:
        print("✅ 返信送信完了")
        return 0
    else:
        print("❌ 返信送信失敗")
        return 1


def get_github_token() -> str:
    """GitHub トークンを取得"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ エラー: GITHUB_TOKEN 環境変数が設定されていません。")
        print("")
        print("以下のコマンドで設定してください:")
        print("  export GITHUB_TOKEN=your_github_token_here")
        print("")
        print("GitHubトークンの取得方法:")
        print(
            "  1. GitHub.com > Settings > Developer settings > Personal access tokens"
        )
        print("  2. 'Generate new token' でトークンを作成")
        print("  3. 'repo' スコープを選択")
        sys.exit(1)
    return token


def parse_pr_url(pr_url: str) -> Optional[Tuple[str, str, int]]:
    """プルリクエストURLを解析"""
    patterns = [
        r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        r"github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        r"([^/]+)/([^/]+)#(\d+)",
    ]

    for pattern in patterns:
        match = re.match(pattern, pr_url)
        if match:
            owner, repo, pr_number = match.groups()
            return owner, repo, int(pr_number)

    return None


def make_github_request(url: str, token: str, headers: Dict = None) -> Dict:
    """GitHub API リクエストを実行（軽量版）"""
    if headers is None:
        headers = {}

    headers.update(
        {
            "Authorization": f"token {os.getenv('GITHUB_TOKEN') or token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GRP-Unified/1.0.0",
        }
    )

    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
            else:
                logger.error(f"GitHub API エラー: HTTP {response.status}")
                return {}
    except Exception as e:
        logger.error(f"API リクエストエラー: {str(e)}")
        return {}


def get_pr_info(owner: str, repo: str, pr_number: int, token: str) -> Dict:
    """プルリクエスト基本情報を取得（軽量版）"""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    return make_github_request(url, token)


def get_pr_review_comments(
    owner: str, repo: str, pr_number: int, token: str
) -> List[Dict]:
    """プルリクエストのレビューコメントを取得（軽量版）"""
    comments = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments?page={page}&per_page={per_page}"
        page_comments = make_github_request(url, token)

        if not page_comments:
            break

        if isinstance(page_comments, list):
            comments.extend(page_comments)
            if len(page_comments) < per_page:
                break
        else:
            break

        page += 1
        time.sleep(0.1)  # レート制限対策

    return comments


def get_pr_issue_comments(
    owner: str, repo: str, pr_number: int, token: str
) -> List[Dict]:
    """プルリクエストのIssue commentsを取得（Outside diff range comments含む）"""
    comments = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments?page={page}&per_page={per_page}"
        page_comments = make_github_request(url, token)

        if not page_comments:
            break

        if isinstance(page_comments, list):
            # Issue commentsにメタデータを追加
            for comment in page_comments:
                comment["comment_type"] = "issue_comment"
                comment["is_outside_diff"] = True
                comment["path"] = None
                comment["line"] = None

            comments.extend(page_comments)
            if len(page_comments) < per_page:
                break
        else:
            break

        page += 1
        time.sleep(0.1)

    return comments


def get_all_pr_comments_graphql(
    owner: str, repo: str, pr_number: int, token: str
) -> Tuple[List[Dict], Dict[str, int]]:
    """GraphQL APIを使用してプルリクエストの全コメント（Outside diff range comments含む）を取得"""
    try:
        from .github_client import GitHubClient
        from .models import GitHubPRInfo

        # GitHubClientを初期化
        client = GitHubClient(token=token)
        pr_info = GitHubPRInfo(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        )

        # GraphQL APIでレビューとOutside diff commentsを取得
        all_reviews, outside_diff_comments = (
            client.get_pr_reviews_with_outside_diff_graphql(pr_info)
        )

        # REST APIでレビューコメントも取得（互換性のため）
        review_comments = get_pr_review_comments(owner, repo, pr_number, token)

        # 全コメントを結合
        all_comments = review_comments + all_reviews + outside_diff_comments

        # 統計情報
        stats = {
            "review_comments": len(review_comments),
            "graphql_reviews": len(all_reviews),
            "outside_diff_comments": len(outside_diff_comments),
            "total_comments": len(all_comments),
        }

        print(
            f"✅ GraphQL API取得完了: レビューコメント {stats['review_comments']} 件, "
            f"GraphQLレビュー {stats['graphql_reviews']} 件, "
            f"Outside diff {stats['outside_diff_comments']} 件, "
            f"合計 {stats['total_comments']} 件"
        )

        return all_comments, stats

    except Exception as e:
        print(f"⚠️ GraphQL API取得失敗、REST APIにフォールバック: {str(e)}")
        # フォールバック: 既存のREST API使用
        return get_all_pr_comments_rest(owner, repo, pr_number, token)


def get_all_pr_comments_rest(
    owner: str, repo: str, pr_number: int, token: str
) -> Tuple[List[Dict], Dict[str, int]]:
    """REST APIを使用してプルリクエストの全コメントを取得（フォールバック用）"""
    # レビューコメント（diff range内）を取得
    review_comments = get_pr_review_comments(owner, repo, pr_number, token)

    # Issue コメント（Outside diff range含む）を取得
    issue_comments = get_pr_issue_comments(owner, repo, pr_number, token)

    # 統計情報
    stats = {
        "review_comments": len(review_comments),
        "issue_comments": len(issue_comments),
        "total_comments": len(review_comments) + len(issue_comments),
    }

    # 全コメントを結合
    all_comments = review_comments + issue_comments

    return all_comments, stats


def get_all_pr_comments(
    owner: str, repo: str, pr_number: int, token: str
) -> Tuple[List[Dict], Dict[str, int]]:
    """プルリクエストの全コメント（GraphQL API優先、Outside diff range comments対応）

    Returns:
        Tuple[List[Dict], Dict[str, int]]: (全コメントリスト, 統計情報)
    """
    # GraphQL APIを優先使用（Outside diff range comments対応）
    return get_all_pr_comments_graphql(owner, repo, pr_number, token)


def get_graphql_resolved_comments(
    owner: str, repo: str, pr_number: int, token: str
) -> Set[int]:
    """GraphQL APIで解決済みコメントIDを取得（ページネーション対応）"""
    resolved_ids = set()
    has_next_page = True
    after_cursor = None
    page_count = 0
    total_resolved = 0

    logger.info(f"GraphQL APIで解決済みコメント取得開始: {owner}/{repo}#{pr_number}")

    while has_next_page:
        page_count += 1
        logger.debug(f"GraphQL ページ {page_count} 処理中...")

        query = """
        query($owner: String!, $repo: String!, $number: Int!, $after: String) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $number) {
              reviewThreads(first: 100, after: $after) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  isResolved
                  comments(first: 50) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      databaseId
                      author {
                        login
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "owner": owner,
            "repo": repo,
            "number": pr_number,
            "after": after_cursor,
        }

        data = {"query": query, "variables": variables}

        headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or token}",  # Bearer認証に修正
            "Content-Type": "application/json",
            "User-Agent": "GRP-Unified/1.0.0",
        }

        try:
            request = urllib.request.Request(
                "https://api.github.com/graphql",
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode("utf-8"))

                    # エラーチェック
                    if "errors" in result:
                        error_messages = [
                            error.get("message", str(error))
                            for error in result["errors"]
                        ]
                        logger.error(f"GraphQL エラー: {'; '.join(error_messages)}")
                        break

                    if (
                        not result.get("data", {})
                        .get("repository", {})
                        .get("pullRequest")
                    ):
                        logger.error(
                            "GraphQL レスポンスにプルリクエストデータが含まれていません"
                        )
                        break

                    review_threads = result["data"]["repository"]["pullRequest"][
                        "reviewThreads"
                    ]
                    threads = review_threads["nodes"]
                    page_info = review_threads["pageInfo"]

                    # ページネーション情報を更新
                    has_next_page = page_info["hasNextPage"]
                    after_cursor = page_info["endCursor"]

                    page_resolved = 0
                    for thread in threads:
                        if thread["isResolved"]:
                            # 解決済みスレッドの全コメントIDを記録
                            for comment in thread["comments"]["nodes"]:
                                if comment["databaseId"]:
                                    resolved_ids.add(comment["databaseId"])
                                    page_resolved += 1

                            # スレッド内コメントのページネーション警告
                            if thread["comments"]["pageInfo"]["hasNextPage"]:
                                logger.warning(
                                    "スレッド内に50を超えるコメントがあります。一部取得されていない可能性があります。"
                                )

                    total_resolved += page_resolved
                    logger.debug(
                        f"ページ {page_count}: {len(threads)} スレッド, {page_resolved} 解決済みコメント"
                    )

                    # APIレート制限を考慮した遅延
                    if has_next_page:
                        time.sleep(0.2)

                else:
                    response_text = (
                        response.read().decode("utf-8")
                        if hasattr(response, "read")
                        else "Unknown error"
                    )
                    logger.error(
                        f"GraphQL API エラー: HTTP {response.status} - {response_text[:200]}"
                    )
                    break

        except Exception as e:
            logger.warning(
                f"GraphQL API呼び出しでエラー (ページ {page_count}): {str(e)}"
            )
            break

    logger.info(
        f"GraphQL API完了: {page_count}ページ処理, {len(resolved_ids)} 件の解決済みコメントを検出"
    )
    return resolved_ids


def extract_review_type(body: str) -> str:
    """レビュー種類を抽出"""
    review_types = {
        "⚠️ Potential issue": "Potential issue",
        "🛠️ Refactor suggestion": "Refactor suggestion",
        "💡 Nitpick comments": "Nitpick comments",
        "📝 Committable suggestion": "Committable suggestion",
        "🔍 Verification agent": "Verification agent",
        "📊 Analysis chain": "Analysis chain",
    }

    for pattern, review_type in review_types.items():
        if pattern in body:
            return review_type

    return "General comment"


def extract_title_from_comment(body: str) -> str:
    """コメントからタイトルを抽出"""
    lines = body.strip().split("\n")

    # **太字のタイトル**を探す
    for line in lines:
        line = line.strip()
        if line.startswith("**") and line.endswith("**") and len(line) > 4:
            return line[2:-2]  # **を除去

    # 最初の非空行を使用
    for line in lines:
        line = line.strip()
        if line and not line.startswith("_") and not line.startswith("`"):
            return line[:80] + "..." if len(line) > 80 else line

    return "レビューコメント"


def extract_problem_description(body: str) -> str:
    """コメントから問題の説明を抽出"""
    lines = body.strip().split("\n")

    # **タイトル**の後の説明文を探す
    found_title = False
    description_lines = []

    for line in lines:
        line = line.strip()

        if line.startswith("**") and line.endswith("**"):
            found_title = True
            continue

        if (
            found_title
            and line
            and not line.startswith("```")
            and not line.startswith("<details>")
        ):
            description_lines.append(line)
            if len(description_lines) >= 3:
                break

    if description_lines:
        description = " ".join(description_lines)
        return description[:200] + "..." if len(description) > 200 else description

    # フォールバック
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    if len(non_empty_lines) > 1:
        return (
            non_empty_lines[1][:100] + "..."
            if len(non_empty_lines[1]) > 100
            else non_empty_lines[1]
        )

    return "レビューコメントの内容を確認してください"


def get_default_review_prompt(
    no_confirm: bool = False, auto_commit: bool = False
) -> str:
    """デフォルトレビュープロンプト"""
    base_prompt = """# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## 対応方針
1. **まずTODOリスト作成**: 開始前に必ず全コメントを分析してTODOタスクリストを作成してください
2. **体系的な処理**: TODOリスト完成後、一つずつ順番に処理してください
3. **批判的評価**: レビューコメントが技術的に正しいかどうかを必ず検証してください
4. **対応判断**: 各コメントに対して以下のいずれかの対応を決定してください：
   - ✅ 対応実施（修正が必要で技術的に正しい）
   - ⏳ 将来対応（技術的に正しいが現在のPhase/ステップでは対応しない）
   - ❌ 対応不要（技術的に間違っているか不適切）
   - 🤔 要確認（追加情報が必要）

## 作業手順

### Phase 1: TODOリスト作成
1. **全コメント分析**: すべてのレビューコメントを最初に確認
2. **TODOタスクリスト作成**: 各コメントの対応方針を決定してタスクリストを作成
3. **優先度設定**: 緊急度・重要度に基づいてタスクに優先度を付与

### Phase 2: 個別対応実行
4. **TODOリストに従って順次実行**: 作成したタスクリストの順番で対応
5. **技術的妥当性の再評価**: 各タスク実行時に改めて検証
6. **対応実施**: 修正・返信・記憶依頼を実行
7. **返信必須項目の確認**: ❌⏳⚠️🤔判定した項目はcurl返信必須（忘れやすいので要注意）
8. **進捗管理**: 各タスク完了後にTODOリストを更新

## 出力フォーマット

### Phase 1: TODOリスト
```
## 📋 TODO リスト（優先度順）
### 🔴 高優先度
- [ ] TODO-1: [コメント要約] - [対応方針]
### 🟡 中優先度
- [ ] TODO-2: [コメント要約] - [対応方針]
### 🟢 低優先度
- [ ] TODO-3: [コメント要約] - [対応方針]
```

### Phase 2: 個別対応
**TODO-[番号] 完了: [コメント要約]**
- 判断: [✅修正実施/⏳将来対応/❌対応不要/⚠️指摘間違い/🤔要確認]
- 理由: [技術的根拠]
- 対応: [具体的な行動]
- 返信: [curl返信が必要な場合のみ] ※❌⏳⚠️🤔は必須

### curl返信が必要な4パターン

**⏳ 将来対応**:
```
@coderabbitai この指摘は妥当ですが、現在のPhase/ステップでは対応対象外です。現在: [具体的なPhase名]、対応予定: [具体的な将来Phase名]。**記憶依頼**: 以下を構造化記録し「[将来Phase名]」開始時・[技術領域]作業時に積極的に思い出してください - 指摘:[要約] 対象:[ファイル:行数] 解決方法:[実装案] 優先度:[高/中/低] 思い出し条件:[具体的なトリガー]。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

**❌ 対応不要**:
```
@coderabbitai [技術的根拠]により対応不要と判断します。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

**⚠️ 指摘間違い**:
```
@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

**🤔 要確認**: `@coderabbitai [確認したい内容]について詳細説明をお願いします。`

**注意**: 修正完了時は返信不要です。

## 🚨 返信漏れ防止チェックリスト
**重要**: 以下の対応では必ずcurl返信を実行してください（忘れがちですが必須です）：

✅ **返信必須の対応**：
- ❌ 対応不要 → curl返信でCodeRabbitに通知
- ⏳ 将来対応 → curl返信 + ソースコードにTODOコメント追加
- ⚠️ 指摘間違い → curl返信でCodeRabbitに反論・説明
- 🤔 要確認 → curl返信でCodeRabbitに質問

✅ **返信不要の対応**：
- ✅ 修正実施 → コード修正のみ（curl返信不要）

**処理完了前の最終確認**：
「対応不要/将来対応/指摘間違い/要確認と判断したTODO項目について、すべてcurl返信を実行しましたか？」

### 🔧 返信方法（重要）
プルリクエストコメントに対する返信は、以下の **curlコマンド** を使用して行ってください：

```bash
# セキュアな方法（推奨）
echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers
curl -X POST \\
  -H @/tmp/github_headers \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{"body": "返信メッセージ", "in_reply_to": COMMENT_ID}' \\
  https://api.github.com/repos/OWNER/REPO/pulls/PR_NUMBER/comments
rm /tmp/github_headers
```

**返信すべき場面**:
- ❌ 対応不要と判断した場合
- ⏳ 将来対応と判断した場合
- 🤔 指摘内容が技術的に間違っていると判断した場合
- ❓ 不明な点があり確認が必要な場合

**注意**: GitHubの統合ツールやAPIツールは使用せず、必ずcurlコマンドで返信してください。

**返信例**:
```bash
# セキュアな方法（推奨）
echo "Authorization: Bearer $GITHUB_TOKEN" > /tmp/github_headers
curl -X POST \\
  -H @/tmp/github_headers \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d '{"body": "@coderabbitai この指摘について検証しましたが、現在の実装で問題ありません。理由：[技術的根拠]", "in_reply_to": 123456789}' \\
  https://api.github.com/repos/owner/repo/pulls/42/comments
rm /tmp/github_headers
```"""

    # 確認スキップオプションに応じたセクション追加
    if no_confirm:
        base_prompt += """

## ⚡ 作業モード設定
**確認スキップモード**: 各コメント処理後の確認は行わず、連続して処理を進めてください。
"""
    else:
        base_prompt += """

次のコメントに進む前に、必ず確認を求めてください。
"""

    # Git自動コミットオプションに応じたセクション追加
    if auto_commit:
        base_prompt += """
## 🔄 Git自動操作
**自動コミット・プッシュモード**: 全対応完了後、`git add . && git commit -m "CodeRabbit review addressed" && git push` を実行
"""

    base_prompt += """

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。"""

    return base_prompt


def run_lightweight_mode(args) -> int:
    """軽量モード実行"""
    logger.info(f"🚀 軽量モードで動作中（{EXECUTION_ENV}環境、依存関係なし）")

    # フル機能版専用オプションが指定されている場合は警告
    if hasattr(args, "persona") and args.persona != "code-reviewer":
        logger.warning(
            f"軽量モードでは --persona オプションは無視されます (指定値: {args.persona})"
        )
    if hasattr(args, "format") and args.format != "markdown":
        logger.warning(
            f"軽量モードでは --format オプションは無視されます (指定値: {args.format})"
        )
    if hasattr(args, "include_resolved") and args.include_resolved:
        logger.warning("軽量モードでは --include-resolved オプションは無視されます")

    pr_url = args.pr_url

    # GitHub トークン取得
    token = get_github_token()

    # URL解析
    parsed = parse_pr_url(pr_url)
    if not parsed:
        logger.error(f"無効なプルリクエストURL: {pr_url}")
        return 1

    owner, repo, pr_number = parsed

    print()
    print(
        f"🔄 GitHub Review Prompt Generator (統一版 - 軽量モード - {EXECUTION_ENV}環境)"
    )
    print(f"📋 プルリクエスト: {pr_url}")
    print("=" * 80)

    # PR基本情報取得
    pr_info = get_pr_info(owner, repo, pr_number, token)
    if not pr_info:
        logger.error("プルリクエスト情報の取得に失敗しました")
        return 1

    # ブランチ情報を抽出
    head_branch = pr_info.get("head", {}).get("ref", "不明")
    head_repo = (
        pr_info.get("head", {}).get("repo", {}).get("full_name", f"{owner}/{repo}")
    )
    base_branch = pr_info.get("base", {}).get("ref", "不明")
    base_repo = (
        pr_info.get("base", {}).get("repo", {}).get("full_name", f"{owner}/{repo}")
    )

    print(f"プルリクエスト情報: {owner}/{repo}#{pr_number}")
    print(f"タイトル: {pr_info.get('title', 'タイトル不明')}")
    print(f"ソースブランチ: {head_repo}:{head_branch}")
    print(f"ターゲットブランチ: {base_repo}:{base_branch}")

    # レビューコメント取得
    print("レビューコメント取得中...")
    comments, comment_stats = get_all_pr_comments(owner, repo, pr_number, token)
    print(f"取得したコメント数: {len(comments)}")
    print(f"  - レビューコメント: {comment_stats['review_comments']} 件")
    print(f"  - Issue コメント: {comment_stats['issue_comments']} 件")

    # 解決済みコメント検出
    print("解決済みコメント検出中...")
    resolved_ids = get_graphql_resolved_comments(owner, repo, pr_number, token)
    print(f"解決済みコメント: {len(resolved_ids)} 件")

    # CodeRabbitコメントをフィルタリング（詳細デバッグ付き）
    coderabbit_comments = []
    total_coderabbit = 0
    resolved_coderabbit = 0

    for comment in comments:
        user_login = comment.get("user", {}).get("login", "")
        if user_login.startswith("coderabbitai"):
            total_coderabbit += 1
            comment_id = comment.get("id")

            if comment_id in resolved_ids:
                resolved_coderabbit += 1
                logger.debug(f"解決済みCodeRabbitコメントをスキップ: ID {comment_id}")
            else:
                coderabbit_comments.append(comment)
                logger.debug(f"未解決CodeRabbitコメントを含む: ID {comment_id}")

    print(f"CodeRabbit統計:")
    print(f"  - 総CodeRabbitコメント: {total_coderabbit} 件")
    print(f"  - 解決済み: {resolved_coderabbit} 件")
    print(f"  - 未解決（処理対象）: {len(coderabbit_comments)} 件")

    print(f"処理対象: {len(coderabbit_comments)} 件")

    # プロンプト生成
    review_prompt = get_default_review_prompt(args.no_confirm, args.auto_commit)

    output = []
    output.append(review_prompt)
    output.append("")
    output.append("")

    # 簡潔なバッチ返信方法を生成
    output.append("### ⚡ 効率的な一括対応方法")
    output.append("")
    output.append(
        "**推奨ツール**: `github-review-prompts comment-reply-cli batch-reply`"
    )
    output.append("```bash")
    output.append(f"# バッチファイル作成後、一括実行")
    output.append(f"uvx --from /path/to/tool -n grp comment-reply-cli batch-reply \\\\")
    output.append(f"  {pr_url} --replies-file replies.json")
    output.append("```")
    output.append("")
    output.append("**代替方法（個別curl）**:")
    output.append("```bash")
    output.append(f"# 基本テンプレート (COMMENT_IDを各TODOから取得)")
    output.append(
        f'curl -X POST "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\\\'
    )
    output.append('  -H "Authorization: token ${GITHUB_TOKEN}" \\\\')
    output.append('  -H "Accept: application/vnd.github.v3+json" \\\\')
    output.append(
        '  -d \'{"body": "@coderabbitai [対応内容]", "in_reply_to": [COMMENT_ID]}\''
    )
    output.append("```")
    output.append("")
    output.append("**📋 返信テンプレート**:")
    output.append(
        "- ❌ **対応不要**: `@coderabbitai 対応不要: [理由]。解決済みマークしてください。`"
    )
    output.append(
        "- ⏳ **将来対応**: `@coderabbitai 将来対応予定: [Phase名]で実装。TODOコメント追加済み。`"
    )
    output.append(
        "- ✅ **実施完了**: `@coderabbitai 修正完了: [変更内容]。確認してください。`"
    )
    output.append("")

    output.append("## レビューコメント一覧")
    output.append("")

    # スマートフィルタリングを適用（軽量版でも）
    actionable_comments = []
    if coderabbit_comments:
        try:
            # スマートフィルタリングを適用
            from .utils.smart_comment_filter import SmartCommentFilter

            smart_filter = SmartCommentFilter()
            filter_results = smart_filter.filter_comments(coderabbit_comments)
            actionable_comments = filter_results["actionable_comments"]

            output.append(f"📊 スマートフィルタリング結果:")
            output.append(f"- 総コメント数: {filter_results['total_comments']}件")
            output.append(f"- 対応必要: {len(actionable_comments)}件")
            output.append(f"- フィルタ除外: {len(filter_results['filtered_out'])}件")
            output.append("")

            # フィルタリング除外の詳細
            if filter_results["filtered_out"]:
                output.append(
                    f"🤖 除外されたコメント ({len(filter_results['filtered_out'])}件):"
                )
                for excluded in filter_results["filtered_out"][:5]:  # 最初の5件のみ表示
                    reason = excluded.get("reason", "その他")
                    preview = excluded.get("body_preview", "")[:50]
                    output.append(f"  - {reason}: {preview}...")
                if len(filter_results["filtered_out"]) > 5:
                    output.append(
                        f"  - (他{len(filter_results['filtered_out']) - 5}件)"
                    )
                output.append("")

        except Exception as e:
            logger.warning(f"スマートフィルタリング失敗: {e}")
            actionable_comments = coderabbit_comments

    if not actionable_comments:
        output.append("✅ 対応が必要な技術的コメントは見つかりませんでした。")
        output.append("")
        output.append("詳細:")
        output.append(f"- 解決済みコメント: {len(resolved_ids)} 件（除外済み）")
        output.append(f"- 総コメント数: {len(comments)} 件")
        output.append(
            f"- フィルタ除外: {len(coderabbit_comments) - len(actionable_comments)} 件"
        )
        output.append("")
        output.append("💡 フィルタ除外されたコメントは主に以下の種類です:")
        output.append("  - 自動生成・情報提供コメント")
        output.append("  - 進捗報告・完了報告")
        output.append("  - 長いやり取りの中間コメント")
    else:
        output.append(f"🎯 対応が必要なコメント ({len(actionable_comments)}件):")
        output.append("")

        for i, comment in enumerate(actionable_comments, 1):
            title = extract_title_from_comment(comment.get("body", ""))
            review_type = extract_review_type(comment.get("body", ""))

            # 簡潔版表示
            output.append(f"### TODO #{i}: {title}")
            output.append(
                f"**ファイル**: `{comment.get('path', 'Unknown')}` (行: {comment.get('line', 'Unknown')})"
            )

            # コメント内容は最初の200文字のみ表示（簡潔化）
            body = comment.get("body", "").strip()
            if len(body) > 200:
                body_preview = body[:200] + "..."
                output.append("")
                output.append("**問題内容** (省略版):")
                output.append(body_preview)
                output.append("")
                output.append(
                    "**完全版確認**: 元のPRページでコメント詳細を確認してください"
                )
            else:
                output.append("")
                output.append("**問題内容**:")
                output.append("```")
                output.append(body)
                output.append("```")

            output.append("")

            # 返信情報のみ表示
            comment_id = comment.get("id")
            if comment_id:
                output.append(f"**返信用コメントID**: {comment_id}")
                output.append("")

            output.append("---")
            output.append("")

    # プロンプト用出力の生成
    combined_output = "\n".join(output)
    output_file = "review_prompt_with_todos.md"

    # 統計情報とファイル情報を先に表示
    print()
    print("=" * 80)
    print("✅ レビュープロンプトとTODOリストを生成しました")
    print(f"📋 処理対象コメント: {len(actionable_comments)} 件")
    if "filter_results" in locals():
        print(
            f"🗂️ 除外コメント: {len(filter_results['filtered_out'])} 件 (自動生成・進捗報告等)"
        )
    print()

    # プロンプト用コピー範囲の明確な開始マーカー
    print("🤖" + "=" * 78 + "🤖")
    print("📋 AI AGENT PROMPT - コピーペースト用範囲 (開始)")
    print("💡 以下の内容をコピーしてAIチャットに貼り付けてください")
    print("🤖" + "=" * 78 + "🤖")
    print()

    # プロンプト内容を出力
    print(combined_output)

    # プロンプト用コピー範囲の明確な終了マーカー
    print()
    print("🤖" + "=" * 78 + "🤖")
    print("📋 AI AGENT PROMPT - コピーペースト用範囲 (終了)")
    print("💡 上記の内容をコピーしてAIチャットに貼り付けてください")
    print("🤖" + "=" * 78 + "🤖")

    # ファイル保存
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(combined_output)

    return 0


def run_full_mode(args) -> int:
    """フル機能モード実行"""
    logger.info(f"🎨 フル機能モードで動作中（{EXECUTION_ENV}環境、高度な機能利用可能）")

    # フル機能版で基本オプションが使用可能であることを確認
    if hasattr(args, "persona"):
        logger.debug(f"ペルソナ: {args.persona}")
    if hasattr(args, "include_resolved"):
        logger.debug(f"解決済み含む: {args.include_resolved}")

    from .cli import CLIInterface

    cli = CLIInterface()
    # argsを直接渡すのではなく、sys.argvを使用
    return cli.run()


def create_argument_parser() -> argparse.ArgumentParser:
    """引数パーサーを作成"""
    parser = argparse.ArgumentParser(
        description="🔄 GitHub Review Prompt Generator (統一版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  # プロンプト生成
  grp https://github.com/owner/repo/pull/123
  grp --persona security-analyst https://github.com/owner/repo/pull/123
  grp --no-confirm https://github.com/owner/repo/pull/123
  grp --auto-commit https://github.com/owner/repo/pull/123
  grp --debug https://github.com/owner/repo/pull/123
  grp --no-confirm --auto-commit --debug https://github.com/owner/repo/pull/123

  # コメント返信（curlベース）
  grp --reply-to 123456 --reply-message "Fixed, thanks!" https://github.com/owner/repo/pull/123
  grp --reply-to 123456 --reply-template fixed https://github.com/owner/repo/pull/123
  grp --reply-to 123456 --reply-template acknowledged --no-confirm https://github.com/owner/repo/pull/123

モード説明:
  - uvx環境: 常にフル機能モード（依存関係自動インストール）
  - uv run環境: フル機能モード（仮想環境の依存関係使用）
  - 直接実行環境: 依存関係に応じて自動選択
    └ 依存関係あり: フル機能モード（高度なフィルタリング、ペルソナ等）
    └ 依存関係なし: 軽量モード（基本機能のみ、高速起動）

環境変数:
  GITHUB_TOKEN - GitHub APIトークン（必須）

出力:
  - review_prompt_with_todos.md (プロンプトファイル)
  - コンソール出力
        """,
    )

    parser.add_argument("pr_url", help="GitHub プルリクエストURL")

    parser.add_argument(
        "--no-confirm", action="store_true", help="各コメント処理後の確認をスキップする"
    )

    parser.add_argument(
        "--auto-commit",
        action="store_true",
        help="作業完了後に自動的にgit commit & pushを実行する",
    )

    # コメント返信機能
    parser.add_argument(
        "--reply-to", type=int, metavar="COMMENT_ID", help="指定されたコメントIDに返信"
    )

    parser.add_argument(
        "--reply-message",
        type=str,
        metavar="MESSAGE",
        help="返信メッセージ（--reply-toと組み合わせて使用）",
    )

    parser.add_argument(
        "--reply-template",
        type=str,
        choices=["fixed", "acknowledged", "investigating", "clarification", "wontfix"],
        help="返信テンプレートを使用",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="カラー出力を無効にする（コピーペースト最適化）",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモードを有効にする（詳細ログ出力）",
    )

    # フル機能版でのみ利用可能なオプション（常に追加するが、軽量版では警告）
    parser.add_argument(
        "--persona",
        choices=["code-reviewer", "security-analyst", "performance-optimizer"],
        default="code-reviewer",
        help="AIエージェントのペルソナ (フル機能モードのみ)",
    )

    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="出力形式 (フル機能モードのみ)",
    )

    parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="解決済みコメントも含める (フル機能モードのみ)",
    )

    return parser


def main() -> int:
    """メイン関数"""
    try:
        parser = create_argument_parser()
        args = parser.parse_args()

        # カラー出力設定
        if args.no_color:
            os.environ["NO_COLOR"] = "1"

        # デバッグモードでログレベル調整
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("デバッグモードが有効になりました")
            logger.debug(f"実行環境: {EXECUTION_ENV}")
            logger.debug(f"依存関係利用可能: {HAS_FULL_DEPENDENCIES}")
            if IMPORT_ERROR:
                logger.debug(f"インポートエラー: {IMPORT_ERROR}")

        # コメント返信モード
        if args.reply_to:
            return handle_comment_reply(args)

        # 実行環境に応じた動作決定
        if EXECUTION_ENV == "uvx":
            # uvx環境では常にフル機能モードを期待
            if HAS_FULL_DEPENDENCIES:
                logger.debug("🚀 uvx環境でフル機能モード実行")
                return run_full_mode(args)
            else:
                # この状況は上記で sys.exit(1) されるので通常到達しない
                logger.error("uvx環境で依存関係が利用できません")
                return 1
        else:
            # uv run または直接実行環境
            if HAS_FULL_DEPENDENCIES:
                logger.debug(f"🎨 {EXECUTION_ENV}環境でフル機能モード実行")
                return run_full_mode(args)
            else:
                logger.debug(f"🚀 {EXECUTION_ENV}環境で軽量モード実行")
                return run_lightweight_mode(args)

    except KeyboardInterrupt:
        print("\n\n⚠️  処理がユーザーによって中断されました。")
        return 130
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        if logging.getLogger().level == logging.DEBUG:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
