"""データモデルと型定義"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, ConfigDict


@dataclass
class ReviewComment:
    """GitHub レビューコメントのデータクラス"""

    id: int
    body: str
    path: str
    line: Optional[int] = None
    original_line: Optional[int] = None
    author: str = ""
    created_at: str = ""
    updated_at: str = ""
    html_url: str = ""
    is_resolved: bool = False
    ai_prompt: Optional[str] = None
    context: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.context is None:
            self.context = {}


class AIPrompt(BaseModel):
    """AI用プロンプトのデータモデル"""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    content: str = Field(..., min_length=1, description="プロンプトの内容")
    location: str = Field(..., description="コメントの場所（ファイルパス:行番号など）")
    file_path: str = Field(..., description="ファイルパス")
    line_number: Optional[int] = Field(None, description="行番号")
    comment_id: int = Field(..., description="コメントID")
    author: str = Field(default="", description="コメント作成者")
    priority: str = Field(
        default="medium", description="優先度", pattern="^(high|medium|low)$"
    )
    category: str = Field(
        default="general",
        description="カテゴリ",
        pattern="^(security|performance|style|logic|general)$",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="追加のコンテキスト情報"
    )


class Configuration(BaseModel):
    """設定データモデル"""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    github_token: Optional[str] = Field(None, description="GitHub APIトークン")
    output_format: str = Field(
        default="markdown", description="出力フォーマット", pattern="^(markdown|json)$"
    )
    persona: str = Field(
        default="code-reviewer",
        description="AIエージェントのペルソナ",
        pattern="^(code-reviewer|security-analyst|performance-optimizer)$",
    )
    include_resolved: bool = Field(
        default=False, description="解決済みコメントを含める"
    )
    debug_mode: bool = Field(default=False, description="デバッグモード")
    rate_limit_delay: float = Field(
        default=1.0, ge=0.1, le=10.0, description="APIレート制限の遅延（秒）"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="API リトライの最大回数"
    )
    output_file: Optional[str] = Field(None, description="出力ファイルパス")
    max_concurrent_requests: int = Field(
        default=5, ge=1, le=20, description="並行リクエストの最大数"
    )
    cache_duration: int = Field(
        default=300, ge=0, le=3600, description="キャッシュ期間（秒）"
    )


class ProcessingStats(BaseModel):
    """処理統計データモデル"""

    model_config = ConfigDict(extra="forbid")

    total_comments: int = Field(default=0, ge=0, description="総コメント数")
    resolved_comments: int = Field(default=0, ge=0, description="解決済みコメント数")
    unresolved_comments: int = Field(default=0, ge=0, description="未解決コメント数")
    non_coderabbit_comments: int = Field(
        default=0, ge=0, description="CodeRabbit以外のコメント数"
    )
    prompts_extracted: int = Field(
        default=0, ge=0, description="抽出されたプロンプト数"
    )
    processing_time: float = Field(default=0.0, ge=0.0, description="処理時間（秒）")
    api_calls: int = Field(default=0, ge=0, description="API呼び出し数")
    errors: List[str] = Field(default_factory=list, description="エラーリスト")


class GitHubPRInfo(BaseModel):
    """GitHub プルリクエスト情報"""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    owner: str = Field(..., min_length=1, description="リポジトリオーナー")
    repo: str = Field(..., min_length=1, description="リポジトリ名")
    pull_number: int = Field(..., gt=0, description="プルリクエスト番号")
    url: str = Field(..., description="プルリクエストURL")


class PersonaConfig(BaseModel):
    """ペルソナ設定"""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., description="役割")
    expertise: str = Field(..., description="専門分野")
    approach: str = Field(..., description="アプローチ方法")
    tone: str = Field(..., description="トーン")
    instructions: List[str] = Field(default_factory=list, description="特別な指示")


# ペルソナ定義
PERSONAS: Dict[str, PersonaConfig] = {
    "code-reviewer": PersonaConfig(
        role="Senior Software Engineer and Code Reviewer",
        expertise="Code quality, security, performance, and best practices",
        approach="Methodical analysis with focus on maintainability and correctness",
        tone="Professional, constructive, and detail-oriented",
        instructions=[
            "Focus on code maintainability and readability",
            "Consider performance implications",
            "Evaluate security aspects",
            "Suggest best practices and design patterns",
        ],
    ),
    "security-analyst": PersonaConfig(
        role="Application Security Specialist",
        expertise="Security vulnerabilities, threat modeling, and secure coding practices",
        approach="Security-first evaluation with risk assessment",
        tone="Cautious, thorough, and security-focused",
        instructions=[
            "Identify potential security vulnerabilities",
            "Assess risk levels and impact",
            "Recommend secure coding practices",
            "Consider OWASP Top 10 and common attack vectors",
        ],
    ),
    "performance-optimizer": PersonaConfig(
        role="Performance Engineering Specialist",
        expertise="Code optimization, scalability, and resource efficiency",
        approach="Performance-centric analysis with benchmarking mindset",
        tone="Analytical, metrics-driven, and optimization-focused",
        instructions=[
            "Identify performance bottlenecks",
            "Suggest optimization strategies",
            "Consider memory and CPU usage",
            "Evaluate scalability implications",
        ],
    ),
}


class APIError(Exception):
    """API関連のエラー"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(APIError):
    """認証エラー"""

    pass


class RateLimitError(APIError):
    """レート制限エラー"""

    pass


class ValidationError(Exception):
    """データ検証エラー"""

    pass


class ProcessingError(Exception):
    """処理エラー"""

    pass
