#!/usr/bin/env python3
"""
Base configuration classes using Pydantic for type-safe configuration management.

This module provides the foundational configuration infrastructure for all tooling scripts,
replacing the legacy common_config.py with modern, type-safe patterns.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.theme import Theme

# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PackageType(str, Enum):
    """Package types in the project"""
    ROOT = "root"
    DART = "dart"
    FLUTTER = "flutter"
    RUST = "rust"


# ============================================================================
# BASE SETTINGS
# ============================================================================

class BaseConfig(BaseSettings):
    """
    Base configuration for all tooling scripts.
    
    Environment variables are automatically loaded with the prefix "RUNTIME_FDR_"
    For example: RUNTIME_FDR_LOG_LEVEL=DEBUG
    """
    
    model_config = SettingsConfigDict(
        env_prefix="RUNTIME_FDR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Logging configuration
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_file: Optional[Path] = Field(default=None, description="Log file path")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    # Project paths (auto-detected)
    project_root: Path = Field(default_factory=lambda: BaseConfig._find_project_root())
    
    # Output configuration
    use_color: bool = Field(default=True, description="Enable colored output")
    quiet: bool = Field(default=False, description="Suppress non-essential output")
    verbose: bool = Field(default=False, description="Enable verbose output")
    
    # Performance settings
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    timeout: int = Field(default=30, ge=1, le=600, description="Command timeout in seconds")
    concurrent_operations: bool = Field(default=True, description="Enable concurrent operations")
    
    @staticmethod
    def _find_project_root() -> Path:
        """Find project root by looking for marker files"""
        current = Path.cwd().resolve()
        
        # Go up until we find dart/pubspec.yaml and flutter/pubspec.yaml
        while current != current.parent:
            if ((current / "dart" / "pubspec.yaml").exists() and 
                (current / "flutter" / "pubspec.yaml").exists()):
                return current
            current = current.parent
        
        # If not found, return current directory (will be validated later)
        return Path.cwd()
    
    @field_validator("project_root")
    def validate_project_root(cls, v: Path) -> Path:
        """Ensure project root is valid"""
        # Skip validation in test environment
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("_PYTEST_RAISE"):
            return v
        
        # Also skip if we're in a CI environment
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return v
        
        # Skip validation if --any flag is present (for global tools)
        if os.environ.get("RUNTIME_FDR_ANY_STRUCTURE") or os.environ.get("ANY_STRUCTURE"):
            return v
        
        dart_pubspec = v / "dart" / "pubspec.yaml"
        flutter_pubspec = v / "flutter" / "pubspec.yaml"
        
        if not dart_pubspec.exists() or not flutter_pubspec.exists():
            raise ValueError(
                f"Invalid project root: {v}. "
                "Must contain dart/pubspec.yaml and flutter/pubspec.yaml"
            )
        return v
    
    @model_validator(mode='before')
    def adjust_log_level(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust log level based on quiet/verbose flags"""
        if values.get("quiet"):
            values["log_level"] = LogLevel.ERROR
        elif values.get("verbose"):
            values["log_level"] = LogLevel.DEBUG
        return values
    
    @property
    def dart_dir(self) -> Path:
        """Get Dart package directory"""
        return self.project_root / "dart"
    
    @property
    def flutter_dir(self) -> Path:
        """Get Flutter package directory"""
        return self.project_root / "flutter"
    
    @property
    def rust_dir(self) -> Path:
        """Get Rust package directory"""
        return self.dart_dir / "rust"
    
    @property
    def console(self) -> Console:
        """Get configured Rich console"""
        if not hasattr(self, "_console"):
            theme = Theme({
                "success": "green",
                "error": "red",
                "warning": "yellow",
                "info": "blue",
                "debug": "dim",
                "header": "bold purple"
            })
            self._console = Console(
                theme=theme,
                force_terminal=True if self.use_color else None,
                no_color=not self.use_color,
                quiet=self.quiet
            )
        return self._console


# ============================================================================
# AI CONFIGURATION
# ============================================================================

class AIConfig(BaseConfig):
    """Configuration for AI-powered tools"""
    
    # Gemini configuration
    gemini_api_key: Optional[str] = Field(default=None)
    gemini_model: str = Field(
        default="gemini-2.5-pro-preview-05-06",
        description="Gemini model to use"
    )
    
    # AI behavior settings
    ai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ai_max_tokens: int = Field(default=2000, ge=100, le=8000)
    ai_streaming: bool = Field(default=True, description="Enable streaming responses")
    
    @model_validator(mode='before')
    def check_api_key_sources(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Check multiple sources for API key"""
        # First check if gemini_api_key is already set
        if values.get("gemini_api_key"):
            return values
        
        # Check GEMINI_API_KEY env var (pydantic will handle with env_prefix)
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("RUNTIME_FDR_GEMINI_API_KEY")
        if api_key:
            values["gemini_api_key"] = api_key
            return values
        
        # Check alternate environment variable
        alt_key = os.getenv("GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS")
        if alt_key:
            values["gemini_api_key"] = alt_key
        
        return values
    
    @property
    def has_ai_configured(self) -> bool:
        """Check if AI is properly configured"""
        return bool(self.gemini_api_key)


# ============================================================================
# GIT CONFIGURATION
# ============================================================================

class GitConfig(BaseConfig):
    """Configuration for Git operations"""
    
    # Git settings
    git_remote: str = Field(default="origin", description="Default git remote")
    git_main_branch: str = Field(default="main", description="Main branch name")
    git_fetch_before_operations: bool = Field(default=True)
    git_push_tags: bool = Field(default=True, description="Push tags after creating")
    
    # Commit settings
    commit_sign: bool = Field(default=False, description="Sign commits with GPG")
    commit_verify: bool = Field(default=True, description="Verify commits before push")
    
    @property
    def git_dir(self) -> Optional[Path]:
        """Get .git directory if in a git repo"""
        git_dir = self.project_root / ".git"
        return git_dir if git_dir.exists() else None


# ============================================================================
# PACKAGE CONFIGURATION
# ============================================================================

class PackageInfo(BaseSettings):
    """Information about a single package"""
    
    name: str
    type: PackageType
    path: Path
    version_file: str
    changelog_path: Path
    
    @property
    def exists(self) -> bool:
        """Check if package exists"""
        return self.path.exists()


class PackageConfig(BaseConfig):
    """Configuration for multi-package management"""
    
    # Package naming convention
    root_package_name: Optional[str] = None
    dart_package_prefix: str = Field(default="runtime_", description="Dart package prefix")
    flutter_package_prefix: str = Field(default="runtime_flutter_", description="Flutter package prefix")
    rust_package_prefix: str = Field(default="runtime_rust_", description="Rust package prefix")
    
    @model_validator(mode='before')
    def detect_package_names(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-detect package names from directory"""
        if not values.get("root_package_name"):
            project_root = values.get("project_root", Path.cwd())
            values["root_package_name"] = project_root.name
        return values
    
    @property
    def dart_package_name(self) -> str:
        """Get Dart package name"""
        return f"{self.dart_package_prefix}{self.root_package_name}"
    
    @property
    def flutter_package_name(self) -> str:
        """Get Flutter package name"""
        return f"{self.flutter_package_prefix}{self.root_package_name}"
    
    @property
    def rust_package_name(self) -> str:
        """Get Rust package name"""
        return f"{self.rust_package_prefix}{self.root_package_name}"
    
    def get_package_info(self) -> Dict[PackageType, PackageInfo]:
        """Get information for all packages"""
        return {
            PackageType.ROOT: PackageInfo(
                name=self.root_package_name,
                type=PackageType.ROOT,
                path=self.project_root,
                version_file="",  # Root doesn't have version file
                changelog_path=self.project_root / "CHANGELOG.md"
            ),
            PackageType.DART: PackageInfo(
                name=self.dart_package_name,
                type=PackageType.DART,
                path=self.dart_dir,
                version_file="pubspec.yaml",
                changelog_path=self.dart_dir / "CHANGELOG.md"
            ),
            PackageType.FLUTTER: PackageInfo(
                name=self.flutter_package_name,
                type=PackageType.FLUTTER,
                path=self.flutter_dir,
                version_file="pubspec.yaml",
                changelog_path=self.flutter_dir / "CHANGELOG.md"
            ),
            PackageType.RUST: PackageInfo(
                name=self.rust_package_name,
                type=PackageType.RUST,
                path=self.rust_dir,
                version_file="Cargo.toml",
                changelog_path=self.rust_dir / "CHANGELOG.md"
            )
        }


# ============================================================================
# COMPLETE CONFIGURATION
# ============================================================================

class ToolingConfig(AIConfig, GitConfig, PackageConfig):
    """
    Complete configuration for tooling scripts.
    
    This combines all configuration aspects and provides a single
    entry point for all tools.
    """
    
    # Tool-specific settings can be added here
    dry_run: bool = Field(default=False, description="Perform dry run without changes")
    interactive: bool = Field(default=True, description="Enable interactive prompts")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    def print_header(self, message: str) -> None:
        """Print a formatted header"""
        self.console.print()
        self.console.rule(f"[header]{message}[/header]", style="header")
        self.console.print()
    
    def print_success(self, message: str) -> None:
        """Print success message"""
        self.console.print(f"[success]✓[/success] {message}")
    
    def print_error(self, message: str) -> None:
        """Print error message"""
        self.console.print(f"[error]✗[/error] {message}", style="error")
    
    def print_warning(self, message: str) -> None:
        """Print warning message"""
        self.console.print(f"[warning]⚠[/warning] {message}", style="warning")
    
    def print_info(self, message: str) -> None:
        """Print info message"""
        self.console.print(f"[info]ℹ[/info] {message}", style="info")
    
    @classmethod
    def from_args(cls, **kwargs) -> "ToolingConfig":
        """
        Create config from command line arguments.
        
        This allows tools to pass CLI args directly:
        config = ToolingConfig.from_args(verbose=args.verbose, quiet=args.quiet)
        """
        return cls(**kwargs)


# ============================================================================
# MIGRATION HELPER
# ============================================================================

def get_config(**overrides) -> ToolingConfig:
    """
    Get configuration instance with optional overrides.
    
    This is the main entry point for tools to get configuration:
    
    ```python
    from tooling.core.base_config import get_config
    
    config = get_config(verbose=True, dry_run=True)
    config = get_config(any_structure=True)  # Skip project structure validation
    ```
    """
    # Handle any_structure flag to bypass validation
    if overrides.get("any_structure", False):
        os.environ["ANY_STRUCTURE"] = "1"
    
    # Set a reasonable default project_root if not provided and in test environment
    if "project_root" not in overrides and (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("_PYTEST_RAISE")):
        # Use parent directory as project root in tests
        overrides["project_root"] = Path.cwd().parent if (Path.cwd() / "tests").exists() else Path.cwd()
    
    # Remove any_structure from overrides as it's not a ToolingConfig field
    if "any_structure" in overrides:
        del overrides["any_structure"]
    
    return ToolingConfig(**overrides)