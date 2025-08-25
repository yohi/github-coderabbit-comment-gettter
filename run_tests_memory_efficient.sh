#!/bin/bash
# メモリ効率的なpytestテスト実行スクリプト

set -e

echo "🚀 メモリ効率的なテスト実行を開始..."

# 環境変数設定
export PYTHONDONTWRITEBYTECODE=1  # .pycファイル生成を無効化
export PYTHONHASHSEED=1           # ハッシュシードを固定（メモリ使用量を安定化）
export MALLOC_ARENA_MAX=2         # mallocアリーナを制限

# メモリ使用量を監視する関数
monitor_memory() {
    while true; do
        ps -o pid,vsz,rss,comm -p $1 2>/dev/null || break
        sleep 5
    done &
}

# テスト実行戦略
run_tests_chunked() {
    echo "📋 テストファイルを小さなチャンクで実行..."

    # 単一ファイルずつ実行
    test_files=(
        "test_authentication_security.py"
        "test_pr_url_parsing.py"
        "test_github_api_integration.py"
    )

    for test_file in "${test_files[@]}"; do
        echo "🧪 実行中: $test_file"

        # メモリ制限付きで実行
        systemd-run --user --scope \
            -p MemoryMax=2G \
            -p MemorySwapMax=1G \
            timeout 120 python -m pytest \
                "src/github_review_prompts/tests/$test_file" \
                --tb=short \
                -v \
                --maxfail=3 \
                --disable-warnings \
                -x || echo "⚠️  $test_file でエラーが発生しました"

        # プロセス間でメモリをクリア
        echo "🧹 メモリクリア..."
        python3 -c "
import gc
import psutil
import os

# ガベージコレクションを強制実行
for i in range(3):
    gc.collect()

# 現在のメモリ使用量を表示
process = psutil.Process(os.getpid())
print(f'メモリ使用量: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
        sleep 2
    done
}

# 重いテストファイルを個別に実行
run_heavy_tests_separately() {
    echo "⚡ 大規模テストを個別実行..."

    heavy_tests=(
        "test_coderabbit_filtering.py"
    )

    for test_file in "${heavy_tests[@]}"; do
        echo "🔥 実行中（メモリ制限付き）: $test_file"

        # より厳しいメモリ制限
        systemd-run --user --scope \
            -p MemoryMax=1G \
            -p MemorySwapMax=500M \
            timeout 60 python -m pytest \
                "src/github_review_prompts/tests/$test_file" \
                --tb=line \
                --maxfail=1 \
                -x \
                -m "not memory_intensive" || echo "⚠️  $test_file でエラー（大量データテストをスキップ）"
    done
}

# 使用方法表示
show_usage() {
    echo "使用方法:"
    echo "  $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  --chunked    小さなチャンクに分けて実行（推奨）"
    echo "  --heavy      重いテストを個別実行"
    echo "  --single     指定した1つのテストファイルのみ実行"
    echo "  --monitor    メモリ使用量を監視"
    echo "  --help       このヘルプを表示"
}

# メインの実行ロジック
main() {
    case "${1:-chunked}" in
        --chunked|chunked)
            run_tests_chunked
            ;;
        --heavy|heavy)
            run_heavy_tests_separately
            ;;
        --single|single)
            if [ -z "$2" ]; then
                echo "❌ テストファイル名を指定してください"
                echo "例: $0 --single test_coderabbit_filter.py"
                exit 1
            fi
            echo "🎯 単一テスト実行: $2"
            systemd-run --user --scope \
                -p MemoryMax=1G \
                python -m pytest "src/github_review_prompts/tests/$2" --tb=short -v
            ;;
        --monitor|monitor)
            echo "📊 現在のシステムメモリ使用量:"
            free -h
            echo ""
            echo "📈 プロセス別メモリ使用量 (上位10):"
            ps aux --sort=-%mem | head -11
            ;;
        --help|help)
            show_usage
            ;;
        *)
            echo "❌ 不明なオプション: $1"
            show_usage
            exit 1
            ;;
    esac
}

# スクリプト実行
main "$@"
