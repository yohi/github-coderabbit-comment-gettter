#!/bin/bash
# CodeRabbit返信漏れチェックスクリプト

set -euo pipefail

REPO_OWNER=${1:-$(git config --get remote.origin.url | sed 's/.*github.com[\/:]//;s/\/.*//;s/.git$//')}
REPO_NAME=${2:-$(git config --get remote.origin.url | sed 's/.*\///;s/.git$//')}
PR_NUMBER=${3:-$(gh pr view --json number -q .number 2>/dev/null || echo "")}

echo "🔍 返信漏れチェック開始"
echo "🎯 対象: $REPO_OWNER/$REPO_NAME (PR: $PR_NUMBER)"

# 必要な返信コメントを取得
echo "📋 返信必要コメント確認中..."
REQUIRED_REPLIES=$(cat comment_decisions.jsonl | jq -r 'select(.decision != "✅") | .id')

if [[ -z "$REQUIRED_REPLIES" ]]; then
    echo "✅ 返信必要コメントなし"
    exit 0
fi

TOTAL_REQUIRED=$(echo "$REQUIRED_REPLIES" | wc -l)
echo "📊 返信必要数: $TOTAL_REQUIRED件"

# 実際の返信をチェック
echo "🔎 実際の返信状況確認中..."

# 現在のユーザー名を安全に取得
CURRENT_USER=$(gh api user -q .login)

SENT_REPLIES=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/pulls/$PR_NUMBER/comments" | \
    jq -r --arg user "$CURRENT_USER" '.[] | select(.user.login == $user) | .in_reply_to_id // empty')

SENT_COUNT=0
MISSING_REPLIES=""

for required_id in $REQUIRED_REPLIES; do
    if echo "$SENT_REPLIES" | grep -q "^$required_id$"; then
        echo "✅ #$required_id: 返信済み"
        ((SENT_COUNT++))
    else
        echo "❌ #$required_id: 返信漏れ"
        MISSING_REPLIES="$MISSING_REPLIES $required_id"
    fi
done

# 結果サマリー
echo ""
echo "📈 返信状況サマリー"
echo "┌─────────────────────────┐"
echo "│ 返信必要: $TOTAL_REQUIRED件          │"
echo "│ 返信済み: $SENT_COUNT件          │"
echo "│ 返信漏れ: $((TOTAL_REQUIRED - SENT_COUNT))件          │"
echo "└─────────────────────────┘"

if [[ $SENT_COUNT -eq $TOTAL_REQUIRED ]]; then
    echo "🎉 全ての返信完了"
    exit 0
else
    echo "⚠️ 返信漏れあり: $MISSING_REPLIES"
    echo "💡 再実行推奨: ./scripts/batch_reply.sh"
    exit 1
fi
