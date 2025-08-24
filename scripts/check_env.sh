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

# GITHUB_TOKEN形式チェック（拡張版）
if ! [[ "$GITHUB_TOKEN" =~ ^(ghp_|ghs_|ghr_|ghu_|gho_|ghd_|github_pat_) ]]; then
    echo "⚠️ GITHUB_TOKEN形式警告: 非標準形式を検出"
    echo "💡 標準形式: ghp_, ghs_, ghr_, ghu_, gho_, ghd_, github_pat_"
    echo "🔄 API接続テストで実際の有効性を確認します..."
fi

# GitHub API接続テスト
echo "🌐 GitHub API接続テスト..."
if ! curl -sf --connect-timeout 5 --max-time 10 \
    -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/user > /dev/null; then
    echo "❌ GitHub API接続失敗"
    echo "💡 TOKENが有効か確認してください"
    exit 1
fi

# 必要コマンドチェック
missing_commands=()
for cmd in curl jq parallel; do
    if ! command -v "$cmd" &> /dev/null; then
        missing_commands+=("$cmd")
    fi
done

if [[ ${#missing_commands[@]} -gt 0 ]]; then
    echo "❌ 不足コマンド: ${missing_commands[*]}"

    # OS検出とインストール案内
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        case "$ID" in
            ubuntu|debian)
                echo "💡 Ubuntu/Debian: sudo apt-get install ${missing_commands[*]}"
                ;;
            centos|rhel|fedora)
                echo "💡 CentOS/RHEL/Fedora: sudo yum install ${missing_commands[*]}"
                ;;
            *)
                echo "💡 一般的なインストール: パッケージマネージャーで ${missing_commands[*]} をインストール"
                ;;
        esac
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        echo "💡 macOS: brew install ${missing_commands[*]}"
    else
        echo "💡 一般的なインストール: パッケージマネージャーで ${missing_commands[*]} をインストール"
    fi
    exit 1
fi

echo "✅ 環境チェック完了"
echo "🚀 CodeRabbit対応準備完了"
