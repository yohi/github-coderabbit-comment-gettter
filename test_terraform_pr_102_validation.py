#!/usr/bin/env python3
"""
Terraform PR #102の標準出力検証用テスト
実際のPRコメント内容をモック化してテスト
"""

import sys
import os
from unittest.mock import Mock, patch
from io import StringIO

# パッケージパスを追加
sys.path.insert(0, './src')

try:
    from github_review_prompts.core.prompt_engine import UnifiedPromptEngine
    print("✅ UnifiedPromptEngine import successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def create_mock_comments():
    """105件のモックコメントを作成（実際のPR #102に基づく）"""
    comments = []
    
    # 🔴 セキュリティ関連（3件）- 実際のコメントに基づく
    security_comments = [
        {
            "id": 2292368740,
            "body": "_💡 Verification agent_\n\nセッション制御条件の誤用修正必須\n\n```diff\nresource \"aws_iam_policy\" \"device_trust\" {\ncount = local.current_config.device_trust_required ? 1 : 0\npolicy = jsonencode({\nVersion = \"2012-10-17\"\nStatement = [\n{\n-        Sid    = \"RequireDeviceRegistration\"\n+        Sid    = \"RestrictToCurrentRegion\"\nEffect = \"Deny\"\n```",
            "path": "modules/security/zero-trust/main.tf",
            "line": 216,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:48:35Z"
        },
        {
            "id": 2292368759,
            "body": "_💡 Verification agent_\n\nセキュリティリスク: トークン関連の修正が必要\n\n```diff\nresource \"aws_lambda_function\" \"security_incident_response\" {\ncount = var.enable_incident_response ? 1 : 0\n-  runtime         = \"python3.9\"\n+  runtime         = \"python3.12\"\n```",
            "path": "modules/security/zero-trust/main.tf", 
            "line": 416,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:48:36Z"
        },
        {
            "id": 2292368767,
            "body": "_⚠️ Potential issue_\n\n**Config Ruleで未サポートの`tags`利用/依存関係の明示不足**\n\n```diff\nresource \"aws_config_config_rule\" \"zero_trust_rules\" {\ncount = var.enable_config_compliance ? length(var.zero_trust_config_rules) : 0\n-  depends_on = [aws_config_configuration_recorder.zero_trust_recorder]\n-\n-  tags = local.final_tags\n+  depends_on = [aws_config_configuration_recorder_status.zero_trust_recorder_status]\n}\n```",
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
            "body": "_💡 Verification agent_\n\nディレクトリ名をリポジトリ名（terraform）に合わせて修正してください\n\n```diff\n-git clone <repository-url>\n-cd terraform-aws-platform\n+git clone <repository-url>\n+cd <your-repo-root>   # 例: cd terraform\n```",
            "path": "developer-tools/DEVELOPER_QUICK_START_GUIDE.md",
            "line": 56,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:46:11Z"
        },
        {
            "id": 2292366623,
            "body": "_🛠️ Refactor suggestion_\n\n**環境名validation（dev, stg, prd）と他モジュール（dev, staging, prod）が不一致です**\n\n```diff\n-  validation {\n-    condition     = contains([\"dev\", \"stg\", \"prd\"], var.environment)\n-    error_message = \"Environment must be dev, stg, or prd.\"\n-  }\n+  validation {\n+    condition     = contains([\"dev\", \"staging\", \"prod\"], var.environment)\n+    error_message = \"Environment must be dev, staging, or prod.\"\n+  }\n```",
            "path": "developer-tools/DEVELOPMENT_BEST_PRACTICES.md",
            "line": 110,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": "2025-08-21T23:46:11Z"
        }
    ]
    
    # 残りのドキュメント関連コメント（5件）
    for i in range(5):
        doc_comments.append({
            "id": 2292366624 + i,
            "body": f"_🛠️ Refactor suggestion_\n\nmarkdown anchor link needs fixing: MD051 violation #{i+1}",
            "path": f"docs/documentation_{i+1}.md",
            "line": 15 + i,
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-21T23:46:1{3+i}Z"
        })
    
    # 🟡 機能改善・品質向上（95件）
    functionality_comments = []
    for i in range(95):
        functionality_comments.append({
            "id": 3000 + i,
            "body": f"_🛠️ Refactor suggestion_\n\n機能改善提案 #{i+1}: Terraformリソースの最適化\n\n```diff\n# Resource optimization\n- old_config = \"value\"\n+ new_config = \"improved_value\"\n```",
            "path": f"modules/infrastructure/resource_{i+1}.tf",
            "line": 20 + (i % 50),
            "user": {"login": "coderabbitai[bot]"},
            "created_at": f"2025-08-21T23:4{7+(i//30)}:{(i%60):02d}Z"
        })
    
    # 全105件を結合
    all_comments = security_comments + doc_comments + functionality_comments
    
    # 正確に105件になるように調整
    return all_comments[:105]


def test_terraform_pr_102_output():
    """Terraform PR #102の標準出力をテスト"""
    print("🧪 Terraform PR #102 標準出力検証テスト開始")
    
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
    
    # 実際のPR #102出力と比較するためのテスト項目
    expected_patterns = [
        # 基本構造
        ("🎯 CodeRabbitレビュー対応プロンプト", "プロンプトタイトル"),
        ("セキュリティ最優先原則", "セキュリティ原則"),
        ("🎯 ペルソナ: シニアセキュリティエンジニア", "ペルソナ設定"),
        
        # 段階的実行戦略
        ("🚨 段階的実行戦略（大量コメント対応）", "段階的実行戦略"),
        ("Phase 1: 🔴緊急対応（最優先30-60分）", "Phase 1定義"),
        ("Phase 2: 🟡重要対応（2-3時間以内）", "Phase 2定義"),
        ("Phase 3: 🟢低優先対応（時間があれば）", "Phase 3定義"),
        ("件数制限: 最大15件", "Phase 1件数制限"),
        ("件数制限: 20-30件", "Phase 2件数制限"),
        ("🔴項目100%完了", "Phase 1成功基準"),
        ("🟡項目80%以上完了", "Phase 2成功基準"),
        
        # コメント分類（実際のPR #102に基づく）
        ("🔴 緊急（セキュリティ・機能破綻）- 3件", "緊急コメント数"),
        ("🟡 重要（機能改善・品質向上）- 95件", "重要コメント数"),
        ("🟢 低優先（スタイル・軽微改善）- 7件", "低優先コメント数"),
        ("がセキュリティ関連", "セキュリティ関連パーセンテージ"),
        
        # リスク軽減システム
        ("🛡️ リスク軽減・エラー防止システム", "リスク軽減システム"),
        ("git checkout -b backup-$(date +%Y%m%d-%H%M)", "バックアップ作成"),
        ("Phase 1完了時", "段階的セーフポイント"),
        ("2時間経過時: 強制休憩", "強制休憩"),
        
        # 現実的成功基準
        ("80%ルール", "80%ルール"),
        ("完璧主義より実用性を優先", "実用性重視"),
        ("Phase 1成功: 🔴緊急項目90%以上完了", "段階的成功定義"),
        
        # TODO項目構造
        ("### TODO #1:", "TODO項目開始"),
        ("```yaml", "YAML形式メタデータ"),
        ("id:", "コメントID"),
        ("priority:", "優先度"),
        ("type:", "タイプ"),
        ("security_risk:", "セキュリティリスク"),
        ("**🎯 最終判断**: [ ] ✅実施 [ ] ❌対応不要 [ ] ⏳将来対応 [ ] 🤔要確認", "最終判断チェック"),
        
        # 返信システム
        ("curl -X POST", "curl返信コマンド"),
        ("Authorization: Bearer $GITHUB_TOKEN", "認証ヘッダー"),
        ("https://api.github.com/repos/yohi/terraform/pulls/102/comments", "PR特有のURL"),
        ("@coderabbitai", "CodeRabbit返信指示"),
        
        # 将来対応メモリ管理
        ("📝 将来対応メモリ管理", "メモリ管理"),
        ("将来のタスクとして記憶し", "メモリ指示"),
        
        # 段階的報告テンプレート
        ("📊 段階的結果報告テンプレート（現実版）", "報告テンプレート"),
        ("Phase別実施状況", "Phase別報告"),
        ("段階的Git操作状況", "Git操作報告"),
        ("成功判定（現実基準）", "現実的成功判定")
    ]
    
    passed = 0
    failed = 0
    
    for pattern, description in expected_patterns:
        if pattern in prompt:
            print(f"✅ {description}: 検出成功")
            passed += 1
        else:
            print(f"❌ {description}: 検出失敗 - '{pattern[:50]}...' が見つかりません")
            failed += 1
    
    # 統計情報
    print(f"\n📈 テスト結果:")
    print(f"✅ 成功: {passed}件")
    print(f"❌ 失敗: {failed}件")
    print(f"📊 成功率: {(passed/(passed+failed)*100):.1f}%")
    
    # プロンプト品質指標
    print(f"📏 生成プロンプト長: {len(prompt):,} 文字")
    
    # セキュリティ関連の詳細確認
    security_count = prompt.count("security_risk: true")
    print(f"🔒 セキュリティリスク項目: {security_count}件")
    
    # TODO項目数の確認
    todo_count = prompt.count("### TODO #")
    print(f"📋 TODO項目数: {todo_count}件")
    
    # 実際の出力品質評価
    quality_score = (passed / len(expected_patterns)) * 100
    print(f"\n🏆 出力品質スコア: {quality_score:.1f}%")
    
    if quality_score >= 90:
        print("🎉 Enterprise Grade Quality achieved!")
    elif quality_score >= 80:
        print("✅ Production Ready Quality")
    elif quality_score >= 70:
        print("⚠️ Acceptable Quality - minor improvements needed")
    else:
        print("❌ Quality improvement required")
    
    return quality_score >= 80


def test_comment_classification_accuracy():
    """コメント分類精度のテスト"""
    print("\n🔬 コメント分類精度テスト")
    
    engine = UnifiedPromptEngine()
    
    test_cases = [
        # セキュリティ関連
        ("AWS credential exposure detected in config file", "security", "セキュリティ"),
        ("github_pat token is hardcoded", "security", "セキュリティ"),
        ("authorization header contains sensitive data", "security", "セキュリティ"),
        
        # ドキュメント関連
        ("README.md anchor link needs fixing: MD051", "documentation", "ドキュメント"),
        ("markdown formatting issue in docs", "documentation", "ドキュメント"),
        
        # 機能関連
        ("terraform resource optimization needed", "functionality", "機能"),
        ("performance improvement suggestion", "functionality", "機能")
    ]
    
    correct = 0
    total = len(test_cases)
    
    for comment_body, expected_type, description in test_cases:
        classification = engine._analyze_comment(comment_body, "test.tf")
        actual_type = classification['issue_type']
        
        if actual_type == expected_type:
            print(f"✅ {description}分類: 正常 ({expected_type})")
            correct += 1
        else:
            print(f"❌ {description}分類: 失敗 (期待: {expected_type}, 実際: {actual_type})")
    
    accuracy = (correct / total) * 100
    print(f"\n📊 分類精度: {accuracy:.1f}% ({correct}/{total})")
    
    return accuracy >= 80


if __name__ == "__main__":
    print("🚀 Terraform PR #102 標準出力検証テスト\n")
    
    try:
        # メインテスト実行
        output_test_passed = test_terraform_pr_102_output()
        
        # 分類精度テスト実行  
        classification_test_passed = test_comment_classification_accuracy()
        
        # 総合評価
        if output_test_passed and classification_test_passed:
            print("\n🎉 総合テスト結果: 合格")
            print("✅ 標準出力は期待される構造と品質を満たしています")
            print("✅ 段階的実行戦略が正常に実装されています")
            print("✅ 105件の大量コメント対応機能が動作します")
            sys.exit(0)
        else:
            print("\n⚠️ 総合テスト結果: 要改善")
            if not output_test_passed:
                print("❌ 標準出力構造に問題があります")
            if not classification_test_passed:
                print("❌ コメント分類精度に問題があります")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)