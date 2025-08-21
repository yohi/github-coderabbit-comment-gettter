"""入力検証ユーティリティ"""

import re
import os
from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import urlparse


def validate_pr_url(url: str) -> bool:
    """GitHub プルリクエストURLの検証"""
    if not url or not isinstance(url, str):
        return False
    
    # 基本的なURL形式の検証
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        
        if parsed.hostname != "github.com":
            return False
        
        # プルリクエストURLのパターンマッチ
        pr_pattern = r"^/([^/]+)/([^/]+)/pull/(\d+)/?$"
        match = re.match(pr_pattern, parsed.path)
        
        if not match:
            return False
        
        owner, repo, pull_number = match.groups()
        
        # 基本的な文字列検証
        if not owner or not repo or not pull_number:
            return False
        
        # プルリクエスト番号が有効な範囲内か
        try:
            pr_num = int(pull_number)
            if pr_num <= 0 or pr_num > 999999:
                return False
        except ValueError:
            return False
        
        return True
        
    except Exception:
        return False


def sanitize_content(content: str, max_length: int = 10000) -> str:
    """コンテンツのサニタイズ"""
    if not isinstance(content, str):
        return ""
    
    # 制御文字を除去（改行・タブは保持）
    sanitized = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', content)
    
    # 長すぎる場合は切り詰め
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized.strip()


def validate_file_path(file_path: str, allow_create: bool = True) -> bool:
    """ファイルパスの検証（ディレクトリトラバーサル攻撃の防止）"""
    if not file_path or not isinstance(file_path, str):
        return False
    
    try:
        # パスを正規化
        normalized_path = Path(file_path).resolve()
        
        # 現在のディレクトリを基準とした相対パス
        current_dir = Path.cwd().resolve()
        
        # ディレクトリトラバーサル攻撃の検出
        try:
            normalized_path.relative_to(current_dir)
        except ValueError:
            # 現在のディレクトリ外へのアクセスを禁止
            return False
        
        # 危険なパスパターンをチェック
        dangerous_patterns = [
            "..",
            "/etc/",
            "/proc/",
            "/sys/",
            "~",
        ]
        
        path_str = str(normalized_path).lower()
        for pattern in dangerous_patterns:
            if pattern in path_str:
                return False
        
        # ファイル作成が許可されていない場合、存在チェック
        if not allow_create and not normalized_path.exists():
            return False
        
        # 親ディレクトリが存在するか、作成可能かチェック
        parent_dir = normalized_path.parent
        if not parent_dir.exists():
            try:
                # 親ディレクトリの作成を試行（実際には作成しない）
                if not allow_create:
                    return False
            except (OSError, PermissionError):
                return False
        
        return True
        
    except (OSError, ValueError, PermissionError):
        return False


def validate_github_token(token: str) -> Tuple[bool, Optional[str]]:
    """GitHub トークンの詳細検証"""
    if not token or not isinstance(token, str):
        return False, "トークンが空です"
    
    token = token.strip()
    
    # Classic personal access token (40文字の16進数)
    if len(token) == 40 and re.match(r"^[a-f0-9]{40}$", token.lower()):
        return True, "classic"
    
    # Personal access token (ghp_ prefix)
    if token.startswith("ghp_") and len(token) == 40:
        return True, "personal"
    
    # Fine-grained personal access token (github_pat_ prefix)
    if token.startswith("github_pat_") and len(token) > 40:
        return True, "fine-grained"
    
    # GitHub App token (ghs_ prefix)
    if token.startswith("ghs_") and len(token) > 40:
        return True, "app"
    
    return False, f"無効なトークン形式: {token[:10]}..."


def validate_persona(persona: str) -> bool:
    """ペルソナ名の検証"""
    valid_personas = {"code-reviewer", "security-analyst", "performance-optimizer"}
    return persona in valid_personas


def validate_output_format(output_format: str) -> bool:
    """出力フォーマットの検証"""
    valid_formats = {"markdown", "json"}
    return output_format in valid_formats