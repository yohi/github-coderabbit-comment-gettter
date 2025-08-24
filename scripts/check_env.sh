#!/bin/bash
# CodeRabbit対応環境チェックスクリプト

set -euo pipefail

echo "🔍 環境チェック開始..."

# GITHUB_TOKEN存在チェック
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo "❌ GITHUB_TOKEN未設定"
    echo "💡 設定方法: export GITHUB_TOKEN='your_token_here'"
    exit 1
fi

# GITHUB_TOKEN形式チェック
if ! [[ "$GITHUB_TOKEN" =~ ^(ghp_|github_pat_) ]]; then
    echo "❌ GITHUB_TOKEN形式不正"
    echo "💡 正しい形式: ghp_xxx または github_pat_xxx"
    exit 1
fi

# GitHub API接続テスト
echo "🌐 GitHub API接続テスト..."
if ! curl -sf -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user > /dev/null; then
    echo "❌ GitHub API接続失敗"
    echo "💡 TOKENが有効か確認してください"
    exit 1
fi

# 必要コマンドチェック
for cmd in curl jq parallel; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ $cmd コマンドが見つかりません"
        echo "💡 インストール: sudo apt-get install $cmd"
        exit 1
    fi
done

echo "✅ 環境チェック完了"
echo "🚀 CodeRabbit対応準備完了"