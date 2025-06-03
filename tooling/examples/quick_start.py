#!/usr/bin/env python3
"""
Quick start example showing configuration and logging together.

This is a minimal example to get you started with the new systems.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.config import load_config, BaseToolConfig
from tooling.core.logging import setup_logging


def main():
    """Simple example of using config and logging together"""
    
    # Load configuration (reads from environment and .env file)
    config = load_config(BaseToolConfig)
    
    # Setup logging using the configuration
    logger = setup_logging(
        tool_name="quick_start",
        config=config  # Automatically uses config settings
    )
    
    # Log some information
    logger.info("Application started", 
        debug_mode=config.debug,
        log_level=config.log_level,
        project_root=str(config.project_root)
    )
    
    # Example: Check if we have AI capabilities
    if config.ai_api_key:
        logger.info("AI features available", model=config.ai_model)
    else:
        logger.warning("No AI API key configured", 
            hint="Set GEMINI_API_KEY environment variable"
        )
    
    # Example: Simulate some work
    logger.info("Processing task", timeout=config.timeout)
    
    # Example: Debug information (only shows if LOG_LEVEL=DEBUG)
    logger.debug("Configuration details",
        use_color=config.use_color,
        use_emoji=config.use_emoji,
        git_timeout=config.git_timeout
    )
    
    logger.info("Application completed successfully")


if __name__ == "__main__":
    print("=== Quick Start Example ===")
    print("This example shows basic usage of config + logging")
    print("\nTry running with different settings:")
    print("  LOG_LEVEL=DEBUG python quick_start.py")
    print("  JSON_OUTPUT=1 python quick_start.py")
    print("  NO_COLOR=1 python quick_start.py")
    print("-" * 50)
    
    main()