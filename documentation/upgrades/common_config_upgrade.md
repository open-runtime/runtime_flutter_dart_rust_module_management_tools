# Upgrade Plan: common_config.py

## Overview
Central configuration module used by all tooling scripts. Currently relies heavily on standard library with manual implementations of common patterns.

## Current State
- **Dependencies**: Standard library only (os, sys, subprocess, dataclasses, typing)
- **Key Features**: Color constants, path management, API keys, Git operations, version utilities
- **Code Quality**: Good structure but could benefit from modern patterns

## Recommended Upgrades

### 1. Configuration Management
```python
# Current: Manual config handling
# Upgrade to: pydantic
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

class ToolingConfig(BaseSettings):
    api_key: str = Field(..., env='GEMINI_API_KEY')
    git_timeout: int = Field(30, ge=1)
    retry_attempts: int = Field(3, ge=1)
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
```

### 2. CLI Enhancement
```python
# Replace manual arg parsing with typer
import typer
from rich.console import Console
from rich.progress import Progress

app = typer.Typer(pretty_exceptions_enable=False)
console = Console()
```

### 3. Git Operations
```python
# Replace subprocess calls with GitPython
from git import Repo
from git.exc import GitCommandError

def get_git_info():
    repo = Repo('.')
    return {
        'branch': repo.active_branch.name,
        'commit': repo.head.commit.hexsha,
        'dirty': repo.is_dirty()
    }
```

### 4. Path Management
```python
# Enhanced path handling with pathlib
from pathlib import Path
from platformdirs import user_config_dir, user_cache_dir

CONFIG_DIR = Path(user_config_dir('tesseract-tooling'))
CACHE_DIR = Path(user_cache_dir('tesseract-tooling'))
```

### 5. Logging Infrastructure
```python
# Replace print statements with structlog
import structlog

logger = structlog.get_logger()
logger = logger.bind(module='common_config')
```

## Dependencies to Add
```toml
[project.dependencies]
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
typer = "^0.9.0"
rich = "^13.7.0"
GitPython = "^3.1.40"
platformdirs = "^4.1.0"
structlog = "^24.1.0"
python-dotenv = "^1.0.0"
```

## Migration Strategy
1. Create new `config.py` with pydantic models
2. Add compatibility layer for existing code
3. Gradually migrate scripts to use new config
4. Replace print statements with structured logging
5. Update Git operations to use GitPython

## Benefits
- Type-safe configuration with validation
- Better error messages and CLI experience
- Reduced boilerplate code
- Improved maintainability
- Cross-platform compatibility