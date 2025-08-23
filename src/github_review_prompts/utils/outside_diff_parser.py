"""範囲外コメント（Outside diff range comments）の解析ユーティリティ"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple

from ..models import (
    OutsideDiffComment,
    OutsideDiffCommentCategory,
    OutsideDiffCommentSeverity,
)

logger = logging.getLogger(__name__)


class OutsideDiffParser:
    """範囲外コメントの解析クラス"""

    # 範囲外コメントセクションの検出パターン
    OUTSIDE_DIFF_PATTERN = re.compile(
        r"> \[!CAUTION\]\s*>\s*Some comments are outside the diff.*?"
        r"<details>\s*<summary>⚠️ Outside diff range comments.*?</summary>.*?"
        r"</details>",
        re.DOTALL | re.IGNORECASE,
    )

    # 重複コメントセクションの検出パターン
    DUPLICATE_COMMENTS_PATTERN = re.compile(
        r"<details>\s*<summary>♻️ Duplicate comments.*?</summary>.*?</details>",
        re.DOTALL | re.IGNORECASE,
    )

    # Nitpickコメントセクションの検出パターン
    NITPICK_COMMENTS_PATTERN = re.compile(
        r"<details>\s*<summary>🧹 Nitpick comments.*?</summary>.*?</details>",
        re.DOTALL | re.IGNORECASE,
    )

    # ファイル別コメントの検出パターン
    FILE_COMMENT_PATTERN = re.compile(
        r"<details>\s*<summary>(.*?)\s*\((\d+)\)</summary>.*?</details>",
        re.DOTALL | re.IGNORECASE,
    )

    # 個別コメントの検出パターン（改良版）
    INDIVIDUAL_COMMENT_PATTERN = re.compile(
        r"`(\d+(?:-\d+)?)`:\s*\*\*(.*?)\*\*\s*(.*?)(?=---|\n`\d+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    # ファイルパス・行番号の詳細解析パターン
    FILE_PATH_PATTERN = re.compile(
        r"([^/\s]+(?:/[^/\s]+)*\.(?:tf|py|js|ts|java|go|rs|rb|php|cpp|c|h|hpp|cs|swift|kt|scala|clj|ex|erl|hs|ml|fs|vb|pas|pl|sh|ps1|yaml|yml|json|xml|html|css|scss|sass|less|md|rst|txt))",
        re.IGNORECASE,
    )

    # 行範囲の詳細解析パターン
    LINE_RANGE_PATTERN = re.compile(r"^(\d+)(?:-(\d+))?$")

    # コード修正案の検出パターン
    CODE_SUGGESTION_PATTERN = re.compile(
        r"```diff\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE
    )

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_outside_diff_comments(self, comment_body: str) -> bool:
        """コメント本文に範囲外コメントが含まれているかを検出

        Args:
            comment_body: コメント本文

        Returns:
            範囲外コメントが含まれている場合True
        """
        return bool(self.OUTSIDE_DIFF_PATTERN.search(comment_body))

    def parse_outside_diff_comments(
        self, comment_body: str, comment_id: int = 0, author: str = ""
    ) -> List[OutsideDiffComment]:
        """範囲外コメントを解析してOutsideDiffCommentのリストを返す

        Args:
            comment_body: コメント本文
            comment_id: コメントID
            author: コメント作成者

        Returns:
            解析されたOutsideDiffCommentのリスト
        """
        outside_diff_comments = []

        # 各カテゴリのコメントを解析
        categories = [
            (
                self.OUTSIDE_DIFF_PATTERN,
                OutsideDiffCommentCategory.ACTIONABLE,
                OutsideDiffCommentSeverity.CAUTION,
            ),
            (
                self.DUPLICATE_COMMENTS_PATTERN,
                OutsideDiffCommentCategory.DUPLICATE,
                OutsideDiffCommentSeverity.WARNING,
            ),
            (
                self.NITPICK_COMMENTS_PATTERN,
                OutsideDiffCommentCategory.NITPICK,
                OutsideDiffCommentSeverity.INFO,
            ),
        ]

        for pattern, category, severity in categories:
            section_match = pattern.search(comment_body)
            if section_match:
                section_content = section_match.group(0)
                comments = self._parse_section_comments(
                    section_content, category, severity, comment_id, author
                )
                outside_diff_comments.extend(comments)

        self.logger.info(
            f"解析完了: {len(outside_diff_comments)}件の範囲外コメントを検出"
        )
        return outside_diff_comments

    def _parse_section_comments(
        self,
        section_content: str,
        category: OutsideDiffCommentCategory,
        severity: OutsideDiffCommentSeverity,
        base_comment_id: int,
        author: str,
    ) -> List[OutsideDiffComment]:
        """セクション内のコメントを解析

        Args:
            section_content: セクションの内容
            category: コメントカテゴリ
            severity: 重要度
            base_comment_id: ベースとなるコメントID
            author: コメント作成者

        Returns:
            解析されたOutsideDiffCommentのリスト
        """
        comments = []

        # ファイル別のコメントセクションを検出
        file_matches = self.FILE_COMMENT_PATTERN.finditer(section_content)

        for file_match in file_matches:
            file_path = file_match.group(1).strip()
            comment_count = int(file_match.group(2))
            file_section = file_match.group(0)

            # 個別のコメントを解析
            individual_comments = self._parse_individual_comments(
                file_section, file_path, category, severity, base_comment_id, author
            )
            comments.extend(individual_comments)

        return comments

    def _parse_individual_comments(
        self,
        file_section: str,
        file_path: str,
        category: OutsideDiffCommentCategory,
        severity: OutsideDiffCommentSeverity,
        base_comment_id: int,
        author: str,
    ) -> List[OutsideDiffComment]:
        """個別コメントの解析

        Args:
            file_section: ファイルセクションの内容
            file_path: ファイルパス
            category: コメントカテゴリ
            severity: 重要度
            base_comment_id: ベースとなるコメントID
            author: コメント作成者

        Returns:
            解析されたOutsideDiffCommentのリスト
        """
        comments = []
        comment_matches = self.INDIVIDUAL_COMMENT_PATTERN.finditer(file_section)

        for i, match in enumerate(comment_matches):
            line_range = match.group(1)
            title = match.group(2).strip()
            description = match.group(3).strip()

            # コード修正案を抽出
            suggested_fix = self._extract_code_suggestion(description)

            # 説明からコード修正案を除去
            clean_description = self.CODE_SUGGESTION_PATTERN.sub(
                "", description
            ).strip()

            comment = OutsideDiffComment(
                id=base_comment_id + i + 1,  # ユニークなIDを生成
                body=f"{title}\n\n{clean_description}",
                file_path=file_path,
                line_range=line_range,
                category=category,
                severity=severity,
                title=title,
                description=clean_description,
                suggested_fix=suggested_fix,
                author=author,
                context={
                    "original_section": file_section,
                    "category_name": category.value,
                    "severity_name": severity.value,
                },
            )
            comments.append(comment)

        return comments

    def _extract_code_suggestion(self, description: str) -> Optional[str]:
        """説明からコード修正案を抽出

        Args:
            description: コメントの説明

        Returns:
            コード修正案（存在する場合）
        """
        code_match = self.CODE_SUGGESTION_PATTERN.search(description)
        if code_match:
            return code_match.group(1).strip()
        return None

    def categorize_by_priority(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, List[OutsideDiffComment]]:
        """コメントを優先度別に分類

        Args:
            comments: OutsideDiffCommentのリスト

        Returns:
            優先度別に分類されたコメント辞書
        """
        priority_map = {
            OutsideDiffCommentSeverity.CAUTION: "🔴 緊急",
            OutsideDiffCommentSeverity.WARNING: "🟡 重要",
            OutsideDiffCommentSeverity.INFO: "🟢 低優先",
        }

        categorized = {}
        for comment in comments:
            priority_key = priority_map[comment.severity]
            if priority_key not in categorized:
                categorized[priority_key] = []
            categorized[priority_key].append(comment)

        return categorized

    def get_priority_order(self) -> List[str]:
        """優先度の順序を取得

        Returns:
            優先度の順序リスト
        """
        return ["🔴 緊急", "🟡 重要", "🟢 低優先"]

    def parse_file_path_details(self, file_path: str) -> Dict[str, Any]:
        """ファイルパスの詳細情報を解析

        Args:
            file_path: ファイルパス

        Returns:
            ファイルパスの詳細情報
        """
        details = {
            "full_path": file_path,
            "directory": "",
            "filename": "",
            "extension": "",
            "language": "unknown",
            "is_config": False,
            "is_test": False,
        }

        if "/" in file_path:
            parts = file_path.split("/")
            details["directory"] = "/".join(parts[:-1])
            details["filename"] = parts[-1]
        else:
            details["filename"] = file_path

        if "." in details["filename"]:
            name_parts = details["filename"].rsplit(".", 1)
            details["extension"] = name_parts[1].lower()

            # 言語判定
            language_map = {
                "tf": "terraform",
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "java": "java",
                "go": "go",
                "rs": "rust",
                "rb": "ruby",
                "php": "php",
                "cpp": "cpp",
                "c": "c",
                "h": "c",
                "hpp": "cpp",
                "cs": "csharp",
                "swift": "swift",
                "kt": "kotlin",
                "scala": "scala",
                "yaml": "yaml",
                "yml": "yaml",
                "json": "json",
                "xml": "xml",
                "html": "html",
                "css": "css",
                "md": "markdown",
            }
            details["language"] = language_map.get(details["extension"], "unknown")

        # 設定ファイル判定
        config_indicators = [
            "config",
            "settings",
            "env",
            ".env",
            "docker",
            "makefile",
            "cmake",
        ]
        details["is_config"] = any(
            indicator in file_path.lower() for indicator in config_indicators
        )

        # テストファイル判定
        test_indicators = ["test", "spec", "__test__", ".test.", ".spec."]
        details["is_test"] = any(
            indicator in file_path.lower() for indicator in test_indicators
        )

        return details

    def parse_line_range_details(self, line_range: str) -> Dict[str, Any]:
        """行範囲の詳細情報を解析

        Args:
            line_range: 行範囲文字列（例: "201-241" or "185"）

        Returns:
            行範囲の詳細情報
        """
        details = {
            "original": line_range,
            "start_line": None,
            "end_line": None,
            "line_count": 0,
            "is_single_line": False,
            "is_large_range": False,
        }

        match = self.LINE_RANGE_PATTERN.match(line_range)
        if match:
            start_str = match.group(1)
            end_str = match.group(2)

            details["start_line"] = int(start_str)

            if end_str:
                details["end_line"] = int(end_str)
                details["line_count"] = details["end_line"] - details["start_line"] + 1
                details["is_single_line"] = False
            else:
                details["end_line"] = details["start_line"]
                details["line_count"] = 1
                details["is_single_line"] = True

            # 大きな範囲の判定（20行以上）
            details["is_large_range"] = details["line_count"] >= 20

        return details

    def extract_structured_code_suggestion(self, description: str) -> Dict[str, Any]:
        """コード修正案の構造化抽出

        Args:
            description: コメントの説明

        Returns:
            構造化されたコード修正案
        """
        suggestion_data = {
            "has_suggestion": False,
            "raw_diff": None,
            "added_lines": [],
            "removed_lines": [],
            "modified_lines": [],
            "context_lines": [],
            "suggestion_type": "unknown",
            "complexity": "low",
        }

        code_match = self.CODE_SUGGESTION_PATTERN.search(description)
        if not code_match:
            return suggestion_data

        suggestion_data["has_suggestion"] = True
        suggestion_data["raw_diff"] = code_match.group(1).strip()

        # diff行を解析
        diff_lines = suggestion_data["raw_diff"].split("\n")

        for line in diff_lines:
            line = line.strip()
            if line.startswith("+"):
                suggestion_data["added_lines"].append(line[1:].strip())
            elif line.startswith("-"):
                suggestion_data["removed_lines"].append(line[1:].strip())
            elif line.startswith("@@"):
                continue  # ヘッダー行はスキップ
            elif line and not line.startswith(" "):
                suggestion_data["context_lines"].append(line)
            elif line.startswith(" "):
                suggestion_data["context_lines"].append(line[1:].strip())

        # 修正タイプの判定
        added_count = len(suggestion_data["added_lines"])
        removed_count = len(suggestion_data["removed_lines"])

        if added_count > 0 and removed_count == 0:
            suggestion_data["suggestion_type"] = "addition"
        elif added_count == 0 and removed_count > 0:
            suggestion_data["suggestion_type"] = "deletion"
        elif added_count > 0 and removed_count > 0:
            suggestion_data["suggestion_type"] = "modification"

        # 複雑度の判定
        total_changes = added_count + removed_count
        if total_changes <= 3:
            suggestion_data["complexity"] = "low"
        elif total_changes <= 10:
            suggestion_data["complexity"] = "medium"
        else:
            suggestion_data["complexity"] = "high"

        return suggestion_data

    def group_related_comments(
        self, comments: List[OutsideDiffComment]
    ) -> Dict[str, List[OutsideDiffComment]]:
        """関連コメントのグループ化

        Args:
            comments: 範囲外コメントのリスト

        Returns:
            グループ化されたコメント辞書
        """
        groups = {
            "by_file": {},
            "by_severity": {},
            "by_category": {},
            "by_language": {},
            "security_related": [],
            "large_changes": [],
            "config_changes": [],
        }

        for comment in comments:
            # ファイル別グループ化
            file_path = comment.file_path
            if file_path not in groups["by_file"]:
                groups["by_file"][file_path] = []
            groups["by_file"][file_path].append(comment)

            # 重要度別グループ化
            severity = comment.severity.value
            if severity not in groups["by_severity"]:
                groups["by_severity"][severity] = []
            groups["by_severity"][severity].append(comment)

            # カテゴリ別グループ化
            category = comment.category.value
            if category not in groups["by_category"]:
                groups["by_category"][category] = []
            groups["by_category"][category].append(comment)

            # ファイル詳細情報に基づくグループ化
            file_details = self.parse_file_path_details(file_path)
            language = file_details["language"]
            if language not in groups["by_language"]:
                groups["by_language"][language] = []
            groups["by_language"][language].append(comment)

            # 特別なグループ化
            # セキュリティ関連
            security_keywords = [
                "security",
                "token",
                "credential",
                "auth",
                "permission",
                "access",
                "vulnerability",
            ]
            if any(
                keyword in comment.title.lower()
                or keyword in comment.description.lower()
                for keyword in security_keywords
            ):
                groups["security_related"].append(comment)

            # 大きな変更
            line_details = self.parse_line_range_details(comment.line_range)
            if line_details["is_large_range"]:
                groups["large_changes"].append(comment)

            # 設定ファイル変更
            if file_details["is_config"]:
                groups["config_changes"].append(comment)

        return groups
