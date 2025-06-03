# Vector Search Library - Tooling Documentation

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Prerequisites & Setup](#prerequisites--setup)
4. [Core Workflows](#core-workflows)
5. [Script Categories](#script-categories)
6. [Detailed Script Documentation](#detailed-script-documentation)
   - [AI-Powered Tools](#ai-powered-tools)
   - [Release Management](#release-management)
   - [Version Control](#version-control)
   - [Validation & Testing](#validation--testing)
   - [Utility Scripts](#utility-scripts)
7. [Common Workflows](#common-workflows)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)
10. [Architecture & Design](#architecture--design)

---

## Overview

The Vector Search Library tooling suite is a comprehensive collection of Python scripts designed to automate and enhance the development workflow. These tools leverage AI (via Google's Gemini API) to provide intelligent commit messages, changelog generation, and release management across a multi-package repository structure.

### Key Features

- **AI-Powered Development**: Intelligent commit messages and changelog generation using Gemini AI
- **Multi-Package Support**: Manages Dart, Flutter, and Rust packages in a monorepo
- **Automated Release Management**: Complete release workflow from version bumping to GitHub releases
- **Smart Changelog Synchronization**: Maintains consistent changelogs across all packages
- **Comprehensive Validation**: Pre-release checks, changelog validation, and version consistency
- **Performance Optimized**: Fast operations with caching, parallel processing, and batch operations

### Repository Structure

```
vector_search/
├── dart/                    # Dart package
│   ├── CHANGELOG.md
│   └── pubspec.yaml
├── flutter/                 # Flutter package
│   ├── CHANGELOG.md
│   └── pubspec.yaml
├── dart/rust/              # Rust package
│   ├── CHANGELOG.md
│   └── Cargo.toml
└── tooling/                # All tooling scripts
    ├── README.md           # This file
    └── *.py               # Python scripts
```

---

## Quick Start

### 1. Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd vector_search

# Run the setup script
./tooling/setup_ai_tools.py

# This will:
# - Install gemini-cli
# - Configure API keys
# - Make all scripts executable
# - Show available tools
```

### 2. Daily Development

```bash
# Make your code changes...

# Generate AI-powered commit message (ultra-fast, 2-3s)
./tooling/smart_commit_fast.py

# Or for more detailed analysis
./tooling/smart_commit_fast.py --max
```

### 3. Release a New Version

```bash
# Complete release workflow
./tooling/release.py

# This will:
# - Check prerequisites
# - Generate changelogs
# - Bump versions
# - Create commits and tags
# - Push to GitHub
```

---

## Prerequisites & Setup

### System Requirements

- **Python**: 3.6 or higher
- **Git**: 2.0 or higher
- **Go**: Required for gemini-cli installation
- **Operating System**: macOS, Linux, or WSL on Windows

### API Key Setup

1. **Get a Gemini API Key**:
   ```bash
   # Visit: https://makersuite.google.com/app/apikey
   ```

2. **Secure Storage**:
   ```bash
   # Create secure key file
   mkdir -p ~/.secrets
   echo 'YOUR-API-KEY' > ~/.secrets/gemini_api_key
   chmod 600 ~/.secrets/gemini_api_key
   ```

3. **Shell Configuration**:
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export GEMINI_API_KEY="$(cat ~/.secrets/gemini_api_key 2>/dev/null)"
   export PATH=$PATH:~/go/bin
   
   # Reload shell
   source ~/.zshrc
   ```

### Running Setup

```bash
# Complete setup with AI tools
./tooling/setup_ai_tools.py

# Or just fix permissions
./tooling/setup_permissions.py
```

---

## Core Workflows

### 1. Smart Commits

The smart commit workflow uses AI to analyze your changes and generate conventional commit messages.

```bash
# Default: Ultra-fast mode (2-3s)
./tooling/smart_commit_fast.py

# Comprehensive analysis (15-20s)
./tooling/smart_commit_fast.py --max

# Enhanced multi-stage analysis (20-30s)
./tooling/smart_commit_fast.py --max --enhanced

# Original detailed analyzer (30-50s)
./tooling/smart_commit.py
```

### 2. Release Management

Complete release workflow with version management and changelog generation.

```bash
# Interactive release process
./tooling/release.py

# Options presented:
# 1. Patch release (bug fixes)
# 2. Minor release (new features)
# 3. Major release (breaking changes)
# 4. Custom version
```

### 3. Changelog Management

Synchronize and generate changelogs across all packages.

```bash
# Generate changelogs for current changes
./tooling/sync_changelogs.py

# Backfill historical changes
./tooling/sync_changelogs.py --smart-historical

# Analyze changelog history
./tooling/analyze_changelog_history.py
```

---

## Script Categories

### AI-Powered Tools

Tools that leverage Gemini AI for intelligent automation.

| Script | Purpose | Speed | Use Case |
|--------|---------|-------|----------|
| `smart_commit_fast.py` | Fast AI commit messages | 2-3s | Daily commits |
| `smart_commit.py` | Detailed commit analysis | 30-50s | Complex changes |
| `sync_changelogs.py` | AI changelog generation | Variable | Release prep |
| `sync_changelog_ultra.py` | Advanced changelog sync | Variable | Enterprise features |

### Release Management

Complete release lifecycle management tools.

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `release.py` | Full release workflow | Creating new releases |
| `prepare_new_patch.py` | Prepare patch release | Quick fixes |
| `push_new_patch.py` | Push release to GitHub | After preparation |
| `retag_release.py` | Fix existing releases | Correcting mistakes |
| `open_pull_request_current_tagged_branch.py` | Open PR for release branch | After release branch creation |
| `open_pull_request_current_tagged_branch.py` | AI-powered PR creation | Any branch needing a PR |

### Version Control

Version management across multiple packages.

| Script | Purpose | Example |
|--------|---------|---------|
| `update_version.py` | Update all versions | `./update_version.py 1.2.3` |
| `get_new_patch_tag.py` | Calculate next version | Shows next patch |
| `pre_release_check.py` | Validate before release | Pre-flight checks |

### Validation & Testing

Quality assurance and validation tools.

| Script | Purpose | Output |
|--------|---------|--------|
| `validate_changelogs.py` | Check changelog entries | Pass/fail status |
| `pre_release_check.py` | Comprehensive validation | Detailed report |
| `test_git_commands.py` | Test git operations | Debug info |

---

## Detailed Script Documentation

### AI-Powered Tools

#### `smart_commit_fast.py`

**Purpose**: Ultra-fast AI-powered commit message generation optimized for speed.

**Features**:
- Default Flash model (2-3s response time)
- Enhanced context gathering (file history, symbols, dependencies)
- Multi-stage analysis with `--max` flag
- Parallel package analysis
- Intelligent file categorization
- GitHub URL generation

**Usage**:
```bash
# Quick mode (default)
./tooling/smart_commit_fast.py

# Maximum analysis
./tooling/smart_commit_fast.py --max

# Enhanced multi-stage analysis
./tooling/smart_commit_fast.py --max --enhanced

# Skip cross-package analysis
./tooling/smart_commit_fast.py --max --skip-cross
```

**How it works**:
1. **Stage 0**: Gathers enhanced context (file history, symbols, dependencies)
2. **Stage 1**: Classifies changes by importance and type
3. **Stage 2**: Deep analysis of critical files
4. **Stage 3**: Analyzes dependency impacts
5. **Stage 4**: Generates metadata and commit message

**Output Example**:
```
feat(dart): implement advanced vector similarity search

- Added new VectorIndex class with HNSW algorithm support
- Implemented cosine and euclidean distance metrics
- Added batch processing for improved performance
- Updated API to support dimension validation

Breaking changes:
- VectorSearch.search() now requires explicit metric parameter
- Removed deprecated VectorSearch.findSimilar() method

Performance: ~3x faster for high-dimensional vectors
Test coverage: Added 25 new unit tests
```

#### `smart_commit.py`

**Purpose**: Original comprehensive commit analyzer with detailed cross-package analysis.

**Features**:
- Real-time progress tracking
- Parallel package analysis
- Cross-package dependency detection
- Comprehensive commit messages
- Interactive staging support

**Usage**:
```bash
# Run the analyzer
./tooling/smart_commit.py

# Will prompt for:
# - Staging unstaged files
# - Editing the generated message
# - Pushing to origin
```

**Analysis Process**:
1. Categorizes files by package
2. Analyzes each package in parallel
3. Detects cross-package impacts
4. Generates comprehensive message

#### `sync_changelogs.py`

**Purpose**: AI-powered changelog generation with git attribution.

**Features**:
- Multiple analysis modes
- Conventional commit parsing
- Automatic PR/issue linking
- Smart deduplication
- Batch processing
- Progress tracking

**Usage**:
```bash
# Current branch only
./tooling/sync_changelogs.py

# Smart historical mode (recommended)
./tooling/sync_changelogs.py --smart-historical

# Rebuild all changelogs
./tooling/sync_changelogs.py --rebuild-all

# Custom date range
CHANGELOG_BACKFILL_DATE=2024-01-01 ./tooling/sync_changelogs.py --smart-historical

# Dry run mode
./tooling/sync_changelogs.py --dry-run
```

**Analysis Modes**:
- **current-branch-only**: Analyzes only current branch changes
- **smart-historical**: Intelligently backfills missing entries
- **rebuild-all**: Complete changelog reconstruction

**Configuration** (via environment variables):
```bash
# Model selection
export GEMINI_MODEL="gemini-2.0-flash-exp"

# Backfill date
export CHANGELOG_BACKFILL_DATE="2024-06-01"

# Max commits to process
export MAX_COMMITS=1000
```

#### `sync_changelog_ultra.py`

**Purpose**: Enterprise-grade changelog synchronization with advanced features.

**Additional Features**:
- SQLite state management
- Webhook notifications
- HTML report generation
- Dependency graph analysis
- Performance metrics
- Resume capability
- Multiple output formats

**Usage**:
```bash
# With visualization
./tooling/sync_changelog_ultra.py --visualize

# Export formats
./tooling/sync_changelog_ultra.py --output-format json,html,release-notes

# Resume interrupted run
./tooling/sync_changelog_ultra.py --resume RUN_ID

# With webhooks
./tooling/sync_changelog_ultra.py --enable-webhooks
```

### Release Management

#### `release.py`

**Purpose**: Unified release management with complete automation.

**Features**:
- Interactive release type selection
- Version mismatch detection
- AI changelog generation
- Pre-release validation
- GitHub release creation
- Post-release instructions

**Workflow**:
```bash
./tooling/release.py

# 1. Checks prerequisites
# 2. Handles uncommitted changes
# 3. Determines release type
# 4. Runs pre-release checks
# 5. Generates changelogs
# 6. Prepares release
# 7. Reviews changes
# 8. Pushes release
# 9. Shows post-release info
```

**Release Types**:
- **Patch**: Bug fixes (1.2.3 → 1.2.4)
- **Minor**: New features (1.2.3 → 1.3.0)
- **Major**: Breaking changes (1.2.3 → 2.0.0)
- **Custom**: Specify exact version

#### `prepare_new_patch.py`

**Purpose**: Prepare a new patch release with changelog entries.

**Process**:
1. Determines next patch version
2. Reads package information
3. Prompts for changelog entries
4. Updates changelog files
5. Updates version numbers

**Usage**:
```bash
./tooling/prepare_new_patch.py

# Interactive prompts for each package:
# - Dart changes
# - Flutter changes
# - Rust changes
```

#### `push_new_patch.py`

**Purpose**: Commit and push prepared patch release.

**Features**:
- Validates changes
- Creates commit
- Creates git tag
- Pushes to remote
- Optional GitHub release

**Usage**:
```bash
./tooling/push_new_patch.py

# Automatically:
# - Commits with "Release vX.Y.Z"
# - Creates tag vX.Y.Z
# - Pushes to origin
# - Creates GitHub release (if gh CLI available)
```

#### `retag_release.py`

**Purpose**: Delete and recreate release tags with updated content.

**Use Cases**:
- Fix changelog entries
- Update release artifacts
- Correct version numbers
- Add missing information

**Features**:
- Safe tag deletion
- Changelog regeneration
- Commit preservation
- GitHub link generation

**Usage**:
```bash
./tooling/retag_release.py

# Interactive process:
# 1. Shows current release info
# 2. Confirms tag deletion
# 3. Updates changelogs
# 4. Allows manual edits
# 5. Recreates tag
# 6. Pushes to remote
```

#### `open_pull_request_current_tagged_branch.py`

**Purpose**: Open a pull request for any branch with AI-powered analysis using Gemini 2.5 Pro.

**Features**:
- Works with any branch type (feature, fix, chore, release, etc.)
- AI-powered PR title and description generation
- Comprehensive change analysis including file changes and commits
- Automatic changelog extraction if version is detected
- Smart label detection based on branch type and changes
- GitHub CLI integration

**Prerequisites**:
- GitHub CLI (`gh`) installed and authenticated
- Gemini API key configured (optional but recommended)

**Usage**:
```bash
./tooling/open_pull_request_current_tagged_branch.py

# Automatically:
# 1. Detects current branch and any associated tags
# 2. Analyzes all changes compared to base branch
# 3. Uses Gemini 2.5 Pro to generate PR title and description
# 4. Extracts changelog entries if version is found
# 5. Shows preview before creating PR
# 6. Adds smart labels based on branch type and changes
# 7. Optionally opens PR in browser
```

**AI Analysis Includes**:
- High-level summary of changes
- Key features or fixes implemented
- Breaking changes detection
- Testing considerations
- File change statistics
- Commit history analysis

### Version Control

#### `update_version.py`

**Purpose**: Update version numbers across all packages.

**Files Updated**:
- `dart/pubspec.yaml`
- `flutter/pubspec.yaml`
- `dart/rust/Cargo.toml`
- `dart/utils/configs/cargo.dart`

**Usage**:
```bash
# Update to specific version
./tooling/update_version.py 1.2.3

# Shows summary of changes
# Validates version format
```

#### `get_new_patch_tag.py`

**Purpose**: Calculate the next patch version tag.

**Features**:
- Semantic version parsing
- GitHub URL generation
- Tag existence checking
- Version validation

**Usage**:
```bash
./tooling/get_new_patch_tag.py

# Output:
# Latest tag: v1.2.3
# New tag: v1.2.4
# GitHub URLs provided
```

### Validation & Testing

#### `pre_release_check.py`

**Purpose**: Comprehensive pre-release validation.

**Checks Performed**:
1. Version consistency
2. Git repository state
3. Version tag availability
4. Changelog completeness
5. Dependency validation
6. Test execution

**Usage**:
```bash
./tooling/pre_release_check.py

# Detailed output with:
# - Check results
# - Fix suggestions
# - Duration metrics
# - Next steps
```

**Output Sections**:
- Prerequisites
- Version Consistency
- Git Status
- Version Tags
- Changelog Entries
- Dependencies
- Tests
- Summary with statistics

#### `validate_changelogs.py`

**Purpose**: Validate changelog format and content.

**Validation Rules**:
- Version headers exist
- No placeholder content
- Valid section names
- No duplicate versions
- Proper date formats
- Non-empty content

**Usage**:
```bash
./tooling/validate_changelogs.py

# Checks all changelogs
# Returns 0 if valid
# Returns 1 if issues found
```

### Utility Scripts

#### `setup_ai_tools.py`

**Purpose**: Complete setup for AI-powered tooling.

**Setup Process**:
1. Checks Go installation
2. Installs gemini-cli
3. Configures API keys
4. Sets permissions
5. Shows available tools

**Usage**:
```bash
./tooling/setup_ai_tools.py

# Interactive setup with:
# - Go installation help
# - API key configuration
# - PATH setup
# - Tool overview
```

#### `setup_permissions.py`

**Purpose**: Ensure all scripts have executable permissions.

**Usage**:
```bash
./tooling/setup_permissions.py

# Makes executable:
# - All .py scripts
# - All .sh scripts
# - Shows results
```

#### `analyze_changelog_history.py`

**Purpose**: Analyze git history for changelog backfilling.

**Features**:
- Repository history analysis
- Version gap detection
- Empty version identification
- Interactive date selection
- Integration with sync_changelogs

**Usage**:
```bash
# Analyze and show options
./tooling/analyze_changelog_history.py

# Auto-run sync after selection
./tooling/analyze_changelog_history.py --auto-run
```

#### `common_config.py`

**Purpose**: Shared configuration and utilities for all scripts.

**Provides**:
- Color constants
- Output functions
- File operations
- Git helpers
- Version utilities
- API key management

**Import**:
```python
from common_config import *

# Available functions:
print_color(Colors.GREEN, "Success!")
print_header("Section Title")
check_git_repo()
get_current_version()
```

### Testing Scripts

#### `test_git_commands.py`

**Purpose**: Test git command execution and output.

**Usage**:
```bash
./tooling/test_git_commands.py

# Tests:
# - Basic git commands
# - Output parsing
# - Error handling
```

#### `simple_changelog_test.py`

**Purpose**: Minimal test for changelog sync functionality.

**Usage**:
```bash
./tooling/simple_changelog_test.py

# Debug tool for:
# - Git command timeouts
# - Commit processing
# - Basic functionality
```

---

## Common Workflows

### Daily Development Workflow

```bash
# 1. Make code changes
git status

# 2. Generate commit message
./tooling/smart_commit_fast.py

# 3. Push to branch
git push origin feature-branch
```

### Release Workflow

```bash
# 1. Ensure clean state
git checkout main
git pull origin main

# 2. Run release tool
./tooling/release.py

# 3. Follow prompts:
#    - Choose release type
#    - Review changes
#    - Confirm release

# 4. Release is automatically:
#    - Tagged
#    - Pushed
#    - Released on GitHub
```

### Changelog Backfill Workflow

```bash
# 1. Analyze history
./tooling/analyze_changelog_history.py

# 2. Choose backfill range
#    - 1 week ago
#    - 1 month ago
#    - Since last release
#    - All history

# 3. Auto-runs sync_changelogs
# 4. Review generated entries
```

### Fix Release Workflow

```bash
# 1. Identify issue with release
git tag -l

# 2. Run retag tool
./tooling/retag_release.py

# 3. Update changelogs
# 4. Tag is recreated
# 5. Push to remote
```

### Manual Version Update

```bash
# 1. Update all versions
./tooling/update_version.py 2.0.0

# 2. Update changelogs
./tooling/sync_changelogs.py

# 3. Commit changes
./tooling/smart_commit_fast.py

# 4. Create tag
git tag v2.0.0
git push origin v2.0.0
```

---

## Configuration

### Environment Variables

```bash
# AI Model Selection
export GEMINI_MODEL="gemini-2.0-flash-exp"  # Fast model
export GEMINI_MODEL="gemini-2.0-flash-exp"  # Pro model

# API Keys
export GEMINI_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"  # Optional

# Changelog Settings
export CHANGELOG_BACKFILL_DATE="2024-01-01"
export MAX_COMMITS=1000
export BATCH_SIZE=10

# Performance
export MAX_WORKERS=4
export CONNECTION_POOL_SIZE=5
```

### Configuration Files

#### `.tooling/config.json` (Optional)

```json
{
  "model": "gemini-2.0-flash-exp",
  "max_commits": 1000,
  "batch_size": 10,
  "cache_ttl": 3600,
  "packages": {
    "dart": {
      "changelog": "dart/CHANGELOG.md",
      "version_file": "dart/pubspec.yaml"
    },
    "flutter": {
      "changelog": "flutter/CHANGELOG.md",
      "version_file": "flutter/pubspec.yaml"
    },
    "rust": {
      "changelog": "dart/rust/CHANGELOG.md",
      "version_file": "dart/rust/Cargo.toml"
    }
  }
}
```

### Git Configuration

```bash
# Recommended git settings
git config core.editor "vim"
git config push.default current
git config pull.rebase true
```

---

## Troubleshooting

### Common Issues

#### 1. API Key Not Found

**Error**: `GEMINI_API_KEY environment variable is not set`

**Solution**:
```bash
# Check current setting
echo $GEMINI_API_KEY

# Set temporarily
export GEMINI_API_KEY="your-key"

# Set permanently (add to ~/.zshrc)
echo 'export GEMINI_API_KEY="your-key"' >> ~/.zshrc
source ~/.zshrc
```

#### 2. gemini-cli Not Found

**Error**: `gemini-cli is not installed`

**Solution**:
```bash
# Run setup
./tooling/setup_ai_tools.py

# Or manually install
go install github.com/eliben/gemini-cli@latest

# Add to PATH
export PATH=$PATH:~/go/bin
```

#### 3. Permission Denied

**Error**: `Permission denied: ./tooling/script.py`

**Solution**:
```bash
# Fix all permissions
./tooling/setup_permissions.py

# Or manually
chmod +x tooling/*.py
```

#### 4. Git Command Timeout

**Error**: `Git command timed out`

**Solution**:
```bash
# Increase timeout in environment
export GIT_TIMEOUT=60

# Or use simple test
./tooling/simple_changelog_test.py
```

#### 5. Version Mismatch

**Error**: `Version mismatch detected`

**Solution**:
```bash
# Check current versions
grep version dart/pubspec.yaml
grep version flutter/pubspec.yaml
grep version dart/rust/Cargo.toml

# Fix with
./tooling/update_version.py 1.2.3
```

### Debug Mode

Enable debug output:
```bash
# Set debug environment
export DEBUG=1
export VERBOSE=1

# Run with Python debugging
python -m pdb tooling/script.py
```

### Performance Issues

#### Slow AI Responses

```bash
# Use fast model
export GEMINI_MODEL="gemini-2.0-flash-exp"

# Reduce batch size
export BATCH_SIZE=5

# Limit commits
export MAX_COMMITS=100
```

#### Memory Issues

```bash
# Reduce workers
export MAX_WORKERS=2

# Clear cache
rm -rf .tooling/cache/
```

---

## Architecture & Design

### Design Principles

1. **Modularity**: Each script has a single, well-defined purpose
2. **Composability**: Scripts can be combined into workflows
3. **Performance**: Optimized for speed with caching and parallelism
4. **Reliability**: Comprehensive error handling and validation
5. **User Experience**: Clear output, progress tracking, and helpful errors

### Technology Stack

- **Language**: Python 3.6+
- **AI**: Google Gemini API (via gemini-cli)
- **Version Control**: Git
- **Caching**: File-based with TTL
- **Parallelism**: ThreadPoolExecutor and ProcessPoolExecutor
- **State Management**: SQLite (in ultra version)

### Key Components

#### 1. Common Configuration (`common_config.py`)

Central module providing:
- Shared constants and colors
- Git operation wrappers
- File parsing utilities
- Version management
- API key handling

#### 2. AI Integration

Two-tier approach:
- **Fast Mode**: Single AI call with optimized prompts
- **Comprehensive Mode**: Multi-stage analysis with context gathering

#### 3. Caching Strategy

- **Prompt/Response Cache**: Reduces API calls
- **Git Command Cache**: Speeds up repeated operations
- **File Content Cache**: Avoids redundant reads
- **TTL Management**: Automatic cache expiration

#### 4. Error Handling

- **Graceful Degradation**: Falls back to simpler methods
- **Clear Error Messages**: User-friendly explanations
- **Recovery Options**: Suggestions for fixing issues
- **State Preservation**: Can resume interrupted operations

### Performance Optimizations

1. **Parallel Processing**:
   - Package analysis runs concurrently
   - File operations are batched
   - Git commands use connection pooling

2. **Smart Caching**:
   - LRU cache for git operations
   - Persistent cache for AI responses
   - Memory cache for file content

3. **Efficient Algorithms**:
   - Incremental changelog updates
   - Similarity matching for deduplication
   - Priority-based file selection

### Security Considerations

1. **API Key Protection**:
   - Never logged or displayed
   - Stored in secure files
   - Environment variable isolation

2. **File Safety**:
   - Automatic backups before changes
   - Dry-run mode for testing
   - Validation before writes

3. **Git Safety**:
   - Clean state validation
   - Remote sync checking
   - Tag existence verification

---

## Contributing

### Adding New Scripts

1. **Follow Naming Convention**: Use descriptive names with underscores
2. **Import Common Config**: Start with `from common_config import *`
3. **Add Documentation**: Include docstrings and usage examples
4. **Handle Errors**: Use try/except with helpful messages
5. **Add to README**: Document in appropriate section

### Code Style

- **PEP 8 Compliance**: Use standard Python formatting
- **Type Hints**: Add where beneficial
- **Docstrings**: Document all classes and functions
- **Comments**: Explain complex logic

### Testing

```bash
# Run basic tests
python -m pytest tooling/tests/

# Test specific script
python tooling/script.py --test

# Dry run mode
python tooling/script.py --dry-run
```

---

## License

Copyright (c) 2025 Tsavo Knott. All Rights Reserved.

These tooling scripts are proprietary and part of the Vector Search Library project.

---

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review script docstrings
3. Run with `--help` flag
4. Check git history for examples

---

*Last updated: 2025*

