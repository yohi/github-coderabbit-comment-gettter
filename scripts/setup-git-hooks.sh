#!/bin/bash
# Git Hooks セットアップスクリプト

set -e

echo "🔧 Git Hooks セットアップ開始..."

# 現在のディレクトリ確認
if [ ! -f "pyproject.toml" ]; then
    echo "❌ エラー: プロジェクトルートディレクトリで実行してください"
    exit 1
fi

# Hooksディレクトリ確認
if [ ! -d ".git/hooks" ]; then
    echo "❌ エラー: .git/hooksディレクトリが存在しません"
    exit 1
fi

# 既存のhooksをバックアップ
backup_dir=".git/hooks-backup-$(date +%Y%m%d_%H%M%S)"
if [ -f ".git/hooks/pre-commit" ] || [ -f ".git/hooks/pre-push" ]; then
    echo "💾 既存hooksをバックアップ中: $backup_dir"
    mkdir -p "$backup_dir"
    [ -f ".git/hooks/pre-commit" ] && cp ".git/hooks/pre-commit" "$backup_dir/"
    [ -f ".git/hooks/pre-push" ] && cp ".git/hooks/pre-push" "$backup_dir/"
fi

# 実行権限確認・付与
echo "🔑 実行権限を設定中..."
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push
chmod +x .git/hooks/pre-commit-memory-safe

# テスト実行で動作確認
echo "🧪 Pre-commitフックのテスト実行..."
if .git/hooks/pre-commit; then
    echo "✅ Pre-commitフック正常動作"
else
    echo "❌ Pre-commitフックにエラーがあります"
    exit 1
fi

echo ""
echo "🎉 Git Hooks セットアップ完了！"
echo ""
echo "📋 設定されたHooks (SAFE_PYTEST_EXECUTION_GUIDE.md完全準拠):"
echo "  • pre-commit: SAFE準拠軽量テスト (run_tests_memory_efficient.sh使用)"
echo "  • pre-push: SAFE準拠分割テスト (chunked + heavy実行)"
echo "  • pre-commit-memory-safe: SAFE最大限準拠 (systemd厳格制限)"
echo ""
echo "🔧 使用方法:"
echo "  通常コミット: git commit (軽量テスト自動実行)"
echo "  Push: git push (包括的テスト自動実行)"
echo "  メモリ安全モード: .git/hooks/pre-commit-memory-safe"
echo ""
echo "⚠️  SAFE準拠の注意事項:"
echo "  • メモリ使用量: systemdで厳格制限 (<1-2GB)"
echo "  • 実行時間: 大幅短縮 (5秒-4分)"
echo "  • テスト失敗時は自動的にコミット/Pushが中止されます"
echo "  • 緊急時は --no-verify オプションでスキップ可能です"
echo "  • バックアップ: $backup_dir"
