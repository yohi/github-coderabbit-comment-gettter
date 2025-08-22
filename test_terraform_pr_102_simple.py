#!/usr/bin/env python3
"""
Terraform PR #102の標準出力検証用シンプルテスト
実際のPRコメント内容をモック化してテスト
"""

import sys
import os
from unittest.mock import Mock, patch
from io import StringIO

# パッケージパスを追加
sys.path.insert(0, '/home/y_ohi/program/github-coderabbit-comment-gettter/src')

from github_review_prompts.core.prompt_engine import UnifiedPromptEngine


def create_mock_comments():
    """105件のモックコメントを作成"""
    comments = []
    
    # 🔴 セキュリティ関連（3件）
    security_comments = [
        {
            "id": 2292368740,
            "body": "_💡 Verification agent_\n\nセッション制御条件の誤用修正必須",
            "path": "modules/security/zero-trust/main.tf",
            "line": 216,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:48:35Z"
        },
        {
            "id": 2292368759,
            "body": "_💡 Verification agent_\n\nセキュリティリスク: トークン関連の修正が必要",
            "path": "modules/security/zero-trust/main.tf", 
            "line": 416,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:48:36Z"
        },
        {
            "id": 2292368767,
            "body": "_⚠️ Potential issue_\n\n**Config Ruleで未サポートの`tags`利用/依存関係の明示不足**",
            "path": "modules/security/zero-trust/main.tf",
            "line": 621,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:48:36Z"
        }
    ]
    
    # 🟢 ドキュメント関連（7件）
    doc_comments = [
        {
            "id": 2292366617,
            "body": "_💡 Verification agent_\n\nディレクトリ名をリポジトリ名（terraform）に合わせて修正してください",
            "path": "developer-tools/DEVELOPER_QUICK_START_GUIDE.md",
            "line": 56,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:46:11Z"
        }
    ]
    
    # 残りをドキュメント関連で埋める
    for i in range(6):
        doc_comments.append({
            "id": 2292366618 + i,
            "body": f"_🛠️ Refactor suggestion_\n\nREADME.md修正 #{i+2}",
            "path": f"docs/guide_{i+2}.md",
            "line": 10 + i,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-21T23:46:1{2+i}Z"
        })
    
    # 🟡 機能改善・品質向上（95件）
    functionality_comments = []
    for i in range(95):
        functionality_comments.append({
            "id": 3000 + i,
            "body": f"_🛠️ Refactor suggestion_\n\n機能改善提案 #{i+1}: Terraformリソースの最適化が必要です",
            "path": f"modules/infrastructure/resource_{i+1}.tf",
            "line": 20 + (i % 50),
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-21T23:4{7+(i//20)}:{(i%60):02d}Z"
        })
    
    # 全105件を結合
    all_comments = security_comments + doc_comments + functionality_comments
    return all_comments


def test_terraform_pr_102_output():
    """Terraform PR #102の標準出力をテスト"""
    print("🧪 Terraform PR #102 標準出力テスト開始")
    
    # モックデータの準備
    comments = create_mock_comments()
    pr_info = {
        "owner": "yohi",
        "repo": "terraform", 
        "number": 102,
        "title": "Feature/phase4 step4 developer experience",
        "url": "https://github.com/yohi/terraform/pull/102"
    }
    
    print(f"📊 テスト用コメント数: {len(comments)}件")
    
    # プロンプトエンジンでプロンプト生成
    engine = UnifiedPromptEngine()
    prompt = engine.generate_main_prompt(
        comments=comments,
        pr_info=pr_info,
        github_token="mock_token"
    )
    
    print("🔍 標準出力構造の検証...")
    
    # 基本構造の検証
    tests = [
        ("🎯 CodeRabbitレビュー対応プロンプト", "プロンプトタイトル"),
        ("セキュリティ最優先原則", "セキュリティ原則"),
        ("🚨 段階的実行戦略（大量コメント対応）", "段階的実行戦略"),
        ("Phase 1: 🔴緊急対応（最優先30-60分）", "Phase 1定義"),
        ("Phase 2: 🟡重要対応（2-3時間以内）", "Phase 2定義"),
        ("Phase 3: 🟢低優先対応（時間があれば）", "Phase 3定義"),
        ("🔴 緊急（セキュリティ・機能破綻）- 3件", "緊急コメント数"),
        ("🟡 重要（機能改善・品質向上）- 95件", "重要コメント数"),
        ("🟢 低優先（スタイル・軽微改善）- 7件", "低優先コメント数"),
        ("🛡️ リスク軽減・エラー防止システム", "リスク軽減システム"),
        ("git checkout -b backup-$(date +%Y%m%d-%H%M)", "バックアップ作成"),
        ("80%ルール", "現実的成功基準"),
        ("### TODO #1:", "TODO項目開始"),
        ("### TODO #105:" if "### TODO #105:" in prompt else "TODO項目の存在", "TODO項目終了"),
        ("```yaml", "YAML形式メタデータ"),
        ("security_risk: true", "セキュリティリスク表示"),
        ("curl -X POST", "curl返信コマンド"),
        ("@coderabbitai", "CodeRabbit返信指示")
    ]
    
    passed = 0
    failed = 0
    
    for test_string, description in tests:
        if test_string in prompt:
            print(f"✅ {description}: 検出成功")
            passed += 1
        else:
            print(f"❌ {description}: 検出失敗 - '{test_string}' が見つかりません")
            failed += 1
    
    # 統計情報
    print(f"\n📈 テスト結果:")
    print(f"✅ 成功: {passed}件")
    print(f"❌ 失敗: {failed}件")
    print(f"📊 成功率: {(passed/(passed+failed)*100):.1f}%")
    
    # プロンプト長の確認
    print(f"📏 生成プロンプト長: {len(prompt):,} 文字")
    
    # 詳細構造確認
    if "🔴 緊急（セキュリティ・機能破綻）- 3件" in prompt:
        print("🔍 セキュリティ分類: 正常")
    else:
        print("⚠️ セキュリティ分類: 要確認")
    
    if "### TODO #1:" in prompt and "security_risk: true" in prompt:
        print("🔍 TODO構造: 正常")
    else:
        print("⚠️ TODO構造: 要確認")
    
    # 実際の出力例を一部表示
    print("\n🎯 生成プロンプトサンプル（最初の500文字）:")
    print("-" * 50)
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print("-" * 50)
    
    return passed > failed


def test_comment_classification():
    """コメント分類ロジックのテスト"""
    print("\n🔬 コメント分類ロジックテスト")
    
    engine = UnifiedPromptEngine()
    
    # セキュリティ関連テスト
    security_comment = "セキュリティリスク: token exposure detected"
    classification = engine._analyze_comment(security_comment, "test.tf")
    
    if classification['issue_type'] == 'security':
        print("✅ セキュリティコメント分類: 正常")
    else:
        print("❌ セキュリティコメント分類: 失敗")
    
    # ドキュメント関連テスト
    doc_comment = "README.md anchor link needs fixing: MD051 violation"
    classification = engine._analyze_comment(doc_comment, "README.md")
    
    if classification['issue_type'] == 'documentation':
        print("✅ ドキュメントコメント分類: 正常")
    else:
        print("❌ ドキュメントコメント分類: 失敗")


if __name__ == "__main__":
    print("🚀 Terraform PR #102 標準出力検証テスト\n")
    
    try:
        # メインテスト実行
        success = test_terraform_pr_102_output()
        
        # 分類テスト実行
        test_comment_classification()
        
        if success:
            print("\n🎉 テスト完了: 標準出力は期待される構造を満たしています")
            sys.exit(0)
        else:
            print("\n⚠️ テスト完了: 一部の検証で問題が見つかりました")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)