#!/usr/bin/env python3
"""
Structured logging setup for all tooling utilities.
Provides consistent logging configuration across all tools.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import logging
import sys
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import os
import json
from datetime import datetime

import structlog
from structlog.contextvars import merge_contextvars
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback

# Import our config module
from .base_config import ToolingConfig as BaseToolConfig, get_config as load_config


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[Path] = None,
    tool_name: Optional[str] = None,
    config: Optional[BaseToolConfig] = None,
    install_traceback: bool = True
) -> structlog.BoundLogger:
    """
    Configure structured logging for all tools.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to output JSON formatted logs
        log_file: Optional file path to write logs to
        tool_name: Name of the tool for context
        config: Optional configuration object to use
        install_traceback: Whether to install rich traceback handler
        
    Returns:
        Configured logger instance
    """
    # Load config if not provided
    if config is None:
        config = load_config()
    
    # Override with provided values
    if level == "INFO" and config.log_level:
        level = config.log_level.value if hasattr(config.log_level, 'value') else str(config.log_level)
    # Note: json_output is passed as parameter, not from config
    
    # Install rich traceback for better error display
    if install_traceback and not json_output:
        install_rich_traceback(show_locals=getattr(config, 'debug', False))
    
    # Configure standard logging first
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[],  # We'll add handlers manually
        force=True
    )
    
    # Create handlers
    handlers = []
    
    if json_output:
        # JSON output to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handlers.append(handler)
    else:
        # Rich console output with color
        console = Console(
            stderr=True,
            force_terminal=config.use_color,
            no_color=not config.use_color
        )
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=getattr(config, 'debug', False),
            rich_tracebacks=True,
            tracebacks_show_locals=getattr(config, 'debug', False),
            markup=True,
            enable_link_path=True
        )
        handler.setLevel(getattr(logging, level.upper()))
        handlers.append(handler)
    
    # Add file handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        handlers.append(file_handler)
    
    # Apply handlers to root logger
    root_logger = logging.getLogger()
    root_logger.handlers = handlers
    
    # Configure structlog
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    shared_processors = [
        merge_contextvars,  # Merge context variables
        structlog.stdlib.add_log_level,  # Add log level
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.stdlib.PositionalArgumentsFormatter(),  # Format positional args
        timestamper,  # Add timestamp
        structlog.processors.StackInfoRenderer(),  # Add stack info
        structlog.processors.format_exc_info,  # Format exceptions
    ]
    
    # Add tool name to context if provided
    if tool_name:
        shared_processors.insert(0, structlog.processors.add_log_level)
        shared_processors.insert(0, lambda _, __, event_dict: {**event_dict, "tool": tool_name})
    
    if json_output:
        # JSON rendering
        renderer = structlog.processors.JSONRenderer()
    else:
        # Console rendering with color
        renderer = structlog.dev.ConsoleRenderer(
            colors=config.use_color,
            exception_formatter=structlog.dev.rich_traceback if getattr(config, 'debug', False) else None
        )
    
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure the ProcessorFormatter for stdlib logging integration
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )
    
    # Apply formatter to all handlers
    for handler in handlers:
        if not isinstance(handler, RichHandler):  # RichHandler has its own formatting
            handler.setFormatter(formatter)
    
    # Get logger
    logger = structlog.get_logger(tool_name or "tooling")
    
    # Log initialization
    logger.debug(
        "logging_initialized",
        level=level,
        json_output=json_output,
        log_file=str(log_file) if log_file else None,
        tool_name=tool_name,
        debug_mode=getattr(config, 'debug', False)
    )
    
    return logger


def get_logger(
    name: Optional[str] = None,
    **context_vars
) -> structlog.BoundLogger:
    """
    Get a logger instance with optional context variables.
    
    Args:
        name: Logger name (defaults to caller's module)
        **context_vars: Additional context to bind to logger
        
    Returns:
        Bound logger instance
    """
    logger = structlog.get_logger(name)
    
    if context_vars:
        logger = logger.bind(**context_vars)
    
    return logger


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator to log function execution time.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        logger.debug(
            "function_start",
            function=func.__name__,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys())
        )
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.debug(
                "function_complete",
                function=func.__name__,
                duration_seconds=round(duration, 3)
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "function_error",
                function=func.__name__,
                duration_seconds=round(duration, 3),
                error_type=type(e).__name__
            )
            raise
    
    return wrapper


def log_context(**context_vars) -> Callable:
    """
    Context manager to temporarily bind context variables to logging.
    
    Args:
        **context_vars: Context variables to bind
        
    Example:
        with log_context(user_id=123, action="create"):
            logger.info("Processing request")
    """
    import contextlib
    from structlog.contextvars import bind_contextvars, unbind_contextvars
    
    @contextlib.contextmanager
    def context():
        bind_contextvars(**context_vars)
        try:
            yield
        finally:
            unbind_contextvars(*context_vars.keys())
    
    return context()


class ProgressLogger:
    """
    Logger that integrates with rich progress bars.
    """
    
    def __init__(self, logger: structlog.BoundLogger, task_name: str):
        self.logger = logger
        self.task_name = task_name
        self.start_time = datetime.now()
        
    def __enter__(self):
        self.logger.info(
            "task_start",
            task=self.task_name,
            start_time=self.start_time.isoformat()
        )
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(
                "task_failed",
                task=self.task_name,
                duration_seconds=round(duration, 3),
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )
        else:
            self.logger.info(
                "task_complete",
                task=self.task_name,
                duration_seconds=round(duration, 3)
            )
            
    def update(self, message: str, **kwargs):
        """Log progress update"""
        self.logger.info(
            "task_progress",
            task=self.task_name,
            message=message,
            **kwargs
        )


# Convenience functions for backward compatibility
def setup_basic_logging(debug: bool = False) -> None:
    """
    Quick setup for basic logging (backward compatibility).
    
    Args:
        debug: Whether to enable debug logging
    """
    level = "DEBUG" if debug else "INFO"
    setup_logging(level=level)


def get_console() -> Console:
    """
    Get a configured Rich console instance.
    
    Returns:
        Rich Console instance
    """
    config = load_config()
    return Console(
        stderr=True,
        force_terminal=config.use_color,
        no_color=not config.use_color
    )