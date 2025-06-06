"""
Enhanced configuration management with Pydantic and YAML support.

This module provides a modern configuration system that:
- Loads from YAML files
- Validates with Pydantic
- Supports environment variables
- Provides project-specific overrides
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
import yaml
from functools import lru_cache
from rich.console import Console

console = Console()


class UIConfig(BaseModel):
    """UI configuration settings"""
    theme: str = Field(default="dark", pattern="^(dark|light|auto)$")
    use_emoji: bool = True
    progress_style: str = Field(default="rainbow", pattern="^(rainbow|blue|green)$")
    table_style: str = Field(default="rounded", pattern="^(rounded|double|ascii)$")
    use_color: bool = True
    interactive_by_default: bool = False


class AIConfig(BaseModel):
    """AI provider configuration"""
    provider: str = Field(default="gemini", pattern="^(gemini|openai)$")
    model: str = "gemini-2.0-flash"
    pro_model: str = "gemini-2.0-flash"
    timeout: int = Field(default=60, ge=10, le=300)
    max_retries: int = Field(default=3, ge=1, le=10)
    cache_responses: bool = True
    cache_ttl: int = Field(default=3600, ge=0)
    
    @field_validator('model', 'pro_model')
    @classmethod
    def validate_model_name(cls, v, info):
        """Validate model names based on provider"""
        provider = info.data.get('provider', 'gemini')
        if provider == 'gemini' and not v.startswith(('gemini', 'models/')):
            raise ValueError(f"Invalid Gemini model: {v}")
        elif provider == 'openai' and not v.startswith(('gpt', 'text-')):
            raise ValueError(f"Invalid OpenAI model: {v}")
        return v


class GitConfig(BaseModel):
    """Git configuration settings"""
    auto_stage: bool = False
    push_after_commit: bool = False
    sign_commits: bool = False
    default_branch: str = "main"


class ReleaseConfig(BaseModel):
    """Release management configuration"""
    create_github_release: bool = True
    generate_release_notes: bool = True
    draft_by_default: bool = False
    prerelease_pattern: str = "-rc"


class ChangelogConfig(BaseModel):
    """Changelog configuration"""
    include_author: bool = True
    include_pr_links: bool = True
    group_by_type: bool = True
    exclude_patterns: List[str] = Field(default_factory=lambda: ["^chore:", "^docs:", "^test:"])


class DevelopmentConfig(BaseModel):
    """Development settings"""
    debug: bool = Field(default=False, json_schema_extra={'env': 'DEBUG'})
    dry_run: bool = Field(default=False, json_schema_extra={'env': 'DRY_RUN'})
    verbose: bool = Field(default=False, json_schema_extra={'env': 'VERBOSE'})
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_file: Optional[Path] = None


class PerformanceConfig(BaseModel):
    """Performance tuning settings"""
    max_workers: int = Field(default=4, ge=1, le=32)
    batch_size: int = Field(default=10, ge=1, le=100)
    connection_pool_size: int = Field(default=5, ge=1, le=20)
    enable_profiling: bool = False


class NotificationConfig(BaseModel):
    """Notification service configuration"""
    enabled: bool = False
    webhook_url: Optional[str] = None


class SlackConfig(NotificationConfig):
    """Slack notification configuration"""
    channel: str = "#releases"


class EmailConfig(NotificationConfig):
    """Email notification configuration"""
    smtp_server: Optional[str] = None
    from_address: Optional[str] = None
    to_addresses: List[str] = Field(default_factory=list)


class NotificationsConfig(BaseModel):
    """All notification configurations"""
    slack: SlackConfig = Field(default_factory=SlackConfig)
    discord: NotificationConfig = Field(default_factory=NotificationConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)


class RuntimeConfig(BaseSettings):
    """Main configuration class for Runtime Tools"""
    ui: UIConfig = Field(default_factory=UIConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    release: ReleaseConfig = Field(default_factory=ReleaseConfig)
    changelog: ChangelogConfig = Field(default_factory=ChangelogConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    custom_commands: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    projects: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = {
        'env_prefix': 'RT_',
        'env_nested_delimiter': '__',
        'case_sensitive': False
    }
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> 'RuntimeConfig':
        """Load configuration from YAML file"""
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Merge with environment variables
            config = cls(**data)
            return config
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load config from {config_path}: {e}[/yellow]")
            return cls()
    
    def get_project_config(self, project_name: str) -> Dict[str, Any]:
        """Get project-specific configuration overrides"""
        return self.projects.get(project_name, {})
    
    def merge_with_project(self, project_name: str) -> 'RuntimeConfig':
        """Create a new config with project-specific overrides"""
        project_config = self.get_project_config(project_name)
        if not project_config:
            return self
        
        # Deep merge configuration
        merged_data = self.model_dump()
        for key, value in project_config.items():
            if key in merged_data and isinstance(merged_data[key], dict):
                merged_data[key].update(value)
            else:
                merged_data[key] = value
        
        return RuntimeConfig(**merged_data)
    
    def save_to_file(self, config_path: Path):
        """Save configuration to YAML file"""
        config_data = self.model_dump(exclude_defaults=True, exclude_none=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    
    # Convenience properties
    @property
    def is_interactive(self) -> bool:
        """Check if interactive mode is enabled"""
        return self.ui.interactive_by_default or os.environ.get('RT_INTERACTIVE', '').lower() == 'true'
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key for current provider"""
        if self.ai.provider == 'gemini':
            return os.environ.get('GEMINI_API_KEY')
        elif self.ai.provider == 'openai':
            return os.environ.get('OPENAI_API_KEY')
        return None
    
    @property
    def should_use_color(self) -> bool:
        """Check if color output is enabled"""
        if os.environ.get('NO_COLOR'):
            return False
        if os.environ.get('RT_NO_COLOR'):
            return False
        return self.ui.use_color
    
    def get_table_style(self):
        """Get Rich table box style"""
        from rich import box
        styles = {
            'rounded': box.ROUNDED,
            'double': box.DOUBLE,
            'ascii': box.ASCII
        }
        return styles.get(self.ui.table_style, box.ROUNDED)


class ConfigManager:
    """Manages configuration loading and caching"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[RuntimeConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def config_paths(self) -> List[Path]:
        """Get configuration file search paths in priority order"""
        paths = []
        
        # 1. Environment variable
        if env_path := os.environ.get('RT_CONFIG'):
            paths.append(Path(env_path))
        
        # 2. Current directory
        paths.append(Path.cwd() / '.rtconfig.yaml')
        paths.append(Path.cwd() / '.rtconfig.yml')
        
        # 3. Project root (looking for .git)
        current = Path.cwd()
        while current != current.parent:
            if (current / '.git').exists():
                paths.append(current / '.rtconfig.yaml')
                paths.append(current / '.rtconfig.yml')
                break
            current = current.parent
        
        # 4. User home directory
        paths.append(Path.home() / '.rtconfig.yaml')
        paths.append(Path.home() / '.config' / 'runtime-tools' / 'config.yaml')
        
        # 5. System-wide
        paths.append(Path('/etc/runtime-tools/config.yaml'))
        
        return paths
    
    @lru_cache(maxsize=1)
    def load(self) -> RuntimeConfig:
        """Load configuration from the first available config file"""
        if self._config is not None:
            return self._config
        
        # Try each path in order
        for path in self.config_paths:
            if path.exists():
                console.print(f"[dim]Loading config from: {path}[/dim]")
                self._config = RuntimeConfig.load_from_file(path)
                return self._config
        
        # No config file found, use defaults
        console.print("[dim]No config file found, using defaults[/dim]")
        self._config = RuntimeConfig()
        return self._config
    
    def reload(self):
        """Force reload configuration"""
        self._config = None
        self.load.cache_clear()
        return self.load()
    
    def get(self) -> RuntimeConfig:
        """Get current configuration"""
        if self._config is None:
            return self.load()
        return self._config
    
    def create_default_config(self, path: Optional[Path] = None):
        """Create a default configuration file"""
        if path is None:
            path = Path.cwd() / '.rtconfig.yaml'
        
        # Load the default template
        template_path = Path(__file__).parent.parent / '.rtconfig.yaml'
        if template_path.exists():
            import shutil
            shutil.copy(template_path, path)
        else:
            # Create from defaults
            config = RuntimeConfig()
            config.save_to_file(path)
        
        console.print(f"[green]✓ Created default config at: {path}[/green]")
        return path


# Global config manager instance
config_manager = ConfigManager()


def get_config() -> RuntimeConfig:
    """Get current runtime configuration"""
    return config_manager.get()


def reload_config() -> RuntimeConfig:
    """Reload configuration from disk"""
    return config_manager.reload()


# For backward compatibility with simple_config
class Config:
    """Backward compatibility wrapper for simple_config.Config"""
    
    @staticmethod
    def get_api_key() -> Optional[str]:
        config = get_config()
        return config.api_key
    
    @staticmethod
    def get_model(use_pro: bool = False) -> str:
        config = get_config()
        return config.ai.pro_model if use_pro else config.ai.model
    
    @staticmethod
    def is_debug() -> bool:
        config = get_config()
        return config.development.debug
    
    @staticmethod
    def is_dry_run() -> bool:
        config = get_config()
        return config.development.dry_run
    
    @staticmethod
    def should_use_color() -> bool:
        config = get_config()
        return config.should_use_color
    
    @staticmethod
    def get_log_level() -> str:
        config = get_config()
        return config.development.log_level 