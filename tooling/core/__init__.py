"""
Core modules and utilities used by all CLI tools.

Quick Start:
    from tooling.core.config_manager import Config  # Backward compatibility wrapper
    from tooling.core.imports import setup_imports
    
    setup_imports()  # Setup import paths
    api_key = Config.get_api_key()  # Get API key
"""

# Import setup should happen first
from .imports import setup_imports

# Configuration modules (in order of recommendation)
from .config_manager import Config  # Backward compatibility wrapper
from .base_config import (  # Recommended for complex tools
    get_config, 
    ToolingConfig,
    BaseConfig,
    AIConfig,
    GitConfig,
    PackageConfig,
    LogLevel,
    PackageType
)

# Utilities
from .logging import get_logger, setup_logging, get_console
from .performance import (
    track_performance,
    measure_operation,
    get_performance_stats,
    print_performance_report
)
# AI client (optional - requires google-generativeai)
try:
    from .ai_client import GeminiClient, get_default_client
except ImportError:
    GeminiClient = None
    get_default_client = None



__all__ = [
    # Setup
    'setup_imports',
    
    # Simple config (recommended)
    'Config',
    
    # Advanced config
    'get_config',
    'ToolingConfig', 
    'BaseConfig',
    'AIConfig',
    'GitConfig',
    'PackageConfig',
    'LogLevel',
    'PackageType',
    
    # Logging
    'get_logger',
    'setup_logging',
    'get_console',
    
    # Performance
    'track_performance',
    'measure_operation', 
    'get_performance_stats',
    'print_performance_report',
    
    # AI Client (optional)
    'GeminiClient',
    'get_default_client'
]

# Mark deprecated modules
import warnings

def __getattr__(name):
    """Provide deprecation warnings for old imports"""
    if name == 'common_config':
        raise ImportError(
            "common_config has been removed. "
            "Use simple_config.Config or base_config.ToolingConfig instead. "
            "See tooling/core/MIGRATION_STATUS.md for migration guide."
        )
    elif name == 'config':
        warnings.warn(
            "The config module is deprecated. "
            "Use base_config instead for Pydantic-based configuration.",
            DeprecationWarning,
            stacklevel=2
        )
        from . import config
        return config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}") 