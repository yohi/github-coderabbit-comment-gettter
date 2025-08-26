# 🤖 AIエージェント向けクイックリファレンス

## 📋 改善プロジェクト概要

**作成日**: 2025年1月24日
**分析対象**: PR #98 (49件コメント処理) + 全ソースコード分析
**GitHub Issues**: #6-#14 (9件作成済み)

## 🎯 新しいセッション開始時の必須手順

### 1. マスターIssue確認
```bash
# 最初に必ずマスターIssueを確認
https://github.com/yohi/github-coderabbit-comment-gettter/issues/6
```

### 2. 現在のPhase確認
- **Phase 1** (緊急): Issues #7, #8, #9
- **Phase 2** (重要): Issues #10, #11, #12
- **Phase 3** (将来): Issues #13, #14

### 3. 優先順位
1. 🔴 **最優先**: パフォーマンス改善 ([Issue #7](https://github.com/yohi/github-coderabbit-comment-gettter/issues/7))
2. 🔴 **緊急**: エラーハンドリング強化 ([Issue #8](https://github.com/yohi/github-coderabbit-comment-gettter/issues/8))
3. 🔴 **重要**: 長文コメント処理 ([Issue #9](https://github.com/yohi/github-coderabbit-comment-gettter/issues/9))

## 🔧 技術的な重要ポイント

### 現在の主要問題
- **49件コメント処理で長時間** → 並列処理導入必要
- **1件エラーで全体停止** → 個別エラー処理必要
- **10,000文字制限で切り詰め** → 要約機能必要
- **2つの設定システム並存** → 統一必要

### 改善効果予測
- **Phase 1完了**: 処理速度3-5倍、エラー耐性大幅改善
- **Phase 2完了**: 企業環境対応、保守性向上
- **Phase 3完了**: 拡張性確保、ユーザー体験向上

## 📂 重要ファイル一覧

### 🔴 緊急修正対象
```
src/github_review_prompts/comment_processor.py    # コメント処理メイン
src/github_review_prompts/core/prompt_engine.py   # プロンプト生成エンジン
src/github_review_prompts/utils/validators.py     # 長文制限処理
```

### 🟡 重要リファクタリング対象
```
src/github_review_prompts/config.py               # 旧設定システム
src/github_review_prompts/utils/enhanced_config.py # 新設定システム
src/github_review_prompts/tests/                  # テスト不足
```

## 🚀 実装開始時のチェックリスト

### Phase 1 開始前
- [ ] 現在のパフォーマンス測定（ベースライン確立）
- [ ] エラーパターンの詳細分析
- [ ] 長文コメントのサンプル収集
- [ ] 並列処理アーキテクチャ設計

### 実装中の注意点
- **段階的実装**: 一度に複数機能を変更しない
- **テスト重視**: 新機能は必ずテストと共に実装
- **互換性維持**: 既存機能を破壊しない
- **ドキュメント更新**: 変更内容を適切に文書化

### 完了時の手順
- [ ] 該当Issueのクローズ
- [ ] マスターIssue (#6) の進捗更新
- [ ] パフォーマンス改善結果の測定・記録
- [ ] 次Phase準備状況の確認

## 🔗 クイックアクセスリンク

### GitHub Issues
- [#6 マスターIssue](https://github.com/yohi/github-coderabbit-comment-gettter/issues/6) - 全体管理・ロードマップ
- [#7 パフォーマンス改善](https://github.com/yohi/github-coderabbit-comment-gettter/issues/7) - 🔴最優先・並列処理
- [#8 エラーハンドリング](https://github.com/yohi/github-coderabbit-comment-gettter/issues/8) - 🔴緊急・信頼性
- [#9 長文コメント処理](https://github.com/yohi/github-coderabbit-comment-gettter/issues/9) - 🔴重要・要約機能
- [#10 設定管理統一](https://github.com/yohi/github-coderabbit-comment-gettter/issues/10) - 🟡高優先度
- [#11 テスト充実](https://github.com/yohi/github-coderabbit-comment-gettter/issues/11) - 🟡高優先度
- [#12 セキュリティ強化](https://github.com/yohi/github-coderabbit-comment-gettter/issues/12) - 🟡高優先度
- [#13 プラグイン機構](https://github.com/yohi/github-coderabbit-comment-gettter/issues/13) - 🟢中優先度
- [#14 Web UI開発](https://github.com/yohi/github-coderabbit-comment-gettter/issues/14) - 🟢中優先度

### 技術リソース
- **分析元PR**: https://github.com/yohi/terraform/pull/98
- **ツール実行**: `uv run grp --help`
- **テスト実行**: `uv run pytest src/github_review_prompts/tests/`

## 💡 成功指標

### Phase 1 目標
- **処理速度**: 100件コメント/5分以内
- **エラー耐性**: 50%エラー発生時でも処理続行
- **情報保持**: 重要情報の95%以上を要約に保持

### 測定方法
```bash
# パフォーマンステスト
time uv run grp --include-resolved --debug [大規模PR_URL]

# エラー耐性テスト
# 意図的にネットワークエラーを発生させて継続性確認

# 要約品質テスト
# 長文コメントの要約結果と元コメントの比較
```

## 🆘 トラブルシューティング

### よくある問題
1. **GITHUB_TOKEN未設定**: `export GITHUB_TOKEN="your_token"`
2. **レート制限**: 処理間隔の調整が必要
3. **メモリ不足**: 大量コメント処理時の段階的処理実装

### 緊急時の対応
1. マスターIssue (#6) にコメントで状況報告
2. 問題の詳細をIssueに記録
3. 必要に応じて新しいIssueを作成

---

**重要**: このリファレンスは改善プロジェクトの全体像を素早く把握するためのものです。
詳細な技術仕様や実装方針は各個別Issueを必ず確認してください。
