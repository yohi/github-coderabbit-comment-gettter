"""CodeRabbitアドバイスに基づく強化された設定管理システム"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigFormat(Enum):
    """設定ファイル形式"""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"


class EnvironmentType(Enum):
    """環境タイプ"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class GitHubConfig:
    """GitHub設定"""

    token: str = ""
    repo: str = ""
    api_base_url: str = "https://api.github.com"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_strategy: str = "adaptive"

    def __post_init__(self):
        # 環境変数からトークンを取得
        if not self.token:
            self.token = os.getenv("GITHUB_TOKEN", "")


@dataclass
class IssueTemplateConfig:
    """Issue テンプレート設定"""

    title_prefix: str = ""
    labels: List[str] = field(default_factory=list)
    assignee: str = ""
    body_template: str = ""
    auto_create: bool = True


@dataclass
class ProcessingRulesConfig:
    """処理ルール設定"""

    auto_create_threshold: str = "medium"  # critical, high, medium, low
    batch_size: int = 10
    rate_limit_delay: float = 1.0
    max_concurrent_requests: int = 5
    enable_duplicate_detection: bool = True
    enable_security_analysis: bool = True
    enable_terraform_analysis: bool = True


@dataclass
class StorageConfig:
    """ストレージ設定"""

    backend: str = "file"  # file, sqlite, postgresql
    connection_string: str = ""
    cache_ttl: int = 3600
    backup_enabled: bool = True
    backup_interval: int = 86400  # 24時間
    cleanup_old_data_days: int = 30


@dataclass
class NotificationConfig:
    """通知設定"""

    enabled: bool = False
    webhook_url: str = ""
    email_recipients: List[str] = field(default_factory=list)
    notification_threshold: str = "high"
    include_progress_reports: bool = True


@dataclass
class EnhancedConfiguration:
    """強化された設定データクラス"""

    # 基本設定
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"

    # GitHub設定
    github: GitHubConfig = field(default_factory=GitHubConfig)

    # Issue テンプレート設定
    issue_templates: Dict[str, IssueTemplateConfig] = field(default_factory=dict)

    # 処理ルール設定
    processing_rules: ProcessingRulesConfig = field(
        default_factory=ProcessingRulesConfig
    )

    # ストレージ設定
    storage: StorageConfig = field(default_factory=StorageConfig)

    # 通知設定
    notifications: NotificationConfig = field(default_factory=NotificationConfig)

    # カスタム設定
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # デフォルトのIssueテンプレートを設定
        if not self.issue_templates:
            self.issue_templates = self._get_default_issue_templates()

    def _get_default_issue_templates(self) -> Dict[str, IssueTemplateConfig]:
        """デフォルトのIssueテンプレートを取得"""
        return {
            "security": IssueTemplateConfig(
                title_prefix="[Security]",
                labels=["security", "terraform", "high-priority"],
                assignee="",
                body_template="""
## 🔒 セキュリティ問題

**ファイル**: {file_path}
**行番号**: {line_number}
**重要度**: {priority}

### 問題の詳細
{comment_body}

### 推奨対応
{recommended_actions}

### 影響範囲
{impact_assessment}
""",
                auto_create=True,
            ),
            "syntax_error": IssueTemplateConfig(
                title_prefix="[Syntax Error]",
                labels=["bug", "terraform", "urgent"],
                assignee="",
                body_template="""
## 🚨 構文エラー

**ファイル**: {file_path}
**行番号**: {line_number}

### エラー内容
{comment_body}

### 修正方法
{recommended_actions}
""",
                auto_create=True,
            ),
            "improvement": IssueTemplateConfig(
                title_prefix="[Improvement]",
                labels=["enhancement", "terraform"],
                assignee="",
                body_template="""
## 💡 改善提案

**ファイル**: {file_path}
**行番号**: {line_number}

### 提案内容
{comment_body}

### 期待される効果
{recommended_actions}
""",
                auto_create=False,
            ),
            "nitpick": IssueTemplateConfig(
                title_prefix="[Nitpick]",
                labels=["nitpick", "low-priority"],
                assignee="",
                body_template="""
## 📝 軽微な指摘

**ファイル**: {file_path}
**行番号**: {line_number}

### 指摘内容
{comment_body}
""",
                auto_create=False,
            ),
        }


class EnhancedConfigManager:
    """強化された設定管理クラス"""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        environment: Optional[str] = None,
    ):
        self.logger = logging.getLogger(__name__)

        # 設定ファイルパスの決定
        self.config_path = self._determine_config_path(config_path)

        # 環境の決定
        self.environment = self._determine_environment(environment)

        # 設定の読み込み
        self.config = self._load_configuration()

        # 設定の検証
        self._validate_configuration()

        self.logger.info(
            f"設定管理初期化完了: {self.config_path} (環境: {self.environment})"
        )

    def _determine_config_path(self, config_path: Optional[Union[str, Path]]) -> Path:
        """設定ファイルパスを決定"""
        if config_path:
            return Path(config_path)

        # 優先順位に従って設定ファイルを探索
        search_paths = [
            Path(".github-review-prompts.yml"),
            Path(".github-review-prompts.yaml"),
            Path(".github-review-prompts.json"),
            Path("config/github-review-prompts.yml"),
            Path("config/github-review-prompts.yaml"),
            Path("config/github-review-prompts.json"),
            Path.home() / ".github-review-prompts.yml",
            Path.home() / ".github-review-prompts.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        # デフォルトパス
        return Path(".github-review-prompts.yml")

    def _determine_environment(self, environment: Optional[str]) -> EnvironmentType:
        """環境を決定"""
        if environment:
            try:
                return EnvironmentType(environment.lower())
            except ValueError:
                self.logger.warning(f"不正な環境指定: {environment}")

        # 環境変数から取得
        env_var = os.getenv("GITHUB_REVIEW_PROMPTS_ENV", "development")
        try:
            return EnvironmentType(env_var.lower())
        except ValueError:
            self.logger.warning(f"不正な環境変数値: {env_var}")
            return EnvironmentType.DEVELOPMENT

    def _load_configuration(self) -> EnhancedConfiguration:
        """設定を読み込み"""
        try:
            if not self.config_path.exists():
                self.logger.info(
                    "設定ファイルが見つかりません。デフォルト設定を使用します。"
                )
                return self._create_default_configuration()

            # ファイル形式の判定
            config_format = self._detect_config_format(self.config_path)

            # 設定ファイルの読み込み
            with open(self.config_path, "r", encoding="utf-8") as f:
                if config_format == ConfigFormat.YAML:
                    raw_config = yaml.safe_load(f)
                elif config_format == ConfigFormat.JSON:
                    raw_config = json.load(f)
                else:
                    raise ValueError(f"サポートされていない設定形式: {config_format}")

            if not raw_config:
                return self._create_default_configuration()

            # 環境固有の設定をマージ
            merged_config = self._merge_environment_config(raw_config)

            # データクラスに変換
            return self._dict_to_config(merged_config)

        except Exception as e:
            self.logger.error(f"設定読み込みエラー: {e}")
            self.logger.info("デフォルト設定を使用します。")
            return self._create_default_configuration()

    def _detect_config_format(self, path: Path) -> ConfigFormat:
        """設定ファイル形式を検出"""
        suffix = path.suffix.lower()
        if suffix in [".yml", ".yaml"]:
            return ConfigFormat.YAML
        elif suffix == ".json":
            return ConfigFormat.JSON
        else:
            # 内容から判定を試行
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.startswith("{"):
                        return ConfigFormat.JSON
                    else:
                        return ConfigFormat.YAML
            except Exception:
                return ConfigFormat.YAML  # デフォルト

    def _merge_environment_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """環境固有の設定をマージ"""
        env_key = f"environments.{self.environment.value}"
        env_config = self._get_nested_value(config, env_key)

        if env_config:
            # 環境固有の設定を基本設定にマージ
            merged = config.copy()
            self._deep_merge(merged, env_config)
            return merged

        return config

    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """ネストされた値を取得"""
        keys = key_path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]):
        """辞書の深いマージ"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _dict_to_config(self, config_dict: Dict[str, Any]) -> EnhancedConfiguration:
        """辞書をEnhancedConfigurationに変換"""
        try:
            # 環境設定
            environment = EnvironmentType(config_dict.get("environment", "development"))

            # GitHub設定
            github_config = GitHubConfig(**config_dict.get("github", {}))

            # Issue テンプレート設定
            issue_templates = {}
            templates_config = config_dict.get("issue_templates", {})
            for name, template_data in templates_config.items():
                issue_templates[name] = IssueTemplateConfig(**template_data)

            # 処理ルール設定
            processing_rules = ProcessingRulesConfig(
                **config_dict.get("processing_rules", {})
            )

            # ストレージ設定
            storage = StorageConfig(**config_dict.get("storage", {}))

            # 通知設定
            notifications = NotificationConfig(**config_dict.get("notifications", {}))

            return EnhancedConfiguration(
                environment=environment,
                debug=config_dict.get("debug", False),
                log_level=config_dict.get("log_level", "INFO"),
                github=github_config,
                issue_templates=issue_templates,
                processing_rules=processing_rules,
                storage=storage,
                notifications=notifications,
                custom=config_dict.get("custom", {}),
            )

        except Exception as e:
            self.logger.error(f"設定変換エラー: {e}")
            return self._create_default_configuration()

    def _create_default_configuration(self) -> EnhancedConfiguration:
        """デフォルト設定を作成"""
        return EnhancedConfiguration(environment=self.environment)

    def _validate_configuration(self):
        """設定を検証"""
        errors = []

        # GitHub トークンの検証
        if not self.config.github.token:
            errors.append("GitHub トークンが設定されていません")

        # リポジトリ設定の検証
        if not self.config.github.repo:
            errors.append("GitHub リポジトリが設定されていません")

        # 処理ルールの検証
        valid_thresholds = ["critical", "high", "medium", "low"]
        if self.config.processing_rules.auto_create_threshold not in valid_thresholds:
            errors.append(
                f"無効な自動作成閾値: {self.config.processing_rules.auto_create_threshold}"
            )

        # ストレージ設定の検証
        valid_backends = ["file", "sqlite", "postgresql"]
        if self.config.storage.backend not in valid_backends:
            errors.append(
                f"無効なストレージバックエンド: {self.config.storage.backend}"
            )

        if errors:
            self.logger.warning("設定検証エラー:")
            for error in errors:
                self.logger.warning(f"  - {error}")

    def save_configuration(self, path: Optional[Path] = None):
        """設定をファイルに保存"""
        save_path = path or self.config_path

        try:
            # 設定を辞書に変換
            config_dict = self._config_to_dict(self.config)

            # ファイル形式の判定
            config_format = self._detect_config_format(save_path)

            # 保存
            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                if config_format == ConfigFormat.YAML:
                    yaml.dump(
                        config_dict,
                        f,
                        default_flow_style=False,
                        allow_unicode=True,
                        indent=2,
                    )
                elif config_format == ConfigFormat.JSON:
                    json.dump(config_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(f"設定を保存しました: {save_path}")

        except Exception as e:
            self.logger.error(f"設定保存エラー: {e}")
            raise

    def _config_to_dict(self, config: EnhancedConfiguration) -> Dict[str, Any]:
        """EnhancedConfigurationを辞書に変換"""
        return {
            "environment": config.environment.value,
            "debug": config.debug,
            "log_level": config.log_level,
            "github": {
                "token": config.github.token,
                "repo": config.github.repo,
                "api_base_url": config.github.api_base_url,
                "timeout": config.github.timeout,
                "max_retries": config.github.max_retries,
                "rate_limit_strategy": config.github.rate_limit_strategy,
            },
            "issue_templates": {
                name: {
                    "title_prefix": template.title_prefix,
                    "labels": template.labels,
                    "assignee": template.assignee,
                    "body_template": template.body_template,
                    "auto_create": template.auto_create,
                }
                for name, template in config.issue_templates.items()
            },
            "processing_rules": {
                "auto_create_threshold": config.processing_rules.auto_create_threshold,
                "batch_size": config.processing_rules.batch_size,
                "rate_limit_delay": config.processing_rules.rate_limit_delay,
                "max_concurrent_requests": config.processing_rules.max_concurrent_requests,
                "enable_duplicate_detection": config.processing_rules.enable_duplicate_detection,
                "enable_security_analysis": config.processing_rules.enable_security_analysis,
                "enable_terraform_analysis": config.processing_rules.enable_terraform_analysis,
            },
            "storage": {
                "backend": config.storage.backend,
                "connection_string": config.storage.connection_string,
                "cache_ttl": config.storage.cache_ttl,
                "backup_enabled": config.storage.backup_enabled,
                "backup_interval": config.storage.backup_interval,
                "cleanup_old_data_days": config.storage.cleanup_old_data_days,
            },
            "notifications": {
                "enabled": config.notifications.enabled,
                "webhook_url": config.notifications.webhook_url,
                "email_recipients": config.notifications.email_recipients,
                "notification_threshold": config.notifications.notification_threshold,
                "include_progress_reports": config.notifications.include_progress_reports,
            },
            "custom": config.custom,
        }

    def create_sample_config(self, path: Optional[Path] = None) -> Path:
        """サンプル設定ファイルを作成"""
        sample_path = path or Path("github-review-prompts.sample.yml")

        sample_config = EnhancedConfiguration()
        sample_config.github.token = "${GITHUB_TOKEN}"
        sample_config.github.repo = "username/repository"

        # サンプル設定を保存
        config_dict = self._config_to_dict(sample_config)

        # コメント付きのサンプル設定を生成
        sample_content = f"""# GitHub Review Prompts Configuration
#
# この設定ファイルはCodeRabbitアドバイスに基づいて最適化されています
#
# 環境: {sample_config.environment.value}
# 作成日時: {datetime.now().isoformat()}

# 基本設定
environment: {sample_config.environment.value}
debug: false
log_level: INFO

# GitHub設定
github:
  token: ${{GITHUB_TOKEN}}  # 環境変数から取得
  repo: "username/repository"
  api_base_url: "https://api.github.com"
  timeout: 30
  max_retries: 3
  rate_limit_strategy: "adaptive"  # exponential_backoff, fixed_delay, adaptive, batch_processing

# Issue テンプレート設定
issue_templates:
  security:
    title_prefix: "[Security]"
    labels: ["security", "terraform", "high-priority"]
    assignee: "username"
    auto_create: true
    body_template: |
      ## 🔒 セキュリティ問題

      **ファイル**: {{file_path}}
      **行番号**: {{line_number}}
      **重要度**: {{priority}}

      ### 問題の詳細
      {{comment_body}}

      ### 推奨対応
      {{recommended_actions}}

  syntax_error:
    title_prefix: "[Syntax Error]"
    labels: ["bug", "terraform", "urgent"]
    assignee: "username"
    auto_create: true
    body_template: |
      ## 🚨 構文エラー

      **ファイル**: {{file_path}}
      **行番号**: {{line_number}}

      ### エラー内容
      {{comment_body}}

# 処理ルール設定
processing_rules:
  auto_create_threshold: "medium"  # critical, high, medium, low
  batch_size: 10
  rate_limit_delay: 1.0
  max_concurrent_requests: 5
  enable_duplicate_detection: true
  enable_security_analysis: true
  enable_terraform_analysis: true

# ストレージ設定
storage:
  backend: "file"  # file, sqlite, postgresql
  connection_string: ""
  cache_ttl: 3600
  backup_enabled: true
  backup_interval: 86400
  cleanup_old_data_days: 30

# 通知設定
notifications:
  enabled: false
  webhook_url: ""
  email_recipients: []
  notification_threshold: "high"
  include_progress_reports: true

# カスタム設定
custom:
  # プロジェクト固有の設定をここに追加
  project_name: "My Terraform Project"
  team: "Infrastructure Team"

# 環境固有の設定（オプション）
environments:
  development:
    debug: true
    log_level: DEBUG
    processing_rules:
      auto_create_threshold: "low"

  production:
    debug: false
    log_level: WARNING
    processing_rules:
      auto_create_threshold: "high"
    notifications:
      enabled: true
"""

        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(sample_content)

        self.logger.info(f"サンプル設定ファイルを作成しました: {sample_path}")
        return sample_path

    def get_issue_template(self, template_name: str) -> Optional[IssueTemplateConfig]:
        """指定されたIssueテンプレートを取得"""
        return self.config.issue_templates.get(template_name)

    def should_auto_create_issue(self, priority: str) -> bool:
        """優先度に基づいてIssueを自動作成すべきかを判定"""
        priority_levels = ["low", "medium", "high", "critical"]
        threshold_index = priority_levels.index(
            self.config.processing_rules.auto_create_threshold
        )
        priority_index = priority_levels.index(priority.lower())

        return priority_index >= threshold_index

    def get_config_summary(self) -> Dict[str, Any]:
        """設定のサマリーを取得"""
        return {
            "config_path": str(self.config_path),
            "environment": self.config.environment.value,
            "github_repo": self.config.github.repo,
            "has_github_token": bool(self.config.github.token),
            "issue_templates_count": len(self.config.issue_templates),
            "auto_create_threshold": self.config.processing_rules.auto_create_threshold,
            "storage_backend": self.config.storage.backend,
            "notifications_enabled": self.config.notifications.enabled,
        }
