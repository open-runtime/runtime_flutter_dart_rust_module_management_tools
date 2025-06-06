# Core Configuration System

This directory contains the core configuration and utility modules for all CLI tools.

## Configuration Modules Overview

### 1. `simple_config.py` (Recommended for Quick Wins)
Simple, static configuration wrapper for common use cases.

```python
from tooling.core.simple_config import Config

# Get API key with fallback
api_key = Config.get_api_key()

# Get model based on mode
model = Config.get_model(use_pro=True)

# Check debug mode
if Config.is_debug():
    print("Debug mode enabled")

# Get project root
root = Config.get_project_root()
```

### 2. `base_config.py` (Recommended for New Tools)
Modern, Pydantic-based configuration with validation and type safety.

```python
from tooling.core.base_config import get_config, ToolingConfig

# Get configuration with overrides
config = get_config(verbose=True, dry_run=True)

# Use built-in output methods
config.print_header("Starting Process")
config.print_success("Operation completed")
config.print_error("Something went wrong")

# Access package information
packages = config.get_package_info()
for pkg_type, info in packages.items():
    print(f"{info.name} at {info.path}")

# Check AI configuration
if config.has_ai_configured:
    response = ai_client.generate(config.gemini_model)
```

### 3. `common_config.py` (Legacy - Being Phased Out)
Original configuration module with mixed utilities. Use `config_bridge.py` for migration.

### 4. `config.py` (Deprecated)
Redundant with `base_config.py`. Will be removed in future versions.

## Migration Guide

### From `common_config.py` to `simple_config.py`

| Old (common_config) | New (simple_config) |
|---------------------|---------------------|
| `check_api_key()` | `Config.get_api_key()` |
| `GEMINI_MODEL` | `Config.get_model()` |
| `os.environ.get('DEBUG')` | `Config.is_debug()` |
| `ensure_project_root()` | `Config.get_project_root()` |

### From `common_config.py` to `base_config.py`

| Old (common_config) | New (base_config) |
|---------------------|-------------------|
| `check_api_key()` | `config.has_ai_configured` |
| `GEMINI_MODEL` | `config.gemini_model` |
| `print_color(Colors.GREEN, msg)` | `config.print_success(msg)` |
| `detect_package_names()` | `config.get_package_info()` |

## Other Core Modules

### `imports.py`
Standardizes Python path setup for all tools.

```python
from tooling.core.imports import setup_imports
setup_imports()  # Auto-called on import
```

### `logging.py`
Structured logging with Rich integration.

```python
from tooling.core.logging import get_logger

logger = get_logger(__name__)
logger.info("operation_started", user="john", action="create")
```

### `performance.py`
Performance tracking utilities.

```python
from tooling.core.performance import track_performance

@track_performance("database_query")
def fetch_data():
    # ... operation ...
```

### `ai_client.py`
Gemini SDK client with caching and templates.

```python
from tooling.core.ai_client import GeminiClient

client = GeminiClient()
response = await client.generate_content_async(
    prompt="Generate a commit message",
    template="commit_message.j2",
    template_context={'files': changed_files}
)
```

## Best Practices

1. **For New Tools**: Use `base_config.py` with Pydantic validation
2. **For Quick Scripts**: Use `simple_config.py` for simplicity
3. **For Legacy Code**: Use `config_bridge.py` during migration
4. **Avoid**: Direct use of `common_config.py` or `config.py`

## Environment Variables

All configuration modules support these environment variables:

- `GEMINI_API_KEY` or `GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS`
- `DEBUG` - Enable debug mode
- `DRY_RUN` - Enable dry run mode
- `NO_COLOR` - Disable colored output
- `LOG_LEVEL` - Set logging level (DEBUG, INFO, WARNING, ERROR)
- `GEMINI_MODEL_FLASH` - Flash model name (default: gemini-2.0-flash-exp)
- `GEMINI_MODEL_PRO` - Pro model name (default: gemini-2.0-flash-exp)

## Configuration Precedence

1. Command-line arguments (highest priority)
2. Environment variables
3. `.env` file
4. Default values (lowest priority) 