# Logging Migration Guide

This guide helps you migrate from the old print-based logging in `common_config.py` to the new structured logging system.

## Overview

The new logging system provides:
- Structured logging with `structlog`
- Beautiful console output with `rich`
- JSON output support
- File logging
- Context management
- Performance tracking
- Type-safe configuration

## Basic Migration

### Old Way (common_config.py)

```python
from tooling.core.common_config import Colors, output_error, output_success, output_info

# Simple messages
output_info("Processing files...")
output_success("Operation completed!")
output_error("Something went wrong")

# With color
print(f"{Colors.BLUE}Debug:{Colors.RESET} Starting process")
```

### New Way (structured logging)

```python
from tooling.core.logging import setup_logging, get_logger

# Setup (once at the start of your tool)
logger = setup_logging(tool_name="my_tool")

# Simple messages
logger.info("Processing files...")
logger.info("Operation completed!", status="success")
logger.error("Something went wrong")

# With structured data
logger.debug("Starting process", 
    process_name="file_sync",
    file_count=42,
    config={"recursive": True}
)
```

## Configuration Integration

### Using with Pydantic Config

```python
from tooling.core.config import load_config, BaseToolConfig
from tooling.core.logging import setup_logging

# Load configuration
config = load_config(BaseToolConfig)

# Setup logging with config
logger = setup_logging(
    level=config.log_level,
    json_output=config.json_output,
    tool_name="my_tool",
    config=config  # Pass config for all settings
)
```

## Common Patterns

### 1. Replacing output_* functions

```python
# Old
output_info("Starting changelog sync...")
output_success(f"✅ Synced {count} files")
output_error(f"❌ Failed: {error}")

# New
logger.info("Starting changelog sync")
logger.info("Synced files", count=count, status="success")
logger.error("Sync failed", error=str(error), error_type=type(error).__name__)
```

### 2. Debug Mode

```python
# Old
if os.getenv('DEBUG'):
    print(f"Debug: {message}")

# New (automatically handled by log level)
logger.debug("Debug message", extra_data={"key": "value"})
```

### 3. Progress Tracking

```python
# Old
for i, file in enumerate(files):
    print(f"Processing {i+1}/{len(files)}: {file}")
    # process file

# New
from tooling.core.logging import ProgressLogger

with ProgressLogger(logger, "file_processing") as progress:
    for i, file in enumerate(files):
        progress.update("Processing file", 
            current=i+1, 
            total=len(files),
            file=str(file)
        )
        # process file
```

### 4. Error Handling

```python
# Old
try:
    # operation
except Exception as e:
    output_error(f"Error: {e}")
    if os.getenv('DEBUG'):
        import traceback
        traceback.print_exc()

# New
try:
    # operation
except Exception as e:
    logger.exception("Operation failed",
        operation="file_sync",
        file_path=str(file_path)
    )
```

## Advanced Features

### Context Management

Add temporary context to all logs within a scope:

```python
from tooling.core.logging import log_context

with log_context(repository="my-repo", branch="main"):
    logger.info("Fetching commits")  # Will include repo and branch
    # All logs here will have the context
```

### Performance Tracking

```python
from tooling.core.logging import log_execution_time

@log_execution_time
def process_changelog(file_path):
    # Function execution time will be logged automatically
    pass
```

### JSON Output

For CI/CD or log aggregation:

```python
# Via environment variable
export JSON_OUTPUT=true

# Or programmatically
logger = setup_logging(json_output=True)
```

### File Logging

```python
from pathlib import Path

logger = setup_logging(
    log_file=Path("logs/my_tool.log"),
    tool_name="my_tool"
)
```

## Migration Checklist

1. **Install Dependencies**
   ```bash
   pip install -r requirements-shared.txt
   ```

2. **Update Imports**
   - Replace `from tooling.core.common_config import output_*`
   - With `from tooling.core.logging import setup_logging, get_logger`

3. **Initialize Logging**
   - Add `logger = setup_logging(tool_name="your_tool")` at the start
   - Pass configuration if available

4. **Replace Print Statements**
   - `output_info()` → `logger.info()`
   - `output_error()` → `logger.error()`
   - `output_success()` → `logger.info(status="success")`
   - `print()` for debug → `logger.debug()`

5. **Add Structured Data**
   - Instead of f-strings, pass data as keyword arguments
   - This enables better filtering and searching

6. **Handle Errors Properly**
   - Use `logger.exception()` in except blocks
   - Rich tracebacks are automatically enabled in debug mode

7. **Test Different Modes**
   - Run with `--debug` or `LOG_LEVEL=DEBUG`
   - Test with `JSON_OUTPUT=true`
   - Check file logging works

## Environment Variables

The new logging system respects these environment variables:

- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `JSON_OUTPUT`: Set to any value to enable JSON output
- `NO_COLOR`: Set to any value to disable colored output
- `TOOL_DEBUG`: Set to any value to enable debug mode

## Benefits

1. **Structured Data**: Easier to search and analyze logs
2. **Consistent Format**: All tools use the same logging format
3. **Better Errors**: Rich tracebacks with local variables in debug mode
4. **Performance**: Track slow operations automatically
5. **Flexibility**: JSON output for machines, pretty output for humans
6. **Context**: Add request IDs, user IDs, etc. to all logs in a scope
7. **Type Safety**: Configuration is validated with Pydantic