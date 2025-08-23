"""
Terraform PR #102の標準出力を正とするテストコード
実際のPRコメント内容をモック化してテスト
"""

import pytest
from unittest.mock import Mock, patch
import json
from datetime import datetime
from io import StringIO
import sys

from github_review_prompts.github_client import GitHubClient
from github_review_prompts.main import main


class TestTerraformPR102:
    """Terraform PR #102の実際の出力を検証するテストクラス"""

    @pytest.fixture
    def mock_pr_data(self):
        """PR #102の基本情報をモック化"""
        return {
            "number": 102,
            "title": "Feature/phase4 step4 developer experience",
            "html_url": "https://github.com/yohi/terraform/pull/102",
            "user": {"login": "yohi"},
            "head": {
                "ref": "feature/phase4-step4-developer-experience",
                "repo": {
                    "full_name": "yohi/terraform",
                    "owner": {"login": "yohi"}
                }
            },
            "base": {
                "ref": "main",
                "repo": {
                    "full_name": "yohi/terraform",
                    "owner": {"login": "yohi"}
                }
            },
            "state": "open",
            "created_at": "2025-08-21T23:45:00Z",
            "updated_at": "2025-08-21T23:48:36Z"
        }

    @pytest.fixture
    def mock_comments_data(self):
        """PR #102の105件のコメントデータをモック化"""
        comments = []
        
        # セキュリティ関連コメント（3件）
        security_comments = [
            {
                "id": 2292368740,
                "body": "_💡 Verification agent_\n\nセッション制御条件の誤用修正必須\n\n```diff\nresource \"aws_iam_policy\" \"device_trust\" {\ncount = local.current_config.device_trust_required ? 1 : 0\npolicy = jsonencode({\nVersion = \"2012-10-17\"\nStatement = [\n{\n-        Sid    = \"RequireDeviceRegistration\"\n+        Sid    = \"RestrictToCurrentRegion\"\nEffect = \"Deny\"\n-        Action = \"*\"\n+        Action = \"*\"\nResource = \"*\"\nCondition = {\nStringNotEquals = {\n\"aws:RequestedRegion\" = [data.aws_region.current.name]\n}\n}\n},\n```",
                "path": "modules/security/zero-trust/main.tf",
                "line": 216,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:48:35Z",
                "updated_at": "2025-08-21T23:48:35Z"
            },
            {
                "id": 2292368759,
                "body": "_💡 Verification agent_\n\nセキュリティリスク: トークン関連の修正が必要\n\n```diff\nresource \"aws_lambda_function\" \"security_incident_response\" {\ncount = var.enable_incident_response ? 1 : 0\n-  runtime         = \"python3.9\"\n+  runtime         = \"python3.12\"\ntimeout         = 300\nmemory_size     = 512\n```",
                "path": "modules/security/zero-trust/main.tf",
                "line": 416,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:48:36Z",
                "updated_at": "2025-08-21T23:48:36Z"
            },
            {
                "id": 2292368767,
                "body": "_⚠️ Potential issue_\n\n**Config Ruleで未サポートの`tags`利用/依存関係の明示不足**\n\n```diff\nresource \"aws_config_config_rule\" \"zero_trust_rules\" {\ncount = var.enable_config_compliance ? length(var.zero_trust_config_rules) : 0\n-  depends_on = [aws_config_configuration_recorder.zero_trust_recorder]\n-\n-  tags = local.final_tags\n+  depends_on = [aws_config_configuration_recorder_status.zero_trust_recorder_status]\n}\n```",
                "path": "modules/security/zero-trust/main.tf",
                "line": 621,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:48:36Z",
                "updated_at": "2025-08-21T23:48:36Z"
            }
        ]
        
        # ドキュメント関連コメント（7件）
        doc_comments = [
            {
                "id": 2292366617,
                "body": "_💡 Verification agent_\n\nディレクトリ名をリポジトリ名（terraform）に合わせて修正してください\n\n```diff\n-git clone <repository-url>\n-cd terraform-aws-platform\n+git clone <repository-url>\n+cd <your-repo-root>   # 例: cd terraform\n```",
                "path": "developer-tools/DEVELOPER_QUICK_START_GUIDE.md",
                "line": 56,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:46:11Z",
                "updated_at": "2025-08-21T23:46:11Z"
            },
            {
                "id": 2292366623,
                "body": "_🛠️ Refactor suggestion_\n\n**環境名validation（dev, stg, prd）と他モジュール（dev, staging, prod）が不一致です**\n\n```diff\n-  validation {\n-    condition     = contains([\"dev\", \"stg\", \"prd\"], var.environment)\n-    error_message = \"Environment must be dev, stg, or prd.\"\n-  }\n+  validation {\n+    condition     = contains([\"dev\", \"staging\", \"prod\"], var.environment)\n+    error_message = \"Environment must be dev, staging, or prod.\"\n+  }\n```",
                "path": "developer-tools/DEVELOPMENT_BEST_PRACTICES.md",
                "line": 110,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:46:11Z",
                "updated_at": "2025-08-21T23:46:11Z"
            }
        ]
        
        # 残りの95件を生成（機能改善・品質向上）
        for i in range(3, 98):  # TODO #3 から TODO #97 まで
            comment_id = 2292366624 + i
            comments.append({
                "id": comment_id,
                "body": f"_🛠️ Refactor suggestion_\n\nTerraform設定の改善提案 #{i}\n\n```diff\n# 変更例\n- old_config = \"value\"\n+ new_config = \"improved_value\"\n```",
                "path": f"modules/terraform/config_{i}.tf",
                "line": 10 + (i % 50),
                "user": {"login": "coderabbitai[bot]"},
                "created_at": f"2025-08-21T23:4{6 + (i % 3)}:{10 + (i % 50):02d}Z",
                "updated_at": f"2025-08-21T23:4{6 + (i % 3)}:{10 + (i % 50):02d}Z"
            })
        
        # 全てのコメントを結合（105件）
        all_comments = security_comments + doc_comments + comments
        
        # 残りを調整して正確に105件にする
        remaining_count = 105 - len(all_comments)
        for i in range(remaining_count):
            comment_id = 2292368700 + i
            all_comments.append({
                "id": comment_id,
                "body": f"_🛠️ Refactor suggestion_\n\n追加のTerraform改善提案 #{len(all_comments) + 1}",
                "path": f"modules/additional/config_{i}.tf",
                "line": 20 + i,
                "user": {"login": "coderabbitai[bot]"},
                "created_at": "2025-08-21T23:48:30Z",
                "updated_at": "2025-08-21T23:48:30Z"
            })
        
        return all_comments[:105]  # 正確に105件を返す

    @pytest.fixture
    def mock_resolved_comments(self):
        """解決済みコメント（0件）をモック化"""
        return []

    def test_pr_102_output_structure(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """PR #102の標準出力構造をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            # GitHubClientのモック設定
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # API呼び出しのモック
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            # 標準出力をキャプチャ
            captured_output = StringIO()
            captured_error = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', captured_error):
                # メイン実行（テストケース）
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass  # 正常終了
            
            output = captured_output.getvalue()
            error_output = captured_error.getvalue()
            
            # 基本的な出力構造の検証
            assert "🔄 GitHub Review Prompt Generator (統一版)" in output
            assert "📋 プルリクエスト: https://github.com/yohi/terraform/pull/102" in output
            assert "📊 取得したコメント数: 105 件" in output
            assert "✅ 解決済みコメント: 0 件" in output
            
    def test_comment_classification(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """コメント分類（🔴3件、🟡95件、🟢7件）をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # コメント分類の検証
            assert "🔴 緊急（セキュリティ・機能破綻）- 3件" in output
            assert "🟡 重要（機能改善・品質向上）- 95件" in output  
            assert "🟢 低優先（スタイル・軽微改善）- 7件" in output
            assert "2%がセキュリティ関連" in output

    def test_phased_execution_strategy_output(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """段階的実行戦略の出力をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # 段階的実行戦略の検証
            assert "🚨 段階的実行戦略（大量コメント対応）" in output
            assert "Phase 1: 🔴緊急対応（最優先30-60分）" in output
            assert "Phase 2: 🟡重要対応（2-3時間以内）" in output
            assert "Phase 3: 🟢低優先対応（時間があれば）" in output
            assert "件数制限: 最大15件" in output
            assert "件数制限: 20-30件" in output

    def test_security_comment_details(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """セキュリティ関連コメントの詳細をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # セキュリティコメントの具体的な内容を検証
            assert "TODO #98:" in output
            assert "セッション制御条件の誤用修正必須" in output
            assert "modules/security/zero-trust/main.tf:216" in output
            assert "security_risk: true" in output
            assert "🔴緊急" in output

    def test_todo_structure(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """TODO項目の構造をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # TODO項目の基本構造を検証
            assert "### TODO #1:" in output
            assert "### TODO #105:" in output
            assert "**分類**:" in output
            assert "```yaml" in output
            assert "id:" in output
            assert "priority:" in output
            assert "type:" in output
            assert "file:" in output
            assert "author: coderabbitai[bot]" in output
            assert "**🎯 最終判断**: [ ] ✅実施 [ ] ❌対応不要 [ ] ⏳将来対応 [ ] 🤔要確認" in output

    def test_curl_command_generation(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """curlコマンド生成をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # curlコマンドの生成を検証
            assert "curl -X POST" in output
            assert 'Authorization: Bearer $GITHUB_TOKEN' in output
            assert "https://api.github.com/repos/yohi/terraform/pulls/102/comments" in output
            assert '"in_reply_to": COMMENT_ID' in output

    def test_risk_mitigation_system(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """リスク軽減システムの出力をテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            output = captured_output.getvalue()
            
            # リスク軽減システムの検証
            assert "🛡️ リスク軽減・エラー防止システム" in output
            assert "**バックアップブランチ作成**: `git checkout -b backup-$(date +%Y%m%d-%H%M)`" in output
            assert "**Phase 1完了時**: `git add . && git commit -m \"Phase1: 緊急対応完了\"`" in output
            assert "**2時間経過時**: 強制休憩（15分以上）" in output

    def test_memory_usage_efficiency(self, mock_pr_data, mock_comments_data, mock_resolved_comments):
        """メモリ効率とパフォーマンスをテスト"""
        with patch('github_review_prompts.github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            mock_client.get_pull_request.return_value = mock_pr_data
            mock_client.get_review_comments.return_value = mock_comments_data
            mock_client.get_resolved_comments.return_value = mock_resolved_comments
            
            import psutil
            import time
            
            # メモリ使用量の測定開始
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_time = time.time()
            
            captured_output = StringIO()
            
            with patch('sys.stdout', captured_output), patch('sys.stderr', StringIO()):
                with patch('sys.argv', ['grp', 'https://github.com/yohi/terraform/pull/102']):
                    try:
                        main()
                    except SystemExit:
                        pass
            
            # パフォーマンス測定
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            execution_time = end_time - start_time
            memory_usage = end_memory - start_memory
            
            # パフォーマンス検証
            assert execution_time < 10.0  # 10秒以内で完了
            assert memory_usage < 100.0   # メモリ使用量100MB以下
            
            output = captured_output.getvalue()
            assert len(output) > 1000  # 十分な出力が生成される


if __name__ == "__main__":
    pytest.main([__file__, "-v"])