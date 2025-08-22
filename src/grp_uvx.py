#!/usr/bin/env python3
"""
GRP UVX - GitHub Review Prompt Generator
UVX専用の完全に独立したバージョン（依存関係なし）
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def get_github_token() -> str:
    """GitHub トークンを取得"""
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ エラー: GITHUB_TOKEN 環境変数が設定されていません。")
        print("")
        print("以下のコマンドで設定してください:")
        print("  export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("")
        print("GitHubトークンの取得方法:")
        print("  1. GitHub.com > Settings > Developer settings > Personal access tokens")
        print("  2. 'Generate new token' でトークンを作成")
        print("  3. 'repo' スコープを選択")
        sys.exit(1)
    return token


def parse_pr_url(pr_url: str) -> Optional[Tuple[str, str, int]]:
    """プルリクエストURLを解析"""
    patterns = [
        r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)',
        r'github\.com/([^/]+)/([^/]+)/pull/(\d+)',
        r'([^/]+)/([^/]+)#(\d+)',
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
    
    headers.update({
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GRP-UVX/1.0.0'
    })
    
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
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


def get_pr_review_comments(owner: str, repo: str, pr_number: int, token: str) -> List[Dict]:
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


def get_graphql_resolved_comments(owner: str, repo: str, pr_number: int, token: str) -> Set[int]:
    """GraphQL APIで解決済みコメントIDを取得"""
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              comments(first: 100) {
                nodes {
                  id
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
        "number": pr_number
    }
    
    data = {
        "query": query,
        "variables": variables
    }
    
    headers = {
        'Authorization': f'token {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'GRP-UVX/1.0.0'
    }
    
    try:
        request = urllib.request.Request(
            'https://api.github.com/graphql',
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                
                resolved_ids = set()
                
                if 'data' in result and result['data']:
                    pr_data = result['data']['repository']['pullRequest']
                    if pr_data and 'reviewThreads' in pr_data:
                        for thread in pr_data['reviewThreads']['nodes']:
                            if thread['isResolved']:
                                for comment in thread['comments']['nodes']:
                                    if comment['databaseId']:
                                        resolved_ids.add(comment['databaseId'])
                
                logger.info(f"GraphQL APIで {len(resolved_ids)} 件の解決済みコメントを検出")
                return resolved_ids
                
    except Exception as e:
        logger.warning(f"GraphQL API呼び出しでエラー: {str(e)}")
    
    return set()


def extract_review_type(body: str) -> str:
    """レビュー種類を抽出"""
    review_types = {
        '⚠️ Potential issue': 'Potential issue',
        '🛠️ Refactor suggestion': 'Refactor suggestion',
        '💡 Nitpick comments': 'Nitpick comments',
        '📝 Committable suggestion': 'Committable suggestion',
        '🔍 Verification agent': 'Verification agent',
        '📊 Analysis chain': 'Analysis chain'
    }
    
    for pattern, review_type in review_types.items():
        if pattern in body:
            return review_type
    
    return 'General comment'


def extract_title_from_comment(body: str) -> str:
    """コメントからタイトルを抽出"""
    lines = body.strip().split('\n')
    
    # **太字のタイトル**を探す
    for line in lines:
        line = line.strip()
        if line.startswith('**') and line.endswith('**') and len(line) > 4:
            return line[2:-2]  # **を除去
    
    # 最初の非空行を使用
    for line in lines:
        line = line.strip()
        if line and not line.startswith('_') and not line.startswith('`'):
            return line[:80] + '...' if len(line) > 80 else line
    
    return 'レビューコメント'


def extract_problem_description(body: str) -> str:
    """コメントから問題の説明を抽出"""
    lines = body.strip().split('\n')
    
    # **タイトル**の後の説明文を探す
    found_title = False
    description_lines = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('**') and line.endswith('**'):
            found_title = True
            continue
        
        if found_title and line and not line.startswith('```') and not line.startswith('<details>'):
            description_lines.append(line)
            if len(description_lines) >= 3:
                break
    
    if description_lines:
        description = ' '.join(description_lines)
        return description[:200] + '...' if len(description) > 200 else description
    
    # フォールバック
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    if len(non_empty_lines) > 1:
        return non_empty_lines[1][:100] + '...' if len(non_empty_lines[1]) > 100 else non_empty_lines[1]
    
    return 'レビューコメントの内容を確認してください'


def generate_coderabbit_curl_commands_for_comment(owner: str, repo: str, pr_number: int, comment_id: int, token: str) -> str:
    """特定のコメントに対するCodeRabbit返信用のcurlコマンドを生成"""
    templates = {
        "対応不要": f"@coderabbitai この指摘について確認しましたが、[技術的根拠]により対応不要と判断します。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。",
        "対応完了": f"@coderabbitai ご指摘いただいた点を修正しました。[修正内容]を実施済みです。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。",
        "要確認": f"@coderabbitai この指摘について追加で確認したい点があります：[確認したい内容]。詳細な説明をお願いします。"
    }
    
    curl_lines = []
    curl_lines.append(f"# コメントID: {comment_id} に対する返信用curlコマンド")
    curl_lines.append("")
    
    for action, message in templates.items():
        # JSONデータの準備（エスケープ処理）
        import json
        data = {
            "body": message,
            "in_reply_to": comment_id  # 特定のコメントに返信
        }
        data_json = json.dumps(data, ensure_ascii=False).replace('"', '\\"')
        
        curl_command = f'''# {action}の場合
curl -X POST \\
  "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" \\
  -H "Authorization: token {token}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d "{data_json}"'''
        
        curl_lines.append(curl_command)
    
    return "\n\n".join(curl_lines)


def generate_general_coderabbit_curl_commands(owner: str, repo: str, pr_number: int, token: str) -> str:
    """PR全体への一般的なCodeRabbit返信用のcurlコマンドを生成"""
    templates = {
        "全体完了": f"@coderabbitai すべてのレビューコメントを確認し、必要な対応を完了しました。各コメントに個別に返信していますので、ご確認ください。",
        "部分対応": f"@coderabbitai レビューコメントを確認しました。対応が必要な項目について修正を行い、対応不要と判断した項目については個別に理由をお伝えしています。"
    }
    
    curl_lines = []
    curl_lines.append("# PR全体に対する返信用curlコマンド（必要に応じて使用）")
    curl_lines.append("")
    
    for action, message in templates.items():
        import json
        data = {
            "body": message
        }
        data_json = json.dumps(data, ensure_ascii=False).replace('"', '\\"')
        
        curl_command = f'''# {action}の場合
curl -X POST \\
  "https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments" \\
  -H "Authorization: token {token}" \\
  -H "Accept: application/vnd.github.v3+json" \\
  -H "Content-Type: application/json" \\
  -d "{data_json}"'''
        
        curl_lines.append(curl_command)
    
    return "\n\n".join(curl_lines)


def get_default_review_prompt(no_confirm: bool = False, auto_commit: bool = False) -> str:
    """デフォルトレビュープロンプト"""
    base_prompt = """# CodeRabbit レビューコメント対応プロンプト

あなたはプログラミングの専門エンジニアです。プルリクエストのレビューコメントに対して、技術的に正確な対応を行ってください。

## 対応方針
1. **一つずつ順番に処理**: 複数のコメントがある場合、必ず一つずつ順番に対応してください
2. **批判的評価**: レビューコメントが技術的に正しいかどうかを必ず検証してください
3. **対応判断**: 各コメントに対して以下のいずれかの対応を決定してください：
   - ✅ 対応実施（修正が必要で技術的に正しい）
   - ❌ 対応不要（技術的に間違っているか不適切）
   - 🤔 要確認（追加情報が必要）

## 作業手順
1. コメントの技術的妥当性を評価
2. 対応要否を判断し、理由を明記
3. **対応する場合**: 具体的な修正を実施後、@coderabbitaiに完了報告
4. **対応しない場合**: GitHub APIを使って@coderabbitaiに技術的根拠を含む返信コメントを作成
5. **重要**: 各対応完了後は必ず該当コメントの解決済み指示を含める

## 出力フォーマット
各コメントに対して以下の形式で回答してください：

**コメント [番号]: [要約]**
- 判断: [✅/❌/🤔]
- 理由: [技術的根拠]
- 対応: [具体的な行動]
- 返信: [@coderabbitaiへの返信内容（対応完了・対応不要の場合）]

### 返信テンプレート

**✅ 対応完了時**:
```
@coderabbitai ご指摘いただいた点を修正しました。[修正内容]を実施済みです。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。
```

**❌ 対応不要時**:
```
@coderabbitai この指摘について確認しましたが、[技術的根拠]により対応不要と判断します。問題がなければこの課題を解決済みにしてください。ただし、この課題のみを解決済みにし、他の課題をすべて解決済みにしないよう注意してください。
```

**🤔 追加確認時**:
```
@coderabbitai この指摘について追加で確認したい点があります：[確認したい内容]。詳細な説明をお願いします。
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
## 🔄 Git自動操作設定
**自動コミット・プッシュモード**: すべてのレビューコメント対応完了後、以下を自動実行してください：

### Git操作手順
1. **ステージング**: `git add .` で変更ファイルをステージング
2. **コミット**: `git commit -m "CodeRabbit review comments addressed - [PR番号]"` でコミット
3. **プッシュ**: `git push` でリモートリポジトリに反映

### コミットメッセージ例
```
CodeRabbit review comments addressed - #123

- Fixed potential security issue in auth module
- Refactored database connection handling
- Updated error handling as suggested
```

**注意**: Git操作実行前に作業内容を簡潔にサマリーしてください。
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
  grp --no-color https://github.com/owner/repo/pull/123
  grp --no-confirm --auto-commit --no-color https://github.com/owner/repo/pull/123

環境変数:
  GITHUB_TOKEN - GitHub APIトークン（必須）

出力:
  - review_prompt_with_todos.md (プロンプトファイル)
  - コンソール出力
        """
    )
    
    parser.add_argument(
        'pr_url',
        help='GitHub プルリクエストURL'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='各コメント処理後の確認をスキップする'
    )
    
    parser.add_argument(
        '--auto-commit',
        action='store_true',
        help='作業完了後に自動的にgit commit & pushを実行する'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='カラー出力を無効にする（コピーペースト最適化）'
    )
    
    try:
        args = parser.parse_args()
    except SystemExit:
        return
    
    # カラー出力設定
    if args.no_color:
        os.environ['NO_COLOR'] = '1'
        
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
    head_branch = pr_info.get('head', {}).get('ref', '不明')
    head_repo = pr_info.get('head', {}).get('repo', {}).get('full_name', f"{owner}/{repo}")
    base_branch = pr_info.get('base', {}).get('ref', '不明')
    base_repo = pr_info.get('base', {}).get('repo', {}).get('full_name', f"{owner}/{repo}")
    
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
    
    # CodeRabbitコメントをフィルタリング
    coderabbit_comments = []
    for comment in comments:
        user_login = comment.get('user', {}).get('login', '')
        if user_login.startswith('coderabbitai'):
            if comment.get('id') not in resolved_ids:
                coderabbit_comments.append(comment)
    
    print(f"CodeRabbitコメント（未解決）: {len(coderabbit_comments)} 件")
    
    # 統計情報
    review_types = {}
    for comment in coderabbit_comments:
        review_type = extract_review_type(comment.get('body', ''))
        review_types[review_type] = review_types.get(review_type, 0) + 1
    
    print(f"CodeRabbit コメントを {len(coderabbit_comments)} 件処理しました")
    print()
    print("レビュー種別の内訳:")
    for review_type, count in review_types.items():
        print(f"  {review_type}: {count}")
    print()
    
    # プロンプト生成
    review_prompt = get_default_review_prompt(args.no_confirm, args.auto_commit)
    
    # PR全体への一般的なcurlコマンドを生成
    general_curl_commands = generate_general_coderabbit_curl_commands(owner, repo, pr_number, token)
    
    output = []
    output.append(review_prompt)
    output.append("")
    output.append("")
    output.append("## 🔧 PR全体への返信用curlコマンド")
    output.append("")
    output.append("レビュー対応完了後、必要に応じて以下のcurlコマンドを使用してください：")
    output.append("")
    output.append(general_curl_commands)
    output.append("")
    output.append("")
    output.append("## レビューコメント一覧")
    output.append("")
    output.append(f"**プルリクエスト**: {owner}/{repo}#{pr_number}")
    output.append(f"**URL**: {pr_url}")
    output.append(f"**タイトル**: {pr_info.get('title', 'タイトル不明')}")
    output.append(f"**作成者**: @{pr_info.get('user', {}).get('login', '不明')}")
    output.append("")
    output.append("### 📂 ブランチ情報")
    output.append(f"**ソースブランチ**: `{head_repo}:{head_branch}`")
    output.append(f"**ターゲットブランチ**: `{base_repo}:{base_branch}`")
    output.append("")
    output.append("### 🔄 作業開始コマンド")
    output.append("```bash")
    # 同じリポジトリかどうかで分岐
    if head_repo == f"{owner}/{repo}":
        output.append(f"# ローカルでソースブランチにチェックアウト")
        output.append(f"git checkout {head_branch}")
        output.append(f"git pull origin {head_branch}")
    else:
        output.append(f"# フォークからのPRの場合")
        output.append(f"git remote add fork https://github.com/{head_repo}.git")
        output.append(f"git fetch fork {head_branch}")
        output.append(f"git checkout -b {head_branch} fork/{head_branch}")
    output.append("```")
    output.append("")
    
    if not coderabbit_comments:
        output.append("⚠️ 対象となるレビューコメントが見つかりませんでした。")
        output.append("")
        output.append(f"- 解決済みコメント: {len(resolved_ids)} 件（除外済み）")
        output.append(f"- 総コメント数: {len(comments)} 件")
    else:
        for i, comment in enumerate(coderabbit_comments, 1):
            title = extract_title_from_comment(comment.get('body', ''))
            review_type = extract_review_type(comment.get('body', ''))
            problem = extract_problem_description(comment.get('body', ''))
            
            output.append(f"### TODO #{i}: {title}")
            output.append(f"**ID**: {comment.get('id', 'Unknown')}")
            output.append(f"**ファイル**: `{comment.get('path', 'Unknown')}`")
            output.append(f"**行**: {comment.get('line', 'Unknown')}")
            output.append(f"**種類**: {review_type}")
            output.append(f"**問題**: {problem}")
            output.append("")
            output.append("**元のコメント**:")
            output.append("```")
            output.append(comment.get('body', '').strip())
            output.append("```")
            output.append("")
            
            # 個別のcurlコマンドを生成
            comment_id = comment.get('id')
            if comment_id:
                comment_curl_commands = generate_coderabbit_curl_commands_for_comment(
                    owner, repo, pr_number, comment_id, token
                )
                output.append("**🔧 このコメントへの返信用curlコマンド**:")
                output.append("```bash")
                output.append(comment_curl_commands)
                output.append("```")
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
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined_output)


if __name__ == "__main__":
    main()