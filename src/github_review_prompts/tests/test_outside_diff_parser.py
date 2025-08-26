"""範囲外コメントパーサーのテスト"""

import pytest
from ..utils.outside_diff_parser import OutsideDiffParser
from ..models import OutsideDiffCommentCategory, OutsideDiffCommentSeverity


class TestOutsideDiffParser:
    """OutsideDiffParserのテストクラス"""

    def setup_method(self):
        """テストセットアップ"""
        self.parser = OutsideDiffParser()

    def test_detect_outside_diff_comments_positive(self):
        """範囲外コメントの検出テスト（正常系）"""
        comment_body = """
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.

<details>
<summary>⚠️ Outside diff range comments (4)</summary><blockquote>

<details>
<summary>modules/scalability/load-balancer-optimizer/main.tf (4)</summary><blockquote>

`201-241`: **aws_lb.optimized に precondition を追加して必須入力を早期検証**

ALB新規作成時の VPC/Subnet/SG 未指定は apply 時に落ちます。

</blockquote></details>

</blockquote></details>
"""

        result = self.parser.detect_outside_diff_comments(comment_body)
        assert result is True

    def test_detect_outside_diff_comments_negative(self):
        """範囲外コメントの検出テスト（否定系）"""
        comment_body = """
This is a regular comment without outside diff markers.
"""

        result = self.parser.detect_outside_diff_comments(comment_body)
        assert result is False

    def test_parse_outside_diff_comments_actionable(self):
        """Actionableコメントの解析テスト"""
        comment_body = """
> [!CAUTION]
> Some comments are outside the diff and can't be posted inline due to platform limitations.

<details>
<summary>⚠️ Outside diff range comments (1)</summary><blockquote>

<details>
<summary>modules/scalability/load-balancer-optimizer/main.tf (1)</summary><blockquote>

`201-241`: **aws_lb.optimized に precondition を追加して必須入力を早期検証**

ALB新規作成時の VPC/Subnet/SG 未指定は apply 時に落ちます。

```diff
 resource "aws_lb" "optimized" {
   count = var.create_optimized_alb ? 1 : 0
+  lifecycle {
+    precondition {
+      condition = !var.create_optimized_alb || (var.vpc_id != "" && length(var.subnet_ids) > 0)
+      error_message = "create_optimized_alb=true の場合、vpc_id / subnet_ids は必須です。"
+    }
+  }
```

</blockquote></details>

</blockquote></details>
"""

        comments = self.parser.parse_outside_diff_comments(
            comment_body, 12345, "coderabbitai[bot]"
        )

        assert len(comments) == 1
        comment = comments[0]

        assert (
            comment.file_path == "modules/scalability/load-balancer-optimizer/main.tf"
        )
        assert comment.line_range == "201-241"
        assert comment.category == OutsideDiffCommentCategory.ACTIONABLE
        assert comment.severity == OutsideDiffCommentSeverity.CAUTION
        assert "aws_lb.optimized に precondition を追加" in comment.title
        assert comment.suggested_fix is not None
        assert "lifecycle" in comment.suggested_fix

    def test_parse_outside_diff_comments_duplicate(self):
        """Duplicateコメントの解析テスト"""
        comment_body = """
<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>modules/scalability/load-balancer-optimizer/variables.tf (1)</summary><blockquote>

`185-200`: **NLB専用/ASG専用属性の混在はPhase5での分離・整理を予定**

`preserve_client_ip`/`proxy_protocol_v2` はNLB向けです。

</blockquote></details>

</blockquote></details>
"""

        comments = self.parser.parse_outside_diff_comments(
            comment_body, 12346, "coderabbitai[bot]"
        )

        assert len(comments) == 1
        comment = comments[0]

        assert comment.category == OutsideDiffCommentCategory.DUPLICATE
        assert comment.severity == OutsideDiffCommentSeverity.WARNING
        assert "NLB専用/ASG専用属性の混在" in comment.title

    def test_parse_outside_diff_comments_nitpick(self):
        """Nitpickコメントの解析テスト"""
        comment_body = """
<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>modules/scalability/load-balancer-optimizer/variables.tf (1)</summary><blockquote>

`131-134`: **メッセージ表記の言語統一（日本語に合わせる）**

他のvalidationが日本語のため、ここも統一すると読み手に優しいです。

</blockquote></details>

</blockquote></details>
"""

        comments = self.parser.parse_outside_diff_comments(
            comment_body, 12347, "coderabbitai[bot]"
        )

        assert len(comments) == 1
        comment = comments[0]

        assert comment.category == OutsideDiffCommentCategory.NITPICK
        assert comment.severity == OutsideDiffCommentSeverity.INFO
        assert "メッセージ表記の言語統一" in comment.title

    def test_categorize_by_priority(self):
        """優先度別分類のテスト"""
        # テスト用のコメントを作成
        from ..models import OutsideDiffComment

        comments = [
            OutsideDiffComment(
                id=1,
                body="test",
                file_path="test.tf",
                line_range="1-10",
                category=OutsideDiffCommentCategory.ACTIONABLE,
                severity=OutsideDiffCommentSeverity.CAUTION,
                title="Caution comment",
                description="Test",
            ),
            OutsideDiffComment(
                id=2,
                body="test",
                file_path="test.tf",
                line_range="11-20",
                category=OutsideDiffCommentCategory.DUPLICATE,
                severity=OutsideDiffCommentSeverity.WARNING,
                title="Warning comment",
                description="Test",
            ),
            OutsideDiffComment(
                id=3,
                body="test",
                file_path="test.tf",
                line_range="21-30",
                category=OutsideDiffCommentCategory.NITPICK,
                severity=OutsideDiffCommentSeverity.INFO,
                title="Info comment",
                description="Test",
            ),
        ]

        categorized = self.parser.categorize_by_priority(comments)

        assert "🔴 緊急" in categorized
        assert "🟡 重要" in categorized
        assert "🟢 低優先" in categorized

        assert len(categorized["🔴 緊急"]) == 1
        assert len(categorized["🟡 重要"]) == 1
        assert len(categorized["🟢 低優先"]) == 1

    def test_get_priority_order(self):
        """優先度順序の取得テスト"""
        order = self.parser.get_priority_order()

        assert order == ["🔴 緊急", "🟡 重要", "🟢 低優先"]

    def test_extract_code_suggestion(self):
        """コード修正案の抽出テスト"""
        description = """
ALB新規作成時の VPC/Subnet/SG 未指定は apply 時に落ちます。

```diff
 resource "aws_lb" "optimized" {
   count = var.create_optimized_alb ? 1 : 0
+  lifecycle {
+    precondition {
+      condition = !var.create_optimized_alb || (var.vpc_id != "")
+      error_message = "create_optimized_alb=true の場合、vpc_id は必須です。"
+    }
+  }
```

対応してください。
"""

        suggestion = self.parser._extract_code_suggestion(description)

        assert suggestion is not None
        assert "lifecycle" in suggestion
        assert "precondition" in suggestion
        assert "condition" in suggestion

    def test_extract_code_suggestion_none(self):
        """コード修正案がない場合のテスト"""
        description = "これはコード修正案を含まない説明です。"

        suggestion = self.parser._extract_code_suggestion(description)

        assert suggestion is None
