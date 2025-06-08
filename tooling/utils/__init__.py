"""
Utility modules for tooling scripts.

This package provides shared utilities for common operations:
- git_utils: Git command execution and repository operations
- version_utils: Semantic version parsing and manipulation
- changelog_utils: Changelog parsing, generation, and validation
- async utilities: Async file and git operations for performance
"""

# File utilities
from .file_utils import (
    extract_yaml_value,
    extract_toml_value,
    update_version_in_file,
    extract_changelog_section,
    cleanup_temp_files,
    ensure_executable,
    update_all_versions,
    update_yaml_version,
    find_files_by_pattern
)

# Git utilities
from .git_utils import (
    GitOperations,
    GitCommandResult,
    GitError,
    NotGitRepositoryError,
    check_git_repo,
    check_git_state,
    check_remote_sync,
    get_current_branch,
    get_git_root,
    has_uncommitted_changes,
    get_latest_tag,
    get_commits_since_tag,
    get_staged_files,
    get_staged_diff,
    get_diff_for_files,
    create_tag,
    push_tag,
    get_commit_messages_since_tag,
    get_remote_url,
    get_commits_since_branch,
    get_changed_files
)

# Version utilities
from .version_utils import (
    # Core classes
    SemanticVersion,
    VersionExtractor,
    VersionUpdater,
    VersionComponent,
    VersionError,
    InvalidVersionError,
    # Functions
    parse_version,
    format_version,
    increment_version,
    validate_version,
    compare_versions,
    parse_version_tuple,
    get_version_from_file,
    update_version_in_file as update_version_in_file_v2  # Avoid name collision
)

# Changelog utilities
from .changelog_utils import (
    # Core classes
    ChangelogSection,
    ChangelogEntry,
    ChangelogVersion,
    Changelog,
    ChangelogParser,
    ChangelogGenerator,
    ChangelogValidator,
    ChangelogError,
    InvalidChangelogError,
    # Functions
    parse_changelog,
    extract_version_content,
    validate_changelog_file,
    extract_changelog_section as extract_changelog_section_v2,  # Avoid name collision
    validate_changelog_format
)

# Changelog submodule
from .changelog import (
    # From git_operations
    ChangelogGitOps
)

# Import models from core
from tooling.core.models import (
    AnalysisMode,
    AnalysisMetrics,
    ConventionalCommit,
    GitCommit,
    VersionEntry,
    CHANGELOG_SECTIONS,
    CONVENTIONAL_TYPES
)

# Async utilities
from .async_file_utils import (
    AsyncFileOperations,
    AsyncJSONOperations,
    AsyncYAMLOperations,
    FileBatchProcessor,
    read_files_async,
    write_files_async,
    process_directory_async
)

from .async_git_utils import (
    AsyncGitOperations,
    AsyncGitResult,
    GitBatchProcessor,
    get_commits_async,
    get_files_content_async,
    analyze_commits_parallel
)

# Subprocess utilities
from .subprocess_helper import (
    run_cli_tool,
    call_tool
)

# Prompt utilities
from .prompts import (
    PromptTemplates,
    PromptBuilder
)

# Package utilities
from .package_utils import (
    PackageNames,
    detect_package_names,
    get_package_info,
    PackageInfo
)

__all__ = [
    # File utilities
    'extract_yaml_value',
    'extract_toml_value',
    'update_version_in_file',
    'extract_changelog_section',
    'cleanup_temp_files',
    'ensure_executable',
    'update_all_versions',
    'update_yaml_version',
    'find_files_by_pattern',
    
    # Git utilities
    'GitOperations',
    'GitCommandResult',
    'GitError',
    'NotGitRepositoryError',
    'check_git_repo',
    'check_git_state',
    'check_remote_sync',
    'get_current_branch',
    'get_git_root',
    'has_uncommitted_changes',
    'get_latest_tag',
    'get_commits_since_tag',
    'get_staged_files',
    'get_staged_diff',
    'get_diff_for_files',
    'create_tag',
    'push_tag',
    'get_commit_messages_since_tag',
    'get_remote_url',
    'get_commits_since_branch',
    'get_changed_files',
    
    # Version utilities
    'SemanticVersion',
    'VersionExtractor',
    'VersionUpdater',
    'VersionComponent',
    'VersionError',
    'InvalidVersionError',
    'parse_version',
    'format_version',
    'increment_version',
    'validate_version',
    'compare_versions',
    'parse_version_tuple',
    'get_version_from_file',
    'update_version_in_file_v2',
    
    # Changelog utilities
    'ChangelogSection',
    'ChangelogEntry',
    'ChangelogVersion',
    'Changelog',
    'ChangelogParser',
    'ChangelogGenerator',
    'ChangelogValidator',
    'ChangelogError',
    'InvalidChangelogError',
    'parse_changelog',
    'extract_version_content',
    'validate_changelog_file',
    'extract_changelog_section_v2',
    'validate_changelog_format',
    
    # Changelog submodule
    'ChangelogGitOps',
    
    # Models from core
    'AnalysisMode',
    'AnalysisMetrics',
    'ConventionalCommit',
    'GitCommit',
    'VersionEntry',
    'CHANGELOG_SECTIONS',
    'CONVENTIONAL_TYPES',
    
    # Async utilities
    'AsyncFileOperations',
    'AsyncJSONOperations',
    'AsyncYAMLOperations',
    'FileBatchProcessor',
    'read_files_async',
    'write_files_async',
    'process_directory_async',
    'AsyncGitOperations',
    'AsyncGitResult',
    'GitBatchProcessor',
    'get_commits_async',
    'get_files_content_async',
    'analyze_commits_parallel',
    
    # Subprocess utilities
    'run_cli_tool',
    'call_tool',
    
    # Prompt utilities
    'PromptTemplates',
    'PromptBuilder',
    
    # Package utilities
    'PackageNames',
    'PackageInfo',
    'detect_package_names',
    'get_package_info',
] 