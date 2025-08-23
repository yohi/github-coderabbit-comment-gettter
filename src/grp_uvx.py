#!/usr/bin/env python3
"""
GRP UVX - GitHub Review Prompt Generator
UVX専用の完全に独立したバージョン（依存関係なし）
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_github_token() -> str:
    """GitHub トークンを取得"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ エラー: GITHUB_TOKEN 環境変数が設定されていません。")
        print("")
        print("以下のコマンドで設定してください:")
        print("  export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
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
    """GitHub API リクエストを実行"""
    if headers is None:
        headers = {}

    headers.update(
        {
            "Authorization": f'token {os.getenv("GITHUB_TOKEN", token)}',
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GRP-UVX/1.0.0",
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
    """プルリクエスト基本情報を取得"""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    return make_github_request(url, token)


def get_pr_review_comments(
    owner: str, repo: str, pr_number: int, token: str
) -> List[Dict]:
    """プルリクエストのレビューコメントを取得"""
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
            page += 1
        else:
            break

    return comments


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
            "Authorization": f'Bearer {os.getenv("GITHUB_TOKEN", token)}',  # Bearer認証に修正
            "Content-Type": "application/json",
            "User-Agent": "GRP-UVX/1.0.0",
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


def generate_coderabbit_curl_commands_for_comment(
    owner: str, repo: str, pr_number: int, comment_id: int, token: str
) -> str:
    """特定のコメントに対するCodeRabbit返信用のcurlコマンドを生成（3パターンのみ）
    NOTE: 認証は環境変数 GITHUB_TOKEN を参照させ、トークン値は出力しない。
    """
    templates = {
        "対応不要": "@coderabbitai この指摘について確認しましたが、[技術的根拠]により対応不要と判断します。この課題のみを解決済みにしてください。",
        "指摘間違い": "@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。この課題のみを解決済みにしてください。",
        "要確認": "@coderabbitai この指摘について追加で確認したい点があります：[確認したい内容]。詳細な説明をお願いします。",
    }

    curl_lines = []
    curl_lines.append(f"# コメントID: {comment_id} に対する返信用curlコマンド")
    curl_lines.append("# 修正完了時は返信不要。以下3パターンのみ使用：")
    curl_lines.append("")

    for action, message in templates.items():
        # JSONデータの準備（エスケープ処理）
        import json

        data = {"body": message, "in_reply_to": comment_id}  # 特定のコメントに返信
        data_json = json.dumps(data, ensure_ascii=False).replace('"', '\\"')

        curl_command = f'''# {action}の場合
curl -X POST \\
  "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\
  -H "Authorization: token ${GITHUB_TOKEN}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d "{data_json}"'''

        curl_lines.append(curl_command)

    return "\n\n".join(curl_lines)


# PR全体への返信は削除（個別コメントへの返信のみ）


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

**⏳ 将来対応**: `@coderabbitai この指摘は妥当ですが、現在のPhase/ステップでは対応対象外です。現在: [具体的なPhase名]、対応予定: [具体的な将来Phase名]。**記憶依頼**: 以下を構造化記録し「[将来Phase名]」開始時・[技術領域]作業時に積極的に思い出してください - 指摘:[要約] 対象:[ファイル:行数] 解決方法:[実装案] 優先度:[高/中/低] 思い出し条件:[具体的なトリガー]。この課題のみを解決済みにしてください。`

**❌ 対応不要**: `@coderabbitai [技術的根拠]により対応不要と判断します。この課題のみを解決済みにしてください。`

**⚠️ 指摘間違い**: `@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。この課題のみを解決済みにしてください。`

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
「対応不要/将来対応/指摘間違い/要確認と判断したTODO項目について、すべてcurl返信を実行しましたか？」"""

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


def main():
    """メイン関数"""
    # 引数解析
    import argparse

    parser = argparse.ArgumentParser(
        description="🔄 GitHub Review Prompt Generator (UVX)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  grp https://github.com/owner/repo/pull/123
  grp --no-confirm https://github.com/owner/repo/pull/123
  grp --auto-commit https://github.com/owner/repo/pull/123
  grp --auto-reply https://github.com/owner/repo/pull/123
  grp --no-color https://github.com/owner/repo/pull/123
  grp --debug https://github.com/owner/repo/pull/123
  grp --no-confirm --auto-commit --auto-reply --no-color --debug https://github.com/owner/repo/pull/123

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

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="カラー出力を無効にする（コピーペースト最適化）",
    )

    parser.add_argument(
        "--auto-reply",
        action="store_true",
        help="コメントに自動的に返信を送信する（curlコマンド生成の代わりに）",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモードを有効にする（詳細ログ出力）",
    )

    try:
        args = parser.parse_args()
    except SystemExit:
        return

    # カラー出力設定
    if args.no_color:
        os.environ["NO_COLOR"] = "1"

    # デバッグモードでログレベル調整
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("デバッグモードが有効になりました")

    pr_url = args.pr_url

    # GitHub トークン取得
    token = get_github_token()

    # URL解析
    parsed = parse_pr_url(pr_url)
    if not parsed:
        logger.error(f"無効なプルリクエストURL: {pr_url}")
        sys.exit(1)

    owner, repo, pr_number = parsed

    print()
    print("🔄 CodeRabbit Review Prompt Generator (UVX)")
    print(f"📋 プルリクエスト: {pr_url}")
    print("=" * 80)

    # PR基本情報取得
    pr_info = get_pr_info(owner, repo, pr_number, token)
    if not pr_info:
        logger.error("プルリクエスト情報の取得に失敗しました")
        sys.exit(1)

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
    comments = get_pr_review_comments(owner, repo, pr_number, token)
    print(f"取得したコメント数: {len(comments)}")

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

    # 統計情報
    review_types = {}
    for comment in coderabbit_comments:
        review_type = extract_review_type(comment.get("body", ""))
        review_types[review_type] = review_types.get(review_type, 0) + 1

    print(f"処理対象: {len(coderabbit_comments)} 件")

    # プロンプト生成
    review_prompt = get_default_review_prompt(args.no_confirm, args.auto_commit)

    # curlコマンドは各TODO項目に直接埋め込み

    output = []
    output.append(review_prompt)
    output.append("")
    output.append("")

    # curlコマンドテンプレートを先に生成
    output.append("### 🔧 CodeRabbit返信用curlコマンド")
    output.append("")
    output.append("**認証**: 環境変数 GITHUB_TOKEN を使用します（値は出力しません）")
    output.append("")
    output.append("#### ❌ 対応不要（完全に不要）の場合")
    output.append("```bash")
    output.append(
        f'curl -X POST "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\\\'
    )
    output.append('  -H "Authorization: token ${GITHUB_TOKEN}" \\\\')
    output.append('  -H "Accept: application/vnd.github.v3+json" \\\\')
    output.append('  -H "Content-Type: application/json" \\\\')
    output.append("  -d '{")
    output.append(
        '    "body": "@coderabbitai 対応不要：[技術的根拠を記載]。適切と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。",'
    )
    output.append('    "in_reply_to": [COMMENT_ID]')
    output.append("  }'")
    output.append("```")
    output.append("")
    output.append("#### 📅 将来対応予定（このフェーズでは対応しない）の場合")
    output.append(
        "**重要**: curlコマンド実行と同時に、該当ソースファイルにTODOコメントを追加してください。"
    )
    output.append("```bash")
    output.append(
        f'curl -X POST "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\\\'
    )
    output.append('  -H "Authorization: token ${GITHUB_TOKEN}" \\\\')
    output.append('  -H "Accept: application/vnd.github.v3+json" \\\\')
    output.append('  -H "Content-Type: application/json" \\\\')
    output.append("  -d '{")
    output.append(
        '    "body": "@coderabbitai この指摘は妥当ですが、現在のPhase/ステップでは対応対象外です。現在: [具体的なPhase名]、対応予定: [具体的な将来Phase名]。**記憶依頼**: 以下を構造化記録し『[将来Phase名]』開始時・[技術領域]作業時に積極的に思い出してください - 指摘:[要約] 対象:[ファイル:行数] 解決方法:[実装案] 優先度:[高/中/低] 思い出し条件:[具体的なトリガー]。適切と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。",'
    )
    output.append('    "in_reply_to": [COMMENT_ID]')
    output.append("  }'")
    output.append("```")
    output.append("**ソースコード修正**: 指摘箇所に以下のTODOコメントを追加")
    output.append("```")
    output.append("// TODO: [次フェーズで対応予定] - [YYYY-MM-DD]")
    output.append("```")
    output.append("")
    output.append("#### 🤔 要確認の場合")
    output.append("```bash")
    output.append(
        f'curl -X POST "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\\\'
    )
    output.append('  -H "Authorization: token ${GITHUB_TOKEN}" \\\\')
    output.append('  -H "Accept: application/vnd.github.v3+json" \\\\')
    output.append('  -H "Content-Type: application/json" \\\\')
    output.append("  -d '{")
    output.append(
        '    "body": "@coderabbitai [確認したい内容]について詳細説明をお願いします。",'
    )
    output.append('    "in_reply_to": [COMMENT_ID]')
    output.append("  }'")
    output.append("```")
    output.append("")
    output.append("#### ⚠️ 指摘間違いの場合")
    output.append("```bash")
    output.append(
        f'curl -X POST "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\\\'
    )
    output.append('  -H "Authorization: token ${GITHUB_TOKEN}" \\\\')
    output.append('  -H "Accept: application/vnd.github.v3+json" \\\\')
    output.append('  -H "Content-Type: application/json" \\\\')
    output.append("  -d '{")
    output.append(
        '    "body": "@coderabbitai この指摘は[具体的な理由]により間違いと判断します。[正しい技術的説明]。妥当と判断される場合は**この特定の課題のみ**を解決済みにしてください。他の課題は変更しないでください。",'
    )
    output.append('    "in_reply_to": [COMMENT_ID]')
    output.append("  }'")
    output.append("```")
    output.append("")
    output.append("**使用方法**:")
    output.append("1. 各TODO項目の「コメントID」を確認")
    output.append("2. 上記テンプレートの `[COMMENT_ID]` を実際の値に置換")
    output.append("3. `[技術的根拠を記載]` 部分に具体的な理由を記入")
    output.append(
        "4. **📅 将来対応予定の場合**: 記憶依頼の各項目（Phase名、技術領域、指摘要約、対象、解決方法、優先度、トリガー条件）を具体的に記入"
    )
    output.append(
        "5. **📅 将来対応予定の場合のみ**: 該当ソースファイルにTODOコメントを追加"
    )
    output.append("6. curlコマンドを実行")
    output.append("")
    output.append("## レビューコメント一覧")
    output.append("")

    if not coderabbit_comments:
        output.append("⚠️ 対象となるレビューコメントが見つかりませんでした。")
        output.append("")
        output.append(f"- 解決済みコメント: {len(resolved_ids)} 件（除外済み）")
        output.append(f"- 総コメント数: {len(comments)} 件")
    else:
        for i, comment in enumerate(coderabbit_comments, 1):
            title = extract_title_from_comment(comment.get("body", ""))
            review_type = extract_review_type(comment.get("body", ""))
            problem = extract_problem_description(comment.get("body", ""))

            output.append(f"### TODO #{i}: {title}")
            output.append(
                f"**ファイル**: `{comment.get('path', 'Unknown')}` (行: {comment.get('line', 'Unknown')})"
            )
            output.append("")
            output.append("```")
            output.append(comment.get("body", "").strip())
            output.append("```")
            output.append("")

            # 自動返信またはcurlコマンド処理
            comment_id = comment.get("id")
            if comment_id:
                if args.auto_reply:
                    # 実際にAPIを使って返信
                    try:
                        # デフォルトの確認メッセージで返信
                        reply_message = f"@coderabbitai この指摘について確認中です。対応後に更新いたします。"

                        # POSTリクエストのデータを準備
                        post_data = {"body": reply_message, "in_reply_to": comment_id}

                        # GitHub API経由で返信
                        reply_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
                        headers = {
                            "Authorization": f'token {os.getenv("GITHUB_TOKEN", token)}',
                            "Accept": "application/vnd.github.v3+json",
                            "Content-Type": "application/json",
                            "User-Agent": "GRP-UVX/1.0.0",
                        }

                        request = urllib.request.Request(
                            reply_url,
                            data=json.dumps(post_data).encode("utf-8"),
                            headers=headers,
                            method="POST",
                        )

                        with urllib.request.urlopen(request) as response:
                            if response.status == 201:
                                result = json.loads(response.read().decode("utf-8"))
                                output.append("**✅ 自動返信完了**:")
                                output.append(f"- 返信ID: {result.get('id')}")
                                output.append(f"- メッセージ: {reply_message}")
                                output.append("")
                            else:
                                raise Exception(f"HTTP {response.status}")

                    except Exception as e:
                        output.append("**❌ 自動返信失敗**:")
                        output.append(f"- エラー: {str(e)}")
                        output.append(f"- 以下のcurlコマンドを手動で実行してください")
                        output.append("")

                        # 手動実行時はコメントIDのみ表示（curlコマンドは全体のヘッダーに含まれているため）
                        output.append(f"- **返信用コメントID**: {comment_id}")
                        output.append(
                            "- **手動実行**: 上記のcurlコマンドテンプレートを使用してください"
                        )
                        output.append("")
                else:
                    # 返信情報のみ表示（curlコマンドは全体のヘッダーに含まれているため個別表示不要）
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
    print(f"📄 ファイル保存: {output_file}")
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
    output_file = "review_prompt_with_todos.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(combined_output)

    # curlコマンドはプロンプト内に直接埋め込み済み（別ファイル不要）


if __name__ == "__main__":
    main()
