#!/usr/bin/env python3
"""本番環境v2.0.0の包括的動作検証テスト"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def run_command(cmd, timeout=60):
    """コマンドを実行して結果を返す"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def test_basic_functionality():
    """基本機能のテスト"""
    print("=== 基本機能テスト ===")

    tests = []

    # 1. バージョン確認
    print("1. バージョン確認...")
    result = run_command("uv run grp --version")
    tests.append({
        "name": "バージョン確認",
        "success": result["success"],
        "details": result["stdout"] if result["success"] else result["stderr"]
    })

    # 2. ヘルプ表示
    print("2. ヘルプ表示...")
    result = run_command("uv run grp --help")
    tests.append({
        "name": "ヘルプ表示",
        "success": result["success"],
        "details": "OK" if result["success"] else result["stderr"]
    })

    # 3. 実際のPRでの動作テスト
    print("3. 実際のPRでの動作テスト...")
    start_time = time.time()
    result = run_command("uv run grp --debug https://github.com/yohi/terraform/pull/98", timeout=120)
    processing_time = time.time() - start_time

    # 出力解析
    success = result["success"]
    if success:
        stdout = result["stdout"]
        # 重要な統計情報を抽出
        stats = {
            "total_comments": None,
            "actionable_comments": None,
            "replies_required": None,
            "replies_not_required": None,
            "estimated_time": None,
            "processing_time": processing_time
        }

        # ログから統計情報を抽出
        for line in stdout.split('\n'):
            if "返信要件分析完了" in line:
                # 例: 総コメント数=22, 返信必要=4, 返信不要=18, 推定時間=286分
                try:
                    parts = line.split("総コメント数=")[1]
                    stats["actionable_comments"] = int(parts.split(",")[0])
                    stats["replies_required"] = int(parts.split("返信必要=")[1].split(",")[0])
                    stats["replies_not_required"] = int(parts.split("返信不要=")[1].split(",")[0])
                    stats["estimated_time"] = int(parts.split("推定時間=")[1].split("分")[0])
                except:
                    pass
            elif "全コメント取得完了" in line:
                try:
                    # 例: 合計 50 件
                    parts = line.split("合計 ")[1]
                    stats["total_comments"] = int(parts.split(" 件")[0])
                except:
                    pass

        tests.append({
            "name": "実際のPR処理",
            "success": True,
            "details": f"処理時間: {processing_time:.2f}秒",
            "stats": stats
        })
    else:
        tests.append({
            "name": "実際のPR処理",
            "success": False,
            "details": result["stderr"]
        })

    return tests

def test_new_features():
    """新機能のテスト"""
    print("\n=== 新機能テスト ===")

    tests = []

    # 1. スマートフィルタリング機能
    print("1. スマートフィルタリング機能...")
    result = run_command("uv run grp --debug https://github.com/yohi/terraform/pull/98 2>&1 | grep -E '(スマートフィルタリング|フィルタ除外)'")
    tests.append({
        "name": "スマートフィルタリング",
        "success": result["success"],
        "details": "フィルタリング機能動作中" if result["success"] else "ログ出力なし"
    })

    # 2. 返信判定マトリックス
    print("2. 返信判定マトリックス...")
    result = run_command("uv run grp --debug https://github.com/yohi/terraform/pull/98 2>&1 | grep -E '(返信判定|返信要件分析)'")
    tests.append({
        "name": "返信判定マトリックス",
        "success": result["success"],
        "details": "返信判定機能動作中" if result["success"] else "ログ出力なし"
    })

    # 3. バッチ返信システム
    print("3. バッチ返信システム...")
    try:
        from github_review_prompts.utils.smart_batch_reply_manager import SmartBatchReplyManager
        manager = SmartBatchReplyManager("dummy_token")
        tests.append({
            "name": "バッチ返信システム",
            "success": True,
            "details": "モジュール正常インポート"
        })
    except Exception as e:
        tests.append({
            "name": "バッチ返信システム",
            "success": False,
            "details": f"インポートエラー: {e}"
        })

    # 4. 使用状況メトリクス
    print("4. 使用状況メトリクス...")
    try:
        from github_review_prompts.utils.usage_metrics import create_usage_metrics_collector
        collector = create_usage_metrics_collector()
        tests.append({
            "name": "使用状況メトリクス",
            "success": True,
            "details": "メトリクス収集システム正常"
        })
    except Exception as e:
        tests.append({
            "name": "使用状況メトリクス",
            "success": False,
            "details": f"インポートエラー: {e}"
        })

    return tests

def test_performance_regression():
    """パフォーマンス回帰テスト"""
    print("\n=== パフォーマンス回帰テスト ===")

    tests = []

    # 処理時間測定（3回実行して平均）
    print("処理時間測定（3回実行）...")
    times = []

    for i in range(3):
        print(f"  実行 {i+1}/3...")
        start_time = time.time()
        result = run_command("uv run grp https://github.com/yohi/terraform/pull/98 > /dev/null 2>&1")
        end_time = time.time()

        if result["success"]:
            times.append(end_time - start_time)
        else:
            tests.append({
                "name": "パフォーマンステスト",
                "success": False,
                "details": f"実行 {i+1} 失敗: {result['stderr']}"
            })
            return tests

    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)

    # パフォーマンス基準（5秒以内）
    performance_ok = avg_time < 5.0

    tests.append({
        "name": "パフォーマンステスト",
        "success": performance_ok,
        "details": f"平均: {avg_time:.2f}秒, 最大: {max_time:.2f}秒, 最小: {min_time:.2f}秒",
        "stats": {
            "average_time": avg_time,
            "max_time": max_time,
            "min_time": min_time
        }
    })

    return tests

def test_error_handling():
    """エラーハンドリングテスト"""
    print("\n=== エラーハンドリングテスト ===")

    tests = []

    # 1. 無効なURL
    print("1. 無効なURL...")
    result = run_command("uv run grp https://invalid-url.com/invalid/repo/pull/123")
    tests.append({
        "name": "無効なURL処理",
        "success": not result["success"],  # エラーになることが期待される
        "details": "適切にエラーハンドリング" if not result["success"] else "エラーが検出されなかった"
    })

    # 2. 存在しないPR
    print("2. 存在しないPR...")
    result = run_command("uv run grp https://github.com/yohi/terraform/pull/99999")
    tests.append({
        "name": "存在しないPR処理",
        "success": not result["success"],  # エラーになることが期待される
        "details": "適切にエラーハンドリング" if not result["success"] else "エラーが検出されなかった"
    })

    return tests

def generate_validation_report(all_tests):
    """検証レポートを生成"""

    report = {
        "validation_timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "total_tests": sum(len(tests) for tests in all_tests.values()),
        "passed_tests": sum(sum(1 for test in tests if test["success"]) for tests in all_tests.values()),
        "failed_tests": sum(sum(1 for test in tests if not test["success"]) for tests in all_tests.values()),
        "test_categories": all_tests
    }

    # 成功率計算
    if report["total_tests"] > 0:
        report["success_rate"] = (report["passed_tests"] / report["total_tests"]) * 100
    else:
        report["success_rate"] = 0

    # レポートファイル保存
    report_file = project_root / f"validation_report_v2.0.0_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report, report_file

def main():
    """メイン検証プロセス"""
    print("🚀 GitHub Review Prompts v2.0.0 本番環境検証開始")
    print("=" * 60)

    # 全テスト実行
    all_tests = {
        "basic_functionality": test_basic_functionality(),
        "new_features": test_new_features(),
        "performance": test_performance_regression(),
        "error_handling": test_error_handling()
    }

    # レポート生成
    report, report_file = generate_validation_report(all_tests)

    # 結果表示
    print("\n" + "=" * 60)
    print("🎯 検証結果サマリー")
    print("=" * 60)
    print(f"総テスト数: {report['total_tests']}")
    print(f"成功: {report['passed_tests']}")
    print(f"失敗: {report['failed_tests']}")
    print(f"成功率: {report['success_rate']:.1f}%")

    # カテゴリ別結果
    for category, tests in all_tests.items():
        passed = sum(1 for test in tests if test["success"])
        total = len(tests)
        print(f"\n📊 {category}: {passed}/{total} ({(passed/total*100):.1f}%)")

        for test in tests:
            status = "✅" if test["success"] else "❌"
            print(f"  {status} {test['name']}: {test['details']}")

            # 統計情報があれば表示
            if "stats" in test and test["stats"]:
                for key, value in test["stats"].items():
                    if value is not None:
                        print(f"    - {key}: {value}")

    print(f"\n📄 詳細レポート: {report_file}")

    # 検証結果の判定
    if report["success_rate"] >= 90:
        print("\n🎉 検証成功！本番環境での使用準備完了")
        return 0
    elif report["success_rate"] >= 75:
        print("\n⚠️  検証部分成功。一部問題があるが使用可能")
        return 1
    else:
        print("\n❌ 検証失敗。問題の修正が必要")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
