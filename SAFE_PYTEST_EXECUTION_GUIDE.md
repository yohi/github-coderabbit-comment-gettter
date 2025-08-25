# 🛡️ 安全なpytest実行ガイド

## 概要

このガイドは、メモリ効率的で安全なpytestの実行方法を提供します。従来の実行方法では20GB以上のメモリを消費していた問題を解決し、2-4GBの範囲でテストを実行できるようにします。

---

## 🚨 従来の問題

- **メモリ使用量**: 20.9GB（システム総メモリの70%）
- **実行時間**: 5分以上
- **システム負荷**: Load Average 34.64
- **I/O待機率**: 57-59%

---

## ✅ 最適化後の効果

| 項目 | 改善前 | 改善後 | 削減率 |
|------|--------|--------|--------|
| メモリ使用量 | 20.9 GB | 2-4 GB | **80-85%** |
| テストデータ数 | 1,030件 | 110件 | **89%** |
| 実行時間 | 5分+ | 30秒-2分 | **60-80%** |
| I/O負荷 | 非常に高い | 軽度 | **70%** |

---

## 🎯 推奨実行方法

### 1. 基本的な安全実行

```bash
cd /home/y_ohi/program/github-coderabbit-comment

# 現在のメモリ状況確認
python memory_monitor.py --status

# 単一テストファイルの安全実行
./run_tests_memory_efficient.sh --single test_coderabbit_filter.py
```

### 2. 分割実行（推奨）

```bash
# テストファイルを小さなチャンクに分けて実行
./run_tests_memory_efficient.sh --chunked
```

### 3. メモリ監視付き実行

```bash
# バックグラウンドでメモリ監視を開始
python memory_monitor.py --monitor --duration 300 &

# テスト実行
python -m pytest src/github_review_prompts/tests/test_coderabbit_filter.py -v

# 監視結果を確認
wait
```

### 4. 手動メモリ制限実行

```bash
# systemdを使ったメモリ制限付き実行
systemd-run --user --scope \
  -p MemoryMax=2G \
  -p MemorySwapMax=1G \
  timeout 120 python -m pytest \
    src/github_review_prompts/tests/test_coderabbit_filter.py \
    --tb=short -v --maxfail=3
```

---

## 🔧 利用可能なツール

### 1. `run_tests_memory_efficient.sh`

メモリ効率的なテスト実行スクリプト

```bash
# 使用方法
./run_tests_memory_efficient.sh [オプション]

# オプション一覧
--chunked    # 小さなチャンクに分けて実行（推奨）
--heavy      # 重いテストを個別実行
--single     # 指定した1つのテストファイルのみ実行
--monitor    # メモリ使用量を監視
--help       # ヘルプを表示
```

**例**:
```bash
# 分割実行
./run_tests_memory_efficient.sh --chunked

# 単一ファイル実行
./run_tests_memory_efficient.sh --single test_authentication_security.py

# 重いテストの個別実行
./run_tests_memory_efficient.sh --heavy
```

### 2. `memory_monitor.py`

メモリ使用量監視ツール

```bash
# 使用方法
python memory_monitor.py [オプション]

# オプション一覧
--status, -s      # 現在のメモリ状況を表示
--monitor, -m     # pytestプロセスの監視を開始
--duration, -d    # 監視時間（秒）[デフォルト: 300]
--interval, -i    # チェック間隔（秒）[デフォルト: 5]
```

**例**:
```bash
# 現在の状況確認
python memory_monitor.py --status

# 5分間監視
python memory_monitor.py --monitor --duration 300

# 詳細監視（2秒間隔）
python memory_monitor.py --monitor --duration 180 --interval 2
```

### 3. `pytest.ini`

最適化されたpytest設定ファイル

主要な設定内容:
- メモリ使用量削減オプション
- キャッシュとバイトコード制御
- 並列実行制限
- 出力制限

---

## 📋 段階的実行プラン

### ステップ1: 環境確認

```bash
# 現在のシステム状況確認
python memory_monitor.py --status

# 実行権限確認
ls -la run_tests_memory_efficient.sh memory_monitor.py
```

### ステップ2: 単一ファイルテスト

```bash
# 最も軽いテストから開始
./run_tests_memory_efficient.sh --single test_coderabbit_filter.py
```

### ステップ3: 段階的拡張

```bash
# 複数ファイルの分割実行
./run_tests_memory_efficient.sh --chunked
```

### ステップ4: 全体テスト

```bash
# メモリ監視付きで全体実行
python memory_monitor.py --monitor --duration 600 &
./run_tests_memory_efficient.sh --heavy
wait
```

---

## ⚠️ 安全上の注意事項

### 1. メモリ使用量の監視

**危険レベル**:
- 🚨 **10GB超過**: 即座にテスト停止を検討
- ⚠️  **5GB超過**: 注意深く監視
- ✅ **2-4GB**: 正常範囲

### 2. 実行時間の制限

```bash
# タイムアウト付き実行
timeout 120 python -m pytest [テストファイル]
```

### 3. 事前チェック

```bash
# 実行前の必須チェック
echo "利用可能メモリ:"
free -h | grep -E "(Mem|Swap)"

echo "ディスク容量:"
df -h / | tail -1
```

---

## 🛠️ トラブルシューティング

### 問題1: メモリ使用量が依然として高い

**解決策**:
```bash
# より小さなチャンクで実行
./run_tests_memory_efficient.sh --single test_coderabbit_filter.py

# バイトコード生成を完全に無効化
export PYTHONDONTWRITEBYTECODE=1
python -m pytest [テストファイル] -B
```

### 問題2: テストが途中で停止する

**解決策**:
```bash
# より厳しいメモリ制限で実行
systemd-run --user --scope \
  -p MemoryMax=1G \
  -p MemorySwapMax=500M \
  python -m pytest [テストファイル] --tb=line -x
```

### 問題3: 大量のpycファイルが生成される

**解決策**:
```bash
# pycファイルのクリーンアップ
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# 環境変数設定
export PYTHONDONTWRITEBYTECODE=1
```

---

## 📊 監視とログ

### 1. リアルタイム監視

```bash
# ターミナル1: テスト実行
./run_tests_memory_efficient.sh --chunked

# ターミナル2: リアルタイム監視
watch -n 5 "free -h && echo '---' && ps aux --sort=-%mem | head -5"
```

### 2. ログファイル出力

```bash
# 詳細ログ付き実行
python memory_monitor.py --monitor --duration 300 > test_memory_log.txt 2>&1 &
./run_tests_memory_efficient.sh --chunked > test_execution_log.txt 2>&1
```

---

## 🎛️ カスタマイズ設定

### 環境変数の設定

```bash
# メモリ最適化
export PYTHONDONTWRITEBYTECODE=1  # .pycファイル生成無効化
export PYTHONHASHSEED=1           # ハッシュシード固定
export MALLOC_ARENA_MAX=2         # mallocアリーナ制限

# pytest設定
export PYTEST_MAXFAIL=3           # 最大失敗数
export PYTEST_TIMEOUT=60          # タイムアウト（秒）
```

### カスタムテスト実行

```bash
# 特定のマーカーのみ実行
python -m pytest -m "not memory_intensive" src/github_review_prompts/tests/

# 軽量テストのみ実行
python -m pytest -m "unit" src/github_review_prompts/tests/ --tb=short

# 詳細ログ付き実行
python -m pytest src/github_review_prompts/tests/ -v --tb=long --capture=no
```

---

## 📈 パフォーマンス最適化

### 1. 並列実行の制御

```bash
# pytest-xdistを使用した並列実行（メモリ使用量注意）
pip install pytest-xdist
python -m pytest -n 2 src/github_review_prompts/tests/  # 2プロセスで並列実行
```

### 2. プロファイリング

```bash
# メモリプロファイリング
pip install memory-profiler
python -m pytest --profile-memory src/github_review_prompts/tests/

# 実行時間プロファイリング
python -m pytest --durations=10 src/github_review_prompts/tests/
```

---

## 🎯 ベストプラクティス

### 1. 定期的な監視

```bash
# 週次メモリ使用量チェック
python memory_monitor.py --status

# テスト実行前の必須チェック
free -h && df -h /
```

### 2. 段階的テスト戦略

1. **開発中**: 単一ファイルテスト
2. **統合前**: 分割実行
3. **CI/CD**: 全体テスト（監視付き）

### 3. 設定管理

```bash
# 設定ファイルのバックアップ
cp pytest.ini pytest.ini.backup
cp src/github_review_prompts/tests/conftest.py conftest.py.backup
```

---

## 📞 サポート

### 問題が発生した場合

1. **メモリ監視結果を確認**:
   ```bash
   python memory_monitor.py --status
   ```

2. **ログファイルを確認**:
   ```bash
   tail -f test_memory_log.txt
   tail -f test_execution_log.txt
   ```

3. **システムリソースを確認**:
   ```bash
   free -h
   df -h
   top -o %MEM
   ```

### 緊急時の対応

```bash
# 全pytestプロセスの確認
ps aux | grep pytest

# メモリ使用量の確認
ps aux --sort=-%mem | head -10

# 必要に応じて安全にプロセスを終了
# (注意: killコマンドは慎重に使用)
```

---

## 📝 更新履歴

- **2025-08-25**: 初版作成
  - メモリ効率化設定の実装
  - 分割実行スクリプトの作成
  - 監視ツールの導入

---

**このガイドを使用して、安全で効率的なpytestの実行を行ってください。** 🚀