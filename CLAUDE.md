# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitHub Review Prompts AI Agent (v2.0.0) extracts AI agent-optimized prompts from GitHub PR review comments, specifically focusing on CodeRabbit comments. It's a production-ready Python tool with comprehensive security features, staged execution strategies, and multi-persona support.

## Development Environment Setup

### Package Management
This project uses **uv** for modern Python dependency management:

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --dev

# Run commands with uv
uv run grp <PR_URL>                    # Lightweight version
uv run github-review-prompts <PR_URL>  # Full-featured version
```

### Environment Variables
```bash
# Required
export GITHUB_TOKEN="your_github_token_here"  # Personal access token

# Optional
export DEFAULT_OUTPUT_FORMAT="markdown"
export DEFAULT_PERSONA="code-reviewer"
export LOG_LEVEL="INFO"
```

## Testing

### Running Tests
```bash
# All tests
uv run pytest

# Specific test module
uv run pytest src/github_review_prompts/tests/test_coderabbit_filter.py

# Test with coverage
uv run pytest --cov=src/github_review_prompts

# Single test function
uv run pytest -k "test_specific_function_name"

# Tests with real PR data (requires GITHUB_TOKEN)
uv run pytest src/github_review_prompts/tests/test_real_pr_processing.py
```

### Development Testing
The project includes comprehensive test suites:
- `conftest.py` - Auto-mocks GITHUB_TOKEN for testing
- `test_*` files in `src/github_review_prompts/tests/` - Unit tests
- Root-level `test_*.py` files - Integration and validation tests
- `production_validation_test.py` - Production readiness validation

## Code Quality Tools

### Linting and Formatting
```bash
# Black formatting (line length: 88, target: py313)
uv run black src/

# Import sorting with isort
uv run isort src/

# Ruff linting
uv run ruff check src/

# Type checking with mypy
uv run mypy src/github_review_prompts/
```

### Build and Distribution
```bash
# Build wheel package
uv build

# Install from local wheel
uvx --from ./dist/github_review_prompts_ai_agent-2.0.0-py3-none-any.whl grp
```

## Architecture Overview

### Core Components

**Entry Points (3 CLI interfaces):**
- `main.py` - Full-featured CLI with advanced options, persona support, detailed analysis
- `unified_cli.py` - Unified interface combining all features
- `grp_uvx.py` - Lightweight version for quick analysis

**Core Engine:**
- `core/prompt_engine.py` - UnifiedPromptEngine with staged execution strategies for handling 20-100+ comments
- `github_client.py` - GitHub API client (REST + GraphQL) with rate limiting and authentication
- `comment_processor.py` - Comment analysis and filtering engine
- `comment_thread_processor.py` - Thread context analysis and resolution detection

**Processing Pipeline:**
1. **URL Parsing** (`utils/parsers.py`) - Extract owner/repo/PR from GitHub URLs
2. **Authentication** (`utils/validators.py`) - Token validation and security checks
3. **Data Fetching** (`github_client.py`) - GraphQL preferred, REST as fallback
4. **Comment Filtering** (`utils/smart_comment_filter.py`) - CodeRabbit-specific filtering
5. **Thread Processing** (`comment_thread_processor.py`) - Multi-comment conversation handling
6. **Classification** (`utils/priority_classifier.py`) - Security/improvement/style categorization
7. **Prompt Generation** (`prompt_generator.py`) - AI agent-optimized output
8. **Output Formatting** (`output_formatter.py`) - Markdown/JSON formatting with statistics

### Key Features Implementation

**Staged Execution Strategy** (`core/prompt_engine.py`):
- Phase 1: 🔴 Critical (security, system failures)
- Phase 2: 🟡 Important (functionality, quality)
- Phase 3: 🟢 Low priority (documentation, style)

**Security-First Design** (`utils/validators.py`, `github_client.py`):
- Token leak prevention
- Secure API request handling
- Environment variable validation

**Outside Diff Handling** (`utils/outside_diff_parser.py`):
- Parses comments on code outside diff hunks
- Maintains proper file/line context
- GraphQL-based precise location detection

## Important Patterns and Conventions

### Import Strategy
The codebase uses conditional imports for both direct execution and module import:
```python
if __name__ == "__main__":
    # Direct execution - absolute imports
    from config import ConfigManager
else:
    # Module import - relative imports
    from .config import ConfigManager
```

### Error Handling
Custom exceptions in `models.py`:
- `APIError` - General API issues
- `AuthenticationError` - Token problems
- `RateLimitError` - GitHub rate limits

### Configuration Management
- `config.py` - ConfigManager for YAML-based configuration
- `github-review-prompts.sample.yml` - Configuration template
- Environment variable precedence over config files

### Output Formats
The tool generates two main outputs:
1. **Console Output** - Colored statistics with comment type breakdown
2. **File Output** - AI agent prompts (Markdown) with embedded metadata

### Comment Type Classification
Comments are automatically classified into:
- Outside Diff, Potential Issue, Refactor Suggestion
- Committable Suggestion, Nitpick, Verification
- Analysis Chain, Other

## Testing with Real Data

Many tests use actual GitHub PR data. The `conftest.py` automatically mocks the GITHUB_TOKEN, but for integration tests:

```bash
# Set real token for integration tests
export GITHUB_TOKEN="ghp_your_real_token"
uv run pytest src/github_review_prompts/tests/test_real_pr_processing.py
```

## Security Considerations

- **Never commit GitHub tokens** - Use environment variables only
- **Token format validation** - Must start with `ghp_` or `github_pat_`
- **Secure curl generation** - Uses temporary header files for API calls
- **Content sanitization** - All user inputs are validated and sanitized

This codebase implements a sophisticated comment processing pipeline with enterprise-grade security and production monitoring capabilities.
