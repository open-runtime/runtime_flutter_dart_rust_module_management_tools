# Development Guide for Runtime FDR (Flutter, Dart, Rust) Module Tools

This guide covers everything you need to know to develop, test, and contribute to the Runtime FDR (Flutter, Dart, Rust) Module Tools.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Virtual Environment Management](#virtual-environment-management)
3. [Command Line Interface](#command-line-interface)
4. [Testing Commands](#testing-commands)
5. [Project Structure](#project-structure)
6. [Adding New Commands](#adding-new-commands)
7. [Common Development Tasks](#common-development-tasks)
8. [Troubleshooting](#troubleshooting)

## Development Setup

### Prerequisites

- Python 3.7 or higher
- Git
- macOS, Linux, or Windows
- Gemini API key (for AI features)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools.git
cd runtime_flutter_dart_rust_module_management_tools

# Create virtual environment (REQUIRED on macOS/Linux)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks (optional but recommended)
pre-commit install
```

## Virtual Environment Management

### Why Virtual Environments?

Modern Python installations (PEP 668) require virtual environments to prevent breaking system packages. This is especially true on:
- macOS with Homebrew Python
- Ubuntu 23.04+
- Fedora 38+
- Any system with `python3-pip` installed via system package manager

### Daily Workflow

```bash
# Navigate to project and activate venv
cd /path/to/runtime_flutter_dart_rust_module_management_tools
source venv/bin/activate

# Your prompt should show (venv)
(venv) $ runtime_fdr_module_tools --help

# When done working
deactivate
```

### Shell Aliases (Recommended)

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Quick activation
alias rfdr-dev='cd ~/path/to/runtime_flutter_dart_rust_module_management_tools && source venv/bin/activate'

# Quick commands (if installed globally)
alias rfdr='runtime_fdr_module_tools'
alias rfdrc='runtime_fdr_module_tools commit'
alias rfdrr='runtime_fdr_module_tools release'
```

### VS Code Integration

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black"
}
```

## Command Line Interface

### Main Entry Point

All commands are accessed through the unified `runtime_fdr_module_tools` command:

```bash
runtime_fdr_module_tools <command> [options]
```

### Command Discovery

Commands are automatically discovered from Python files in `tooling/cli/`. The command name matches the filename (without .py extension).

### Examples

```bash
# View all available commands
runtime_fdr_module_tools

# Get detailed help
runtime_fdr_module_tools --list

# Show usage examples
runtime_fdr_module_tools --examples

# Show help for all commands at once
runtime_fdr_module_tools --help-all

# Run a specific command
runtime_fdr_module_tools smart_commit_fast
runtime_fdr_module_tools validate_changelogs --help

# Use aliases
runtime_fdr_module_tools commit  # Alias for smart_commit_fast
runtime_fdr_module_tools c       # Short alias
```

## Testing Commands

### Without Installation

You can test commands directly without installing:

```bash
# From project root (with venv activated)
python tooling/cli/main_router.py <command> [options]

# Examples
python tooling/cli/main_router.py --list
python tooling/cli/main_router.py commit --help
python tooling/cli/main_router.py validate_changelogs
```

### With Installation

After `pip install -e .`:

```bash
# Commands are available globally in the venv
runtime_fdr_module_tools commit
runtime_fdr_module_tools release
```

## Project Structure

```
runtime_flutter_dart_rust_module_management_tools/
├── tooling/
│   ├── cli/                    # All CLI commands
│   │   ├── main_router.py      # Unified entry point
│   │   ├── smart_commit_fast.py
│   │   ├── smart_commit.py
│   │   ├── validate_changelogs.py
│   │   └── ...                 # Other commands
│   ├── core/                   # Shared utilities
│   │   └── common_config.py    # Common functions and constants
│   ├── utils/                  # Helper modules
│   └── tests/                  # Test files
├── setup.py                    # Package configuration
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Direct dependencies
├── requirements-dev.txt        # Development dependencies
├── DEVELOPMENT.md              # This file
└── README.md                   # User documentation
```

## Adding New Commands

### 1. Create Command File

Create a new Python file in `tooling/cli/`:

```python
#!/usr/bin/env python3
"""
my_new_command.py - Description of what this command does

This command does X, Y, and Z.

Author: Your Name
License: MIT
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tooling.core.common_config import *
except ImportError:
    from core.common_config import *

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='What this command does'
    )
    parser.add_argument('--example', help='Example argument')
    args = parser.parse_args()
    
    # Your command logic here
    print_color(Colors.GREEN, "Command executed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 2. Test Your Command

```bash
# Test directly
python tooling/cli/my_new_command.py --help

# Test through router
python tooling/cli/main_router.py my_new_command --help

# After reinstalling
pip install -e .
runtime_fdr_module_tools my_new_command --help
```

### 3. Add Alias (Optional)

Edit `tooling/cli/main_router.py` and add to the `ALIASES` dictionary:

```python
ALIASES = {
    # ... existing aliases ...
    "mnc": "my_new_command",  # Add your alias
}
```

### 4. Update Documentation

- Add command to README.md command list
- Update this DEVELOPMENT.md if needed
- Add docstring to your command file

## Common Development Tasks

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tooling/tests/test_my_feature.py

# Run with coverage
pytest --cov=tooling --cov-report=html
```

### Code Formatting

```bash
# Format code with black
black tooling/

# Sort imports
isort tooling/

# Type checking
mypy tooling/
```

### Debugging

```bash
# Run command with Python debugger
python -m pdb tooling/cli/main_router.py commit

# Add breakpoints in code
import pdb; pdb.set_trace()

# Verbose output (add to your commands)
if args.verbose:
    print_color(Colors.GRAY, f"Debug: {variable}")
```

### Building Documentation

```bash
# Generate command list
runtime_fdr_module_tools --list > COMMANDS.md

# Update README sections
# (Currently manual, could be automated)
```

## Troubleshooting

### Common Issues

#### 1. "command not found: runtime_fdr_module_tools"

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall in development mode
pip install -e .

# Check installation
which runtime_fdr_module_tools
```

#### 2. Import Errors

```bash
# Ensure you're in the project root
pwd  # Should show .../runtime_flutter_dart_rust_module_management_tools

# Reinstall dependencies
pip install -e ".[dev]"
```

#### 3. "externally-managed-environment" Error

You must use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

#### 4. API Key Issues

```bash
# Check if API key is set
echo $GEMINI_API_KEY

# Run setup
runtime_fdr_module_tools setup_ai_tools
```

### Development Tips

1. **Always use virtual environment** - It's not optional on modern systems
2. **Test commands both ways** - Direct Python and through `runtime_fdr_module_tools`
3. **Follow existing patterns** - Look at existing commands for examples
4. **Use common_config.py** - Don't duplicate functionality
5. **Add helpful error messages** - Users appreciate clear guidance
6. **Document edge cases** - In code comments and docstrings

### Getting Help

- Check existing commands for patterns
- Read `tooling/core/common_config.py` for available utilities
- Open an issue on GitHub for questions
- Review closed PRs for examples

## Release Process

When you're ready to release:

1. Ensure all tests pass
2. Update version in `setup.py` and `pyproject.toml`
3. Update CHANGELOG.md
4. Create PR with changes
5. After merge, tag release
6. GitHub Actions will handle PyPI deployment

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes following the patterns above
4. Test thoroughly
5. Commit with meaningful messages (use `runtime_fdr_module_tools commit`!)
6. Push and create Pull Request

Remember: This project eats its own dog food - use the tools to develop the tools! 