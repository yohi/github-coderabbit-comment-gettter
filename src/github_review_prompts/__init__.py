"""GitHub Review Prompts AI Agent

AI agent-optimized prompts extraction from GitHub PR review comments.
"""

__version__ = "1.4.1"
__author__ = "yohi"
__email__ = "yohi@example.com"

from .models import (
    ReviewComment,
    AIPrompt,
    Configuration,
    ProcessingStats,
    GitHubPRInfo,
    PersonaConfig,
    PERSONAS,
    OutsideDiffComment,
    OutsideDiffCommentCategory,
    OutsideDiffCommentSeverity,
)
from .github_client import GitHubClient
from .comment_processor import CommentProcessor
from .prompt_generator import AIPromptGenerator
from .output_formatter import OutputFormatter
from .config import ConfigManager
from .cli import CLIInterface
from .utils.resolution_master import ResolutionMasterController
from .utils.coderabbit_enhanced_system import CodeRabbitEnhancedSystem
from .utils.enhanced_config import EnhancedConfigManager
from .utils.priority_classifier import EnhancedPriorityClassifier
from .utils.database_tracker import DatabaseProgressTracker
from .utils.enhanced_github_manager import EnhancedGitHubIssueManager

__all__ = [
    # Data models
    "ReviewComment",
    "AIPrompt",
    "Configuration",
    "ProcessingStats",
    "GitHubPRInfo",
    "PersonaConfig",
    "PERSONAS",
    "OutsideDiffComment",
    "OutsideDiffCommentCategory",
    "OutsideDiffCommentSeverity",
    # Resolution tracking classes
    "ResolutionMasterController",
    # CodeRabbit enhanced classes
    "CodeRabbitEnhancedSystem",
    "EnhancedConfigManager",
    "EnhancedPriorityClassifier",
    "DatabaseProgressTracker",
    "EnhancedGitHubIssueManager",
    # Core classes
    "GitHubClient",
    "CommentProcessor",
    "AIPromptGenerator",
    "OutputFormatter",
    "ConfigManager",
    "CLIInterface",
]
