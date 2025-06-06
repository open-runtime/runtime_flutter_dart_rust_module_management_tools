#!/usr/bin/env python3
"""
Demonstration of the shared utility modules.

This example shows how to use the git, version, and changelog utilities
in your own tools.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.core.logging import get_logger
from tooling.utils import (
    # Git utilities
    GitOperations, GitError, NotGitRepositoryError,
    
    # Version utilities
    SemanticVersion, VersionComponent, parse_version, increment_version,
    VersionExtractor, VersionUpdater,
    
    # Changelog utilities
    ChangelogParser, ChangelogGenerator, ChangelogValidator,
    parse_changelog, validate_changelog_file
)


def demo_git_operations():
    """Demonstrate git utility functions."""
    print("\n=== Git Operations Demo ===\n")
    
    logger = get_logger("git_demo")
    git = GitOperations(logger)
    
    try:
        # Check if we're in a git repository
        if not git.is_git_repository():
            print("Not in a git repository!")
            return
            
        print("✓ In a git repository")
        
        # Get current branch
        branch = git.get_current_branch()
        print(f"Current branch: {branch}")
        
        # Get latest tag
        latest_tag = git.get_latest_tag()
        if latest_tag:
            print(f"Latest tag: {latest_tag}")
        else:
            print("No tags found")
            
        # Check working directory status
        is_clean = git.is_working_directory_clean()
        print(f"Working directory clean: {is_clean}")
        
        if not is_clean:
            changes = git.get_uncommitted_changes()
            if changes['staged']:
                print(f"  Staged files: {len(changes['staged'])}")
            if changes['unstaged']:
                print(f"  Unstaged files: {len(changes['unstaged'])}")
            if changes['untracked']:
                print(f"  Untracked files: {len(changes['untracked'])}")
                
        # Get recent commits
        commits = git.get_commit_messages(from_ref=latest_tag, to_ref="HEAD")
        if commits:
            print(f"\nCommits since {latest_tag}:")
            for commit in commits[:5]:  # Show first 5
                print(f"  - {commit['subject']} ({commit['author_name']})")
                
        # Get GitHub URL
        github_url = git.get_github_url()
        if github_url:
            print(f"\nGitHub URL: {github_url}")
            
    except GitError as e:
        print(f"Git error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def demo_version_operations():
    """Demonstrate version utility functions."""
    print("\n=== Version Operations Demo ===\n")
    
    # Parse version strings
    versions = ["v1.2.3", "2.0.0-beta.1", "3.0.0+build.123"]
    
    print("Parsing versions:")
    for v_str in versions:
        try:
            version = parse_version(v_str)
            print(f"  {v_str} -> major={version.major}, minor={version.minor}, patch={version.patch}")
            if version.prerelease:
                print(f"    prerelease: {version.prerelease}")
            if version.build:
                print(f"    build: {version.build}")
        except Exception as e:
            print(f"  Failed to parse {v_str}: {e}")
    
    # Increment versions
    print("\nIncrementing versions:")
    base_version = "v1.2.3"
    print(f"  Base: {base_version}")
    print(f"  Patch: {increment_version(base_version, VersionComponent.PATCH)}")
    print(f"  Minor: {increment_version(base_version, VersionComponent.MINOR)}")
    print(f"  Major: {increment_version(base_version, VersionComponent.MAJOR)}")
    
    # Version comparison
    print("\nComparing versions:")
    v1, v2 = "v1.2.3", "v1.2.4"
    print(f"  {v1} < {v2}: {parse_version(v1) < parse_version(v2)}")
    
    # Extract version from files
    print("\nExtracting versions from files:")
    extractor = VersionExtractor()
    
    # Try to find pyproject.toml
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        version = extractor.extract_from_file(pyproject_path)
        if version:
            print(f"  pyproject.toml: {version}")
            
    # Try to find package.json
    package_json_path = Path("package.json")
    if package_json_path.exists():
        version = extractor.extract_from_file(package_json_path)
        if version:
            print(f"  package.json: {version}")


def demo_changelog_operations():
    """Demonstrate changelog utility functions."""
    print("\n=== Changelog Operations Demo ===\n")
    
    # Sample changelog content
    sample_changelog = """# Changelog
All notable changes to this project will be documented in this file.

## [1.2.0] - 2024-01-15

### Added
- New feature X with improved performance
- Support for configuration file (#123)

### Fixed
- Bug in component Y (@author)
- Memory leak in process Z

## [1.1.0] - 2024-01-01

### Added
- Initial implementation of feature A

### Changed
- Refactored module B for better maintainability
"""
    
    # Parse changelog
    print("Parsing sample changelog:")
    parser = ChangelogParser()
    changelog = parser.parse_content(sample_changelog)
    
    print(f"  Found {len(changelog.versions)} versions")
    for version in changelog.versions:
        print(f"  - {version.version} ({version.date})")
        for section, entries in version.sections.items():
            print(f"    {section.value}: {len(entries)} entries")
    
    # Generate changelog entries from commits
    print("\nGenerating changelog entries from commits:")
    generator = ChangelogGenerator()
    
    sample_commits = [
        {"subject": "feat: add new API endpoint", "author_name": "John Doe"},
        {"subject": "fix: resolve memory leak in cache", "author_name": "Jane Smith"},
        {"subject": "docs: update README with examples", "author_name": "Bob Wilson"},
        {"subject": "feat!: breaking change in config format", "author_name": "Alice Brown"},
    ]
    
    for commit in sample_commits:
        entry = generator.generate_entry_from_commit(commit)
        if entry:
            print(f"  [{entry.section.value}] {entry.text}")
    
    # Validate changelog
    print("\nValidating changelog:")
    validator = ChangelogValidator()
    errors = validator.validate_changelog(changelog)
    
    if errors:
        print("  Validation errors:")
        for error in errors:
            print(f"    - {error}")
    else:
        print("  ✓ Changelog is valid")
    
    # Look for actual CHANGELOG.md
    changelog_path = Path("CHANGELOG.md")
    if changelog_path.exists():
        print(f"\nValidating {changelog_path}:")
        errors = validate_changelog_file(changelog_path)
        if errors:
            print("  Validation errors:")
            for error in errors[:5]:  # Show first 5
                print(f"    - {error}")
        else:
            print("  ✓ CHANGELOG.md is valid")


def main():
    """Run all demonstrations."""
    print("=== Shared Utilities Demonstration ===")
    print("This demo shows how to use the git, version, and changelog utilities.")
    
    # Run demos
    demo_git_operations()
    demo_version_operations()
    demo_changelog_operations()
    
    print("\n=== Demo Complete ===")
    print("These utilities are available for use in all CLI tools.")
    print("Import them from tooling.utils as shown in this example.")


if __name__ == "__main__":
    main()