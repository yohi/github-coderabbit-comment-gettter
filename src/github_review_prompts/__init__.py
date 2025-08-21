"""GitHub Review Prompts AI Agent

AI agent-optimized prompts extraction from GitHub PR review comments.
"""

__version__ = "1.0.0"
__author__ = "yohi"
__email__ = "yohi@example.com"

from .models import (
    ReviewComment, 
    AIPrompt, 
    Configuration, 
    ProcessingStats,
    GitHubPRInfo,
    PersonaConfig,
    PERSONAS
)
from .github_client import GitHubClient
from .comment_processor import CommentProcessor
from .prompt_generator import AIPromptGenerator
from .output_formatter import OutputFormatter
from .config import ConfigManager
from .cli import CLIInterface

__all__ = [
    # Data models
    "ReviewComment", 
    "AIPrompt", 
    "Configuration", 
    "ProcessingStats",
    "GitHubPRInfo",
    "PersonaConfig",
    "PERSONAS",
    
    # Core classes
    "GitHubClient",
    "CommentProcessor", 
    "AIPromptGenerator",
    "OutputFormatter",
    "ConfigManager",
    "CLIInterface",
]