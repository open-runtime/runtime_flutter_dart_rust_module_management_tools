#!/usr/bin/env python3
"""
Example of using the new Pydantic-based configuration system.

Run this example to see the new config in action:
    python -m tooling.examples.config_example
"""

import os
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.base_config import get_config, ToolingConfig, PackageType
from tooling.core.config_migration import create_migration_config


def demonstrate_new_config():
    """Demonstrate the new configuration system"""
    
    # Method 1: Direct usage with type-safe config
    print("=== Method 1: Direct Pydantic Config ===")
    config = get_config(verbose=True)
    
    # Print with rich formatting
    config.print_header("New Configuration System Demo")
    
    # Show configuration values
    config.print_info(f"Project root: {config.project_root}")
    config.print_info(f"Log level: {config.log_level}")
    config.print_info(f"Dart package: {config.dart_package_name}")
    config.print_info(f"Flutter package: {config.flutter_package_name}")
    config.print_info(f"Rust package: {config.rust_package_name}")
    
    # Check AI configuration
    if config.has_ai_configured:
        config.print_success("AI is configured and ready!")
    else:
        config.print_warning("AI is not configured")
    
    # Show package information
    config.print_header("Package Information")
    packages = config.get_package_info()
    
    for pkg_type, pkg_info in packages.items():
        if pkg_info.exists:
            config.print_success(f"{pkg_type.value}: {pkg_info.name} at {pkg_info.path}")
        else:
            config.print_error(f"{pkg_type.value}: {pkg_info.name} not found at {pkg_info.path}")
    
    print("\n" + "="*60 + "\n")


def demonstrate_migration_helper():
    """Demonstrate migration from old to new system"""
    
    print("=== Method 2: Migration Helper (Backward Compatible) ===")
    helper = create_migration_config(quiet=False)
    
    # Use old-style functions with new config
    helper.print_header("Migration Helper Demo")
    
    # Old-style color printing
    from tooling.cli.cli_utils import Colors
    helper.print_color(Colors.GREEN, "✓ Success message")
    helper.print_color(Colors.RED, "✗ Error message")
    helper.print_color(Colors.YELLOW, "⚠ Warning message")
    helper.print_color(Colors.BLUE, "ℹ Info message")
    
    # Get package info in old format
    old_style_info = helper.get_package_info()
    helper.print_header("Old-Style Package Info")
    
    for key, info in old_style_info.items():
        helper.print_color(Colors.GRAY, f"{key}: {info['name']}")
    
    print("\n" + "="*60 + "\n")


def demonstrate_environment_variables():
    """Show how environment variables work"""
    
    print("=== Environment Variable Configuration ===")
    
    # Set some environment variables
    os.environ["RUNTIME_FDR_LOG_LEVEL"] = "DEBUG"
    os.environ["RUNTIME_FDR_USE_COLOR"] = "false"
    os.environ["RUNTIME_FDR_MAX_RETRIES"] = "5"
    
    # Create config - it will pick up env vars automatically
    config = get_config()
    
    config.print_header("Environment Variable Demo")
    print(f"Log level from env: {config.log_level}")
    print(f"Use color from env: {config.use_color}")
    print(f"Max retries from env: {config.max_retries}")
    
    # Clean up
    del os.environ["RUNTIME_FDR_LOG_LEVEL"]
    del os.environ["RUNTIME_FDR_USE_COLOR"]
    del os.environ["RUNTIME_FDR_MAX_RETRIES"]
    
    print("\n" + "="*60 + "\n")


def demonstrate_validation():
    """Show validation in action"""
    
    print("=== Validation Demo ===")
    
    try:
        # This will fail validation
        config = get_config(max_retries=20)  # Max is 10
    except Exception as e:
        print(f"Validation error (expected): {e}")
    
    try:
        # This will also fail
        config = get_config(timeout=1000)  # Max is 600
    except Exception as e:
        print(f"Validation error (expected): {e}")
    
    # This will succeed
    config = get_config(max_retries=5, timeout=60)
    print(f"Valid config created: retries={config.max_retries}, timeout={config.timeout}s")
    
    print("\n" + "="*60 + "\n")


def main():
    """Run all demonstrations"""
    print("\n🚀 Pydantic Configuration System Demo\n")
    
    try:
        demonstrate_new_config()
        demonstrate_migration_helper()
        demonstrate_environment_variables()
        demonstrate_validation()
        
        print("✅ All demonstrations completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()