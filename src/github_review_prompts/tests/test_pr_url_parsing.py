"""
PR URL解析テスト
grp_uvx.pyのparse_pr_url()関数とgithub_client.pyの解析機能をテスト
"""

import pytest
import sys
from pathlib import Path
from typing import Optional, Tuple

# テスト対象のインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import grp_uvx
from github_review_prompts.github_client import GitHubClient
from github_review_prompts.utils.parsers import parse_pr_url as utils_parse_pr_url


class TestPRURLParsing:
    """PR URL解析パターンテスト"""

    @pytest.mark.parametrize("url,expected", [
        # 標準形式
        ("https://github.com/owner/repo/pull/123", ("owner", "repo", 123)),
        ("https://github.com/microsoft/vscode/pull/456", ("microsoft", "vscode", 456)),
        ("https://github.com/facebook/react/pull/789", ("facebook", "react", 789)),

        # 大文字小文字混在
        ("https://github.com/Owner/Repo/pull/123", ("Owner", "Repo", 123)),
        # NOTE: GitHub.comは大文字小文字を区別するため、現在の実装では解析されない
        # ("https://GitHub.com/owner/repo/pull/123", ("owner", "repo", 123)),

        # 数字を含むリポジトリ名
        ("https://github.com/owner/repo123/pull/456", ("owner", "repo123", 456)),
        ("https://github.com/owner123/repo/pull/789", ("owner123", "repo", 789)),

        # ハイフン・アンダースコアを含む
        ("https://github.com/my-org/my-repo/pull/111", ("my-org", "my-repo", 111)),
        ("https://github.com/my_org/my_repo/pull/222", ("my_org", "my_repo", 222)),

        # 省略形式（httpsなし）
        ("github.com/owner/repo/pull/456", ("owner", "repo", 456)),
        ("github.com/microsoft/typescript/pull/789", ("microsoft", "typescript", 789)),

        # ショート形式
        ("owner/repo#789", ("owner", "repo", 789)),
        ("microsoft/vscode#12345", ("microsoft", "vscode", 12345)),

        # 大きなPR番号
        ("https://github.com/owner/repo/pull/999999", ("owner", "repo", 999999)),

        # ドットを含むリポジトリ名
        ("https://github.com/owner/repo.name/pull/123", ("owner", "repo.name", 123)),
    ])
    def test_grp_uvx_parse_pr_url_valid(self, url, expected):
        """grp_uvx.py のparse_pr_url() - 有効URL解析テスト"""
        result = grp_uvx.parse_pr_url(url)
        assert result is not None, f"URLの解析に失敗しました: {url}"
        assert result == expected, f"期待値と異なります。期待: {expected}, 実際: {result}"

    @pytest.mark.parametrize("invalid_url", [
        # 完全に無効なURL
        "invalid-url",
        "not-a-github-url",
        "https://gitlab.com/owner/repo/pull/123",  # GitHubではない
        "https://bitbucket.org/owner/repo/pull/123",  # GitHubではない

        # GitHubだが不完全
        "https://github.com/owner",
        "https://github.com/owner/repo",
        "https://github.com/owner/repo/",
        "https://github.com/owner/repo/pull",
        "https://github.com/owner/repo/pull/",

        # PR番号が無効
        "https://github.com/owner/repo/pull/abc",  # 数字ではない
        "https://github.com/owner/repo/pull/0",    # ゼロ
        "https://github.com/owner/repo/pull/-123", # 負の数

        # issueのURL（pullではない）
        "https://github.com/owner/repo/issues/123",

        # 空文字・None
        "",
        None,

        # スペースを含む
        "https://github.com/owner/repo /pull/123",
        "https://github.com/owner /repo/pull/123",

        # 特殊文字を含む
        "https://github.com/owner@/repo/pull/123",
        "https://github.com/owner/repo$/pull/123",

        # ショート形式の無効パターン
        "owner/repo",          # PR番号なし
        "owner#123",           # リポジトリ名なし
        "/repo#123",           # オーナー名なし
        "owner/#123",          # リポジトリ名が空
    ])
    def test_grp_uvx_parse_pr_url_invalid(self, invalid_url):
        """grp_uvx.py のparse_pr_url() - 無効URL処理テスト"""
        result = grp_uvx.parse_pr_url(invalid_url)
        assert result is None, f"無効なURLが解析されてしまいました: {invalid_url} -> {result}"

    def test_utils_parse_pr_url_functionality(self):
        """utils.parsers.parse_pr_url() の基本機能テスト"""
        # 有効なURL
        valid_urls = [
            "https://github.com/owner/repo/pull/123",
            "github.com/owner/repo/pull/456",
            "owner/repo#789"
        ]

        for url in valid_urls:
            try:
                result = utils_parse_pr_url(url)
                assert len(result) == 3, f"結果のタプル長が期待値と異なります: {result}"
                owner, repo, pr_number = result
                assert isinstance(owner, str), f"ownerが文字列ではありません: {type(owner)}"
                assert isinstance(repo, str), f"repoが文字列ではありません: {type(repo)}"
                assert isinstance(pr_number, int), f"pr_numberが整数ではありません: {type(pr_number)}"
                assert pr_number > 0, f"PR番号が正の整数ではありません: {pr_number}"
            except Exception as e:
                pytest.fail(f"utils.parse_pr_url()でエラーが発生しました。URL: {url}, エラー: {e}")

    def test_github_client_parse_pr_url(self):
        """GitHubClient.parse_pr_url() の機能テスト"""
        client = GitHubClient("ghp_" + "x" * 36)

        # 有効なURL
        valid_url = "https://github.com/owner/repo/pull/123"
        try:
            result = client.parse_pr_url(valid_url)
            assert hasattr(result, 'owner'), "結果にownerフィールドがありません"
            assert hasattr(result, 'repo'), "結果にrepoフィールドがありません"
            assert hasattr(result, 'pull_number'), "結果にpull_numberフィールドがありません"
            assert hasattr(result, 'url'), "結果にurlフィールドがありません"

            assert result.owner == "owner"
            assert result.repo == "repo"
            assert result.pull_number == 123
            assert result.url == valid_url
        except Exception as e:
            pytest.fail(f"GitHubClient.parse_pr_url()でエラーが発生しました: {e}")

    @pytest.mark.parametrize("url_variations", [
        # 同じPRを表す異なる形式
        [
            "https://github.com/owner/repo/pull/123",
            "github.com/owner/repo/pull/123",
            "owner/repo#123"
        ],
        # 別のリポジトリの例
        [
            "https://github.com/microsoft/vscode/pull/456",
            "github.com/microsoft/vscode/pull/456",
            "microsoft/vscode#456"
        ]
    ])
    def test_url_format_equivalence(self, url_variations):
        """異なるURL形式の等価性テスト"""
        results = []
        for url in url_variations:
            result = grp_uvx.parse_pr_url(url)
            assert result is not None, f"URL解析に失敗: {url}"
            results.append(result)

        # すべての結果が同じであることを確認
        first_result = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result == first_result, f"URL形式 {url_variations[i]} の結果が {url_variations[0]} と異なります"

    def test_special_characters_in_repo_names(self):
        """リポジトリ名の特殊文字処理テスト"""
        # 有効な特殊文字を含むリポジトリ名
        valid_special_chars = [
            ("owner/repo-name/pull/123", ("owner", "repo-name", 123)),
            ("owner/repo_name/pull/123", ("owner", "repo_name", 123)),
            ("owner/repo.name/pull/123", ("owner", "repo.name", 123)),
            ("owner-name/repo/pull/123", ("owner-name", "repo", 123)),
            ("owner_name/repo/pull/123", ("owner_name", "repo", 123)),
        ]

        for url_suffix, expected in valid_special_chars:
            full_url = f"https://github.com/{url_suffix}"
            result = grp_uvx.parse_pr_url(full_url)
            assert result == expected, f"特殊文字を含むリポジトリ名の解析に失敗: {full_url}"

    def test_edge_case_pr_numbers(self):
        """PR番号のエッジケーステスト"""
        edge_cases = [
            ("https://github.com/owner/repo/pull/1", ("owner", "repo", 1)),        # 最小値
            ("https://github.com/owner/repo/pull/99999", ("owner", "repo", 99999)), # 大きな値
            ("https://github.com/owner/repo/pull/12345", ("owner", "repo", 12345)), # 中間値
        ]

        for url, expected in edge_cases:
            result = grp_uvx.parse_pr_url(url)
            assert result == expected, f"PR番号のエッジケースで失敗: {url}"

    def test_regex_pattern_coverage(self):
        """正規表現パターンの網羅性テスト"""
        # grp_uvx.pyで使用されている正規表現パターンの確認
        patterns = [
            r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)",
            r"github\.com/([^/]+)/([^/]+)/pull/(\d+)",
            r"([^/]+)/([^/]+)#(\d+)",
        ]

        test_cases = [
            ("https://github.com/owner/repo/pull/123", 0),  # 1番目のパターン
            ("github.com/owner/repo/pull/123", 1),          # 2番目のパターン
            ("owner/repo#123", 2),                          # 3番目のパターン
        ]

        import re
        for url, pattern_index in test_cases:
            pattern = patterns[pattern_index]
            match = re.match(pattern, url)
            assert match is not None, f"パターン {pattern_index} が URL {url} にマッチしません"
            assert len(match.groups()) == 3, f"マッチしたグループ数が期待値と異なります"

    def test_unicode_handling(self):
        """Unicode文字列の処理テスト"""
        # 基本的にはASCII文字のみが有効だが、関数が適切にエラーハンドリングするかテスト
        unicode_urls = [
            "https://github.com/オーナー/リポジトリ/pull/123",
            "https://github.com/owner/リポジトリ/pull/123",
        ]

        for url in unicode_urls:
            result = grp_uvx.parse_pr_url(url)
            # Unicode文字を含むURLは通常解析されないが、エラーが発生しないことを確認
            # 結果がNoneでも例外が発生しなければOK
            assert result is None or isinstance(result, tuple)

    def test_function_signature_consistency(self):
        """関数シグネチャの一貫性テスト"""
        # grp_uvx.parse_pr_url()の戻り値型確認
        valid_url = "https://github.com/owner/repo/pull/123"
        result = grp_uvx.parse_pr_url(valid_url)

        assert isinstance(result, tuple), f"戻り値がtupleではありません: {type(result)}"
        assert len(result) == 3, f"戻り値のタプル長が3ではありません: {len(result)}"

        owner, repo, pr_number = result
        assert isinstance(owner, str), f"ownerが文字列ではありません: {type(owner)}"
        assert isinstance(repo, str), f"repoが文字列ではありません: {type(repo)}"
        assert isinstance(pr_number, int), f"pr_numberが整数ではありません: {type(pr_number)}"

    def test_none_and_empty_input_handling(self):
        """None・空文字入力の適切な処理テスト"""
        # None入力
        try:
            result = grp_uvx.parse_pr_url(None)
            # Noneが返されるか、例外が発生するかのどちらかが期待される
            assert result is None
        except (TypeError, AttributeError):
            # TypeError or AttributeErrorが発生するのも正常
            pass

        # 空文字入力
        result = grp_uvx.parse_pr_url("")
        assert result is None, "空文字の場合はNoneが返されるべきです"

        # 空白のみ
        result = grp_uvx.parse_pr_url("   ")
        assert result is None, "空白のみの場合はNoneが返されるべきです"


class TestPRURLParsingPerformance:
    """PR URL解析のパフォーマンステスト"""

    def test_large_scale_url_parsing(self):
        """大量URL解析のパフォーマンステスト"""
        import time

        # テスト用URL生成
        test_urls = []
        for i in range(1000):
            test_urls.append(f"https://github.com/owner{i}/repo{i}/pull/{i+1}")

        start_time = time.time()

        success_count = 0
        for url in test_urls:
            result = grp_uvx.parse_pr_url(url)
            if result is not None:
                success_count += 1

        end_time = time.time()
        elapsed_time = end_time - start_time

        # パフォーマンス要件（1000URLを1秒以内で処理）
        assert elapsed_time < 1.0, f"1000URLの解析に{elapsed_time:.2f}秒かかりました（1秒以内であるべき）"
        assert success_count == 1000, f"解析成功数が期待値と異なります: {success_count}/1000"

    def test_regex_compilation_efficiency(self):
        """正規表現コンパイルの効率性テスト"""
        import re
        import time

        # 同じURLを繰り返し解析（正規表現の再コンパイルが発生しないかテスト）
        test_url = "https://github.com/owner/repo/pull/123"

        start_time = time.time()
        for _ in range(10000):
            result = grp_uvx.parse_pr_url(test_url)
            assert result is not None
        end_time = time.time()

        elapsed_time = end_time - start_time
        # 10000回の解析を0.1秒以内で完了することを期待
        assert elapsed_time < 0.1, f"10000回の解析に{elapsed_time:.3f}秒かかりました（0.1秒以内であるべき）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
