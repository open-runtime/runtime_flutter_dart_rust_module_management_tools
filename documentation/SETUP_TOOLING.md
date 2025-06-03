# Vector Search Tooling Setup Guide

This document provides comprehensive documentation for all tooling scripts in the `./tooling` directory. These scripts automate various development workflows including releases, version management, changelog generation, and AI-powered commit messages.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Core Release Management](#core-release-management)
3. [Version Management](#version-management)
4. [AI-Powered Commit Tools](#ai-powered-commit-tools)
5. [Changelog Management](#changelog-management)
6. [Validation and Testing](#validation-and-testing)
7. [Common Workflows](#common-workflows)
8. [Troubleshooting](#troubleshooting)

## Initial Setup

### 1. Install AI Tools (Required for AI Features)

```bash
python tooling/setup_ai_tools.py
```

This script:
- Installs Go (if not present)
- Installs gemini-cli for AI-powered features
- Configures Gemini API key
- Sets up proper permissions
- Validates the installation

### 2. Set Script Permissions

```bash
python tooling/setup_permissions.py
```

Makes all tooling scripts executable (chmod +x).

### 3. Configure Environment

Set your Gemini API key (required for AI features):
```bash
export GEMINI_API_KEY="your-api-key-here"
```

## Core Release Management

### release.py - Unified Release Manager

**Purpose**: Central entry point for creating releases with full automation.

**Usage**:
```bash
python tooling/release.py [options]
```

**Options**:
- `--type {patch,minor,major}` - Release type (interactive if not specified)
- `--skip-tests` - Skip test execution
- `--skip-github-release` - Skip GitHub release creation
- `--use-ai` - Enable AI for changelog generation
- `--no-push` - Prepare release without pushing

**Features**:
- Interactive release type selection
- AI-powered changelog generation
- Version mismatch detection and fixing
- Pre-release validation checks
- Automated commit and tag creation
- GitHub release integration
- Rollback on failure

### prepare_new_patch.py - Manual Release Preparation

**Purpose**: First step in manual release process - updates versions and changelogs.

**Usage**:
```bash
python tooling/prepare_new_patch.py
```

**Operations**:
1. Determines next patch version
2. Extracts package information
3. Prompts for changelog entries
4. Updates version files
5. Prepares changes for commit

### push_new_patch.py - Manual Release Finalization

**Purpose**: Final step in manual release process - commits and pushes changes.

**Usage**:
```bash
python tooling/push_new_patch.py [--skip-github-release]
```

**Operations**:
1. Validates uncommitted changes
2. Creates git commit with release message
3. Creates annotated git tag
4. Pushes changes to remote
5. Optionally creates GitHub release

## Version Management

### get_new_patch_tag.py - Next Version Calculator

**Purpose**: Calculates the next semantic version number.

**Usage**:
```bash
python tooling/get_new_patch_tag.py
```

**Output**: Next patch version (e.g., v0.5.201)

### update_version.py - Version Synchronizer

**Purpose**: Updates version numbers across all package files.

**Usage**:
```bash
python tooling/update_version.py <version>
```

**Example**:
```bash
python tooling/update_version.py 0.5.201
```

**Updates**:
- `dart/pubspec.yaml`
- `flutter/pubspec.yaml`
- `dart/rust/Cargo.toml`

### retag_release.py - Release Fixer

**Purpose**: Delete and recreate a release tag (for fixing mistakes).

**Usage**:
```bash
python tooling/retag_release.py
```

**Features**:
- Safe tag deletion (local and remote)
- AI-powered changelog updates
- Preserves release timestamp
- Commit and tag recreation

### open_pull_request_current_tagged_branch.py - AI-Powered PR Creator/Updater

**Purpose**: Create or update pull requests for any branch with AI-powered analysis.

**Usage**:
```bash
python tooling/open_pull_request_current_tagged_branch.py
```

**Features**:
- Works with any branch type
- Creates new PRs or updates existing ones
- Gemini 2.5 Pro analysis of changes
- Smart PR title and description generation
- Automatic changelog extraction
- Intelligent label detection
- GitHub CLI integration
- Shows diff of changes when updating
- Interactive workflow with preview

**Update Mode**:
When a PR already exists for the current branch, the tool offers to:
1. Update the PR with fresh AI-generated content
2. View the existing PR in browser
3. Cancel the operation

The update process shows what will change and optionally displays a diff of the description changes.

## AI-Powered Commit Tools

### smart_commit_fast.py - Ultra-Fast AI Commits

**Purpose**: Quick commits with AI-generated messages (2-3 seconds).

**Usage**:
```bash
python tooling/smart_commit_fast.py [options]
```

**Options**:
- `--enhanced` - Use multi-stage analysis for better messages
- `--conventional` - Force conventional commit format
- `--no-emoji` - Disable emoji usage
- `--metadata` - Include git metadata in message
- `--verbose` - Show analysis details

**Features**:
- Enhanced context gathering from file content
- Multi-stage commit analysis
- GitHub URL integration
- Intelligent emoji selection
- Parallel file processing

### smart_commit.py - Comprehensive Commit Analyzer

**Purpose**: Detailed analysis for complex multi-package changes.

**Usage**:
```bash
python tooling/smart_commit.py [options]
```

**Options**:
- `--verbose` - Show detailed analysis
- `--conventional` - Use conventional commit format
- `--max-files` - Limit files analyzed (default: 50)

**Features**:
- Cross-package dependency detection
- Deep file content analysis
- Comprehensive commit messages
- Package-specific change summaries

## Changelog Management

### sync_changelogs.py - Production Changelog Generator

**Purpose**: Generate changelog entries from git history using AI.

**Usage**:
```bash
# Basic usage (since last tag)
python tooling/sync_changelogs.py

# Specify range
python tooling/sync_changelogs.py --since-tag v0.5.195 --until-tag v0.5.200

# Custom date range
python tooling/sync_changelogs.py --since-date "2024-01-01"
```

**Options**:
- `--since-tag` - Start tag for changelog generation
- `--until-tag` - End tag (default: HEAD)
- `--since-date` - Alternative to tags, use date
- `--packages` - Specific packages to update
- `--force` - Regenerate existing entries
- `--parallel` - Number of parallel processes
- `--config` - Custom config file path

**Features**:
- Tag-based commit processing
- GitHub user attribution
- File content analysis
- Response caching
- Parallel processing
- Multi-package support

### sync_changelog_ultra.py - Enhanced Changelog Generator

**Purpose**: Advanced changelog generation with enterprise features.

**Usage**:
```bash
python tooling/sync_changelog_ultra.py [options]
```

**Additional Features**:
- Asynchronous processing
- Embeddings for semantic analysis
- Breaking change detection
- Webhook notifications
- Changelog visualization
- Multiple export formats

### validate_changelogs.py - Changelog Validator

**Purpose**: Ensure all changelogs have proper entries.

**Usage**:
```bash
python tooling/validate_changelogs.py
```

**Checks**:
- Version entry presence
- Section formatting
- Placeholder detection
- Cross-package consistency

### analyze_changelog_history.py - History Analyzer

**Purpose**: Analyze repository history for changelog backfilling.

**Usage**:
```bash
python tooling/analyze_changelog_history.py
```

**Features**:
- Repository history visualization
- Changelog gap detection
- Interactive range selection
- Tag timeline display

## Validation and Testing

### pre_release_check.py - Pre-Release Validator

**Purpose**: Comprehensive validation before releases.

**Usage**:
```bash
python tooling/pre_release_check.py [--skip-tests]
```

**Checks**:
- Version consistency across packages
- Clean git working directory
- Tag availability
- Changelog completeness
- Test suite execution (optional)
- Build verification

### test_git_commands.py - Git Command Tester

**Purpose**: Debug git command execution issues.

**Usage**:
```bash
python tooling/test_git_commands.py
```

### test_hang.py - Hang Debugger

**Purpose**: Isolate hanging issues in scripts.

**Usage**:
```bash
python tooling/test_hang.py
```

### simple_changelog_test.py - Minimal Test

**Purpose**: Basic changelog functionality test.

**Usage**:
```bash
python tooling/simple_changelog_test.py
```

## Common Workflows

### 1. Daily Development Workflow

```bash
# Make changes to code
git add .

# Quick AI commit
python tooling/smart_commit_fast.py

# Or for complex changes
python tooling/smart_commit.py
```

### 2. Release Workflow (Automated)

```bash
# Run unified release manager
python tooling/release.py

# It will:
# 1. Ask for release type (patch/minor/major)
# 2. Run pre-release checks
# 3. Generate changelogs with AI
# 4. Update versions
# 5. Commit and tag
# 6. Push to remote
# 7. Create GitHub release
```

### 3. Release Workflow (Manual)

```bash
# Step 1: Prepare release
python tooling/prepare_new_patch.py

# Step 2: Review changes
git status
git diff

# Step 3: Push release
python tooling/push_new_patch.py
```

### 4. Changelog Backfilling

```bash
# Step 1: Analyze history
python tooling/analyze_changelog_history.py

# Step 2: Generate changelogs for range
python tooling/sync_changelogs.py --since-tag v0.5.195 --until-tag v0.5.200

# Step 3: Validate
python tooling/validate_changelogs.py
```

### 5. Fixing a Released Version

```bash
# If you need to fix a release after tagging
python tooling/retag_release.py
```

### 6. Creating or Updating Pull Requests

```bash
# Create a new PR with AI-generated content
python tooling/open_pull_request_current_tagged_branch.py

# If PR already exists, the tool will offer to:
# - Update it with fresh AI analysis
# - View it in browser
# - Cancel operation

# Update workflow:
# 1. Shows current PR info
# 2. Generates new content with AI
# 3. Shows preview and optional diff
# 4. Updates PR on confirmation
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   python tooling/setup_permissions.py
   ```

2. **Missing Gemini API Key**
   ```bash
   export GEMINI_API_KEY="your-key"
   # Or run setup again
   python tooling/setup_ai_tools.py
   ```

3. **Git Command Hangs**
   ```bash
   # Test git commands
   python tooling/test_git_commands.py
   
   # Check for SSH key issues
   ssh -T git@github.com
   ```

4. **Version Mismatch**
   ```bash
   # Fix version inconsistencies
   python tooling/update_version.py 0.5.201
   ```

5. **Failed Tests**
   ```bash
   # Run release without tests
   python tooling/release.py --skip-tests
   ```

### Debug Mode

Most scripts support verbose output:
```bash
python tooling/script_name.py --verbose
```

### Configuration

The tooling uses `common_config.py` for shared configuration:
- Package locations
- Version file paths
- Color output settings
- API key management
- Error handling utilities

## Best Practices

1. **Always run pre-release checks** before releasing
2. **Use AI commits** for better commit messages
3. **Keep changelogs updated** with each release
4. **Test scripts** in a clean working directory
5. **Set up AI tools** for the best experience
6. **Use the unified release manager** for consistency

## Requirements

- Python 3.7+
- Git
- Dart SDK (for dart package operations)
- Flutter SDK (for flutter package operations)
- Go (for gemini-cli installation)
- GitHub CLI (`gh`) - optional, for GitHub releases
- Gemini API key (for AI features)

## Support

For issues or questions:
1. Check the troubleshooting section
2. Run scripts with `--verbose` for detailed output
3. Review individual script docstrings for specific details
4. Check git status and ensure clean working directory