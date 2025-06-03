# Runtime FDR (Flutter, Dart, Rust) Package Tools - Multi-Package Repository Management Suite

A comprehensive collection of CLI tools for managing multi-package repositories with AI-powered commit messages, changelog generation, and release automation.

## Features

- 🤖 **AI-Powered Commit Messages**: Generate intelligent commit messages using Gemini AI
- 📋 **Automated Changelog Management**: Sync and generate changelogs across multiple packages
- 🚀 **Release Automation**: Complete release workflow from version bumping to GitHub releases
- ✅ **Validation Tools**: Pre-release checks, changelog validation, and version consistency
- 🔗 **GitHub Integration**: Create PRs, generate release notes, and manage tags
- 📦 **Multi-Package Support**: Manage Dart, Flutter, Rust, and other packages in a monorepo

## Installation

### From PyPI

```bash
pip install runtime-fdr-pkg-tools
```

### From Source (Recommended for Development)

**Important**: On macOS with Homebrew Python or any system with PEP 668 compliance, you must use a virtual environment.

```bash
# Clone the repository
git clone https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools.git
cd runtime_flutter_dart_rust_package_management_tools

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# The runtime_fdr_tools command is now available
runtime_fdr_tools --help
```

### With Optional Dependencies

```bash
# Install with AI features (OpenAI support)
pip install runtime-fdr-pkg-tools[ai]

# Install with development tools
pip install runtime-fdr-pkg-tools[dev]

# Install everything
pip install runtime-fdr-pkg-tools[all]
```

### Virtual Environment Setup (Required on macOS/Linux)

Modern Python installations (especially on macOS with Homebrew) require using virtual environments to avoid breaking system packages:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (you'll need to do this each time you work on the project)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Your prompt should now show (venv)
# Install the package
pip install -e .

# When done, deactivate
deactivate
```

**Pro tip**: Add an alias to your shell configuration:
```bash
# Add to ~/.zshrc or ~/.bashrc
alias rfdr='cd /path/to/runtime_flutter_dart_rust_package_management_tools && source venv/bin/activate'
```

## Quick Start

### Initial Setup

```bash
# View all available tools
runtime_fdr_tools

# Or get detailed help for all commands
runtime_fdr_tools --list

# Set up AI tools and API keys
runtime_fdr_tools setup_ai_tools

# This will:
# - Install gemini-cli
# - Configure API keys
# - Set up permissions
# - Show available tools
```

### Daily Workflow

```bash
# Generate AI-powered commit message (ultra-fast, 2-3s)
runtime_fdr_tools commit  # or runtime_fdr_tools c

# Generate changelog entries
runtime_fdr_tools sync_changelogs  # or runtime_fdr_tools changelog

# Create a new release
runtime_fdr_tools release  # or runtime_fdr_tools r
```

## Available Commands

### Main Entry Point

All commands are accessed through the unified `runtime_fdr_tools` command:

```bash
runtime_fdr_tools <command> [options]
```

Commands map directly to Python files in the tooling/cli directory.

| Option | Description |
|---------|-------------|
| `--list` | Show all available commands with descriptions |
| `--examples` | Show usage examples |
| `--help-all` | Show detailed help for all commands in one view |

### AI-Powered Commit Tools

| Command | Aliases | Description | Speed |
|---------|---------|-------------|-------|
| `smart_commit_fast` | `commit`, `c` | Ultra-fast AI commit messages | 2-3s |
| `smart_commit_fast --max` | | Comprehensive analysis | 15-20s |
| `smart_commit` | `commit_detailed`, `cd` | Original detailed analyzer | 30-50s |

### Changelog Management

| Command | Aliases | Description |
|---------|---------|-------------|
| `sync_changelogs` | `changelog`, `cl` | Generate changelog entries with AI |
| `analyze_changelog_history` | `analyze` | Analyze changelog history and patterns |

### Release Management

| Command | Aliases | Description |
|---------|---------|-------------|
| `release` | `r` | Complete release workflow |
| `prepare_new_patch` | `prepare` | Prepare a new patch version |
| `push_new_patch` | `push` | Push release and create GitHub release |
| `retag_release` | `retag` | Fix/update an existing release tag |

### Version Management

| Command | Aliases | Description |
|---------|---------|-------------|
| `update_version` | `version`, `v` | Update version across all packages |
| `get_new_patch_tag` | `next` | Calculate next patch version |

### Validation Tools

| Command | Aliases | Description |
|---------|---------|-------------|
| `validate_changelogs` | `validate` | Validate changelog entries |
| `pre_release_check` | `check` | Comprehensive pre-release validation |

### GitHub Integration

| Command | Aliases | Description |
|---------|---------|-------------|
| `open_pull_request_current_tagged_branch` | `pr` | Create pull request with AI analysis |
| `generate_release_notes` | `notes` | Generate release notes |

### Setup and Configuration

| Command | Aliases | Description |
|---------|---------|-------------|
| `setup_ai_tools` | `setup`, `s` | Complete AI tools setup |
| `setup_permissions` | `permissions` | Fix script permissions |
| `install_gemini_cli` | `gemini` | Install gemini-cli |

## Configuration

### API Keys

Set up your Gemini API key:

```bash
# Option 1: Environment variable
export GEMINI_API_KEY="your-api-key"

# Option 2: Secure file
mkdir -p ~/.secrets
echo 'your-api-key' > ~/.secrets/gemini_api_key
chmod 600 ~/.secrets/gemini_api_key

# Add to shell config
echo 'export GEMINI_API_KEY="$(cat ~/.secrets/gemini_api_key 2>/dev/null)"' >> ~/.zshrc
```

### Project Structure

The tools expect a multi-package repository structure:

```
your-project/
├── dart/
│   ├── CHANGELOG.md
│   └── pubspec.yaml
├── flutter/
│   ├── CHANGELOG.md
│   └── pubspec.yaml
├── dart/rust/
│   ├── CHANGELOG.md
│   └── Cargo.toml
└── CHANGELOG.md  # Root changelog
```

## Common Workflows

### Daily Development

```bash
# Make your changes
git add .

# Generate AI commit message
runtime_fdr_tools commit  # or runtime_fdr_tools c

# Push to branch
git push
```

### Release Workflow

```bash
# Start release process
runtime_fdr_tools release  # or runtime_fdr_tools r

# This will:
# 1. Check prerequisites
# 2. Generate changelogs
# 3. Bump versions
# 4. Create commits and tags
# 5. Push to GitHub
```

### Changelog Backfill

```bash
# Analyze history
runtime_fdr_tools analyze_changelog_history

# Generate changelogs for historical commits
runtime_fdr_tools sync_changelogs --smart-historical
```

## Architecture

### Package Structure

```
runtime-fdr-pkg-tools/
├── tooling/
│   ├── core/           # Core utilities (common_config)
│   ├── cli/            # CLI command modules
│   ├── utils/          # Helper utilities
│   └── tests/          # Test modules
├── setup.py            # Package configuration
├── pyproject.toml      # Modern Python packaging
└── requirements.txt    # Dependencies
```

### Dependencies

The package is organized into modular components:

- **Core Module**: `common_config.py` - Shared utilities and constants
- **CLI Modules**: Individual command implementations
- **Test Modules**: Testing utilities

### Inter-Script Dependencies

```
common_config.py
    ├── Used by all CLI scripts
    └── Provides: colors, git ops, file parsing, etc.

release.py
    ├── Calls: prepare_new_patch.py
    ├── Calls: push_new_patch.py
    ├── Calls: sync_changelogs.py
    └── Calls: pre_release_check.py

smart_commit_fast.py / smart_commit.py
    └── Standalone (uses common_config)

sync_changelogs.py
    └── Can call: analyze_changelog_history.py
```

## Development

**Important**: See [DEVELOPMENT.md](DEVELOPMENT.md) for comprehensive development documentation.

### Quick Start for Developers

```bash
# Clone the repository
git clone https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools.git
cd runtime_flutter_dart_rust_package_management_tools

# Create and activate virtual environment (REQUIRED)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .[dev]

# Test the installation
runtime_fdr_tools --help
```

### Key Points

- **Virtual Environment Required**: Modern Python (PEP 668) requires venv
- **Unified CLI**: All commands through `runtime_fdr_tools`
- **Auto-discovery**: Commands map to Python files in `tooling/cli/`
- **Development Mode**: Use `pip install -e .` for live code changes

### Adding New Commands

1. Create `tooling/cli/your_command.py`
2. Command is automatically available as `runtime_fdr_tools your_command`
3. Add aliases in `main_router.py` if desired
4. See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed instructions

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```bash
   rt-setup  # Run setup to configure API key
   ```

2. **Import Errors**
   ```bash
   pip install -e .  # Reinstall in development mode
   ```

3. **Command Not Found**
   ```bash
   # Ensure pip scripts directory is in PATH
   export PATH="$PATH:~/.local/bin"
   ```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.

## Author

Tsavo Knott (2025)

---

For more detailed documentation, see the [Wiki](https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools/wiki).
