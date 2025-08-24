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

# モジュール内インポート（相対インポート）
if __name__ == "__main__":
    # 直接実行時は絶対インポート
    import sys

    sys.path.append(str(Path(__file__).parent.parent))
    from models import OutsideDiffComment
    from comment_processor import CommentProcessor
    from prompt_generator import AIPromptGenerator
else:
    # モジュールとして実行時は相対インポート
    from ..models import OutsideDiffComment
    from ..comment_processor import CommentProcessor
    from ..prompt_generator import AIPromptGenerator
    from ..utils.outside_diff_parser import OutsideDiffParser
    from ..utils.ai_agent_optimizer import AIAgentOptimizer
    from ..utils.platform_detector import PlatformLimitationDetector
    from ..utils.duplicate_manager import DuplicateCommentManager
    from ..utils.reply_decision_matrix import ReplyDecisionMatrix
    from ..utils.resolution_master import ResolutionMasterController
    from ..utils.smart_comment_filter import SmartCommentFilter
    from ..utils.parsers import extract_ai_agent_prompt

logger = logging.getLogger(__name__)


class UnifiedPromptEngine:
    """統一プロンプト生成エンジン"""

    def __init__(self, project_root: str = ".", github_token: Optional[str] = None):
        # 新しいシンプル構造では動的生成を使用
        self.logger = logging.getLogger(__name__)
        self.project_root = project_root
        self.github_token = github_token

        # Phase 2 & 3: 高度化・最適化機能の初期化
        try:
            self.outside_diff_parser = OutsideDiffParser()
            self.ai_optimizer = AIAgentOptimizer()
            self.platform_detector = PlatformLimitationDetector()
            self.duplicate_manager = DuplicateCommentManager()
            self.reply_decision_matrix = ReplyDecisionMatrix()
            self.smart_comment_filter = SmartCommentFilter()

            # 解決状態追跡システム（最新機能）
            self.resolution_master = ResolutionMasterController(
                project_root=project_root, github_token=github_token
            )

            self.enhanced_features_available = True
            self.resolution_tracking_available = True
            self.logger.info(
                "全ての高度化・最適化機能が利用可能です（解決状態追跡含む）"
            )
        except Exception as e:
            self.logger.warning(f"拡張機能の初期化に失敗: {e}")
            self.enhanced_features_available = False
            self.resolution_tracking_available = False

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

        # スマートフィルタリングを適用 - タスク化と返信判定を分離
        actionable_comments = []
        reply_required_comments = []

        if comments:
            try:
                from ..utils.smart_comment_filter import SmartCommentFilter
                from ..utils.parsers import extract_outside_diff_comments

                smart_filter = SmartCommentFilter()
                filter_results = smart_filter.filter_comments(comments)
                actionable_comments = filter_results["actionable_comments"]

                # Outside diff range commentsを処理
                outside_diff_comments = []
                for comment in comments:
                    comment_body = comment.get("body", "")
                    extracted_outside = extract_outside_diff_comments(comment_body)

                    if extracted_outside:
                        # Outside diff commentsを通常のコメント形式に変換
                        for outside_comment in extracted_outside:
                            synthetic_comment = {
                                "id": f"{comment.get('id', 'unknown')}_outside_{len(outside_diff_comments)}",
                                "body": f"🔧 **{outside_comment['title']}** (行: {outside_comment['line']})\n\n{outside_comment['content']}",
                                "path": outside_comment["file_path"],
                                "line": outside_comment["line"],
                                "user": {"login": "coderabbitai[bot]"},
                                "created_at": comment.get("created_at", ""),
                                "priority": outside_comment["priority"],
                                "category": outside_comment["category"],
                                "is_outside_diff": True,
                            }
                            outside_diff_comments.append(synthetic_comment)

                # シンプルな返信必要判定（CodeRabbitの技術的指摘）
                for comment in comments:
                    author = comment.get("user", {}).get("login", "")
                    body = comment.get("body", "")

                    # CodeRabbitの技術的指摘で返信必要なパターン
                    if author and author.strip().lower().startswith("coderabbitai"):
                        technical_indicators = [
                            "_⚠️ Potential issue_",
                            "_🛠️ Refactor suggestion_",
                            "_💡 Verification agent_",
                            "_🔒 Security issue_",
                            "_⚡ Performance issue_",
                        ]

                        # 技術的指摘だが、検証スクリプトのみの場合は除外
                        has_technical_indicator = any(
                            indicator in body for indicator in technical_indicators
                        )
                        is_verification_script_only = (
                            "検証スクリプト" in body
                            or "rg -nP" in body
                            or "#!/bin/bash" in body
                        )

                        # 技術的指摘があり、検証スクリプトのみでない場合は返信必要
                        if has_technical_indicator and not is_verification_script_only:
                            # 具体的な修正指示があるかチェック
                            has_concrete_action = any(
                                keyword in body.lower()
                                for keyword in [
                                    "修正",
                                    "変更",
                                    "update",
                                    "fix",
                                    "change",
                                    "add",
                                    "remove",
                                    "variable",
                                    "変数",
                                    "validation",
                                    "バリデーション",
                                    "runtime",
                                ]
                            )

                            if has_concrete_action:
                                reply_required_comments.append(comment)

                # Outside diff commentsもスマートフィルターを通す
                outside_filter = SmartCommentFilter()
                for comment in outside_diff_comments:
                    should_task, reason, comment_type = (
                        outside_filter.should_create_task(comment)
                    )
                    if should_task:
                        if comment not in actionable_comments:
                            actionable_comments.append(comment)
                    else:
                        # スマートフィルターで除外されたOutside diffコメントでも
                        # 具体的な技術的修正提案がある場合は返信必要
                        has_technical_indicator = any(
                            indicator in comment.get("body", "")
                            for indicator in [
                                "_⚠️ Potential issue_",
                                "_🛠️ Refactor suggestion_",
                                "_🔒 Security issue_",
                            ]
                        )
                        has_concrete_action = any(
                            keyword in comment.get("body", "").lower()
                            for keyword in [
                                "修正",
                                "変更",
                                "fix",
                                "change",
                                "update",
                                "variable",
                                "変数",
                            ]
                        )
                        if has_technical_indicator and has_concrete_action:
                            reply_required_comments.append(comment)

                # 結合: タスク化必要 + 返信のみ必要なコメント（スマートフィルター適用後）
                for comment in reply_required_comments:
                    if comment not in actionable_comments:
                        # 返信必要コメントもスマートフィルターを通す
                        outside_filter = SmartCommentFilter()
                        should_task, reason, comment_type = (
                            outside_filter.should_create_task(comment)
                        )
                        if should_task or comment_type.value == "actionable":
                            actionable_comments.append(comment)

                # フィルタリング結果をログ出力
                self.logger.info(
                    f"フィルタリング結果: "
                    f"総コメント数={filter_results['total_comments']}, "
                    f"タスク化必要={len(filter_results['actionable_comments'])}, "
                    f"返信必要={len(reply_required_comments)}, "
                    f"Outside diff={len(outside_diff_comments)}, "
                    f"表示対象={len(actionable_comments)}"
                )

            except Exception as e:
                self.logger.warning(f"フィルタリング・返信判定失敗: {e}")
                actionable_comments = comments

        # 表示対象コメントを使用（タスク化 + 返信必要）
        comments = actionable_comments

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
**❌ 対応不要**:
```
@coderabbitai [技術的根拠]により対応不要と判断します。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

**⏳ 将来対応**:
```
@coderabbitai 妥当な指摘ですが[現フェーズ]では対応しません。[将来フェーズ]で対応予定です。この課題を将来のタスクとして記憶し、[将来フェーズ]開始時に再度指摘してください。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

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

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
```

**実用例2: パフォーマンス最適化延期**
```
@coderabbitai この指摘は技術的に妥当ですが、現在のプロトタイプ段階では対応しません。
理由: 機能検証が優先、パフォーマンス最適化は本格運用前に実施
予定: Phase3（本格運用準備フェーズ）で対応予定
依頼: この課題を将来のタスクとして記憶し、Phase3開始時に再度指摘してください。

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
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

問題ないと判断できれば、このコメントスレッドを解決済みにマークし、返信末尾に以下を追加してください：

[CR_RESOLUTION_CONFIRMED:TECHNICAL_ISSUE_RESOLVED]
✅ エンジニアによる技術的検証完了 - CodeRabbitによる解決済みマーク実行可能
[/CR_RESOLUTION_CONFIRMED]
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

            # 返信判定マトリックスによる分析
            reply_analysis = None
            if self.enhanced_features_available and hasattr(
                self, "reply_decision_matrix"
            ):
                try:
                    context = {
                        "current_phase": options.get("current_phase", "development"),
                        "future_phase": options.get(
                            "future_phase", "quality_improvement"
                        ),
                    }
                    reply_analysis = (
                        self.reply_decision_matrix.analyze_reply_requirements(
                            comments, context
                        )
                    )

                    # 返信チェックリストを追加
                    checklist = self.reply_decision_matrix.get_reply_checklist(
                        reply_analysis
                    )
                    prompt_parts.append(f"\n{checklist}\n")

                except Exception as e:
                    self.logger.warning(f"返信判定マトリックス処理エラー: {e}")

            for i, comment in enumerate(comments, 1):
                # 返信判定マトリックスの結果を取得
                reply_decision = None
                if reply_analysis:
                    for decision_info in reply_analysis["decisions"]:
                        if decision_info["comment_id"] == comment.get("id"):
                            reply_decision = decision_info["decision"]
                            break

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

                # 返信判定結果を追加
                reply_info = ""
                if reply_decision:
                    reply_info = f"""
**返信判定**: {reply_decision.action.value}
**返信要否**: {'必要' if reply_decision.reply_required.name == 'REQUIRED' else '不要'}
**推定時間**: {reply_decision.estimated_time}分
"""

                prompt_parts.append(
                    f"""
### TODO #{i}: {self._extract_comment_title(comment)}
**分類**: {classification}
{reply_info}
{self._format_single_comment(comment, pr_info, github_token)}

**🎯 最終判断**: [ ] ✅実施 [ ] ❌対応不要 [ ] ⏳将来対応 [ ] 🤔要確認

---"""
                )

        return "\n".join(prompt_parts)

    def generate_resolution_aware_prompt(
        self,
        comments: List[Dict],
        pr_info: Dict,
        pr_url: str = "",
        options: Dict = None,
        enable_resolution_tracking: bool = True,
    ) -> str:
        """解決状態追跡機能付きの最高レベルプロンプト生成

        Args:
            comments: コメントリスト
            pr_info: プルリクエスト情報
            pr_url: プルリクエストURL
            options: 生成オプション
            enable_resolution_tracking: 解決状態追跡を有効にするか

        Returns:
            解決状態追跡機能付きプロンプト
        """
        try:
            self.logger.info("解決状態追跡機能付きプロンプト生成開始")

            # 1. 範囲外コメントの検出・解析
            outside_diff_comments = []
            if self.enhanced_features_available:
                for comment in comments:
                    if self._is_outside_diff_comment(comment):
                        parsed_comments = (
                            self.outside_diff_parser.parse_outside_diff_comments(
                                comment.get("body", "")
                            )
                        )
                        outside_diff_comments.extend(parsed_comments)

            if not outside_diff_comments:
                self.logger.info("範囲外コメントが見つかりませんでした")
                return self.generate_ultimate_enhanced_prompt(
                    comments, pr_info, pr_url, options, self.github_token
                )

            # 2. 解決状態追跡（有効な場合）
            if enable_resolution_tracking and self.resolution_tracking_available:
                # 解決状態追跡付きで処理
                tracking_result = (
                    self.resolution_master.process_comments_with_resolution_tracking(
                        outside_diff_comments, pr_url, enable_github_integration=True
                    )
                )

                # 解決状態追跡付きプロンプト生成
                enhanced_prompt = self.resolution_master.generate_enhanced_prompt_with_resolution_context(
                    outside_diff_comments, pr_info, include_progress_info=True
                )

                # 統計情報を追加
                stats_section = f"""
## 📊 解決状態追跡統計

- **総コメント数**: {tracking_result['total_comments']}
- **解決済み**: {tracking_result['resolved_comments']}
- **未解決**: {tracking_result['unresolved_comments']}
- **進捗率**: {tracking_result.get('progress_report', {}).get('summary', {}).get('completion_rate', 0):.1f}%

"""
                enhanced_prompt = stats_section + enhanced_prompt

                self.logger.info(
                    f"解決状態追跡機能付きプロンプト生成完了: {tracking_result['resolved_comments']}/{tracking_result['total_comments']} 解決済み"
                )
                return enhanced_prompt

            else:
                # 基本的な範囲外コメント処理のみ
                self.logger.info("解決状態追跡なしで範囲外コメント処理")
                return self.generate_enhanced_prompt_with_outside_diff(
                    comments, pr_info, outside_diff_comments, options, self.github_token
                )

        except Exception as e:
            self.logger.error(f"解決状態追跡機能付きプロンプト生成エラー: {e}")
            # フォールバック: 基本プロンプト生成
            return self.generate_main_prompt(
                comments, pr_info, options, self.github_token
            )

    def _is_outside_diff_comment(self, comment: Dict) -> bool:
        """コメントが範囲外コメントかどうかを判定"""
        try:
            body = comment.get("body", "")

            # 範囲外コメントの特徴的なパターンを検出
            outside_diff_patterns = [
                r"\*\*Actionable comments posted:\s*\d+\*\*",
                r"`\d+(?:-\d+)?`:\s*\*\*.*?\*\*",
                r"---\s*\*\*Duplicate comments posted:\s*\d+\*\*",
                r"---\s*\*\*Nitpick comments posted:\s*\d+\*\*",
            ]

            for pattern in outside_diff_patterns:
                if re.search(pattern, body, re.IGNORECASE | re.DOTALL):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"範囲外コメント判定エラー: {e}")
            return False

    def generate_enhanced_prompt_with_outside_diff(
        self,
        comments: List[Dict],
        pr_info: Dict,
        outside_diff_comments: List[OutsideDiffComment] = None,
        options: Dict = None,
        github_token: str = None,
    ) -> str:
        """範囲外コメントを含む拡張プロンプトを生成

        Args:
            comments: 通常のレビューコメント
            pr_info: プルリクエスト情報
            outside_diff_comments: 範囲外コメントのリスト
            options: オプション設定
            github_token: GitHubトークン

        Returns:
            範囲外コメントを含む統合プロンプト
        """
        if options is None:
            options = {}

        # 基本プロンプトを生成
        base_prompt = self.generate_main_prompt(
            comments, pr_info, options, github_token
        )

        # 範囲外コメントがない場合は基本プロンプトを返す
        if not outside_diff_comments:
            return base_prompt

        # 範囲外コメント用のプロンプト生成器を初期化
        try:
            persona = options.get(
                "persona", "security-analyst"
            )  # デフォルトはセキュリティアナリスト
            prompt_generator = AIPromptGenerator(
                persona=persona, github_token=github_token
            )

            # 範囲外コメント用セクションを生成
            outside_diff_section = prompt_generator.generate_outside_diff_section(
                outside_diff_comments
            )

            # 統計情報を追加
            stats_section = self._generate_outside_diff_stats(outside_diff_comments)

            # 基本プロンプトと範囲外コメントセクションを統合
            guidance_block = """
## 📋 統合対応指針

### 🔒 セキュリティファースト原則
1. **範囲外コメント優先**: プラットフォーム制限により見落としやすいため、最優先で対応
2. **段階的対応**: 🔴緊急 → 🟡重要 → 🟢低優先の順で処理
3. **影響範囲検証**: 各修正が他の箇所に与える影響を慎重に確認

### 📊 対応完了の報告形式
各範囲外コメントの対応完了時は以下の形式で報告してください：

```
✅ 範囲外TODO #[todo_number]: [title]
**ファイル**: [file_path]
**行範囲**: [line_range]
**対応内容**: [具体的な対応内容]
**検証結果**: [影響範囲の確認結果]
```

### ⚠️ 対応不要の判断
範囲外コメントでも対応不要と判断する場合：

```
❌ 範囲外TODO #[todo_number]: [title]
**理由**: [技術的根拠に基づく詳細な理由]
**判断**: 対応不要（範囲外コメント）
```
"""

            enhanced_prompt = "\n\n".join(
                [base_prompt, outside_diff_section, stats_section, guidance_block]
            )

            self.logger.info(
                f"範囲外コメント統合完了: {len(outside_diff_comments)}件のコメントを統合"
            )
            return enhanced_prompt

        except Exception as e:
            self.logger.error(f"範囲外コメント統合エラー: {e}")
            # エラーが発生した場合は基本プロンプトを返す
            return base_prompt

    def _generate_outside_diff_stats(
        self, outside_diff_comments: List[OutsideDiffComment]
    ) -> str:
        """範囲外コメントの統計情報を生成

        Args:
            outside_diff_comments: 範囲外コメントのリスト

        Returns:
            統計情報のセクション
        """
        if not outside_diff_comments:
            return ""

        # カテゴリ別の集計
        category_counts = {}
        severity_counts = {}
        file_counts = {}

        for comment in outside_diff_comments:
            # カテゴリ別
            category = comment.category.value
            category_counts[category] = category_counts.get(category, 0) + 1

            # 重要度別
            severity = comment.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # ファイル別
            file_path = comment.file_path
            file_counts[file_path] = file_counts.get(file_path, 0) + 1

        stats = f"""
## 📊 範囲外コメント統計

### 📈 全体サマリー
- **総コメント数**: {len(outside_diff_comments)}件
- **対象ファイル数**: {len(file_counts)}ファイル

### 🎯 重要度別内訳
"""

        # 重要度別の表示
        severity_icons = {"caution": "🔴", "warning": "🟡", "info": "🟢"}
        severity_names = {"caution": "緊急", "warning": "重要", "info": "低優先"}

        for severity in ["caution", "warning", "info"]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                icon = severity_icons[severity]
                name = severity_names[severity]
                stats += f"- **{icon} {name}**: {count}件\n"

        stats += "\n### 📂 ファイル別内訳\n"

        # ファイル別の表示（上位5ファイル）
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for file_path, count in sorted_files:
            stats += f"- **{file_path}**: {count}件\n"

        if len(file_counts) > 5:
            stats += f"- その他 {len(file_counts) - 5}ファイル\n"

        return stats

    def generate_ultimate_enhanced_prompt(
        self,
        comments: List[Dict],
        pr_info: Dict,
        pr_url: str = "",
        options: Dict = None,
        github_token: str = None,
    ) -> str:
        """全機能統合版の最高レベルプロンプトを生成

        Args:
            comments: 通常のレビューコメント
            pr_info: プルリクエスト情報
            pr_url: プルリクエストURL
            options: オプション設定
            github_token: GitHubトークン

        Returns:
            全機能統合プロンプト
        """
        if options is None:
            options = {}

        if not self.enhanced_features_available:
            self.logger.warning(
                "拡張機能が利用できません。基本プロンプトを生成します。"
            )
            return self.generate_main_prompt(comments, pr_info, options, github_token)

        try:
            # Phase 1: 範囲外コメントの検出・解析
            outside_diff_comments = []
            for comment in comments:
                if self.outside_diff_parser.detect_outside_diff_comments(
                    comment.get("body", "")
                ):
                    parsed_comments = (
                        self.outside_diff_parser.parse_outside_diff_comments(
                            comment.get("body", ""),
                            comment.get("id", 0),
                            comment.get("user", {}).get("login", ""),
                        )
                    )
                    outside_diff_comments.extend(parsed_comments)

            # Phase 2: 詳細情報の付与
            for comment in outside_diff_comments:
                comment.file_details = self.outside_diff_parser.parse_file_path_details(
                    comment.file_path
                )
                comment.line_details = (
                    self.outside_diff_parser.parse_line_range_details(
                        comment.line_range
                    )
                )
                comment.suggestion_details = (
                    self.outside_diff_parser.extract_structured_code_suggestion(
                        comment.description
                    )
                )

            # Phase 3: 最適化・分析
            optimization_result = self.ai_optimizer.optimize_work_instructions(
                outside_diff_comments
            )
            platform_analysis = self.platform_detector.analyze_comment_accessibility(
                comments
            )

            # 重複管理（PR URLが提供されている場合）
            duplicate_analysis = {}
            if pr_url and outside_diff_comments:
                tracking_result = self.duplicate_manager.track_comments(
                    pr_url, outside_diff_comments
                )
                duplicate_analysis = self.duplicate_manager.find_cross_pr_duplicates(
                    outside_diff_comments
                )

            # 基本プロンプトの生成
            if outside_diff_comments:
                base_prompt = self.generate_enhanced_prompt_with_outside_diff(
                    comments, pr_info, outside_diff_comments, options, github_token
                )
            else:
                base_prompt = self.generate_main_prompt(
                    comments, pr_info, options, github_token
                )

            # 最適化情報の統合
            optimization_section = self._generate_optimization_section(
                optimization_result
            )
            platform_section = self._generate_platform_analysis_section(
                platform_analysis
            )
            duplicate_section = (
                self._generate_duplicate_analysis_section(duplicate_analysis)
                if duplicate_analysis
                else ""
            )

            # 最終統合プロンプト
            ultimate_prompt = f"""{base_prompt}

{optimization_section}

{platform_section}

{duplicate_section}

## 🚀 統合実行戦略

### 📊 実行サマリー
- **総コメント数**: {len(comments)}件
- **範囲外コメント数**: {len(outside_diff_comments)}件
- **推定作業時間**: {optimization_result.get('estimated_time_minutes', 0)}分
- **複雑度スコア**: {optimization_result.get('complexity_score', 0)}/100
- **推奨アプローチ**: {optimization_result.get('recommended_approach', 'sequential')}

### 🎯 最適化された実行順序
{self._format_priority_order(optimization_result.get('priority_order', []))}

### 🔒 セキュリティ・品質チェックリスト
- [ ] GitHub トークンの環境変数確認完了
- [ ] 範囲外コメントの位置特定完了
- [ ] プラットフォーム制限への対応確認完了
- [ ] 重複コメントの統合・スキップ判断完了
- [ ] 高リスク項目の手動レビュー完了

### ⚡ 効率化機会
{self._format_automation_opportunities(optimization_result.get('automation_opportunities', []))}

---

**🎉 このプロンプトは全3フェーズの機能統合により生成されました**
- **Phase 1**: 範囲外コメント基本対応
- **Phase 2**: 高度化機能（詳細解析・グループ化）
- **Phase 3**: 最適化機能（AI指示最適化・制限検出・重複管理）
"""

            self.logger.info(
                f"統合プロンプト生成完了: {len(outside_diff_comments)}件の範囲外コメントを統合"
            )
            return ultimate_prompt

        except Exception as e:
            self.logger.error(f"統合プロンプト生成エラー: {e}")
            # エラーが発生した場合は基本プロンプトにフォールバック
            return self.generate_main_prompt(comments, pr_info, options, github_token)

    def _generate_optimization_section(
        self, optimization_result: Dict[str, Any]
    ) -> str:
        """最適化セクションを生成"""
        if not optimization_result:
            return ""

        return f"""
## 🤖 AI最適化分析結果

### 📈 作業効率分析
- **複雑度スコア**: {optimization_result.get('complexity_score', 0)}/100
- **推定作業時間**: {optimization_result.get('estimated_time_minutes', 0)}分
- **推奨アプローチ**: {optimization_result.get('recommended_approach', 'sequential')}

### ⚠️ リスク評価
**全体リスクレベル**: {optimization_result.get('risk_assessment', {}).get('overall_risk_level', 'low')}

{self._format_risk_details(optimization_result.get('risk_assessment', {}))}

### 🔧 手動レビュー必須項目
{self._format_manual_review_items(optimization_result.get('manual_review_required', []))}
"""

    def _generate_platform_analysis_section(
        self, platform_analysis: Dict[str, Any]
    ) -> str:
        """プラットフォーム分析セクションを生成"""
        if not platform_analysis:
            return ""

        return f"""
## 🌐 プラットフォーム制限分析

### 📊 アクセシビリティスコア
**スコア**: {platform_analysis.get('accessibility_score', 0)}/100

### 📋 コメント分類
- **アクセス可能**: {platform_analysis.get('accessible_comments', 0)}件
- **制限あり**: {platform_analysis.get('limited_comments', 0)}件
- **アクセス不可**: {platform_analysis.get('inaccessible_comments', 0)}件

### 💡 推奨事項
{self._format_recommendations(platform_analysis.get('recommendations', []))}
"""

    def _generate_duplicate_analysis_section(
        self, duplicate_analysis: Dict[str, Any]
    ) -> str:
        """重複分析セクションを生成"""
        if not duplicate_analysis:
            return ""

        exact_duplicates = len(duplicate_analysis.get("exact_duplicates", []))
        similar_comments = len(duplicate_analysis.get("similar_comments", []))

        return f"""
## 🔄 重複コメント分析

### 📊 重複統計
- **完全重複**: {exact_duplicates}件
- **類似コメント**: {similar_comments}件

### 💡 重複対応推奨事項
{self._format_recommendations(duplicate_analysis.get('recommendations', []))}
"""

    def _format_priority_order(self, priority_order: List[Dict[str, Any]]) -> str:
        """優先順序をフォーマット"""
        if not priority_order:
            return "優先順序情報がありません。"

        formatted = ""
        for item in priority_order[:5]:  # 上位5件のみ表示
            formatted += f"""
**{item.get('rank', 0)}位**: {item.get('title', 'タイトル不明')}
- ファイル: `{item.get('file_path', '')}`
- リスクレベル: {item.get('risk_level', 'unknown')}
- 推定時間: {item.get('estimated_time_minutes', 0)}分
"""

        if len(priority_order) > 5:
            formatted += f"\n...他{len(priority_order) - 5}件"

        return formatted

    def _format_automation_opportunities(
        self, opportunities: List[Dict[str, Any]]
    ) -> str:
        """自動化機会をフォーマット"""
        if not opportunities:
            return "自動化機会は検出されませんでした。"

        formatted = ""
        for opp in opportunities:
            formatted += f"- **{opp.get('automation_type', 'unknown')}**: {opp.get('description', '')}"
            if opp.get("estimated_time_saved_minutes"):
                formatted += f" (節約時間: {opp['estimated_time_saved_minutes']}分)"
            formatted += "\n"

        return formatted

    def _format_risk_details(self, risk_assessment: Dict[str, Any]) -> str:
        """リスク詳細をフォーマット"""
        if not risk_assessment:
            return ""

        formatted = ""

        security_risks = risk_assessment.get("security_risks", [])
        if security_risks:
            formatted += f"**🔒 セキュリティリスク**: {len(security_risks)}件\n"

        breaking_risks = risk_assessment.get("breaking_change_risks", [])
        if breaking_risks:
            formatted += f"**💥 破壊的変更リスク**: {len(breaking_risks)}件\n"

        performance_risks = risk_assessment.get("performance_risks", [])
        if performance_risks:
            formatted += f"**⚡ パフォーマンスリスク**: {len(performance_risks)}件\n"

        mitigation_strategies = risk_assessment.get("mitigation_strategies", [])
        if mitigation_strategies:
            formatted += "\n**軽減戦略**:\n"
            for strategy in mitigation_strategies:
                formatted += f"- {strategy}\n"

        return formatted

    def _format_manual_review_items(self, manual_items: List[Dict[str, Any]]) -> str:
        """手動レビュー項目をフォーマット"""
        if not manual_items:
            return "手動レビューが必要な項目はありません。"

        formatted = ""
        for item in manual_items:
            formatted += f"""
**{item.get('title', 'タイトル不明')}**
- ファイル: `{item.get('file_path', '')}`
- 理由: {', '.join(item.get('reasons', []))}
- 優先度: {item.get('review_priority', 'medium')}
"""

        return formatted

    def _format_recommendations(self, recommendations: List[str]) -> str:
        """推奨事項をフォーマット"""
        if not recommendations:
            return "推奨事項はありません。"

        return "\n".join(f"- {rec}" for rec in recommendations)

    def _format_single_comment(
        self, comment: Dict, pr_info: Dict, github_token: str = None
    ) -> str:
        """構造化された単一コメントのフォーマット（スレッド情報を含む）"""
        # 基本情報抽出
        comment_id = comment.get("id", "unknown")
        author = comment.get("user", {}).get("login", "Unknown")
        created_at = comment.get("created_at", "Unknown")
        file_path = comment.get("path", "Unknown")
        line_number = comment.get("line") or comment.get("original_line", "Unknown")
        body = comment.get("body", "")

        # スレッド情報の取得
        thread_info = comment.get("_thread_info", {})

        # 🤖Prompt for AI Agentsの抽出
        ai_agent_prompt = extract_ai_agent_prompt(body)
        if ai_agent_prompt is None:
            logger.warning(
                f"AI Agent prompt extraction failed for comment {comment_id}"
            )
            ai_agent_prompt = ""  # デフォルト値を設定

        # 自動分類とメタデータ生成
        classification_data = self._analyze_comment(body, file_path)

        # 完全機械化YAMLメタデータ（スレッド情報を含む）
        security_risk = classification_data["issue_type"] == "security"
        yaml_data = f"""```yaml
id: {comment_id}
priority: {classification_data['classification_emoji']} {classification_data['severity']}
type: {classification_data['issue_type']}
file: {file_path}:{line_number}
author: {author}
created_at: {created_at}
auto_decision: {classification_data['auto_decision']}
security_risk: {str(security_risk).lower()}"""

        # スレッド情報を追加
        if thread_info:
            yaml_data += f"""
thread_comments: {thread_info.get('total_comments', 1)}
has_coderabbit_response: {str(thread_info.get('has_coderabbit_response', False)).lower()}
is_resolved: {str(thread_info.get('is_resolved', False)).lower()}"""

        yaml_data += "\n```"

        # AI Agentsプロンプトがある場合は優先表示
        if ai_agent_prompt:
            # AI Agentsプロンプトを優先表示
            supplement_content = self._optimize_comment_format(body)
            # 補足情報は200文字に制限
            if len(supplement_content) > 200:
                supplement_content = (
                    supplement_content[:200] + "...\n(詳細は元PRのコメント参照)"
                )

            optimized_content = f"""🤖 **Prompt for AI Agents** (優先対応指示)

```
{ai_agent_prompt}
```

**📋 補足情報** (元のコメント内容)
{supplement_content}"""
        else:
            # 通常の最適化フォーマット
            optimized_content = self._optimize_comment_format(body)

        # CodeRabbitの最新コメント情報を追加
        if thread_info.get("coderabbit_last_comment"):
            coderabbit_info = thread_info["coderabbit_last_comment"]
            optimized_content += (
                f"\n\n**💬 CodeRabbit最新コメント**: {coderabbit_info['summary']}"
            )

            # 解決マーカーがある場合は明記
            if thread_info.get("is_resolved"):
                optimized_content += (
                    "\n\n**✅ 解決状態**: CodeRabbitにより解決済みマーク済み"
                )

        parts = [
            yaml_data,
            "",
            optimized_content,
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
        if (file_path and file_path.endswith(".md")) or any(
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
## ⚡ 効率的な並列返信方法（推奨）

### **方法1: バックグラウンド並列実行（推奨）**
複数のcurlコマンドを並列で実行して処理時間を短縮：

```bash
# 並列実行で高速化（推奨）
{{
  curl -X POST \\
    -H "Authorization: Bearer $GITHUB_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{{"body": "返信内容1", "in_reply_to": COMMENT_ID1}}' \\
    "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" &

  curl -X POST \\
    -H "Authorization: Bearer $GITHUB_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{{"body": "返信内容2", "in_reply_to": COMMENT_ID2}}' \\
    "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" &

  curl -X POST \\
    -H "Authorization: Bearer $GITHUB_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{{"body": "返信内容3", "in_reply_to": COMMENT_ID3}}' \\
    "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments" &

  # 全ての並列処理の完了を待機
  wait
}}
```

### **方法2: xargs並列実行**
```bash
# コマンドリストファイルを作成
cat > reply_commands.txt << 'EOF'
curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" -d '{{"body": "返信1", "in_reply_to": ID1}}' "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/json" -d '{{"body": "返信2", "in_reply_to": ID2}}' "https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
EOF

# 並列実行（最大5並列）
cat reply_commands.txt | xargs -I {{}} -P 5 bash -c "{{}}"
```

### **方法3: 個別実行（シンプル）**
```bash
curl -X POST \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"body": "返信内容", "in_reply_to": COMMENT_ID}}' \\
  https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments
```

**🎯 推奨**: 方法1の並列実行で大幅な時間短縮を実現してください。
**⚠️ 注意**:
- 同時実行数は5件以下に制限（API制限考慮）
- 各コマンドの末尾に`&`を付けてバックグラウンド実行
- 最後に`wait`で全処理の完了を待機
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
