#!/usr/bin/env python3
"""バッチ返信システムの統合テスト"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from github_review_prompts.utils.smart_batch_reply_manager import (
    SmartBatchReplyManager, BatchReply, ReplyPriority
)
from github_review_prompts.utils.reply_decision_matrix import ReplyDecisionMatrix


def test_integrated_batch_system():
    """統合バッチシステムのテスト"""

    print("=== バッチ返信システム統合テスト ===")

    # 実際のPRコメントをシミュレート
    sample_comments = [
        {
            "id": 2296181566,
            "user": {"login": "coderabbitai[bot]"},
            "body": "_⚠️ Potential issue_\n\nセキュリティ上の問題があります。パスワードがハードコードされています。",
            "created_at": "2025-01-24T10:00:00Z"
        },
        {
            "id": 2296272971,
            "user": {"login": "yohi"},
            "body": "@coderabbitai 指摘された問題の大部分は既に解決済みです。確認してください。",
            "created_at": "2025-01-24T10:30:00Z"
        },
        {
            "id": 3217140550,
            "user": {"login": "coderabbitai[bot]"},
            "body": "<!-- This is an auto-generated reply by CodeRabbit -->\n✅ Actions performed\n\nReview triggered.",
            "created_at": "2025-01-24T10:45:00Z"
        }
    ]

    # 1. 返信判定マトリックスで分析
    print("\n1. 返信判定マトリックス分析...")
    matrix = ReplyDecisionMatrix()
    context = {'current_phase': 'development', 'future_phase': 'quality_improvement'}
    analysis = matrix.analyze_reply_requirements(sample_comments, context)

    print(f"   総コメント数: {analysis['total_comments']}")
    print(f"   返信必要: {analysis['reply_required_count']}")
    print(f"   返信不要: {analysis['reply_not_required_count']}")

    # 2. 返信が必要なコメントからBatchReplyを作成
    print("\n2. バッチ返信データ作成...")
    batch_replies = []

    for decision_info in analysis['decisions']:
        decision = decision_info['decision']
        comment_id = decision_info['comment_id']

        if decision.reply_required.name == 'REQUIRED':
            # 返信内容を生成
            reply_context = {
                'technical_reason': '技術的制約',
                'detailed_explanation': 'この指摘は現在の実装方針と合致しません',
                'reference': '公式ドキュメント参照'
            }

            reply_body = matrix.generate_reply_message(decision, reply_context)
            if reply_body:
                priority = ReplyPriority.CRITICAL if decision.priority == 'high' else ReplyPriority.NORMAL

                batch_reply = BatchReply(
                    comment_id=comment_id,
                    reply_body=reply_body,
                    priority=priority,
                    template_type=decision.template_type or 'general'
                )
                batch_replies.append(batch_reply)

    print(f"   作成された返信: {len(batch_replies)}件")

    # 3. バッチ返信マネージャーでバッチ最適化
    print("\n3. バッチ最適化...")
    manager = SmartBatchReplyManager("dummy_token")
    batches = manager.optimize_reply_batch(batch_replies)

    print(f"   最適化されたバッチ数: {len(batches)}")
    for i, batch in enumerate(batches, 1):
        priority_counts = {}
        for reply in batch:
            priority_counts[reply.priority.value] = priority_counts.get(reply.priority.value, 0) + 1
        print(f"   バッチ {i}: {len(batch)}件 ({priority_counts})")

    # 4. GitHub API用のcurlコマンド生成
    print("\n4. GitHub API用コマンド生成...")
    pr_info = {
        "owner": "yohi",
        "repo": "terraform",
        "pull_number": 98
    }

    commands = manager.generate_batch_commands(batches, pr_info)
    print(f"   生成されたcurlコマンド数: {len(commands)}")

    # 5. 効率性分析
    print("\n5. 効率性分析...")

    # 従来方式（1コメント1API）vs バッチ方式
    traditional_api_calls = len(batch_replies)
    batch_api_calls = len(batches)
    efficiency_improvement = ((traditional_api_calls - batch_api_calls) / traditional_api_calls * 100) if traditional_api_calls > 0 else 0

    print(f"   従来方式: {traditional_api_calls}回のAPI呼び出し")
    print(f"   バッチ方式: {batch_api_calls}回のAPI呼び出し")
    print(f"   効率改善: {efficiency_improvement:.1f}%削減")

    # 6. 実際のcurlコマンド例を表示
    if commands:
        print(f"\n6. 実行可能なcurlコマンド例:")
        print("=" * 50)
        print(commands[0][:500] + "..." if len(commands[0]) > 500 else commands[0])
        print("=" * 50)

    return {
        'total_comments': len(sample_comments),
        'replies_needed': len(batch_replies),
        'batches_created': len(batches),
        'api_efficiency': efficiency_improvement,
        'commands_generated': len(commands)
    }


if __name__ == "__main__":
    try:
        results = test_integrated_batch_system()

        print(f"\n🎉 統合テスト完了!")
        print(f"📊 結果サマリー:")
        print(f"   - 処理コメント数: {results['total_comments']}")
        print(f"   - 返信必要数: {results['replies_needed']}")
        print(f"   - 作成バッチ数: {results['batches_created']}")
        print(f"   - API効率改善: {results['api_efficiency']:.1f}%")
        print(f"   - 生成コマンド数: {results['commands_generated']}")

    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
