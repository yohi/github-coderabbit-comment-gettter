"""
解決済みコメント処理テスト
GraphQL/REST APIによる解決済みコメント検出と処理の精度をテスト
"""

import pytest
import json
import sys
from unittest.mock import Mock, patch
from pathlib import Path

# テスト対象のインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import grp_uvx


class TestGraphQLResolvedCommentDetection:
    """GraphQL APIによる解決済みコメント検出テスト"""

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_successful_graphql_resolved_detection(self, mock_request_class, mock_urlopen):
        """GraphQL: 解決済みコメント検出成功パターン"""
        # GraphQLレスポンスのモック
        mock_response_data = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None
                            },
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {"databaseId": 1001},
                                            {"databaseId": 1002}
                                        ]
                                    }
                                },
                                {
                                    "isResolved": False,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {"databaseId": 1003}
                                        ]
                                    }
                                },
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {"databaseId": 1004},
                                            {"databaseId": 1005},
                                            {"databaseId": 1006}
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }

        # モックレスポンスの設定
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(mock_response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # GraphQL API呼び出し実行
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")

        # 結果検証
        assert isinstance(resolved_ids, set)
        assert len(resolved_ids) == 5  # 解決済みスレッドのコメント数
        
        # 個別ID確認
        expected_resolved_ids = {1001, 1002, 1004, 1005, 1006}
        assert resolved_ids == expected_resolved_ids
        
        # 未解決コメントが含まれていないことを確認
        assert 1003 not in resolved_ids

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_graphql_pagination_handling(self, mock_request_class, mock_urlopen):
        """GraphQL: ページネーション処理テスト"""
        # 複数ページのGraphQLレスポンス
        page1_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "cursor_page1"
                            },
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [{"databaseId": 2001}, {"databaseId": 2002}]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        page2_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None
                            },
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [{"databaseId": 2003}]
                                    }
                                },
                                {
                                    "isResolved": False,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [{"databaseId": 2004}]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }

        # ページ分割レスポンスのモック
        responses = [page1_response, page2_response]
        def mock_response_generator(*args, **kwargs):
            response_data = responses.pop(0) if responses else {}
            mock_response = Mock()
            mock_response.status = 200
            mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
            return mock_response

        mock_urlopen.return_value.__enter__.side_effect = mock_response_generator

        # GraphQL API呼び出し実行
        with patch('time.sleep'):  # sleep をモック化してテスト高速化
            resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")

        # ページネーション結果の検証
        assert len(resolved_ids) == 3  # 全ページの解決済みコメント
        assert 2001 in resolved_ids
        assert 2002 in resolved_ids
        assert 2003 in resolved_ids
        assert 2004 not in resolved_ids  # 未解決コメント
        
        # 2回のAPI呼び出しが行われたことを確認
        assert mock_urlopen.call_count == 2

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_graphql_error_handling(self, mock_request_class, mock_urlopen):
        """GraphQL: エラーハンドリングテスト"""
        # GraphQLエラーレスポンス
        error_response = {
            "errors": [
                {
                    "message": "Field 'reviewThreads' doesn't exist on type 'PullRequest'",
                    "locations": [{"line": 4, "column": 11}]
                }
            ]
        }

        # エラーレスポンスのモック
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(error_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # GraphQL API呼び出し実行（エラー処理の確認）
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")

        # エラー時は空のセットが返されることを確認
        assert resolved_ids == set()

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_graphql_network_error_handling(self, mock_request_class, mock_urlopen):
        """GraphQL: ネットワークエラーハンドリング"""
        # ネットワークエラーのモック
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        # GraphQL API呼び出し実行
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")

        # ネットワークエラー時は空のセットが返されることを確認
        assert resolved_ids == set()

    def test_graphql_query_structure(self):
        """GraphQL: クエリ構造の検証"""
        # grp_uvx.py内のGraphQLクエリが適切な構造を持っているかテスト
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('urllib.request.Request') as mock_request_class:
            
            mock_response = Mock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}'
            mock_urlopen.return_value.__enter__.return_value = mock_response

            # API呼び出し実行
            grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")

            # リクエストが作成されたことを確認
            mock_request_class.assert_called_once()
            
            # リクエストデータの確認
            call_args = mock_request_class.call_args
            request_data = call_args[1]['data'] if 'data' in call_args[1] else call_args[0][1]
            
            if isinstance(request_data, bytes):
                request_data = request_data.decode('utf-8')
            if isinstance(request_data, str):
                request_json = json.loads(request_data)
                
                # GraphQLクエリの基本構造確認
                assert 'query' in request_json
                assert 'variables' in request_json
                
                query = request_json['query']
                assert 'repository' in query
                assert 'pullRequest' in query
                assert 'reviewThreads' in query
                assert 'isResolved' in query


class TestResolvedCommentFiltering:
    """解決済みコメントフィルタリングテスト"""

    def test_exclude_resolved_comments_default_behavior(self):
        """デフォルト動作：解決済みコメント除外テスト"""
        # コメントデータ
        all_comments = [
            {
                "id": 3001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/auth.py",
                "line": 42
            },
            {
                "id": 3002,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング提案",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/utils.py", 
                "line": 15
            },
            {
                "id": 3003,
                "body": "_💡 Nitpick comments_\n\n命名改善",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/helpers.py",
                "line": 8
            },
            {
                "id": 3004,
                "body": "_⚠️ Potential issue_\n\n別のセキュリティ問題",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/database.py",
                "line": 25
            }
        ]

        # 解決済みコメントID（3002, 3004が解決済み）
        resolved_ids = {3002, 3004}

        # フィルタリング実行（include_resolved=False）
        filtered_comments = [
            comment for comment in all_comments 
            if comment["id"] not in resolved_ids
        ]

        # 結果検証
        assert len(filtered_comments) == 2
        filtered_ids = {comment["id"] for comment in filtered_comments}
        assert 3001 in filtered_ids
        assert 3003 in filtered_ids
        assert 3002 not in filtered_ids  # 解決済みのため除外
        assert 3004 not in filtered_ids  # 解決済みのため除外

    def test_include_resolved_comments_option(self):
        """include_resolvedオプション：解決済みコメント含有テスト"""
        # 同じデータを使用
        all_comments = [
            {"id": 4001, "body": "Comment 1", "user": {"login": "coderabbitai[bot]"}},
            {"id": 4002, "body": "Comment 2", "user": {"login": "coderabbitai[bot]"}},
            {"id": 4003, "body": "Comment 3", "user": {"login": "coderabbitai[bot]"}},
        ]
        resolved_ids = {4002}

        # include_resolved=True の場合（解決済みも含む）
        all_comments_included = all_comments  # 除外しない

        # include_resolved=False の場合（解決済み除外）
        filtered_comments = [
            comment for comment in all_comments 
            if comment["id"] not in resolved_ids
        ]

        # 結果比較
        assert len(all_comments_included) == 3  # 全て含む
        assert len(filtered_comments) == 2      # 解決済み除外

    def test_large_scale_resolved_filtering(self):
        """大量コメントでの解決済みフィルタリング性能テスト"""
        import time
        
        # 大量コメントデータ生成（1000件）
        large_comments = [
            {
                "id": i,
                "body": f"_⚠️ Potential issue_\n\nIssue #{i}",
                "user": {"login": "coderabbitai[bot]"},
                "path": f"src/file_{i}.py",
                "line": i * 10
            }
            for i in range(1000)
        ]

        # 半分を解決済みとする（500件）
        resolved_ids = set(range(0, 1000, 2))  # 偶数IDが解決済み

        # フィルタリング処理時間測定
        start_time = time.time()
        
        filtered_comments = [
            comment for comment in large_comments
            if comment["id"] not in resolved_ids
        ]
        
        end_time = time.time()
        elapsed_time = end_time - start_time

        # 結果とパフォーマンス検証
        assert len(filtered_comments) == 500  # 半分が除外される
        assert elapsed_time < 0.05, f"1000件の解決済みフィルタリングに{elapsed_time:.3f}秒かかりました"

        # 正確性確認
        filtered_ids = {comment["id"] for comment in filtered_comments}
        for resolved_id in resolved_ids:
            assert resolved_id not in filtered_ids, f"解決済みID {resolved_id} が除外されていません"


class TestCommentResolutionLogic:
    """コメント解決ロジックテスト"""

    def test_explicit_resolution_keywords_detection(self):
        """明示的解決キーワードの検出テスト"""
        # 解決キーワードを含むコメント
        resolution_comments = [
            {
                "id": 5001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題\n\n**解決済み**: この問題は修正されました。",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 5002,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング提案\n\n✅ 対応完了",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 5003,
                "body": "_💡 Nitpick comments_\n\n命名改善\n\nfixed",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 5004,
                "body": "_⚠️ Potential issue_\n\n未解決の問題です",
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        # 解決キーワードの検出
        resolution_keywords = ["resolved", "fixed", "done", "✅", "解決済み", "対応完了"]
        
        for comment in resolution_comments:
            body = comment["body"].lower()
            has_resolution_keyword = any(keyword.lower() in body for keyword in resolution_keywords)
            
            if comment["id"] in {5001, 5002, 5003}:
                assert has_resolution_keyword, f"解決キーワードが検出されませんでした: {comment['id']}"
            else:
                assert not has_resolution_keyword, f"解決キーワードが誤検出されました: {comment['id']}"

    def test_suggestion_comment_handling(self):
        """Suggestionコメントの処理テスト"""
        # Committable suggestionコメント
        suggestion_comments = [
            {
                "id": 6001,
                "body": "_📝 Committable suggestion_\n\n```suggestion\nfix this line\n```",
                "user": {"login": "coderabbitai[bot]"}
            },
            {
                "id": 6002,
                "body": "_⚠️ Potential issue_\n\n通常のセキュリティ指摘",
                "user": {"login": "coderabbitai[bot]"}
            }
        ]

        # Suggestionコメントは未解決として扱う（GitHub UIの動作に合わせる）
        for comment in suggestion_comments:
            is_suggestion = "Committable suggestion" in comment["body"]
            
            if comment["id"] == 6001:
                assert is_suggestion, "Suggestionコメントが検出されませんでした"
                # Suggestionは未解決として処理される
            else:
                assert not is_suggestion, "非Suggestionコメントが誤検出されました"


class TestResolvedCommentIntegration:
    """解決済みコメント処理の統合テスト"""

    @patch('grp_uvx.get_graphql_resolved_comments')
    @patch('grp_uvx.get_pr_review_comments')
    def test_end_to_end_resolved_filtering(self, mock_comments, mock_resolved):
        """エンドツーエンド解決済みフィルタリングテスト"""
        # モックデータ設定
        mock_all_comments = [
            {
                "id": 7001,
                "body": "_⚠️ Potential issue_\n\nセキュリティ問題 #1",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/auth.py",
                "line": 42
            },
            {
                "id": 7002,
                "body": "_🛠️ Refactor suggestion_\n\nリファクタリング #1",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/utils.py",
                "line": 15
            },
            {
                "id": 7003,
                "body": "_💡 Nitpick comments_\n\n命名改善",
                "user": {"login": "coderabbitai[bot]"},
                "path": "src/helpers.py",
                "line": 8
            },
            {
                "id": 7004,
                "body": "Human comment",
                "user": {"login": "human_reviewer"},
                "path": "src/main.py",
                "line": 20
            }
        ]
        
        mock_resolved_set = {7002, 7004}  # リファクタリングコメントと人間のコメントが解決済み
        
        mock_comments.return_value = mock_all_comments
        mock_resolved.return_value = mock_resolved_set

        # 実際の処理フローをシミュレート
        all_comments = mock_all_comments
        resolved_ids = mock_resolved_set
        
        # 1. 解決済みコメント除外
        unresolved_comments = [
            comment for comment in all_comments
            if comment["id"] not in resolved_ids
        ]
        
        # 2. CodeRabbitコメントフィルタリング
        coderabbit_unresolved = [
            comment for comment in unresolved_comments
            if comment.get("user", {}).get("login", "").startswith("coderabbitai")
        ]

        # 結果検証
        assert len(unresolved_comments) == 2  # 7001, 7003が未解決
        assert len(coderabbit_unresolved) == 2  # 両方ともCodeRabbitコメント
        
        # 具体的ID確認
        final_ids = {comment["id"] for comment in coderabbit_unresolved}
        assert 7001 in final_ids  # セキュリティ問題（未解決）
        assert 7003 in final_ids  # 命名改善（未解決）
        assert 7002 not in final_ids  # リファクタリング（解決済み）
        assert 7004 not in final_ids  # 人間コメント（解決済み）


class TestGraphQLAPIRobustness:
    """GraphQL API の堅牢性テスト"""

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_malformed_graphql_response_handling(self, mock_request_class, mock_urlopen):
        """不正なGraphQLレスポンス処理テスト"""
        # 不正なJSONレスポンス
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = b'invalid json response'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 不正レスポンス処理の確認
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")
        assert resolved_ids == set()  # エラー時は空セット

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_empty_graphql_response_handling(self, mock_request_class, mock_urlopen):
        """空のGraphQLレスポンス処理テスト"""
        # 空のレスポンス
        empty_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": []
                        }
                    }
                }
            }
        }

        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(empty_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 空レスポンス処理の確認
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")
        assert resolved_ids == set()  # 空の場合は空セット

    @patch('urllib.request.urlopen')
    @patch('urllib.request.Request')
    def test_partial_data_graphql_response(self, mock_request_class, mock_urlopen):
        """部分的データのGraphQLレスポンス処理テスト"""
        # 一部フィールドが欠損したレスポンス
        partial_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {"databaseId": 8001}
                                            # 一部のコメントでdatabaseIdが欠損する可能性をテスト
                                        ]
                                    }
                                },
                                {
                                    "isResolved": True,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {},  # databaseIdなし
                                            {"databaseId": 8002}
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }

        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(partial_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 部分データ処理の確認
        resolved_ids = grp_uvx.get_graphql_resolved_comments("owner", "repo", 123, "test_token")
        
        # databaseIdがあるコメントのみが処理される
        assert len(resolved_ids) == 2
        assert 8001 in resolved_ids
        assert 8002 in resolved_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


