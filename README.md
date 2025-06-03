# Runtime Tooling - Multi-Package Repository Management Suite

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
pip install runtime-tooling
```

### From Source

```bash
git clone https://github.com/yourusername/runtime-tooling.git
cd runtime-tooling
pip install -e .
```

### With Optional Dependencies

```bash
# Install with AI features (OpenAI support)
pip install runtime-tooling[ai]

# Install with development tools
pip install runtime-tooling[dev]

# Install everything
pip install runtime-tooling[all]
```

## Quick Start

### Initial Setup

```bash
# Set up AI tools and API keys
rt-setup

# This will:
# - Install gemini-cli
# - Configure API keys
# - Set up permissions
# - Show available tools
```

### Daily Workflow

```bash
# Generate AI-powered commit message (ultra-fast, 2-3s)
rtc  # or rt-commit-fast

# Generate changelog entries
rtcl  # or rt-changelog

# Create a new release
rtr  # or rt-release
```

## Available Commands

### AI-Powered Commit Tools

| Command | Description | Speed |
|---------|-------------|-------|
| `rtc` or `rt-commit-fast` | Ultra-fast AI commit messages | 2-3s |
| `rt-commit-fast --max` | Comprehensive analysis | 15-20s |
| `rt-commit` | Original detailed analyzer | 30-50s |

### Changelog Management

| Command | Description |
|---------|-------------|
| `rtcl` or `rt-changelog` | Generate changelog entries with AI |
| `rt-changelog-ultra` | Ultra-fast changelog sync (experimental) |
| `rt-changelog-analyze` | Analyze changelog history and patterns |

### Release Management

| Command | Description |
|---------|-------------|
| `rtr` or `rt-release` | Complete release workflow |
| `rt-prepare-patch` | Prepare a new patch version |
| `rt-push-patch` | Push release and create GitHub release |
| `rt-retag` | Fix/update an existing release tag |

### Version Management

| Command | Description |
|---------|-------------|
| `rt-version` | Update version across all packages |
| `rt-next-tag` | Calculate next patch version |

### Validation Tools

| Command | Description |
|---------|-------------|
| `rt-validate` | Validate changelog entries |
| `rt-prerelease-check` | Comprehensive pre-release validation |

### GitHub Integration

| Command | Description |
|---------|-------------|
| `rt-pr` | Create pull request with AI analysis |
| `rt-release-notes` | Generate release notes |

### Setup and Configuration

| Command | Description |
|---------|-------------|
| `rt-setup` | Complete AI tools setup |
| `rt-setup-permissions` | Fix script permissions |
| `rt-install-gemini` | Install gemini-cli |

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
rtc

# Push to branch
git push
```

### Release Workflow

```bash
# Start release process
rtr

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
rt-changelog-analyze

# Generate changelogs for historical commits
rt-changelog --smart-historical
```

## Architecture

### Package Structure

```
runtime-tooling/
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

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/runtime-tooling.git
cd runtime-tooling

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Format code
black tooling/
isort tooling/

# Type checking
mypy tooling/
```

### Adding New Commands

1. Create a new module in `tooling/cli/`
2. Add entry point in `setup.py` and `pyproject.toml`
3. Update `tooling/cli/__init__.py`
4. Add documentation to README

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

For more detailed documentation, see the [Wiki](https://github.com/yourusername/runtime-tooling/wiki).
