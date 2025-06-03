#!/usr/bin/env python3
"""
Example demonstrating the structured logging setup.

This shows how to use the new logging system in your tools.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.logging import (
    setup_logging,
    get_logger,
    log_execution_time,
    log_context,
    ProgressLogger
)
from tooling.core.config import load_config


@log_execution_time
def slow_function(duration: float = 1.0):
    """Example function that takes some time"""
    logger = get_logger(__name__)
    logger.info("slow_function_started", duration=duration)
    time.sleep(duration)
    logger.info("slow_function_completed")
    return f"Slept for {duration} seconds"


def example_basic_logging():
    """Example of basic logging setup"""
    print("\n=== Basic Logging Example ===")
    
    # Setup logging
    logger = setup_logging(level="INFO", tool_name="example_tool")
    
    # Log at different levels
    logger.debug("This is a debug message (won't show at INFO level)")
    logger.info("This is an info message", user="test_user", action="login")
    logger.warning("This is a warning", low_memory=True, threshold_mb=100)
    logger.error("This is an error", error_code=404, endpoint="/api/users")
    
    # Log with structured data
    logger.info(
        "user_action",
        action="create_file",
        file_path="/tmp/test.txt",
        size_bytes=1024,
        metadata={"type": "text", "encoding": "utf-8"}
    )


def example_debug_logging():
    """Example with debug logging enabled"""
    print("\n=== Debug Logging Example ===")
    
    # Setup with debug level
    logger = setup_logging(level="DEBUG", tool_name="debug_example")
    
    logger.debug("Debug mode enabled", system_info={"os": "darwin", "python": "3.11"})
    logger.info("Running slow function")
    
    # This will log execution time due to decorator
    result = slow_function(0.5)
    logger.info("Function result", result=result)


def example_json_logging():
    """Example with JSON output"""
    print("\n=== JSON Logging Example ===")
    
    # Setup with JSON output
    logger = setup_logging(level="INFO", json_output=True, tool_name="json_example")
    
    logger.info(
        "application_start",
        version="1.0.0",
        environment="development",
        features=["logging", "config", "validation"]
    )
    
    logger.warning(
        "deprecation_warning",
        feature="old_api",
        removal_version="2.0.0",
        alternative="new_api"
    )


def example_context_logging():
    """Example using context managers"""
    print("\n=== Context Logging Example ===")
    
    logger = setup_logging(level="INFO", tool_name="context_example")
    
    # Use context manager to add temporary context
    with log_context(request_id="abc123", user_id=42):
        logger.info("Processing request")
        
        with log_context(operation="database_query"):
            logger.info("Executing query", table="users", limit=10)
            
        logger.info("Request completed")
    
    # Context is removed after the with block
    logger.info("Outside context (no request_id or user_id)")


def example_progress_logging():
    """Example using progress logger"""
    print("\n=== Progress Logging Example ===")
    
    logger = setup_logging(level="INFO", tool_name="progress_example")
    
    # Use progress logger for long-running tasks
    with ProgressLogger(logger, "data_processing") as progress:
        progress.update("Loading data", files_count=100)
        time.sleep(0.5)
        
        progress.update("Processing files", processed=50, total=100)
        time.sleep(0.5)
        
        progress.update("Saving results", output_file="results.json")
        time.sleep(0.5)


def example_error_logging():
    """Example of error logging with traceback"""
    print("\n=== Error Logging Example ===")
    
    logger = setup_logging(level="INFO", tool_name="error_example")
    
    try:
        # This will cause an error
        result = 1 / 0
    except Exception as e:
        logger.exception(
            "calculation_error",
            operation="division",
            numerator=1,
            denominator=0
        )


def example_file_logging():
    """Example logging to file"""
    print("\n=== File Logging Example ===")
    
    log_file = Path("example.log")
    logger = setup_logging(
        level="DEBUG",
        tool_name="file_example",
        log_file=log_file
    )
    
    logger.info("Logging to file", log_file=str(log_file))
    logger.debug("Debug information", detail="This will be in the file")
    logger.warning("Warning message", severity="medium")
    
    print(f"Log file created at: {log_file.absolute()}")


def main():
    """Run all examples"""
    examples = [
        example_basic_logging,
        example_debug_logging,
        example_json_logging,
        example_context_logging,
        example_progress_logging,
        example_error_logging,
        example_file_logging
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")
        
        # Small pause between examples
        time.sleep(0.5)
    
    print("\n=== All examples completed ===")


if __name__ == "__main__":
    main()