#!/usr/bin/env python3
"""
Enhanced configuration module using Pydantic for validation and settings management.
This module provides structured configuration with type safety and validation.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

from typing import Optional, Dict, Any
from pathlib import Path
import os

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class BaseToolConfig(BaseSettings):
    """Base configuration for all tools with validation and type safety"""
    
    # Common settings
    debug: bool = Field(False, env='TOOL_DEBUG', description="Enable debug mode")
    log_level: str = Field('INFO', env='LOG_LEVEL', description="Logging level")
    timeout: int = Field(30, env='TOOL_TIMEOUT', ge=1, le=600, description="Default timeout in seconds")
    
    # Git settings
    git_timeout: int = Field(30, env='GIT_TIMEOUT', ge=1, le=300, description="Git command timeout")
    default_branch: str = Field('main', env='DEFAULT_BRANCH', description="Default git branch")
    
    # AI settings
    ai_api_key: Optional[str] = Field(None, env='GEMINI_API_KEY', description="Gemini API key")
    ai_model: str = Field('gemini-2.5-pro-preview-05-06', env='GEMINI_MODEL', description="AI model to use")
    ai_timeout: int = Field(60, env='AI_TIMEOUT', ge=1, le=600, description="AI request timeout")
    
    # Paths
    project_root: Optional[Path] = Field(None, description="Project root directory")
    
    # Output formatting
    use_color: bool = Field(True, env='NO_COLOR', description="Use colored output")
    use_emoji: bool = Field(True, env='NO_EMOJI', description="Use emoji in output")
    json_output: bool = Field(False, env='JSON_OUTPUT', description="Output in JSON format")
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level is valid"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @validator('project_root', pre=True, always=True)
    def set_project_root(cls, v):
        """Set project root if not provided"""
        if v is None:
            # Try to find project root by looking for dart/pubspec.yaml
            current = Path.cwd()
            while current != current.parent:
                if (current / 'dart' / 'pubspec.yaml').exists():
                    return current
                current = current.parent
            # Fallback to current directory
            return Path.cwd()
        return Path(v) if isinstance(v, str) else v
    
    @validator('use_color', pre=True)
    def parse_no_color(cls, v, values):
        """Handle NO_COLOR environment variable"""
        # NO_COLOR env var means disable color when set to any value
        no_color = os.environ.get('NO_COLOR')
        if no_color is not None:
            return False
        return v
    
    def model_post_init(self, __context: Any) -> None:
        """Post-initialization setup"""
        # Normalize API key (check alternative env vars)
        if not self.ai_api_key:
            alt_key = os.environ.get('GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS')
            if alt_key:
                self.ai_api_key = alt_key
                os.environ['GEMINI_API_KEY'] = alt_key


class ChangelogConfig(BaseToolConfig):
    """Configuration for changelog-related tools"""
    
    # Changelog settings
    changelog_ai_model: str = Field('gemini-2.5-pro-preview-05-06', env='CHANGELOG_AI_MODEL')
    changelog_style: str = Field('keep-a-changelog', env='CHANGELOG_STYLE')
    include_pr_links: bool = Field(True, env='CHANGELOG_INCLUDE_PR_LINKS')
    include_author: bool = Field(True, env='CHANGELOG_INCLUDE_AUTHOR')
    group_by_type: bool = Field(True, env='CHANGELOG_GROUP_BY_TYPE')
    
    # Date range settings
    default_since_days: int = Field(30, env='CHANGELOG_SINCE_DAYS', ge=1, le=365)
    
    @validator('changelog_style')
    def validate_changelog_style(cls, v):
        """Validate changelog style"""
        valid_styles = ['keep-a-changelog', 'conventional', 'angular']
        if v not in valid_styles:
            raise ValueError(f"Invalid changelog style: {v}. Must be one of {valid_styles}")
        return v


class ReleaseConfig(BaseToolConfig):
    """Configuration for release-related tools"""
    
    # Release settings
    create_github_release: bool = Field(True, env='CREATE_GITHUB_RELEASE')
    github_token: Optional[str] = Field(None, env='GITHUB_TOKEN')
    draft_release: bool = Field(False, env='DRAFT_RELEASE')
    prerelease_pattern: str = Field(r'-(?:alpha|beta|rc)', env='PRERELEASE_PATTERN')
    
    # Version settings
    version_bump_default: str = Field('patch', env='VERSION_BUMP_DEFAULT')
    
    @validator('version_bump_default')
    def validate_version_bump(cls, v):
        """Validate version bump type"""
        valid_types = ['major', 'minor', 'patch']
        if v not in valid_types:
            raise ValueError(f"Invalid version bump type: {v}. Must be one of {valid_types}")
        return v


class CommitConfig(BaseToolConfig):
    """Configuration for commit-related tools"""
    
    # Commit message settings
    commit_style: str = Field('conventional', env='COMMIT_STYLE')
    max_subject_length: int = Field(72, env='COMMIT_MAX_SUBJECT_LENGTH', ge=50, le=100)
    require_issue_reference: bool = Field(False, env='COMMIT_REQUIRE_ISSUE')
    sign_commits: bool = Field(False, env='COMMIT_SIGN')
    
    # AI commit settings
    ai_analyze_depth: int = Field(3, env='COMMIT_AI_DEPTH', ge=1, le=10)
    ai_include_context: bool = Field(True, env='COMMIT_AI_CONTEXT')
    
    @validator('commit_style')
    def validate_commit_style(cls, v):
        """Validate commit style"""
        valid_styles = ['conventional', 'angular', 'atom', 'jira']
        if v not in valid_styles:
            raise ValueError(f"Invalid commit style: {v}. Must be one of {valid_styles}")
        return v


def load_config(config_class=BaseToolConfig, **overrides) -> BaseToolConfig:
    """
    Load configuration with overrides.
    
    Args:
        config_class: The configuration class to use
        **overrides: Keyword arguments to override configuration values
        
    Returns:
        Configured instance
    """
    # Load from environment and .env file
    config = config_class(**overrides)
    
    return config


# Backward compatibility helpers
def get_config_value(key: str, default: Any = None) -> Any:
    """Get a configuration value (backward compatibility)"""
    config = load_config()
    return getattr(config, key, default)


def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    config = load_config()
    return config.debug


def get_ai_config() -> Dict[str, Any]:
    """Get AI-related configuration"""
    config = load_config()
    return {
        'api_key': config.ai_api_key,
        'model': config.ai_model,
        'timeout': config.ai_timeout
    }