"""パーサーのテスト"""

import unittest
from github_review_prompts.utils.parsers import (
    parse_pr_url,
    extract_ai_agent_prompt,
    categorize_prompt,
    determine_priority
)


class TestParsers(unittest.TestCase):
    """パーサーユーティリティのテストクラス"""
    
    def test_parse_pr_url_valid(self):
        """有効なPR URLの解析テスト"""
        test_cases = [
            ("https://github.com/owner/repo/pull/123", ("owner", "repo", 123)),
            ("https://github.com/test-org/test-repo/pull/1", ("test-org", "test-repo", 1)),
            ("https://github.com/owner/repo/pull/999999", ("owner", "repo", 999999)),
        ]
        
        for url, expected in test_cases:
            with self.subTest(url=url):
                result = parse_pr_url(url)
                self.assertEqual(result, expected)
    
    def test_parse_pr_url_invalid(self):
        """無効なPR URLの解析テスト"""
        invalid_urls = [
            "not-a-url",
            "https://gitlab.com/owner/repo/pull/123",
            "https://github.com/owner/repo/issue/123",
            "https://github.com/owner/repo/pull/abc",
            "https://github.com/owner/repo/pull/-1",
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_pr_url(url)
    
    def test_extract_ai_agent_prompt(self):
        """AI プロンプト抽出テスト"""
        # CodeRabbit標準形式
        coderabbit_comment = """
        <details>
        <summary>🤖 Prompt for AI Agents</summary>
        
        Replace hardcoded strings with constants to improve maintainability.
        
        </details>
        """
        
        result = extract_ai_agent_prompt(coderabbit_comment)
        self.assertIsNotNone(result)
        self.assertIn("Replace hardcoded strings", result)
        
        # プロンプトが含まれていないコメント
        normal_comment = "This is a regular comment without AI prompt."
        result = extract_ai_agent_prompt(normal_comment)
        self.assertIsNone(result)
    
    def test_categorize_prompt(self):
        """プロンプトカテゴリ分類テスト"""
        test_cases = [
            ("Fix security vulnerability", "security"),
            ("Optimize performance for better speed", "performance"),
            ("Improve code formatting and style", "style"),
            ("Fix logic error in condition", "logic"),
            ("General improvement", "general"),
        ]
        
        for prompt, expected_category in test_cases:
            with self.subTest(prompt=prompt):
                result = categorize_prompt(prompt)
                self.assertEqual(result, expected_category)
    
    def test_determine_priority(self):
        """優先度判定テスト"""
        test_cases = [
            ("Critical security issue must be fixed", "security", "high"),
            ("Minor style suggestion", "style", "low"), 
            ("Performance optimization", "performance", "medium"),
        ]
        
        for prompt, category, expected_priority in test_cases:
            with self.subTest(prompt=prompt):
                result = determine_priority(prompt, category)
                self.assertEqual(result, expected_priority)


if __name__ == "__main__":
    unittest.main()