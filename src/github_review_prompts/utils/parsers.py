"""パーザーユーティリティ"""

import re
import html
from typing import Tuple, Optional
from urllib.parse import urlparse


def parse_pr_url(pr_url: str) -> Tuple[str, str, int]:
    """プルリクエストURLを解析してowner, repo, pull_numberを取得"""
    if not pr_url or not isinstance(pr_url, str):
        raise ValueError(f"無効なプルリクエストURL: {pr_url}")

    # URLを正規化
    url = pr_url.strip()

    try:
        parsed = urlparse(url)

        # github.com以外は拒否
        if parsed.hostname != "github.com":
            raise ValueError(f"GitHub以外のURL: {parsed.hostname}")

        # プルリクエストURLのパターンマッチ
        pr_pattern = r"^/([^/]+)/([^/]+)/pull/(\d+)/?$"
        match = re.match(pr_pattern, parsed.path)

        if not match:
            raise ValueError(
                f"プルリクエストURLの形式が正しくありません: {parsed.path}"
            )

        owner, repo, pull_number_str = match.groups()

        # 基本的な検証
        if not owner or not repo or not pull_number_str:
            raise ValueError("URLの構成要素が不完全です")

        # プルリクエスト番号の変換と検証
        try:
            pull_number = int(pull_number_str)
            if pull_number <= 0:
                raise ValueError(f"無効なプルリクエスト番号: {pull_number}")
        except ValueError as e:
            raise ValueError(
                f"プルリクエスト番号の変換に失敗: {pull_number_str}"
            ) from e

        return owner, repo, pull_number

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"URL解析エラー: {str(e)}") from e


def extract_ai_agent_prompt(comment_body: str) -> Optional[str]:
    """コメント本文からPrompt for AI Agentsブロックを抽出"""
    if not comment_body or not isinstance(comment_body, str):
        return None

    # 複数のパターンに対応
    patterns = [
        # CodeRabbit標準形式: <details><summary>🤖 Prompt for AI Agents</summary>.....</details>
        r"<details>\s*<summary>🤖 Prompt for AI Agents</summary>\s*(.*?)\s*</details>",
        # Markdown形式1: 🤖 Prompt for AI Agents...```...```
        r"🤖 Prompt for AI Agents.*?\n```\n(.*?)\n```",
        # Markdown形式2: Prompt for AI Agents...```...```
        r"Prompt for AI Agents.*?\n```\n(.*?)\n```",
        # HTML形式: <summary>Prompt for AI Agents</summary>...<br>
        r"<summary>.*?Prompt for AI Agents.*?</summary>\s*(.*?)(?:\n|<br|$)",
        # シンプルなマークダウン: **Prompt for AI Agents**...
        r"\*\*Prompt for AI Agents\*\*\s*(.*?)(?:\n\n|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, comment_body, re.DOTALL | re.IGNORECASE)
        if match:
            prompt_text = match.group(1).strip()

            # HTMLタグとマークダウン記法を除去
            prompt_text = _clean_extracted_prompt(prompt_text)

            if prompt_text:  # 空でない場合のみ返す
                return prompt_text

    return None


def _clean_extracted_prompt(text: str) -> str:
    """抽出されたプロンプトテキストをクリーンアップ"""
    if not text:
        return ""

    # HTMLタグを除去
    text = re.sub(r"<[^>]+>", "", text)

    # マークダウンコードブロック記法を除去
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n```", "", text)
    text = re.sub(r"```", "", text)

    # マークダウン強調記法を除去
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # *italic*
    text = re.sub(r"_(.*?)_", r"\1", text)  # _italic_
    text = re.sub(r"`(.*?)`", r"\1", text)  # `code`

    # 余分な空白文字を除去
    text = re.sub(r"\s+", " ", text)

    # HTMLエンティティをデコード
    text = html.unescape(text)

    return text.strip()


def categorize_prompt(prompt: str, file_path: str = "") -> str:
    """プロンプト内容からカテゴリを推定"""
    if not prompt:
        return "general"

    prompt_lower = prompt.lower()
    file_lower = file_path.lower()

    # セキュリティ関連キーワード
    security_keywords = [
        "security",
        "vulnerability",
        "sanitiz",
        "validat",
        "escap",
        "inject",
        "xss",
        "csrf",
        "sql",
        "auth",
        "permission",
        "encrypt",
        "decrypt",
        "token",
        "password",
        "secret",
        "private",
        "sensitive",
        "exposure",
    ]

    # パフォーマンス関連キーワード
    performance_keywords = [
        "performance",
        "optimization",
        "optimize",
        "speed",
        "memory",
        "cache",
        "efficient",
        "slow",
        "fast",
        "bottleneck",
        "scale",
        "resource",
        "cpu",
        "ram",
        "database",
        "query",
        "index",
        "algorithm",
        "complexity",
    ]

    # スタイル関連キーワード
    style_keywords = [
        "style",
        "format",
        "naming",
        "convention",
        "consistent",
        "readable",
        "maintainable",
        "clean",
        "organize",
        "structure",
        "comment",
        "doc",
        "variable",
        "function",
        "class",
        "method",
        "indentation",
        "spacing",
    ]

    # ロジック関連キーワード
    logic_keywords = [
        "logic",
        "algorithm",
        "condition",
        "loop",
        "error",
        "exception",
        "handle",
        "return",
        "null",
        "undefined",
        "edge",
        "case",
        "bug",
        "fix",
        "correct",
        "implement",
        "refactor",
        "simplify",
    ]

    # キーワードマッチングによるカテゴリ判定
    if any(keyword in prompt_lower for keyword in security_keywords):
        return "security"
    elif any(keyword in prompt_lower for keyword in performance_keywords):
        return "performance"
    elif any(keyword in prompt_lower for keyword in style_keywords):
        return "style"
    elif any(keyword in prompt_lower for keyword in logic_keywords):
        return "logic"

    # ファイル拡張子による補助的な判定（file_pathがある場合のみ）
    if file_lower and file_lower.endswith((".sql", ".db")):
        return "performance"
    elif file_lower and file_lower.endswith((".css", ".scss", ".less")):
        return "style"
    elif file_lower and file_lower.endswith((".test.", ".spec.")):
        return "logic"

    return "general"


def extract_outside_diff_comments(comment_body: str) -> list:
    """Outside diff range commentsセクションから個別コメントを抽出"""
    if not comment_body or not isinstance(comment_body, str):
        return []

    extracted_comments = []

    # Outside diff range commentsセクションを探す
    outside_diff_pattern = r"<summary>⚠️ Outside diff range comments \(\d+\)</summary><blockquote>(.*?)</blockquote></details>"
    outside_match = re.search(
        outside_diff_pattern, comment_body, re.DOTALL | re.IGNORECASE
    )

    if not outside_match:
        return []

    outside_content = outside_match.group(1)

    # 各個別コメントを抽出
    individual_comment_pattern = r"<details>\s*<summary>(.*?)</summary><blockquote>\s*(.*?)\s*</blockquote></details>"

    for match in re.finditer(individual_comment_pattern, outside_content, re.DOTALL):
        file_info = match.group(1).strip()
        comment_content = match.group(2).strip()

        # ファイル名と行番号を抽出
        file_match = re.match(r"([^(]+)\s*\(\d+\)", file_info)
        if file_match:
            file_path = file_match.group(1).strip()

            # 行番号とタイトルを抽出
            line_match = re.search(r"`(\d+-\d+|\d+)`:\s*\*\*(.*?)\*\*", comment_content)
            line_info = line_match.group(1) if line_match else "unknown"
            title = line_match.group(2) if line_match else "修正が必要"

            # コメント本文をクリーンアップ
            clean_content = _clean_extracted_comment(comment_content)

            extracted_comments.append(
                {
                    "file_path": file_path,
                    "line": line_info,
                    "title": title,
                    "content": clean_content,
                    "priority": _determine_comment_priority(clean_content),
                    "category": _determine_comment_category(clean_content, file_path),
                }
            )

    return extracted_comments


def _clean_extracted_comment(text: str) -> str:
    """Outside diff commentsから抽出されたコメントをクリーンアップ"""
    if not text:
        return ""

    # 不要なマークダウン記法を除去
    text = re.sub(
        r"`(\d+-\d+|\d+)`:\s*\*\*(.*?)\*\*\s*", "", text
    )  # 行番号とタイトルを除去
    text = re.sub(r"```diff\n(.*?)\n```", r"\1", text, flags=re.DOTALL)  # diffブロック
    text = re.sub(
        r"```[a-zA-Z]*\n?(.*?)\n?```", r"\1", text, flags=re.DOTALL
    )  # コードブロック
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # Italic
    text = re.sub(r"`(.*?)`", r"\1", text)  # Inline code

    # HTMLタグを除去
    text = re.sub(r"<[^>]+>", "", text)

    # 余分な空白を除去
    text = re.sub(r"\s+", " ", text)
    text = html.unescape(text)

    return text.strip()


def _determine_comment_priority(content: str) -> str:
    """Outside diff commentの優先度を判定"""
    if not content:
        return "medium"

    content_lower = content.lower()

    # 緊急度の高いキーワード
    critical_keywords = [
        "セキュリティ",
        "security",
        "vulnerability",
        "脆弱性",
        "重要",
        "critical",
        "必須",
        "required",
        "must",
        "リスク",
        "risk",
        "危険",
        "danger",
        "バグ",
        "bug",
        "エラー",
        "error",
        "問題",
        "issue",
    ]

    # 中優先度キーワード
    medium_keywords = [
        "修正",
        "fix",
        "改善",
        "improve",
        "最適化",
        "optimize",
        "推奨",
        "recommend",
        "should",
        "better",
    ]

    # 低優先度キーワード
    low_keywords = [
        "提案",
        "suggestion",
        "consider",
        "検討",
        "任意",
        "optional",
        "スタイル",
        "style",
        "format",
        "フォーマット",
        "軽微",
        "minor",
    ]

    if any(keyword in content_lower for keyword in critical_keywords):
        return "high"
    elif any(keyword in content_lower for keyword in low_keywords):
        return "low"
    else:
        return "medium"


def _determine_comment_category(content: str, file_path: str) -> str:
    """Outside diff commentのカテゴリを判定"""
    if not content:
        return "general"

    content_lower = content.lower()
    file_lower = file_path.lower()

    # セキュリティ関連
    if any(
        keyword in content_lower
        for keyword in [
            "セキュリティ",
            "security",
            "vulnerability",
            "脆弱性",
            "injection",
            "xss",
            "csrf",
            "認証",
            "auth",
            "token",
            "password",
            "encrypt",
            "decrypt",
            "sanitiz",
        ]
    ):
        return "security"

    # 型安全性・TypeScript関連
    if any(
        keyword in content_lower
        for keyword in [
            "型",
            "type",
            "typescript",
            "interface",
            "generics",
            "cast",
            "any",
            "unknown",
        ]
    ):
        return "type-safety"

    # パフォーマンス関連
    if any(
        keyword in content_lower
        for keyword in [
            "パフォーマンス",
            "performance",
            "optimization",
            "memory",
            "cpu",
            "bottleneck",
            "効率",
            "efficient",
            "speed",
            "slow",
        ]
    ):
        return "performance"

    # アーキテクチャ・設計関連
    if any(
        keyword in content_lower
        for keyword in [
            "アーキテクチャ",
            "architecture",
            "design",
            "pattern",
            "structure",
            "モジュール",
            "module",
            "依存",
            "dependency",
        ]
    ):
        return "architecture"

    return "general"


def determine_priority(prompt: str, category: str) -> str:
    """プロンプト内容から優先度を推定"""
    if not prompt:
        return "medium"

    prompt_lower = prompt.lower()

    # 高優先度キーワード
    high_priority_keywords = [
        "critical",
        "security",
        "vulnerability",
        "crash",
        "error",
        "fail",
        "break",
        "bug",
        "urgent",
        "important",
        "must",
        "required",
        "necessary",
    ]

    # 低優先度キーワード
    low_priority_keywords = [
        "style",
        "format",
        "minor",
        "suggestion",
        "consider",
        "optional",
        "improve",
        "enhance",
        "better",
        "nice",
        "clean",
        "organize",
    ]

    # セキュリティカテゴリは基本的に高優先度
    if category == "security":
        return "high"

    # キーワードベースの判定
    if any(keyword in prompt_lower for keyword in high_priority_keywords):
        return "high"
    elif any(keyword in prompt_lower for keyword in low_priority_keywords):
        return "low"

    # デフォルトは中優先度
    return "medium"
