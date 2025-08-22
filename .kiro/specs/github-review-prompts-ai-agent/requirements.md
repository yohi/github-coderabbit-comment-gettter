# Requirements Document

## Introduction

This feature enhances the existing GitHub review prompts extraction tool to create AI agent-optimized prompts from CodeRabbit PR reviews. The tool will extract unresolved review comments, format them with appropriate personas and context, and generate structured prompts that guide AI agents to carefully evaluate and respond to each review comment individually while considering the possibility of incorrect or unnecessary suggestions.

## Requirements

### Requirement 1

**User Story:** As a developer, I want to extract CodeRabbit review comments from GitHub PRs and convert them into AI agent prompts, so that I can efficiently address review feedback with AI assistance.

#### Acceptance Criteria

1. WHEN a GitHub PR URL is provided THEN the system SHALL extract all unresolved CodeRabbit review comments
2. WHEN extracting comments THEN the system SHALL use GitHub's GraphQL API to accurately determine resolution status
3. WHEN a comment is marked as resolved THEN the system SHALL exclude it from the output
4. WHEN comments are found THEN the system SHALL preserve the original comment content and location information

### Requirement 2

**User Story:** As a developer, I want AI agent prompts to include appropriate personas and context, so that the AI can provide more accurate and contextually relevant responses.

#### Acceptance Criteria

1. WHEN generating prompts THEN the system SHALL include a clear persona definition for the AI agent
2. WHEN formatting prompts THEN the system SHALL include file path and line number context
3. WHEN creating prompts THEN the system SHALL emphasize the need for careful evaluation of suggestions
4. WHEN outputting prompts THEN the system SHALL include instructions for handling incorrect or unnecessary comments

### Requirement 3

**User Story:** As a developer, I want the AI agent to process review comments one at a time, so that each comment receives focused attention and reduces the risk of overlooking important details.

#### Acceptance Criteria

1. WHEN generating prompts THEN the system SHALL structure output to encourage sequential processing
2. WHEN formatting instructions THEN the system SHALL explicitly state that comments should be addressed individually
3. WHEN creating prompts THEN the system SHALL include clear separation between different review comments
4. WHEN outputting instructions THEN the system SHALL discourage batch processing of multiple comments

### Requirement 4

**User Story:** As a developer, I want the AI agent to provide justification for rejecting review comments, so that I can understand the reasoning and maintain code quality standards.

#### Acceptance Criteria

1. WHEN generating prompts THEN the system SHALL include instructions for documenting rejection reasons
2. WHEN formatting output THEN the system SHALL provide a template for rejection responses
3. WHEN creating instructions THEN the system SHALL require explanation of why a comment was deemed incorrect or unnecessary
4. WHEN outputting prompts THEN the system SHALL include examples of proper rejection documentation

### Requirement 5

**User Story:** As a developer, I want to use Python 3.13 with uv for virtual environment management, so that I can maintain consistent and modern development practices.

#### Acceptance Criteria

1. WHEN setting up the project THEN the system SHALL use Python 3.13 as the target version
2. WHEN managing dependencies THEN the system SHALL use uv for virtual environment management
3. WHEN configuring the project THEN the system SHALL include appropriate pyproject.toml configuration
4. WHEN installing dependencies THEN the system SHALL use uv for package management

### Requirement 6

**User Story:** As a developer, I want enhanced accuracy in comment resolution detection, so that I don't waste time on already-addressed issues.

#### Acceptance Criteria

1. WHEN checking comment resolution status THEN the system SHALL prioritize GraphQL API results over heuristic methods
2. WHEN GraphQL API is unavailable THEN the system SHALL fall back to REST API methods
3. WHEN resolution status is uncertain THEN the system SHALL err on the side of inclusion rather than exclusion
4. WHEN processing comments THEN the system SHALL handle pagination for large PRs with many comments

### Requirement 7

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can troubleshoot issues and understand the tool's behavior.

#### Acceptance Criteria

1. WHEN API calls fail THEN the system SHALL provide clear error messages with context
2. WHEN processing comments THEN the system SHALL log progress and statistics
3. WHEN encountering malformed data THEN the system SHALL continue processing other comments
4. WHEN debugging is needed THEN the system SHALL provide detailed diagnostic information

### Requirement 8

**User Story:** As a developer, I want flexible output options, so that I can integrate the tool into different workflows.

#### Acceptance Criteria

1. WHEN generating output THEN the system SHALL support both console and file output
2. WHEN saving to file THEN the system SHALL use UTF-8 encoding for international character support
3. WHEN formatting output THEN the system SHALL use clear markdown structure
4. WHEN no prompts are found THEN the system SHALL provide informative feedback rather than empty output