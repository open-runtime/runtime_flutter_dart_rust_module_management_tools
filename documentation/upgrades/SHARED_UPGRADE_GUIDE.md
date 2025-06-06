# Shared Upgrade Guide for Tesseract Tooling

## Overview
This document outlines common dependencies and improvements that should be implemented across all Python files in the tooling suite to reduce technical debt and improve maintainability.

## ✅ Completed Implementations

### Structured Logging (June 2025)
The structured logging infrastructure has been fully implemented across the tooling suite:

**What was implemented:**
- Created `tooling/core/logging.py` with comprehensive `structlog` setup
- Added `tooling/cli/cli_utils.py` with unified print functions
- Updated `tooling/core/common_config.py` to integrate logging with backward compatibility
- Migrated key CLI tools (`smart_commit.py`, `smart_commit_fast.py`) to use structured logging

**Key features:**
- **Dual output**: User-friendly colored console + structured logs
- **Multiple modes**: JSON output, file logging, rich console output
- **Context tracking**: Request IDs, user IDs, operation tracking
- **Progress logging**: Built-in progress tracking for long operations
- **Backward compatible**: Existing `print_color()` calls still work
- **Performance**: Minimal overhead, especially in production mode

**Usage example:**
```python
from tooling.core.logging import setup_logging, get_logger
from tooling.cli.cli_utils import print_info, print_success, print_error

# Setup logging for your tool
logger = setup_cli_logging(
    tool_name="my_tool",
    verbose=True,
    debug=False,
    json_output=False
)

# Use structured logging
logger.info("operation_start", file_count=10, mode="fast")

# Use CLI print functions
print_info("Processing files...")
print_success("Operation completed!")
print_error("Something went wrong")

# Context management
from tooling.core.logging import log_context
with log_context(request_id="abc-123", user="admin"):
    logger.info("processing_request")
```

## 🎯 Core Principles

1. **Type Safety**: Use type hints and runtime validation
2. **Async First**: Implement async operations where beneficial
3. **Structured Logging**: Replace print statements with proper logging ✅ **COMPLETED**
4. **Error Handling**: Consistent error handling and recovery
5. **Configuration**: Centralized, validated configuration
6. **Testing**: Comprehensive test coverage
7. **Documentation**: Auto-generated API docs

## 📦 Common Dependencies

### Essential Core Dependencies
```toml
[project.dependencies]
# CLI and UI
click = "^8.1.7"          # CLI framework (alternative: typer)
rich = "^13.7.0"          # Beautiful terminal output
tqdm = "^4.66.1"          # Progress bars

# Configuration and Validation
pydantic = "^2.5.0"       # Data validation and settings
pydantic-settings = "^2.1.0"  # Settings management
python-dotenv = "^1.0.0"  # Environment variable loading

# Logging and Monitoring
structlog = "^24.1.0"     # Structured logging
loguru = "^0.7.2"         # Alternative: simpler logging

# Git Operations
GitPython = "^3.1.40"     # Git operations
pygit2 = "^1.13.3"        # Performance-critical git ops

# Async Support
aiohttp = "^3.9.0"        # Async HTTP client
asyncio-throttle = "^1.0.2"  # Rate limiting

# Testing
pytest = "^7.4.3"         # Testing framework
pytest-asyncio = "^0.21.1"  # Async test support
pytest-cov = "^4.1.0"     # Coverage reporting
pytest-mock = "^3.12.0"   # Mocking support

# Code Quality
black = "^23.12.0"        # Code formatting
ruff = "^0.1.9"          # Fast linting
mypy = "^1.8.0"          # Type checking
pre-commit = "^3.6.0"     # Git hooks
```

### Specialized Dependencies
```toml
# For specific use cases
jinja2 = "^3.1.2"         # Template engine
pandas = "^2.1.4"         # Data analysis
redis = "^5.0.1"          # Distributed caching
semver = "^3.0.2"         # Semantic versioning
tabulate = "^0.9.0"       # Table formatting
humanize = "^4.9.0"       # Human-readable output
tenacity = "^8.2.3"       # Retry logic
```

## 🏗️ Common Infrastructure Components

### 1. Base Configuration Class
```python
# shared/config.py
from pydantic import BaseSettings, Field
from typing import Optional
import os

class BaseToolConfig(BaseSettings):
    """Base configuration for all tools"""
    
    # Common settings
    debug: bool = Field(False, env='TOOL_DEBUG')
    log_level: str = Field('INFO', env='LOG_LEVEL')
    timeout: int = Field(30, env='TOOL_TIMEOUT')
    
    # Git settings
    git_timeout: int = Field(30, env='GIT_TIMEOUT')
    default_branch: str = Field('main', env='DEFAULT_BRANCH')
    
    # AI settings
    ai_api_key: Optional[str] = Field(None, env='GEMINI_API_KEY')
    ai_model: str = Field('gemini-1.5-flash', env='AI_MODEL')
    ai_timeout: int = Field(60, env='AI_TIMEOUT')
    
    class Config:
        env_file = '.env'
        case_sensitive = False
```

### 2. Logging Setup ✅ **IMPLEMENTED**
```python
# tooling/core/logging.py - FULLY IMPLEMENTED
import structlog
from rich.logging import RichHandler
import logging

def setup_logging(level: str = "INFO", json: bool = False):
    """Configure structured logging for all tools"""
    
    # Full implementation available in tooling/core/logging.py
    # Features implemented:
    # - JSON output for production
    # - Rich console output for development
    # - File logging support
    # - Progress tracking with ProgressLogger
    # - Context management with log_context()
    # - Integration with common_config.py print functions
    # - CLI utilities in tooling/cli/cli_utils.py

# Example usage:
from tooling.core.logging import setup_logging, get_logger
from tooling.cli.cli_utils import print_info, print_success, print_error

logger = setup_logging(tool_name="my_tool", level="INFO")
logger.info("operation_start", tool="my_tool", version="1.0.0")

# CLI-friendly output functions
print_info("Processing files...")
print_success("Operation completed!")
print_error("Something went wrong")
```

**Key files created/updated:**
- `tooling/core/logging.py` - Complete logging infrastructure
- `tooling/cli/cli_utils.py` - CLI print utilities with logging
- `tooling/core/common_config.py` - Updated to integrate logging
- `tooling/cli/smart_commit.py` - Migrated to use structured logging
- `tooling/cli/smart_commit_fast.py` - Migrated to use structured logging

```

### 3. Error Handling
```python
# shared/errors.py
from typing import Optional, Any
from rich.console import Console
from rich.panel import Panel
import sys

console = Console()

class ToolError(Exception):
    """Base exception for all tool errors"""
    def __init__(self, message: str, code: int = 1, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

class GitError(ToolError):
    """Git operation errors"""
    pass

class ValidationError(ToolError):
    """Validation errors"""
    pass

class APIError(ToolError):
    """External API errors"""
    pass

def handle_error(error: Exception, debug: bool = False):
    """Consistent error handling across tools"""
    if isinstance(error, ToolError):
        console.print(Panel(
            f"[red bold]Error:[/red bold] {error.message}",
            title=f"[red]{error.__class__.__name__}[/red]",
            border_style="red"
        ))
        if error.details and debug:
            console.print("[dim]Details:[/dim]", error.details)
        sys.exit(error.code)
    else:
        console.print(Panel(
            f"[red bold]Unexpected Error:[/red bold] {str(error)}",
            title="[red]Error[/red]",
            border_style="red"
        ))
        if debug:
            console.print_exception()
        sys.exit(1)
```

### 4. CLI Base Class
```python
# shared/cli.py
import click
from rich.console import Console
from typing import Optional
import asyncio

console = Console()

class AsyncCommand(click.Command):
    """Click command that supports async functions"""
    
    def invoke(self, ctx):
        rv = super().invoke(ctx)
        if asyncio.iscoroutine(rv):
            return asyncio.run(rv)
        return rv

def common_options(func):
    """Common CLI options for all tools"""
    func = click.option('--debug', is_flag=True, help='Enable debug mode')(func)
    func = click.option('--json', is_flag=True, help='Output JSON format')(func)
    func = click.option('--quiet', is_flag=True, help='Suppress output')(func)
    func = click.option('--config', type=click.Path(), help='Config file path')(func)
    return func

def create_cli(name: str, help: str):
    """Create a CLI app with common setup"""
    @click.group(name=name, help=help)
    @click.version_option()
    @common_options
    @click.pass_context
    def cli(ctx, debug, json, quiet, config):
        ctx.ensure_object(dict)
        ctx.obj['debug'] = debug
        ctx.obj['json'] = json
        ctx.obj['quiet'] = quiet
        ctx.obj['config'] = config
        
        # Setup logging
        from .logging import setup_logging
        level = 'DEBUG' if debug else 'INFO'
        setup_logging(level=level, json=json)
        
    return cli
```

### 5. Git Operations Helper
```python
# shared/git.py
from git import Repo
from typing import List, Optional, Tuple
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class GitHelper:
    """Common Git operations with error handling"""
    
    def __init__(self, repo_path: str = '.'):
        self.repo = Repo(repo_path)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential())
    def get_current_branch(self) -> str:
        """Get current branch name"""
        return self.repo.active_branch.name
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential())
    def get_commits_between(self, from_ref: str, to_ref: str = 'HEAD') -> List[str]:
        """Get commits between two references"""
        return list(self.repo.iter_commits(f'{from_ref}..{to_ref}'))
    
    async def get_file_history(self, file_path: str, limit: int = 10) -> List[dict]:
        """Get file history asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _get_history():
            commits = list(self.repo.iter_commits(paths=file_path, max_count=limit))
            return [
                {
                    'sha': c.hexsha,
                    'author': c.author.name,
                    'date': c.authored_datetime,
                    'message': c.message.strip()
                }
                for c in commits
            ]
        
        return await loop.run_in_executor(None, _get_history)
```

### 6. Progress Tracking
```python
# shared/progress.py
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console
from contextlib import contextmanager
from typing import Optional

console = Console()

@contextmanager
def progress_tracker(description: str, total: Optional[int] = None):
    """Unified progress tracking"""
    if total is None:
        # Indeterminate progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(description, total=None)
            yield progress, task
    else:
        # Determinate progress
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task(description, total=total)
            yield progress, task
```

### 7. Caching Layer
```python
# shared/cache.py
from functools import lru_cache, wraps
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional
import pickle

class FileCache:
    """Simple file-based cache"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / '.cache' / 'tesseract-tools'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_key(self, key: str) -> str:
        """Generate cache key"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        cache_file = self.cache_dir / f"{self._get_key(key)}.pkl"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        cache_file = self.cache_dir / f"{self._get_key(key)}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(value, f)

def cached(ttl: int = 3600):
    """Decorator for caching function results"""
    cache = FileCache()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
```

## 🔧 Implementation Strategy

### Phase 1: Foundation (Week 1-2) ✅ **LOGGING COMPLETED**
1. Set up shared package structure
2. Implement base configuration
3. ~~Add logging infrastructure~~ ✅ **COMPLETED**
4. Create error handling framework
5. Add basic tests

### Migrating Tools to New Logging (Quick Guide)

For tools that haven't been migrated yet, follow this pattern:

```python
#!/usr/bin/env python3
# At the top of your tool file

# Import logging utilities
try:
    from tooling.core.common_config import *
    from tooling.core.logging import setup_logging, get_logger
    from tooling.cli.cli_utils import (
        setup_cli_logging, print_info, print_success, 
        print_error, print_warning
    )
except ImportError:
    # Fallback imports for direct execution
    from core.common_config import *
    from core.logging import setup_logging, get_logger
    from cli_utils import (
        setup_cli_logging, print_info, print_success,
        print_error, print_warning
    )

# In your main() function
def main():
    args = parse_arguments()
    
    # Setup logging
    logger = setup_cli_logging(
        tool_name="your_tool_name",
        verbose=args.verbose,
        debug=args.debug,
        quiet=args.quiet,
        json_output=args.json
    )
    
    # Replace print statements:
    # print_color(Colors.BLUE, "msg") → print_info("msg")
    # print_color(Colors.GREEN, "msg") → print_success("msg") 
    # print_color(Colors.YELLOW, "msg") → print_warning("msg")
    # print_color(Colors.RED, "msg") → print_error("msg")
    
    # Add structured logging
    logger.info("operation_start", user=args.user, mode=args.mode)
    
    # Use progress logger for long operations
    from tooling.core.logging import ProgressLogger
    with ProgressLogger(logger, "Processing files") as progress:
        for i, file in enumerate(files):
            progress.update(f"Processing {file}", current=i, total=len(files))
```

### Phase 2: Core Components (Week 3-4)
1. Implement Git helpers
2. Add progress tracking
3. Create caching layer
4. Build CLI framework
5. Add type hints throughout

### Phase 3: Tool Migration (Week 5-8)
1. Migrate one tool at a time
2. Start with simple tools (e.g., validate_changelogs)
3. Update tests for each tool
4. Maintain backward compatibility
5. Document changes

### Phase 4: Advanced Features (Week 9-10)
1. Add async support where beneficial
2. Implement performance monitoring
3. Add telemetry/metrics
4. Create plugin system
5. Build web UI (optional)

## 📊 Success Metrics

1. **Code Reduction**: 30-40% less code through shared components
2. **Performance**: 2x faster execution for I/O operations
3. **Reliability**: 90% reduction in unhandled errors
4. **Test Coverage**: >80% coverage across all tools
5. **Developer Experience**: 50% reduction in setup time

## 🚀 Quick Start for Developers

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff . --fix

# Type check
mypy .

# Install pre-commit hooks
pre-commit install
```

## 📝 Migration Checklist for Each Tool

- [ ] Add type hints to all functions
- [x] Replace print with structured logging ✅ **COMPLETED**
- [ ] Use pydantic for configuration
- [ ] Add proper error handling
- [ ] Implement progress tracking (partially complete via ProgressLogger)
- [ ] Add comprehensive tests
- [ ] Update documentation
- [ ] Add CLI using click/typer
- [ ] Implement caching where appropriate
- [ ] Add async support if beneficial

## 🎉 Benefits Summary

1. **Consistency**: Uniform patterns across all tools
2. **Maintainability**: Easier to update and fix bugs
3. **Performance**: Faster execution through async and caching
4. **Reliability**: Better error handling and recovery
5. **Developer Experience**: Modern Python patterns and tooling
6. **Extensibility**: Easy to add new features
7. **Testing**: Comprehensive test coverage
8. **Documentation**: Auto-generated from code