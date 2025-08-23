"""
統一プロンプトエンジン
全てのプロンプト生成ロジックを統合
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UnifiedPromptEngine:
    """統一プロンプト生成エンジン"""

    def __init__(self):
        # 新しいシンプル構造では動的生成を使用
        pass

    def generate_main_prompt(
        self,
        comments: List[Dict],
        pr_info: Dict,
        options: Dict = None,
        github_token: str = None,
    ) -> str:
        """メインプロンプトを生成（従来版ベース）"""
        if options is None:
            options = {}

        prompt_parts = []

        # 改善されたシンプルプロンプト
        prompt_parts.append(
            f"""# 🎯 CodeRabbitレビュー対応プロンプト

## 🔑 作業開始前の必須確認

**⚠️ 最重要**: 作業を開始する前に、以下を**必ず確認**してください：

### GITHUB_TOKEN環境変数の確認
```bash
echo $GITHUB_TOKEN
```
**期待する結果**: `ghp_` または `github_pat_` で始まるトークンが表示される

**❌ もしトークンが表示されない場合**:
```bash
# トークンを設定してください
export GITHUB_TOKEN="your_github_token_here"

# 設定確認
echo $GITHUB_TOKEN
```

**🚨 重要**: GITHUB_TOKENが設定されていない場合、コメント返信のcurlコマンドが動作しません。必ず設定を確認してから作業を開始してください。

## セキュリティ最優先原則

**🎯 ペルソナ: シニアセキュリティエンジニア**
あなたは経験豊富なシニアソフトウェアエンジニアとして、セキュリティファーストの視点で技術的判断を行ってください。

**専門性**: セキュリティ・コード品質・長期保守性を重視
**判断基準**: 保守的・安全第一・技術的根拠に基づく説明

1. **認証情報保護**: `$GITHUB_TOKEN` 環境変数のみ使用（ハードコード禁止）
2. **変更範囲限定**: 関連ファイルのみ修正（`git add .` 禁止）
3. **トークン検証**: 作業前に必ず `echo $GITHUB_TOKEN` で設定確認

## 優先度判定（3段階）
🔴 **緊急**: セキュリティ・機能破綻
🟡 **重要**: 機能改善・リファクタリング
🟢 **低優先**: スタイル・軽微改善

## 🚨 段階的実行戦略（大量コメント対応）

**⚠️ 重要**: 大量コメント（20件以上）の場合、以下の段階的アプローチを採用してください。

### Phase 1: 🔴緊急対応（最優先30-60分）
**対象**: セキュリティ・システム破綻リスク
**件数制限**: 最大15件
**実行方針**: 即座対応・品質最優先・完璧実行
**成功基準**: 🔴項目100%完了

### Phase 2: 🟡重要対応（2-3時間以内）
**対象**: 機能改善・品質向上
**件数制限**: 20-30件
**実行方針**: 効率重視・バッチ処理
**成功基準**: 🟡項目80%以上完了

### Phase 3: 🟢低優先対応（時間があれば）
**対象**: ドキュメント・スタイル改善
**実行判断**: 残り時間・エネルギーに応じて
**成功基準**: 🟢項目50%以上完了（努力目標）

## 作業フロー（改良版）
0. **🔑 環境確認**: `echo $GITHUB_TOKEN` でトークン設定確認（必須）
1. **🔍 事前分析**: 全コメントを🔴🟡🟢で完全分類
2. **⚡ Phase 1実行**: 🔴緊急項目のみ集中対応
3. **🛡️ 中間検証**: Git中間コミット・休憩
4. **🎯 Phase 2実行**: 🟡重要項目の効率対応
5. **🔄 段階確認**: 解決済みマーク・返信状況確認
6. **💡 Phase 3判断**: 時間・エネルギー評価後に🟢対応
7. **📋 最終報告**: 実行サマリー・未完了項目明記

## 判断基準とアクション
| 判断 | アクション | 返信要否 | 解決済みマーク | メモリ指示 |
|------|------------|----------|----------------|------------|
| ✅ 実施 | 修正実行 | 不要 | 自動処理 | 不要 |
| ❌ 対応不要 | 技術的根拠で拒否 | **必須** | **CodeRabbitに依頼** | 不要 |
| ⏳ 将来対応 | TODOコメント追加 | **必須** | **CodeRabbitに依頼** | **記憶依頼** |
| 🤔 要確認 | 詳細確認要求 | **必須** | 確認完了後 | 不要 |

## 返信テンプレート
**❌ 対応不要**: `@coderabbitai [技術的根拠]により対応不要と判断します。技術的に妥当であれば、この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。他のコメントには影響しないでください。`

**⏳ 将来対応**: `@coderabbitai 妥当な指摘ですが[現フェーズ]では対応しません。[将来フェーズ]で対応予定です。この課題を将来のタスクとして記憶し、[将来フェーズ]開始時に再度指摘してください。適切と判断される場合は、この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。`

**🤔 要確認**: `@coderabbitai [確認内容]について詳細説明をお願いします。`

## 📝 将来対応メモリ管理

**CodeRabbitメモリ指示の重要性：**
- 将来フェーズでのタスク忘れ防止
- 継続的な品質向上の実現
- 技術的負債の蓄積防止
- プロジェクト進行に応じた最適なタイミングでの対応

**メモリ指示テンプレート：**
```
@coderabbitai この指摘は技術的に妥当ですが、現在の[現フェーズ名]では対応しません。
理由: [対応しない理由]
予定: [将来フェーズ名]で対応予定
依頼: この課題を将来のタスクとして記憶し、[将来フェーズ名]開始時または
      関連する改修時に再度指摘してください。
      この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。
```

**記録すべき情報：**
- 課題の具体的内容
- 対応しない理由
- 予定対応フェーズ
- 関連するファイル・機能
- 優先度レベル

**実用例1: リファクタリング延期**
```
@coderabbitai この指摘は技術的に妥当ですが、現在のMVP開発フェーズでは対応しません。
理由: 機能実装を優先し、リファクタリングは後回し
予定: Phase2（品質改善フェーズ）で対応予定
依頼: この課題を将来のタスクとして記憶し、Phase2開始時または
      当該ファイルの次回修正時に再度指摘してください。
      この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。
```

**実用例2: パフォーマンス最適化延期**
```
@coderabbitai この指摘は技術的に妥当ですが、現在のプロトタイプ段階では対応しません。
理由: 機能検証が優先、パフォーマンス最適化は本格運用前に実施
予定: Phase3（本格運用準備フェーズ）で対応予定
依頼: この課題を将来のタスクとして記憶し、Phase3開始時に再度指摘してください。
      この特定のコメントスレッドのみを解決済み（resolved）にマークしてください。
```

## 📌 重要な解決済みマーク指示

**CodeRabbitに解決済み依頼する場合の注意点：**
- 「この特定のコメントスレッドのみ」を明記
- 他のコメントに影響しないよう強調
- 技術的判断の根拠を具体的に説明
- 間違った指摘であることを明確に伝える

**例文：**
```
@coderabbitai この指摘はXXXの理由により技術的に不適切です。
[具体的な技術的根拠]
妥当と判断される場合は、この特定のコメントスレッドのみを
解決済み（resolved）にマークしてください。
```

**重要**: エンジニアとしての技術的判断を最優先し、疑問がある場合はCodeRabbitに返信で確認してください。"""
        )

        # 返信方法の追加
        curl_instruction = self._generate_curl_section(pr_info, github_token)
        prompt_parts.append(curl_instruction)

        # 検証チェックリストセクション
        prompt_parts.append(
            """
## 🔍 最終検証チェックリスト（強化版）

### ✅ 環境設定検証（最優先）
- [ ] **GITHUB_TOKEN確認**: `echo $GITHUB_TOKEN` でトークン表示確認
- [ ] **トークン形式確認**: `ghp_` または `github_pat_` で始まることを確認
- [ ] **権限確認**: `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user` で認証テスト

### ✅ 修正作業検証
- [ ] 構文チェック: `python -m py_compile <ファイル名>`
- [ ] Lintチェック: `ruff check <ファイル名>`
- [ ] トークン漏洩チェック: `grep -r "github_pat\\|ghp_" src/`
- [ ] 機能テスト実行

### ✅ 返信作業検証
- [ ] ❌対応不要: 返信送信完了
- [ ] ⏳将来対応: 返信+メモリ依頼完了
- [ ] 🤔要確認: 返信送信完了
- [ ] 解決済みマーク依頼: 適切な項目に実施

### ✅ Git作業検証
- [ ] `git status` 確認済み
- [ ] `git add <ファイル名>` 実行済み（関連ファイルのみ）
- [ ] `git commit -m "CodeRabbitレビューコメント対応"` 実行済み
- [ ] `git push` 実行済み

### ✅ 報告作業検証
- [ ] 作業サマリー出力済み
- [ ] 未完了項目明記済み
- [ ] 次回推奨事項記載済み
- [ ] 完了確認チェック実施済み

**🎯 全チェック完了時のみ作業終了宣言可能**

## Git操作方針
**手動確認推奨**: 作業完了後、以下を**段階的に実行**
1. `git status` で変更確認
2. `git add <ファイル名>` で関連ファイルのみ追加
3. `git commit -m "CodeRabbitレビューコメント対応"`
4. 内容確認後 `git push`

## 🎯 作業完了必須プロセス

**⚠️ 重要**: 全てのレビューコメント対応完了後、以下を**必ず実行**してください。

### Phase 0: 環境設定最終確認（必須）
- [ ] **GITHUB_TOKEN設定確認**: `echo $GITHUB_TOKEN` 実行
- [ ] **トークン有効性確認**: `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user` 実行
- [ ] **API権限確認**: レスポンスで認証成功を確認

### Phase 1: 最終検証（必須）
- [ ] 全TODOの処理状況確認
- [ ] 修正ファイルのテスト実行
- [ ] トークン漏洩最終チェック
- [ ] 構文エラー0件確認

### Phase 2: Git操作（必須）
- [ ] `git status` で変更ファイル確認
- [ ] 関連ファイルのみ個別add: `git add <ファイル名>`
- [ ] コミット実行: `git commit -m "CodeRabbitレビューコメント対応"`
- [ ] プッシュ実行: `git push`

### Phase 3: コメント返信（必須）
- [ ] ❌対応不要の返信完了確認
- [ ] ⏳将来対応の返信完了確認
- [ ] 🤔要確認の返信完了確認
- [ ] 解決済みマーク依頼確認

### Phase 4: 結果報告出力（必須）
- [ ] 作業サマリー生成
- [ ] 未完了項目の明記
- [ ] 次回作業推奨事項

## 🛡️ リスク軽減・エラー防止システム

### 作業開始前の安全準備
- [ ] **バックアップブランチ作成**: `git checkout -b backup-$(date +%Y%m%d-%H%M)`
- [ ] **現在の状態保存**: `git stash push -m "作業開始前の状態"`
- [ ] **作業時間制限設定**: Phase毎のタイムボックス設定

### 段階的セーフポイント
- [ ] **Phase 1完了時**: `git add . && git commit -m "Phase1: 緊急対応完了"`
- [ ] **Phase 2完了時**: `git add . && git commit -m "Phase2: 重要対応完了"`
- [ ] **2時間経過時**: 強制休憩（15分以上）

### エラー回復手順
**問題発生時の復旧方法**:
1. **軽微なエラー**: `git checkout HEAD -- <ファイル名>` で個別復旧
2. **重大なエラー**: `git reset --hard HEAD` で最後のコミットに復旧
3. **完全リセット**: `git checkout backup-*` でバックアップブランチに切り替え

## 🎯 現実的成功基準（完璧主義の緩和）

### 段階的成功定義
- **Phase 1成功**: 🔴緊急項目90%以上完了
- **Phase 2成功**: 🟡重要項目70%以上完了
- **Phase 3成功**: 🟢低優先項目30%以上完了
- **全体成功**: Phase 1成功 + Phase 2一部完了

### 部分完了の容認
- **80%ルール**: 完璧主義より実用性を優先
- **未完了項目の引き継ぎ**: 明確な残作業リスト作成
- **時間切れ対応**: 優雅な終了・次回継続計画

## 🚨 忘れ防止システム（改良版）

### 段階的リマインダー
- **Phase開始時**: 「制限時間X分・対象X件」を表示
- **Phase完了時**: 「中間コミット・休憩」を指示
- **時間切れ前**: 「残り10分・優雅な終了準備」を表示

### 柔軟な完了判定
**必須条件**: Phase 1完了 + 中間コミット
**推奨条件**: Phase 2部分完了 + 返信実行
**理想条件**: 全Phase完了 + 完全報告

### 自己チェック質問（現実版）
作業終了前に以下を自問：
- [ ] 「🔴緊急項目は完了しましたか？」
- [ ] 「中間コミットは実行しましたか？」
- [ ] 「必要な返信を送信しましたか？」
- [ ] 「未完了項目を明記しましたか？」

**🔴項目完了なら成功・他は努力目標**"""
        )

        # 結果報告テンプレート
        prompt_parts.append(
            """

## 📊 段階的結果報告テンプレート（現実版）

**各Phase完了後および最終作業完了後に報告してください：**

---
# 🎯 CodeRabbitレビューコメント段階的対応報告

## 📈 作業サマリー
**対応期間**: [開始時刻] ～ [現在時刻]
**総作業時間**: X時間Y分
**総コメント数**: X件（🔴:Y件、🟡:Z件、🟢:W件）
**実行Phase**: Phase 1/2/3 完了
**全体進捗**: X%（現実的目標達成度）

### 📊 実行状況概要
- **修正実行**: X件（コード変更・ファイル修正）
- **コメント返答**: Y件（curl実行・CodeRabbit返信）
- **Git操作**: Z件のコミット + W回のプッシュ
- **未完了**: V件（🔴:A件、🟡:B件、🟢:C件）

### 🎯 作業完了判定
**作業状態**: ✅完全完了 / 🔄作業継続中 / ⏸️一時中断 / ❌中断・要再開
- **完全完了**: 全TODO対応 + 全返信完了 + Git操作完了
- **作業継続中**: 一部未完了だが作業継続予定
- **一時中断**: 技術的課題等で一時停止・近日再開予定
- **中断・要再開**: 重大な問題で中断・要調査・再開時期未定

## 🔧 Phase別実施状況

### 🔴 Phase 1: 緊急対応（必須）
**対象**: X件 → **完了**: Y件 → **成功率**: Z%
- [ ] TODO #X: [概要] → ✅完了/❌未完了/⏳次回継続
- [ ] [重要なセキュリティ修正のみ列挙]

### 🟡 Phase 2: 重要対応（推奨）
**対象**: X件 → **完了**: Y件 → **成功率**: Z%
- [ ] TODO #X: [概要] → ✅完了/❌未完了/⏳次回継続
- [ ] [主要な機能修正のみ列挙]

### 🟢 Phase 3: 低優先対応（努力目標）
**対象**: X件 → **完了**: Y件 → **成功率**: Z%
- [ ] 実行判断: ✅実行/❌時間不足/⏳次回対応

## ⚡ Git操作実行状況（詳細）

### 📝 実行されたGit操作
**⚠️ 重要**: 実行したGit操作を以下のフォーマットで必ず記録してください

#### コミット実行状況
- [ ] **Phase 1コミット**: ✅完了/❌未実行
  - **実行した場合**: コミットハッシュ: `git log --oneline -1` の結果を記載
  - **コミットメッセージ**: [実際のメッセージ]
  - **変更ファイル数**: X件

- [ ] **Phase 2コミット**: ✅完了/❌未実行
  - **実行した場合**: コミットハッシュ: `git log --oneline -1` の結果を記載
  - **コミットメッセージ**: [実際のメッセージ]
  - **変更ファイル数**: X件

- [ ] **最終コミット**: ✅完了/❌未実行
  - **実行した場合**: コミットハッシュ: `git log --oneline -1` の結果を記載
  - **コミットメッセージ**: [実際のメッセージ]
  - **変更ファイル数**: X件

#### プッシュ実行状況
- [ ] **リモートプッシュ**: ✅完了/❌未実行
  - **実行した場合**: `git push` 実行済み
  - **プッシュ先**: origin/[ブランチ名]
  - **プッシュしたコミット数**: X件

#### バックアップ・安全対策
- [ ] **バックアップブランチ作成**: ✅完了/❌未実行
  - **作成した場合**: ブランチ名: backup-YYYYMMDD-HHMM
- [ ] **作業前stash**: ✅実行/❌未実行

### 🔍 Git状態確認コマンド
**作業完了後に以下を実行して結果を記載**:
```bash
# 最新コミット確認
git log --oneline -3

# 現在のブランチ・状態確認
git status --porcelain

# リモートとの差分確認
git log --oneline origin/[ブランチ名]..HEAD
```

## 💬 コメント返答実行状況（詳細）

### 📊 返答実行サマリー
**総返答件数**: X件 / 全コメント数Y件 → **返答率**: Z%

#### 優先度別返答状況
- [ ] **🔴緊急コメント返答**: X件対象 → Y件完了 → **完了率**: Z%
  - ✅実施判断: X件（修正実行のため返答不要）
  - ❌対応不要: X件（技術的根拠で拒否・返答済み）
  - ⏳将来対応: X件（メモリ依頼・返答済み）
  - 🤔要確認: X件（詳細確認要求・返答済み）

- [ ] **🟡重要コメント返答**: X件対象 → Y件完了 → **完了率**: Z%
  - ✅実施判断: X件（修正実行のため返答不要）
  - ❌対応不要: X件（技術的根拠で拒否・返答済み）
  - ⏳将来対応: X件（メモリ依頼・返答済み）
  - 🤔要確認: X件（詳細確認要求・返答済み）

- [ ] **🟢低優先コメント返答**: X件対象 → Y件完了 → **完了率**: Z%
  - ✅実施判断: X件（修正実行のため返答不要）
  - ❌対応不要: X件（技術的根拠で拒否・返答済み）
  - ⏳将来対応: X件（メモリ依頼・返答済み）
  - 🤔要確認: X件（詳細確認要求・返答済み）

### 🔗 実行したcurlコマンド記録
**⚠️ 重要**: 実際に実行したcurlコマンドの件数を記録

#### 返答送信実行状況
- [ ] **❌対応不要返信**: X件実行
  - 実行例: `curl -X POST ... -d '{"body": "@coderabbitai 技術的根拠により対応不要...", "in_reply_to": 12345}'`
  - 成功: X件 / 失敗: Y件

- [ ] **⏳将来対応返信**: X件実行
  - 実行例: `curl -X POST ... -d '{"body": "@coderabbitai 妥当な指摘ですが現フェーズでは...", "in_reply_to": 12345}'`
  - 成功: X件 / 失敗: Y件

- [ ] **🤔要確認返信**: X件実行
  - 実行例: `curl -X POST ... -d '{"body": "@coderabbitai 詳細説明をお願いします...", "in_reply_to": 12345}'`
  - 成功: X件 / 失敗: Y件

#### 解決済みマーク依頼状況
- [ ] **解決済み依頼**: X件実行
  - CodeRabbitに解決済みマークを依頼したコメント数
  - 依頼理由: 技術的に不適切な指摘 / 対応完了

## 🎯 成功判定（現実基準）
- [ ] **必須条件**: 🔴緊急項目90%以上完了 → ✅達成/❌未達成
- [ ] **推奨条件**: 🟡重要項目70%以上完了 → ✅達成/❌未達成
- [ ] **理想条件**: 🟢低優先項目30%以上完了 → ✅達成/❌未達成

**総合判定**: ✅成功/△部分成功/❌要再実行

## ⚠️ 残対応状況・継続作業計画（詳細）

### 📊 作業完了状況サマリー
**作業状態**: ✅完全完了 / 🔄作業継続中 / ⏸️一時中断 / ❌未着手

#### 完了判定
- [ ] **全Phase完了**: ✅完了 / 🔄継続中
- [ ] **必須項目完了**: ✅完了 / 🔄継続中
- [ ] **返信完了**: ✅完了 / 🔄継続中
- [ ] **Git操作完了**: ✅完了 / 🔄継続中

### 🔴 緊急項目未完了（最優先継続）
**残件数**: X件 / 対象Y件 → **未完了率**: Z%

#### 具体的未完了項目
- [ ] **TODO #X**: [コメント概要]
  - **未完了理由**: [技術的制約/時間不足/情報不足/その他]
  - **必要な対応**: [具体的な作業内容]
  - **推定作業時間**: X分
  - **次回優先度**: 🔴最優先/🟡高/🟢中/⚪低

- [ ] **TODO #Y**: [コメント概要]
  - **未完了理由**: [理由]
  - **必要な対応**: [作業内容]
  - **推定作業時間**: X分
  - **次回優先度**: 🔴最優先/🟡高/🟢中/⚪低

### 🟡 重要項目未完了（推奨継続）
**残件数**: X件 / 対象Y件 → **未完了率**: Z%

#### 代表的未完了項目（上位5件）
- [ ] **TODO #X**: [概要] → 推定X分 → 🟡高優先度
- [ ] **TODO #Y**: [概要] → 推定X分 → 🟢中優先度
- [ ] **TODO #Z**: [概要] → 推定X分 → 🟢中優先度

### 🟢 低優先項目未完了（時間があれば）
**残件数**: X件 / 対象Y件 → **未完了率**: Z%
**対応判断**: ✅次回対応 / ❌スキップ / ⏳将来検討

### 🔧 技術的課題・制約事項
#### 解決が必要な技術課題
- [ ] **課題1**: [課題内容]
  - **制約要因**: [技術的制約/環境制約/知識不足]
  - **解決方法**: [具体的な解決アプローチ]
  - **必要リソース**: [時間/ツール/情報]

- [ ] **課題2**: [課題内容]
  - **制約要因**: [制約要因]
  - **解決方法**: [解決アプローチ]
  - **必要リソース**: [リソース]

### 📅 次回作業計画
#### 継続作業の優先順位
1. **🔴緊急未完了**: X件 → 推定X時間
2. **🟡重要未完了**: Y件 → 推定Y時間
3. **技術課題解決**: Z件 → 推定Z時間
4. **🟢低優先対応**: W件 → 推定W時間

#### 推奨次回作業開始時期
- **即座継続**: 🔴緊急項目が残っている場合
- **1-2日以内**: 🟡重要項目のみ残っている場合
- **1週間以内**: 🟢低優先項目のみ残っている場合
- **適宜対応**: 技術課題解決後

### ⚠️ 継続作業時の注意事項
- [ ] **環境設定**: GITHUB_TOKEN再確認必須
- [ ] **ブランチ状態**: 作業ブランチの最新化
- [ ] **前回作業**: 前回のコミット・プッシュ状況確認
- [ ] **優先順位**: 🔴緊急項目から必ず開始

## 📋 時間・エネルギー管理
**作業時間**: X時間Y分
**休憩回数**: X回
**エネルギーレベル**: 高/中/低
**次回推奨開始時期**: [推奨日時]

## 🏆 達成成果
**✅ 完了した重要修正**:
1. [最重要な成果1]
2. [最重要な成果2]
3. [最重要な成果3]

**📈 改善された品質指標**:
- セキュリティリスク: X件解消
- 機能問題: X件修正
- コード品質: X%向上

**✅ 作業完了**: [完了日時] - **Phase X まで完了**

---"""
        )

        # 重要な注意事項
        prompt_parts.append(
            """

**重要**: CodeRabbitのコメントは必ずしも正しくないことがあります。エンジニアとしての技術的判断を最優先し、疑問がある場合は遠慮なく返信で確認してください。

---"""
        )

        # コメント処理
        if comments:
            # セキュリティ関連コメントの自動検出
            security_keywords = [
                "token",
                "credential",
                "secret",
                "github_pat",
                "ghp_",
                "authorization",
                "bearer",
            ]
            security_count = sum(
                1
                for comment in comments
                if any(
                    keyword.lower() in comment.get("body", "").lower()
                    for keyword in security_keywords
                )
            )

            # ドキュメント関連の低優先コメント検出
            doc_keywords = ["readme", "md051", "markdown", "anchor", "documentation"]
            doc_count = sum(
                1
                for comment in comments
                if any(
                    keyword.lower() in comment.get("body", "").lower()
                    for keyword in doc_keywords
                )
            )

            other_count = len(comments) - security_count - doc_count
            security_percentage = (
                int((security_count / len(comments)) * 100) if comments else 0
            )

            prompt_parts.append(
                f"""
## 🚨 レビューコメント分析（{len(comments)}件）- {security_percentage}%がセキュリティ関連

### 🔴 緊急（セキュリティ・機能破綻）- {security_count}件
**即座対応必須**: トークン漏洩リスク、システム破綻要因

### 🟡 重要（機能改善・品質向上）- {other_count}件
**PR内対応**: 機能改善、リファクタリング、品質向上

### 🟢 低優先（スタイル・軽微改善）- {doc_count}件
**余裕があれば**: ドキュメント修正、スタイル改善

### ⚡ 推奨対応順序
1. **🔴 セキュリティ関連**: トークン埋め込み・漏洩の完全除去（最優先）
2. **🔴 その他緊急**: システム破綻リスクの修正
3. **🟡 品質改善**: 機能・コード品質の向上
4. **🟢 軽微修正**: ドキュメント・スタイル改善

**🚨 重要**: {security_percentage}%がセキュリティ関連の緊急案件です。トークン漏洩リスクが高いため、🔴項目の完全解決を最優先してください。

### 🔍 根本原因分析
- **設計問題**: トークン値を直接文字列生成に使用
- **移行不完全**: 環境変数参照への移行が部分的
- **整合性不備**: テストコードとの整合性問題

---
## 🔍 対象コメント一覧
"""
            )

            for i, comment in enumerate(comments, 1):
                # セキュリティ関連かどうかの自動判定
                is_security = any(
                    keyword.lower() in comment.get("body", "").lower()
                    for keyword in security_keywords
                )

                # ドキュメント関連の低優先判定
                doc_keywords = [
                    "readme",
                    "md051",
                    "markdown",
                    "anchor",
                    "documentation",
                ]
                is_doc_low_priority = any(
                    keyword.lower() in comment.get("body", "").lower()
                    for keyword in doc_keywords
                )

                if is_security:
                    classification = "🔴緊急"
                elif is_doc_low_priority:
                    classification = "🟢低優先"
                else:
                    classification = "[🔴緊急/🟡重要/🟢低優先] ← 内容確認して分類"

                prompt_parts.append(
                    f"""
### TODO #{i}: {self._extract_comment_title(comment)}
**分類**: {classification}

{self._format_single_comment(comment, pr_info, github_token)}

---"""
                )

        return "\n".join(prompt_parts)

    def _format_single_comment(
        self, comment: Dict, pr_info: Dict, github_token: str = None
    ) -> str:
        """構造化された単一コメントのフォーマット"""
        # 基本情報抽出
        comment_id = comment.get("id", "unknown")
        author = comment.get("user", {}).get("login", "Unknown")
        created_at = comment.get("created_at", "Unknown")
        file_path = comment.get("path", "Unknown")
        line_number = comment.get("line") or comment.get("original_line", "Unknown")
        body = comment.get("body", "")

        # 自動分類とメタデータ生成
        classification_data = self._analyze_comment(body, file_path)

        # 完全機械化YAMLメタデータ
        security_risk = classification_data["issue_type"] == "security"
        yaml_data = f"""```yaml
id: {comment_id}
priority: {classification_data['classification_emoji']} {classification_data['severity']}
type: {classification_data['issue_type']}
file: {file_path}:{line_number}
author: {author}
created_at: {created_at}
auto_decision: {classification_data['auto_decision']}
security_risk: {str(security_risk).lower()}
```"""

        # パターンベース最適化フォーマット
        optimized_content = self._optimize_comment_format(body)

        parts = [
            yaml_data,
            "",
            optimized_content,
            "",
            "**🎯 最終判断**: [ ] ✅実施 [ ] ❌対応不要 [ ] ⏳将来対応 [ ] 🤔要確認",
        ]

        return "\n".join(parts)

    def _analyze_comment(self, body: str, file_path: str) -> Dict[str, str]:
        """コメントの自動分析・分類"""
        body_lower = body.lower()

        # 分類・重要度マッピングルール
        classification_rules = {
            "security": {"emoji": "🔴", "priority": 1, "auto_decision": "✅実施"},
            "functionality": {"emoji": "🔴", "priority": 2, "auto_decision": "✅実施"},
            "performance": {"emoji": "🟡", "priority": 3, "auto_decision": "✅実施"},
            "maintainability": {
                "emoji": "🟡",
                "priority": 4,
                "auto_decision": "🤔要確認",
            },
            "style": {"emoji": "🟢", "priority": 5, "auto_decision": "⏳将来対応"},
            "documentation": {
                "emoji": "🟢",
                "priority": 6,
                "auto_decision": "⏳将来対応",
            },
        }

        # セキュリティ関連判定
        security_keywords = [
            "token",
            "credential",
            "secret",
            "github_pat",
            "ghp_",
            "authorization",
            "bearer",
            "security",
            "漏洩",
            "vulnerability",
        ]
        if any(keyword in body_lower for keyword in security_keywords):
            return {
                "classification": "urgent",
                "classification_emoji": "🔴",
                "issue_type": "security",
                "severity": "critical",
                "auto_decision": "✅実施",
                "title": self._extract_title(body),
                "tools_detected": self._extract_tools(body),
            }

        # ドキュメント関連判定
        if file_path.endswith(".md") or any(
            keyword in body_lower
            for keyword in ["readme", "md051", "markdown", "anchor", "documentation"]
        ):
            return {
                "classification": "low_priority",
                "classification_emoji": "🟢",
                "issue_type": "documentation",
                "severity": "low",
                "auto_decision": "⏳将来対応",
                "title": self._extract_title(body),
                "tools_detected": self._extract_tools(body),
            }

        # 機能・品質関連（デフォルト）
        return {
            "classification": "important",
            "classification_emoji": "🟡",
            "issue_type": "functionality",
            "severity": "medium",
            "auto_decision": "🤔要確認",
            "title": self._extract_title(body),
            "tools_detected": self._extract_tools(body),
        }

    def _extract_title(self, body: str) -> str:
        """コメントからタイトルを抽出"""
        lines = body.split("\n")
        first_line = lines[0].strip()

        # ## や ** などのマークダウン記号を除去
        clean_line = (
            first_line.replace("**", "").replace("##", "").replace("*", "").strip()
        )

        # 50文字でカット
        if len(clean_line) > 50:
            return clean_line[:47] + "..."
        return clean_line or "レビューコメント"

    def _extract_tools(self, body: str) -> str:
        """コメントからツール検出情報を抽出"""
        tools = []

        # 一般的なツール
        tool_patterns = [
            "markdownlint",
            "eslint",
            "pylint",
            "ruff",
            "black",
            "mypy",
            "tsc",
            "prettier",
        ]
        for tool in tool_patterns:
            if tool.lower() in body.lower():
                tools.append(tool)

        # MD051 など特定のルール
        if "md051" in body.lower():
            tools.append("MD051")

        return str(tools) if tools else "[]"

    def _optimize_comment_format(self, body: str) -> str:
        """GitHubコメントをパターンベースで最適化"""
        import re

        # パターン1: 問題説明 + diffブロック
        problem_diff = self._extract_problem_and_diff(body)
        if problem_diff:
            return self._format_problem_diff_pattern(problem_diff)

        # パターン2: 複数ファイル指摘
        file_list = self._extract_file_list_pattern(body)
        if file_list:
            return self._format_file_list_pattern(file_list)

        # パターン3: 検証スクリプト提供
        script_pattern = self._extract_script_pattern(body)
        if script_pattern:
            return self._format_script_pattern(script_pattern)

        # フォールバック: 未知パターンは要点抽出
        return self._format_fallback_pattern(body)

    def _extract_problem_and_diff(self, body: str) -> dict:
        """問題説明とdiffブロックを抽出（改善版）"""
        import re

        # より正確な問題説明抽出
        problem = self._extract_clear_problem(body)

        # 重複diff除去付きの抽出
        diff_blocks = self._extract_unique_diffs(body)

        if problem and diff_blocks:
            return {"problem": problem, "diffs": diff_blocks}
        return None

    def _extract_file_list_pattern(self, body: str) -> dict:
        """複数ファイル指摘パターンを抽出（修正版）"""
        import re

        # より正確なファイル情報抽出
        file_info = self._extract_structured_files(body)

        if len(file_info["files"]) >= 2:  # 複数ファイル
            problem = self._extract_clear_problem(body)
            concrete_actions = self._extract_concrete_actions(body)

            return {
                "problem": problem,
                "files": file_info,  # 構造化ファイル情報全体を渡す
                "actions": concrete_actions,
            }
        return None

    def _extract_script_pattern(self, body: str) -> dict:
        """検証スクリプトパターンを抽出"""
        import re

        # shellスクリプトブロック
        script_blocks = re.findall(r"```(?:shell|bash)\n(.*?)\n```", body, re.DOTALL)

        if script_blocks:
            problem_desc = body.split("\n")[0].strip()
            return {"problem": problem_desc, "scripts": script_blocks}
        return None

    def _extract_solution_method(self, body: str) -> str:
        """修正方法を抽出"""
        lines = body.split("\n")
        for line in lines:
            if any(
                keyword in line.lower()
                for keyword in ["対応:", "修正:", "fix:", "solution:"]
            ):
                return line.strip()
        return "詳細は原文参照"

    def _format_problem_diff_pattern(self, data: dict) -> str:
        """問題+diff パターンの整形（完全版）"""

        # 重複除去済みのdiffを表示
        diff_blocks = data.get("diffs", [])

        if diff_blocks:
            # 最も適切なdiffを1つ選択（最初の有効なもの）
            best_diff = None
            for diff in diff_blocks:
                if diff and len(diff.strip()) > 10:
                    best_diff = diff
                    break

            if best_diff:
                diff_text = f"```diff\n{best_diff}\n```"
            else:
                diff_text = "（修正案は原文参照）"
        else:
            diff_text = "（修正案は原文参照）"

        return f"""**問題**: {data['problem']}

**修正案**:
{diff_text}"""

    def _format_file_list_pattern(self, data: dict) -> str:
        """ファイルリスト パターンの整形（完全改善版）"""

        # 統一されたファイル情報を使用
        files_info = data.get("files", {}).get("files", [])
        actions = data.get("actions", [])

        result_parts = []

        # 問題説明
        problem = data.get("problem", "修正が必要な問題")
        result_parts.append(f"**問題**: {problem}")

        # 統一されたファイルリスト
        if files_info:
            file_lines = []
            for file_info in files_info:
                path = file_info.get("path", "")
                lines = file_info.get("lines", "")
                description = file_info.get("description", "")

                if path:
                    line_part = f" (L{lines})" if lines else ""
                    desc_part = f": {description}" if description else ""
                    file_lines.append(f"- `{path}`{line_part}{desc_part}")

            if file_lines:
                result_parts.append(f"**対象ファイル**:\n" + "\n".join(file_lines))

        # 具体的な修正アクション
        if actions:
            action_lines = []
            for i, action in enumerate(actions, 1):
                if action and len(action.strip()) > 5:
                    action_lines.append(f"{i}. {action.strip()}")

            if action_lines:
                result_parts.append(f"**修正アクション**:\n" + "\n".join(action_lines))

        return "\n\n".join(result_parts)

    def _format_script_pattern(self, data: dict) -> str:
        """スクリプト パターンの整形"""
        script_text = "\n".join(
            f"```shell\n{script}\n```" for script in data["scripts"]
        )

        return f"""**問題**: {data['problem']}

**検証スクリプト**:
{script_text}"""

    def _format_fallback_pattern(self, body: str) -> str:
        """フォールバック: 要点抽出"""
        lines = body.split("\n")
        important_lines = []

        # HTMLタグや詳細セクションを除外
        skip_patterns = [
            "<details>",
            "<summary>",
            "<!-- ",
            "_💡 Verification agent_",
            "_🧩 Analysis chain_",
        ]
        in_details = False

        for line in lines[:10]:  # 最初の10行のみ
            line = line.strip()

            if "<details>" in line:
                in_details = True
                continue
            if "</details>" in line:
                in_details = False
                continue
            if in_details:
                continue

            if line and not any(pattern in line for pattern in skip_patterns):
                # マークダウン記号を除去
                clean_line = (
                    line.replace("**", "").replace("*", "").replace("_", "").strip()
                )
                if clean_line and len(clean_line) > 10:
                    important_lines.append(clean_line)

                if len(important_lines) >= 3:  # 最大3行
                    break

        summary = (
            "\n".join(important_lines) if important_lines else "詳細は技術的検証が必要"
        )

        return f"""**要点**:
{summary}

**注意**: 複雑なコメントのため、原文確認推奨"""

    def _extract_clear_problem(self, body: str) -> str:
        """明確な問題説明を抽出（改良版）"""
        import re

        # パターン1: **で囲まれた主要な問題説明
        main_problems = re.findall(r"\*\*(.*?)\*\*", body, re.DOTALL)

        for problem in main_problems:
            problem = problem.strip()
            # より具体的なキーワードチェック
            important_keywords = [
                "が不正",
                "重大",
                "セキュリティ",
                "リスク",
                "漏洩",
                "埋め込み",
                "トークン",
                "統一",
                "修正",
            ]
            if len(problem) > 15 and any(
                keyword in problem for keyword in important_keywords
            ):
                # 改行を除去して単一行に
                return re.sub(r"\s+", " ", problem)

        # パターン2: 最初の意味のある行
        lines = body.split("\n")
        for line in lines[:5]:  # 最初の5行から探索
            line = line.strip()
            # マークダウン記号・絵文字を除去
            clean_line = re.sub(r"^_.*?_\s*", "", line)
            clean_line = re.sub(r"[💡🧩⚠️]", "", clean_line).strip()

            # 意味のある文章かチェック
            if len(clean_line) > 20 and (
                "の" in clean_line or "を" in clean_line or "が" in clean_line
            ):
                return clean_line

        # パターン3: コメント全体から要約生成
        return self._generate_problem_summary(body)

    def _generate_problem_summary(self, body: str) -> str:
        """コメント全体から問題要約を生成"""
        import re

        # セキュリティ関連キーワードチェック
        if any(
            keyword in body.lower()
            for keyword in ["token", "security", "漏洩", "セキュリティ"]
        ):
            return "セキュリティリスク: トークン関連の修正が必要"

        # 機能関連
        if any(
            keyword in body.lower() for keyword in ["function", "機能", "bug", "バグ"]
        ):
            return "機能問題: コード動作の修正が必要"

        # ドキュメント関連
        if any(
            keyword in body.lower()
            for keyword in ["md051", "markdown", "アンカー", "document"]
        ):
            return "ドキュメント問題: リンクまたは形式の修正が必要"

        # フォールバック
        return "コード品質改善: 詳細は原文を確認してください"

    def _extract_unique_diffs(self, body: str) -> list:
        """重複除去付きdiffブロック抽出（完全版）"""
        import re

        # diffブロックまたはsuggestionブロック
        diff_blocks = re.findall(r"```(?:diff|suggestion)\n(.*?)\n```", body, re.DOTALL)

        # より厳密な重複除去
        unique_diffs = []
        seen_signatures = set()

        for diff in diff_blocks:
            diff_clean = diff.strip()

            # 重複判定用署名の生成（より厳密）
            signature = self._generate_diff_signature(diff_clean)

            if signature and signature not in seen_signatures:
                seen_signatures.add(signature)
                # 統一フォーマットに整形
                formatted_diff = self._format_unified_diff(diff_clean)
                if formatted_diff:  # 空でない場合のみ追加
                    unique_diffs.append(formatted_diff)

        return unique_diffs

    def _generate_diff_signature(self, diff_content: str) -> str:
        """diff重複判定用の署名生成"""
        import re

        lines = diff_content.split("\n")
        core_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # 行番号・プレフィックス除去で本質的内容を抽出
                clean_line = re.sub(r"^\s*\d+\s*", "", line)  # 行番号
                clean_line = re.sub(r"^[-+\s]*", "", clean_line)  # diff記号
                clean_line = clean_line.strip()

                if clean_line and len(clean_line) > 2:  # 意味のある行のみ
                    core_lines.append(clean_line)

        # 本質的な変更内容のみで署名生成
        return "|".join(core_lines)

    def _format_unified_diff(self, diff_content: str) -> str:
        """diffを統一フォーマットに整形（完全版）"""
        import re

        lines = diff_content.split("\n")
        formatted_lines = []
        has_meaningful_content = False

        for line in lines:
            line = line.strip()
            if line:
                # 行番号削除（先頭の数字を除去）
                clean_line = re.sub(r"^\s*\d+\s*", "", line)

                # 意味のある変更行かチェック
                if clean_line and (
                    clean_line.startswith("+")
                    or clean_line.startswith("-")
                    or clean_line.startswith("##")
                ):
                    formatted_lines.append(clean_line)
                    has_meaningful_content = True
                elif clean_line and not clean_line.startswith("@"):  # @@行は除外
                    formatted_lines.append(clean_line)

        # 意味のある変更がない場合は空を返す
        if not has_meaningful_content:
            return ""

        result = "\n".join(formatted_lines)

        # 最終的に空または短すぎる場合は除外
        return result if len(result.strip()) > 10 else ""

    def _extract_structured_files(self, body: str) -> dict:
        """構造化されたファイル情報抽出（改良版）"""
        import re

        # ファイル情報の統一収集
        file_info_map = {}  # ファイル名 -> {lines: set, description: str}

        # パターン1: ファイル名(行XX/YY) 形式
        file_line_matches = re.findall(
            r"([a-zA-Z0-9_/.]+\.py)\s*(?:\（?(?:行)?(\d+(?:[／/,]\d+)*)\）?)", body
        )
        for file_path, line_nums in file_line_matches:
            if file_path not in file_info_map:
                file_info_map[file_path] = {"lines": set(), "description": ""}

            if line_nums:
                # 複数行番号を分割処理
                for line_num in re.split(r"[／/,]", line_nums):
                    if line_num.strip():
                        file_info_map[file_path]["lines"].add(line_num.strip())

        # パターン2: "- filename: description" 形式
        lines = body.split("\n")
        for line in lines:
            match = re.match(
                r"[-*]\s*([a-zA-Z0-9_/.]+\.py)\s*(?:\（.*?\）)?\s*[:：]\s*(.+)", line
            )
            if match:
                file_path, description = match.group(1), match.group(2).strip()
                if file_path not in file_info_map:
                    file_info_map[file_path] = {"lines": set(), "description": ""}
                file_info_map[file_path]["description"] = description

        # 統一されたファイルリスト生成
        unified_files = []
        for file_path, info in file_info_map.items():
            line_info = sorted(info["lines"]) if info["lines"] else []
            line_str = ", ".join(line_info) if line_info else ""
            unified_files.append(
                {
                    "path": file_path,
                    "lines": line_str,
                    "description": info["description"],
                }
            )

        return {"files": unified_files}

    def _extract_concrete_actions(self, body: str) -> list:
        """具体的な修正アクション抽出（改良版）"""
        import re

        actions = []

        # パターン1: セキュリティ関連の統一修正
        if "token" in body.lower() and "${GITHUB_TOKEN}" in body:
            actions.append("全ての生トークン埋め込みを ${GITHUB_TOKEN} 環境変数に変更")

        # パターン2: 具体的な置換指示
        replace_patterns = re.findall(r"`([^`]+)`\s*[→を]\s*`([^`]+)`", body)
        for old, new in replace_patterns[:2]:
            actions.append(f"置換: `{old}` → `{new}`")

        # パターン3: ファイル追加・修正
        add_patterns = re.findall(r"\+\s*(.+)", body)
        for addition in add_patterns[:2]:
            if len(addition.strip()) > 5 and "<" not in addition:
                actions.append(f"追加: {addition.strip()}")

        # パターン4: 一般的な対応指示
        lines = body.split("\n")
        for line in lines:
            for pattern in [
                r"対応[:：]\s*(.+)",
                r"修正[:：]\s*(.+)",
                r"変更[:：]\s*(.+)",
            ]:
                match = re.search(pattern, line)
                if match and len(match.group(1).strip()) > 10:
                    actions.append(match.group(1).strip())
                    break

        return actions[:3]  # 最大3つまで

    def _generate_curl_section(self, pr_info: Dict, github_token: str = None) -> str:
        """curl返信セクションを生成"""
        owner = pr_info.get("owner", "OWNER")
        repo = pr_info.get("repo", "REPO")
        pr_number = pr_info.get("number", "PR_NUMBER")

        return f"""
## 返信方法
GitHub UIまたはGitHub CLI推奨。curl使用時は：

```bash
curl -X POST \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "返信内容", "in_reply_to": COMMENT_ID}}' \\
  https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments
```

**重要**: セキュリティのため、実際のトークン値は環境変数から参照してください。"""

    def _extract_comment_title(self, comment: Dict) -> str:
        """コメントからタイトルを抽出"""
        body = comment.get("body", "")
        if not body:
            return "レビューコメント"

        # 最初の行または50文字でタイトルを作成
        first_line = body.split("\n")[0].strip()
        if len(first_line) > 50:
            return first_line[:47] + "..."
        return first_line if first_line else "レビューコメント"
