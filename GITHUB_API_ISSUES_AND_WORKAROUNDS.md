# GitHub API Issues and Workarounds

## 概要

GitHub Review Prompts AI Agent の開発中に発見された GitHub API の問題と対応策をまとめたドキュメント

## 発見された問題

### 1. GitHub GraphQL API の `isResolved` フィールドの不整合

#### 問題の詳細
- **事象**: GitHub GraphQL API の `reviewThreads` で `isResolved: true` と返されるコメントが、実際の Web UI では未解決として表示される
- **影響**: 技術的に重要なコメントが GRP 出力から除外され、AI エージェントプロンプトに含まれない
- **具体例**: PR #100 の `docs/automation/content-indexer.sh` に関するコメント（`#discussion_r2297225969` 等）

#### 検証結果
- **GitHub GraphQL API**: `isResolved: true`, `resolvedBy: { "login": "yohi" }`
- **Web UI (PlaywrightMCP検証)**: "Resolve conversation" ボタンが表示され、未解決状態
- **コメント内容**: 477行目のJSON配列生成バグなど技術的に重要な指摘

#### 推定原因
1. GitHub内部の状態管理とWeb UIの表示ロジックの不整合
2. APIの過剰な自動解決判定
3. 手動解決→再オープンされた状態のAPI同期遅延

### 2. GitHub REST API のコメントアクセス不整合

#### 問題の詳細
- **事象**: ページネーション経由では存在するコメントが、直接アクセスでは 404 エラー
- **具体例**: Comment ID `2297225969`
  - `GET /repos/yohi/rundeck/pulls/100/comments?page=X` では存在
  - `GET /repos/yohi/rundeck/pulls/100/comments/2297225969` では 404

## 実装した対応策

### 1. リプライベース判定アプローチ（v2.0 - 推奨）

```python
def _is_thread_truly_resolved(self, thread: Dict[str, Any], comments_data: Dict[str, Any]) -> bool:
    """リプライがないインラインコメントは未解決とする効率的アプローチ"""

    comments = comments_data.get("nodes", [])

    # コメントが存在しない場合は未解決として扱う
    if not comments:
        return False

    # 1つのコメントのみ（リプライなし）の場合は未解決
    if len(comments) == 1:
        return False

    # 複数コメント（リプライあり）の場合、明示的な解決確認をチェック
    for comment in comments:
        comment_body = comment.get("body", "")

        # CodeRabbit解決確認マーカー
        if re.search(r"\[CR_RESOLUTION_CONFIRMED.*?\[/CR_RESOLUTION_CONFIRMED\]",
                    comment_body, re.IGNORECASE | re.DOTALL):
            return True

        # 開発者による明示的な解決コメント
        resolved_keywords = [
            "Fixed", "Resolved", "Done", "Completed", "Applied",
            "修正済み", "対応済み", "完了", "適用済み", "解決済み"
        ]

        if any(keyword in comment_body for keyword in resolved_keywords):
            # 質問や議論の継続を示すパターンは除外
            discussion_patterns = [
                "?", "？", "How", "Why", "どう", "なぜ", "どのよう",
                "Should we", "するべき", "検討", "議論"
            ]

            if not any(pattern in comment_body for pattern in discussion_patterns):
                return True

    # リプライはあるが明示的な解決表明がない場合は未解決
    return False
```

### 2. 技術指摘保守的アプローチ（v1.0 - 廃止）

```python
# v1.0 - プロンプトサイズが大きくなりすぎるため廃止
def _is_thread_truly_resolved_v1(self, thread: Dict[str, Any], comments_data: Dict[str, Any]) -> bool:
    """技術的指摘を含むコメントは常に未解決として扱う（旧版）"""

    # 技術的指摘を含むコメントは常に未解決として扱う
    for comment in comments_data.get("nodes", []):
        comment_body = comment.get("body", "")
        technical_markers = [
            "⚠️ Potential issue", "🛠️ Refactor suggestion",
            "🧹 Nitpick", "💡 Codebase verification run"
        ]
        if any(marker in comment_body for marker in technical_markers):
            return False

    return False  # デフォルト未解決
```

## 解決判定アプローチの比較

### v2.0 - リプライベース判定（推奨）

#### 利点
- **プロンプトサイズ最適化**: 適切なサイズ（34件のTODO）
- **実用的判定**: 開発者の実際の対応状況を反映
- **効率的フィルタリング**: リプライがあるコメントは認識済みとして扱う
- **重要コメント保持**: 技術的に重要な問題は確実に含まれる

#### 判定ロジック
1. **リプライなし（単一コメント）**: → **未解決**
2. **リプライあり + 明示的解決**: → **解決済み**
3. **リプライあり + 議論継続**: → **未解決**

#### 実測結果（PR #100）
- **コメント総数**: 509件
- **生成TODO**: 34件（適切なサイズ）
- **content-indexer.sh**: 重要な技術指摘が正しく含まれる

### v1.0 - 技術指摘保守的アプローチ（廃止）

#### 問題点
- **プロンプトサイズ過大**: 技術指摘コメントが多すぎる場合
- **非効率**: 開発者が既に認識しているコメントも重複して含む
- **コンテキスト制限**: AI エージェントの処理能力を超える可能性

### 3. 設定オプション（将来的拡張）

```yaml
github:
  resolution_strategy: "reply_based"  # "api_trust" | "reply_based" | "technical_conservative"
  force_include_technical_comments: false  # v2.0ではfalse（効率性重視）
  reply_analysis:
    resolved_keywords:
      - "Fixed"
      - "Resolved"
      - "Done"
      - "修正済み"
      - "対応済み"
    discussion_patterns:
      - "?"
      - "How"
      - "Why"
      - "検討"
      - "議論"
```

## 検証方法

### 1. PlaywrightMCP による Web UI 検証
```bash
# 手順
1. GitHub にログイン
2. PR ページにアクセス
3. コメントの実際の表示状態を確認
4. "Resolve conversation" ボタンの有無を確認
```

### 2. API レスポンス比較
```bash
# GraphQL API
curl -X POST -H "Authorization: bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { repository(owner: \"yohi\", name: \"rundeck\") { pullRequest(number: 100) { reviewThreads(first: 100) { nodes { id isResolved resolvedBy { login } comments(first: 10) { nodes { id body } } } } } } }"}' \
  https://api.github.com/graphql

# REST API (ページネーション)
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/yohi/rundeck/pulls/100/comments?page=1&per_page=100"
```

## 今後の課題

### 1. 短期的対応
- [ ] 他のプロジェクトでも同様の問題が発生しないか検証
- [ ] 設定ファイルによる resolution_strategy の選択機能
- [ ] ログ出力の充実（API vs Web UI の状態差異検出）

### 2. 中期的対応
- [ ] GitHub Enterprise Server での検証
- [ ] 大規模 PR（1000+ コメント）での性能検証
- [ ] Web UI 状態の自動検証機能（PlaywrightMCP 統合）

### 3. 長期的対応
- [ ] GitHub API チームへの不整合報告
- [ ] 代替 API エンドポイントの調査
- [ ] リアルタイム状態同期の実装

## 関連リソース

- **GitHub GraphQL API Documentation**: https://docs.github.com/en/graphql
- **GitHub REST API Documentation**: https://docs.github.com/en/rest
- **PlaywrightMCP**: ブラウザ自動化による Web UI 検証
- **Issue Tracking**: 本プロジェクトの Issues で継続的に追跡

### 3. GitHub API間の不整合による重要コメント欠落（新発見）

#### 問題の詳細
- **事象**: GraphQL `reviewThreads` で取得できるコメントと、REST API `/comments` で取得できるコメントに差異
- **影響**: REST API でのみ確認できる重要な技術指摘コメントが GRP 出力から除外
- **具体例**: Comment ID `2297225971` (`docs/automation/content-indexer.sh:609`)
  - ✅ REST API: 正常に取得可能
  - ❌ GraphQL `reviewThreads`: 含まれない
  - ❌ Direct REST API: 404エラー

#### 検証結果
```
📊 各コメントソースでの状況:
- GraphQLレビュー: 386件 (対象コメント見つからず)
- Outside diff comments: 20件 (対象コメント見つからず)
- RESTレビューコメント（未解決のみ）: 0件 (フィルタリングで除外)
- RESTレビューコメント（全て）: ✅ 発見 (パス: docs/automation/content-indexer.sh:609)
```

#### 根本原因
`get_all_pr_comments()` で `unresolved_only=True` が設定されていたため、**ハイブリッドアプローチでは未解決と判定されるコメントが、古い解決済み判定ロジックで除外**されていた。

## 実装した対応策

### 4. ハイブリッドアプローチの実装（v3.0 - 最新）

#### 概要
GraphQL APIとREST APIの両方を活用して、コメント取得の完全性と解決済み判定の精度を両立する手法。

#### 実装詳細
```python
def get_comments_via_hybrid_approach(self, pr_info: GitHubPRInfo, page_size: int = 100) -> Tuple[Set[int], Dict[int, str]]:
    """ハイブリッドアプローチ: GraphQL + REST API補完でコメント取得"""

    # Step 1: GraphQL APIで解決済み判定付きコメント取得
    graphql_resolved_ids, graphql_comment_bodies = self.get_resolved_comments_via_graphql(pr_info, page_size)

    # Step 2: REST APIで全コメント取得（補完用）
    rest_all_comments = self._get_all_comments_via_rest(pr_info, page_size)

    # Step 3: 結果をマージ
    return self._merge_graphql_and_rest_results(
        graphql_resolved_ids, graphql_comment_bodies, rest_all_comments
    )

def _merge_graphql_and_rest_results(self, ...) -> Tuple[Set[int], Dict[int, str]]:
    """GraphQLとREST APIの結果をマージして完全性を確保"""

    # GraphQLで欠落したコメントをREST APIから補完
    missing_in_graphql = rest_comment_ids - graphql_comment_ids

    if missing_in_graphql:
        # 欠落コメントを補完（解決状況は保守的に未解決として扱う）
        for comment_id in missing_in_graphql:
            rest_comment = rest_all_comments[comment_id]
            merged_comment_bodies[comment_id] = rest_comment["body"]
```

#### 修正内容
```python
# 修正前: 古い解決済み判定ロジックで重要コメントが除外
review_comments = self.get_pr_review_comments(pr_info, page_size, unresolved_only=True)

# 修正後: ハイブリッドアプローチに統一、解決済み判定は一元化
review_comments = self.get_pr_review_comments(pr_info, page_size, unresolved_only=False)
```

#### 効果測定
- **修正前**: 413コメント (`docs/automation/content-indexer.sh` コメント欠落)
- **修正後**: 444コメント (`docs/automation/content-indexer.sh` **6件追加**)
- **改善率**: +31コメント (7.5%向上)

#### 成果
1. **完全性の向上**: GitHub API間の不整合に対する耐性
2. **重要コメント保護**: セキュリティ・品質指摘の取りこぼし防止
3. **統一的判定**: ハイブリッドアプローチによる一貫した解決済み判定

## 解決判定アプローチの比較

### v3.0 - ハイブリッドアプローチ + リプライベース判定（最新・推奨）

#### 実測結果（PR #100 最終版）
- **全コメント取得**: 924件（GraphQL + REST統合）
- **ハイブリッド解決済み判定**: 511件→480件解決済み
- **最終プロンプト出力**: 444件処理→64件TODO
- **重要技術指摘**: `docs/automation/content-indexer.sh` 6件含む

#### 技術的優位性
1. **API不整合への対応**: GraphQL欠落をREST APIで補完
2. **解決済み判定の精度**: リプライベース + CodeRabbitマーカー認識
3. **パフォーマンス**: 必要最小限のAPI呼び出し
4. **保守性**: 統一的なコメント処理フロー

## 今後の課題

### 1. 短期的対応
- [x] ハイブリッドアプローチ実装
- [x] `unresolved_only=True` 問題修正
- [x] 重要コメント取りこぼし解決
- [ ] 他プロジェクトでの動作検証
- [ ] REST API URL構築エラー修正

### 2. 中期的対応
- [ ] GitHub Enterprise Server での検証
- [ ] 大規模 PR（1000+ コメント）での性能検証
- [ ] ハイブリッドアプローチのログ充実
- [ ] 設定による戦略選択機能

## 更新履歴

- **2025-01-25**: 初版作成 - PR #100 での GraphQL API 不整合問題と対応策を記録
- **2025-01-25**: v2.0アップデート - リプライベース判定アプローチに変更、プロンプトサイズ最適化を実現
- **2025-01-25**: v3.0アップデート - ハイブリッドアプローチ実装、`unresolved_only=True`問題修正、重要コメント取りこぼし解決
