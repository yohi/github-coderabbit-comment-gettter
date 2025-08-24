#!/bin/bash
# CodeRabbit並列返信スクリプト

set -euo pipefail

# パラメータ設定
MAX_CONCURRENT=${1:-5}
TIMEOUT_MIN=${2:-45}
REPO_OWNER=${3:-$(git config --get remote.origin.url | sed 's/.*github.com[\/:]//;s/\/.*//;s/.git$//')}
REPO_NAME=${4:-$(git config --get remote.origin.url | sed 's/.*\///;s/.git$//')}
PR_NUMBER=${5:-$(gh pr view --json number -q .number 2>/dev/null || echo "")}

echo "⚡ CodeRabbit並列返信開始"
echo "📊 設定: 並列数=$MAX_CONCURRENT, タイムアウト=${TIMEOUT_MIN}分"
echo "🎯 対象: $REPO_OWNER/$REPO_NAME (PR: $PR_NUMBER)"

# 環境チェック
./scripts/check_env.sh

# 返信関数定義
reply_single_comment() {
    local comment_data="$1"
    local comment_id=$(echo "$comment_data" | jq -r '.id')
    local decision=$(echo "$comment_data" | jq -r '.decision')
    local reply_text=$(echo "$comment_data" | jq -r '.reply')

    if [[ "$decision" == "✅" ]]; then
        echo "⏩ #$comment_id: コード修正のみ（返信不要）"
        return 0
    fi

    echo "📤 #$comment_id: 返信送信中..."

    # JSON ペイロードを jq で安全に作成
    local json_payload
    json_payload=$(jq -n --arg body "$reply_text" --argjson in_reply_to "$comment_id" \
        '{body: $body, in_reply_to: $in_reply_to}')

    if curl -s -X POST \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        --data-binary "$json_payload" \
        "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/pulls/$PR_NUMBER/comments" > /dev/null; then
        echo "✅ #$comment_id: 返信完了"
    else
        echo "❌ #$comment_id: 返信失敗"
        return 1
    fi
}

export -f reply_single_comment
export GITHUB_TOKEN REPO_OWNER REPO_NAME PR_NUMBER

# 並列実行
echo "🚀 並列返信実行..."
if timeout ${TIMEOUT_MIN}m parallel -j $MAX_CONCURRENT reply_single_comment :::: <(cat comment_decisions.jsonl); then
    echo "🎉 並列返信完了"
else
    echo "⏰ タイムアウトまたはエラーで終了"
    exit 1
fi
