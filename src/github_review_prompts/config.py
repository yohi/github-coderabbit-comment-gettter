"""設定管理モジュール"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from .models import Configuration


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._config: Optional[Configuration] = None
        self.logger = logging.getLogger(__name__)
    
    def load_config(self) -> Configuration:
        """設定を読み込み"""
        if self._config is not None:
            return self._config
        
        config_data = self._load_from_env()
        
        # 設定ファイルがあれば読み込み
        if self.config_file and Path(self.config_file).exists():
            try:
                file_config = self._load_from_file(self.config_file)
                # 環境変数を優先してマージ
                config_data.update({k: v for k, v in file_config.items() if k not in config_data or config_data[k] is None})
            except Exception as e:
                self.logger.warning(f"設定ファイル読み込みエラー: {e}")
        
        # デフォルト設定ファイルも確認
        default_config_paths = [
            ".github-review-prompts.yml",
            os.path.expanduser("~/.github-review-prompts.yml"),
            "/etc/github-review-prompts.yml"
        ]
        
        for config_path in default_config_paths:
            if Path(config_path).exists():
                try:
                    file_config = self._load_from_file(config_path)
                    # 既存の設定を優先してマージ
                    config_data.update({k: v for k, v in file_config.items() if k not in config_data or config_data[k] is None})
                    break
                except Exception as e:
                    self.logger.debug(f"設定ファイル {config_path} 読み込み失敗: {e}")
        
        self._config = Configuration(**config_data)
        return self._config
    
    def _load_from_env(self) -> Dict[str, Any]:
        """環境変数から設定を読み込み"""
        return {
            "github_token": os.environ.get("GITHUB_TOKEN"),
            "output_format": os.environ.get("DEFAULT_OUTPUT_FORMAT", "markdown"),
            "persona": os.environ.get("DEFAULT_PERSONA", "code-reviewer"),
            "include_resolved": os.environ.get("INCLUDE_RESOLVED", "false").lower() == "true",
            "debug_mode": os.environ.get("DEBUG_MODE", "false").lower() == "true",
            "rate_limit_delay": float(os.environ.get("RATE_LIMIT_DELAY", "1.0")),
            "max_retries": int(os.environ.get("MAX_RETRIES", "3")),
            "output_file": os.environ.get("DEFAULT_OUTPUT_FILE"),
            "max_concurrent_requests": int(os.environ.get("MAX_CONCURRENT_REQUESTS", "5")),
            "cache_duration": int(os.environ.get("CACHE_DURATION", "300")),
        }
    
    def _load_from_file(self, config_path: str) -> Dict[str, Any]:
        """設定ファイルから読み込み"""
        config_data = {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            file_data = yaml.safe_load(f)
        
        if not isinstance(file_data, dict):
            return config_data
        
        # GitHub設定
        github_config = file_data.get("github", {})
        if "token" in github_config:
            config_data["github_token"] = github_config["token"]
        
        # 出力設定
        output_config = file_data.get("output", {})
        if "format" in output_config:
            config_data["output_format"] = output_config["format"]
        if "default_file" in output_config:
            config_data["output_file"] = output_config["default_file"]
        
        # ペルソナ設定
        personas_config = file_data.get("personas", {})
        if "default" in personas_config:
            config_data["persona"] = personas_config["default"]
        
        # 処理設定
        processing_config = file_data.get("processing", {})
        if "include_resolved" in processing_config:
            config_data["include_resolved"] = processing_config["include_resolved"]
        if "max_concurrent_requests" in processing_config:
            config_data["max_concurrent_requests"] = processing_config["max_concurrent_requests"]
        if "cache_duration" in processing_config:
            config_data["cache_duration"] = processing_config["cache_duration"]
        
        return config_data
    
    def validate_token(self, token: str) -> bool:
        """GitHub トークンの基本的な検証"""
        if not token:
            return False
        
        # GitHub personal access tokenの基本的なパターンチェック
        if not (token.startswith("ghp_") or token.startswith("github_pat_")):
            # classic tokenの場合は40文字の16進数
            if len(token) == 40 and all(c in "0123456789abcdef" for c in token.lower()):
                return True
            return False
        
        # fine-grained personal access tokenの場合
        if token.startswith("github_pat_"):
            return len(token) > 40
        
        # personal access token (classic)の場合
        if token.startswith("ghp_"):
            return len(token) == 40
        
        return False
    
    def setup_logging(self, level: Optional[str] = None, format_str: Optional[str] = None) -> None:
        """ログ設定のセットアップ"""
        log_level = level or os.environ.get("LOG_LEVEL", "INFO")
        log_format = format_str or os.environ.get("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # requests ライブラリのログレベルを下げる
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)