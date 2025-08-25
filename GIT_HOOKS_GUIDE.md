# 🪝 Git Hooks テスト自動化ガイド

## 概要

このプロジェクトでは、Git hooksを使用してコミット・Push時にテストを自動実行します。
SAFE_PYTEST_EXECUTION_GUIDE.mdに準拠したメモリ効率的なテスト実行を行います。

---

## 🚀 セットアップ

### 自動セットアップ（推奨）

```bash
# プロジェクトルートで実行
./scripts/setup-git-hooks.sh
```

### 手動セットアップ

```bash
# 実行権限付与
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push
chmod +x .git/hooks/pre-commit-memory-safe

# 動作確認
.git/hooks/pre-commit
```

---

## 🪝 利用可能なHooks

### 1. Pre-commit Hook
**SAFE準拠軽量テスト実行（コミット時）**

- **実行方法**: `run_tests_memory_efficient.sh --single`
- **対象テスト**: 認証・セキュリティテスト
- **実行時間**: 5-10秒
- **メモリ使用量**: <1GB (systemd制限)
- **実行タイミング**: `git commit`

```bash
# SAFE_PYTEST_EXECUTION_GUIDE.md 準拠実行
./run_tests_memory_efficient.sh --single test_authentication_security.py

# または systemd メモリ制限実行
systemd-run --user --scope -p MemoryMax=1G python -m pytest
```

### 2. Pre-push Hook
**SAFE準拠分割テスト実行（Push時）**

- **実行方法**: `run_tests_memory_efficient.sh --chunked` + `--heavy`
- **対象テスト**: 全機能（分割実行）
- **実行時間**: 2-4分
- **メモリ使用量**: <2GB (systemd制限)
- **実行タイミング**: `git push`

```bash
# SAFE_PYTEST_EXECUTION_GUIDE.md 準拠分割実行
./run_tests_memory_efficient.sh --chunked  # 小さなチャンクで実行
./run_tests_memory_efficient.sh --heavy    # 重いテスト個別実行

# または systemd メモリ制限実行
systemd-run --user --scope -p MemoryMax=2G python -m pytest
```

### 3. Memory Safe Hook（オプション）
**SAFE準拠超軽量テスト実行**

- **実行方法**: `systemd-run` 最大メモリ制限
- **対象テスト**: 最小限のクリティカルテスト
- **実行時間**: 5-15秒
- **メモリ使用量**: <1GB (systemd厳格制限)
- **実行方法**: 手動実行

```bash
# SAFE_PYTEST_EXECUTION_GUIDE.md 最大限準拠
.git/hooks/pre-commit-memory-safe

# 内部実行: systemd 厳格メモリ制限
systemd-run --user --scope -p MemoryMax=1G -p MemorySwapMax=500M
```

---

## 📊 SAFE_PYTEST_EXECUTION_GUIDE.md完全準拠設定

すべてのhooksで以下のSAFE準拠最適化が適用されます：

```bash
# SAFE推奨環境変数
export PYTHONDONTWRITEBYTECODE=1  # .pycファイル生成無効化
export PYTHONHASHSEED=1           # ハッシュシード固定
export MALLOC_ARENA_MAX=2         # mallocアリーナ制限

# SAFE推奨pytest設定
--tb=short                        # 短縮トレースバック
--maxfail=3                       # 最大失敗数制限
-q                                # 簡潔出力

# SAFE推奨実行方法
./run_tests_memory_efficient.sh   # メモリ効率スクリプト使用
systemd-run --user --scope        # systemdメモリ制限
timeout <時間>                     # タイムアウト制御
```

---

## 🎛️ 使用方法

### 通常の開発フロー

```bash
# 1. コード変更
vim src/some_file.py

# 2. 軽量テスト付きコミット
git add .
git commit -m "Feature: 新機能追加"
# → Pre-commitフックが自動実行（30-45秒）

# 3. 包括的テスト付きPush
git push origin feature-branch
# → Pre-pushフックが自動実行（4-6分）
```

### 緊急時のスキップ

```bash
# テストをスキップしてコミット
git commit --no-verify -m "Hotfix: 緊急修正"

# テストをスキップしてPush
git push --no-verify origin main
```

### メモリ制約環境での使用

```bash
# 超軽量モードで事前テスト
.git/hooks/pre-commit-memory-safe

# 問題なければ通常コミット
git commit -m "安全確認済みの変更"
```

---

## ⚠️ トラブルシューティング

### 問題1: メモリ不足エラー

**症状**: テスト実行中にプロセスが強制終了

**解決策**:
```bash
# 1. メモリ使用量確認
free -h

# 2. 超軽量モード使用
.git/hooks/pre-commit-memory-safe

# 3. 必要に応じてスキップ
git commit --no-verify
```

### 問題2: タイムアウトエラー

**症状**: テストが指定時間内に完了しない

**解決策**:
```bash
# 1. 手動でテスト実行して問題特定
timeout 60 python -m pytest src/github_review_prompts/tests/test_authentication_security.py -v

# 2. システムリソース確認
top -o %MEM

# 3. 一時的にスキップ
git commit --no-verify
```

### 問題3: Hooks無効化・復元

**無効化**:
```bash
# バックアップ作成
mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled
mv .git/hooks/pre-push .git/hooks/pre-push.disabled
```

**復元**:
```bash
# 再セットアップ
./scripts/setup-git-hooks.sh
```

---

## 🔧 カスタマイズ

### テスト対象の変更

Pre-commitフックで異なるテストを実行したい場合：

```bash
# .git/hooks/pre-commit を編集
timeout 45 python -m pytest \
    src/github_review_prompts/tests/your_custom_test.py \
    --tb=short -q --maxfail=3
```

### タイムアウト時間の調整

```bash
# Pre-commitフック内
export PYTEST_TIMEOUT=60  # 60秒に変更

# Pre-pushフック内
export PYTEST_TIMEOUT=180 # 3分に変更
```

---

## 📈 パフォーマンス指標

| Hook        | 実行時間 | メモリ使用量       | テスト数 | 対象範囲         | SAFE準拠レベル |
| ----------- | -------- | ------------------ | -------- | ---------------- | -------------- |
| Pre-commit  | 5-10秒   | <1GB (systemd制限) | ~20      | 認証セキュリティ | ✅ 完全準拠     |
| Pre-push    | 2-4分    | <2GB (systemd制限) | ~100     | 分割実行         | ✅ 完全準拠     |
| Memory Safe | 5-15秒   | <1GB (厳格制限)    | ~1       | 最小限           | ✅ 最大限準拠   |

---

## 🎯 ベストプラクティス

### 1. 段階的テスト戦略

```bash
# 開発中: Memory Safeモードで頻繁チェック
.git/hooks/pre-commit-memory-safe

# コミット前: Pre-commitで確実チェック
git commit

# Push前: Pre-pushで包括チェック
git push
```

### 2. CI/CD連携

```bash
# GitHub Actions等でも同じhooksを使用
- name: Run Git Hooks Tests
  run: |
    .git/hooks/pre-push
```

### 3. チーム開発

```bash
# 新規メンバーへの共有
git clone <repository>
cd <project>
./scripts/setup-git-hooks.sh
```

---

## 🛠️ 保守・更新

### Hooksの更新

```bash
# 最新版に更新
./scripts/setup-git-hooks.sh

# 既存のhooksは自動バックアップされます
```

### ログの確認

```bash
# Git操作ログでhooks実行状況確認
git log --oneline -10

# 詳細なテスト結果が必要な場合
.git/hooks/pre-commit 2>&1 | tee test-log.txt
```

---

## 📞 サポート

### よくある質問

**Q: Hooksを一時的に無効化したい**
```bash
A: git commit --no-verify を使用
```

**Q: メモリが足りない場合は？**
```bash
A: .git/hooks/pre-commit-memory-safe を使用
```

**Q: 特定のテストだけ実行したい**
```bash
A: .git/hooks内のファイルを直接編集
```

### 技術サポート

1. **メモリ監視**: `python memory_monitor.py --status`
2. **システムリソース**: `free -h && df -h`
3. **プロセス確認**: `ps aux | grep pytest`

---

**安全で効率的な開発を実現するGit Hooksをご活用ください！** 🚀
