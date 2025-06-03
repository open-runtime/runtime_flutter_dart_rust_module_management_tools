#!/usr/bin/env python3
"""
validate_changelogs.py - Validate that all changelogs have entries for the current version

This script checks all project changelogs to ensure they have proper entries
for the current version, including content and standard sections.

Requires: Python 3.6+

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Tuple, List, Dict, Set, Optional
from collections import defaultdict

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import our common configuration
try:
    # Support both direct execution and package imports
import sys
import os

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try package import first (when installed via pip)
    from tooling.core.common_config import *
except ImportError:
    # Fall back to direct import (when running file directly)
    from core.common_config import *
except ImportError:
    print("Error: Could not import common_config.py", file=sys.stderr)
    print("Make sure common_config.py exists in the same directory", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# CHANGELOG VALIDATION
# ============================================================================

class ChangelogValidator:
    """Validates changelog entries for consistency and completeness"""
    
    # Standard changelog sections according to Keep a Changelog
    # Plus additional sections commonly used in this project
    STANDARD_SECTIONS = {
        'Added': 'for new features',
        'Changed': 'for changes in existing functionality', 
        'Deprecated': 'for soon-to-be removed features',
        'Removed': 'for now removed features',
        'Fixed': 'for any bug fixes',
        'Security': 'in case of vulnerabilities',
        'Breaking Changes': 'for changes that break backward compatibility',
        'Breaking': 'for changes that break backward compatibility (short form)',
        'Performance': 'for performance improvements',
        'Dependencies': 'for dependency updates'
    }
    
    # Common placeholder text that indicates incomplete entries
    PLACEHOLDER_PATTERNS = [
        r'^n/?a$',
        r'^none$',
        r'^nothing$',
        r'^tbd$',
        r'^todo$',
        r'^-\s*$',
        r'^\.\.\.$',
        r'^pending$',
        r'^wip$',
        r'^work in progress$'
    ]
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.version_counts = defaultdict(int)
    
    def validate_changelog(self, changelog_file: str, package_name: str, version: str) -> bool:
        """Validate a single changelog file
        
        Args:
            changelog_file: Path to the changelog file
            package_name: Name of the package (for display)
            version: Version to check for
            
        Returns:
            True if valid, False if there are errors
        """
        print_color(Colors.BLUE, f"📋 Checking {package_name} changelog...")
        
        changelog_path = Path(changelog_file)
        has_error = False
        
        # Check if file exists
        if not changelog_path.exists():
            print_color(Colors.RED, f"  ❌ Changelog file not found: {changelog_file}")
            self.errors.append(f"{package_name}: Changelog file not found")
            return False
        
        # Read the changelog content
        try:
            with open(changelog_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print_color(Colors.RED, f"  ❌ Error reading changelog: {e}")
            self.errors.append(f"{package_name}: Error reading file")
            return False
        
        # Check for duplicate version entries
        duplicate_versions = self._check_duplicate_versions(content, package_name)
        if duplicate_versions:
            has_error = True
            for dup_version in duplicate_versions:
                print_color(Colors.RED, f"  ❌ Duplicate version entry found: {dup_version}")
        
        # Check if version header exists
        version_pattern = f"^## \\[v{re.escape(version)}\\]"
        if not re.search(version_pattern, content, re.MULTILINE):
            print_color(Colors.RED, f"  ❌ No entry for version v{version}")
            self.errors.append(f"{package_name}: No entry for version v{version}")
            return False
        
        # Extract the content for this version
        version_content = extract_changelog_section(changelog_file, version)
        
        # Check if content is empty or only whitespace
        if not version_content or not version_content.strip():
            print_color(Colors.YELLOW, f"  ⚠️  Version v{version} exists but has no content")
            self.warnings.append(f"{package_name}: Version exists but has no content")
            has_error = True
        else:
            # Count lines with actual content
            content_lines = [line for line in version_content.split('\n') if line.strip()]
            line_count = len(content_lines)
            print_color(Colors.GREEN, f"  ✅ Version v{version} has {line_count} lines of content")
            
            # Check for standard sections and validate them
            sections_validation = self._validate_sections(version_content, package_name)
            
            if sections_validation['invalid_sections']:
                has_error = True
                print_color(Colors.RED, f"  ❌ Invalid section names found: {', '.join(sections_validation['invalid_sections'])}")
                print_color(Colors.YELLOW, f"    💡 Valid sections are: {', '.join(self.STANDARD_SECTIONS.keys())}")
            
            if sections_validation['valid_sections']:
                sections_str = ', '.join(sections_validation['valid_sections'])
                print_color(Colors.GRAY, f"  ✓ Found {len(sections_validation['valid_sections'])} valid sections: {sections_str}")
            else:
                print_color(Colors.YELLOW, "  ⚠️  No standard changelog sections found")
                self.warnings.append(f"{package_name}: No standard changelog sections")
            
            # Check for placeholder content
            placeholder_issues = self._check_placeholder_content(version_content, package_name)
            if placeholder_issues:
                has_error = True
                for issue in placeholder_issues:
                    print_color(Colors.RED, f"  ❌ {issue}")
            
            # Check for meaningful content (not just section headers)
            if self._has_only_empty_sections(version_content):
                print_color(Colors.YELLOW, "  ⚠️  Sections exist but have no meaningful content")
                self.warnings.append(f"{package_name}: Empty sections")
                has_error = True
        
        # Check date format
        date_issue = self._validate_version_date(content, version, package_name)
        if date_issue:
            print_color(Colors.YELLOW, f"  ⚠️  {date_issue}")
        
        return not has_error
    
    def _check_duplicate_versions(self, content: str, package_name: str) -> List[str]:
        """Check for duplicate version entries in the changelog
        
        Args:
            content: Full changelog content
            package_name: Name of the package
            
        Returns:
            List of duplicate version numbers
        """
        version_pattern = re.compile(r'^## \[(v[0-9]+\.[0-9]+\.[0-9]+)\]', re.MULTILINE)
        versions = version_pattern.findall(content)
        
        duplicates = []
        seen = set()
        for version in versions:
            if version in seen:
                duplicates.append(version)
                self.errors.append(f"{package_name}: Duplicate version entry {version}")
            seen.add(version)
        
        return duplicates
    
    def _validate_sections(self, content: str, package_name: str) -> Dict[str, List[str]]:
        """Validate changelog sections against standard names
        
        Args:
            content: Version content to validate
            package_name: Name of the package
            
        Returns:
            Dict with 'valid_sections' and 'invalid_sections' lists
        """
        section_pattern = re.compile(r'^### (.+)$', re.MULTILINE)
        found_sections = section_pattern.findall(content)
        
        valid_sections = []
        invalid_sections = []
        
        for section in found_sections:
            section = section.strip()
            if section in self.STANDARD_SECTIONS:
                valid_sections.append(section)
            else:
                invalid_sections.append(section)
                self.errors.append(f"{package_name}: Invalid section '{section}'")
        
        return {
            'valid_sections': valid_sections,
            'invalid_sections': invalid_sections
        }
    
    def _check_placeholder_content(self, content: str, package_name: str) -> List[str]:
        """Check for placeholder content like 'N/A' or 'TODO'
        
        Args:
            content: Version content to check
            package_name: Name of the package
            
        Returns:
            List of issues found
        """
        issues = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):  # Skip headers
                # Check against placeholder patterns
                for pattern in self.PLACEHOLDER_PATTERNS:
                    if re.match(pattern, stripped, re.IGNORECASE):
                        issues.append(f"Placeholder content '{stripped}' found")
                        self.errors.append(f"{package_name}: Placeholder content '{stripped}'")
                        break
                
                # Check for lines that are just "- N/A" or similar
                # First check if line starts with dash
                if stripped.startswith('-'):
                    # Remove dash and whitespace
                    content_after_dash = stripped[1:].strip()
                    # Check if what remains matches any placeholder
                    for pattern in self.PLACEHOLDER_PATTERNS:
                        if re.match(pattern, content_after_dash, re.IGNORECASE):
                            if f"Placeholder content '{stripped}' found" not in issues:
                                issues.append(f"Empty list item '{stripped}'")
                            break
        
        return issues
    
    def _has_only_empty_sections(self, content: str) -> bool:
        """Check if changelog has only empty sections or placeholder content
        
        Args:
            content: Changelog content to check
            
        Returns:
            True if all sections are empty or contain only placeholders
        """
        # Split by section headers
        sections = re.split(r'^### ', content, flags=re.MULTILINE)
        
        has_sections = len(sections) > 1
        has_content = False
        
        # Check each section (skip first split which is before any section)
        for section in sections[1:]:
            lines = section.strip().split('\n')
            # Remove the section header line
            content_lines = lines[1:] if len(lines) > 1 else []
            
            # Check if there's any non-empty, non-placeholder content
            for line in content_lines:
                stripped = line.strip()
                if stripped and stripped != '-':
                    # Check if it's not a placeholder
                    is_placeholder = False
                    for pattern in self.PLACEHOLDER_PATTERNS:
                        if re.match(pattern, stripped.lstrip('- '), re.IGNORECASE):
                            is_placeholder = True
                            break
                    
                    if not is_placeholder:
                        has_content = True
                        break
            
            if has_content:
                break
        
        return has_sections and not has_content
    
    def _validate_version_date(self, content: str, version: str, package_name: str) -> str:
        """Validate the date format for a version entry
        
        Args:
            content: Full changelog content
            version: Version to check
            package_name: Package name
            
        Returns:
            Warning message if date issue found, empty string otherwise
        """
        # Look for the version with its date
        pattern = f"^## \\[v{re.escape(version)}\\] - (.+)$"
        match = re.search(pattern, content, re.MULTILINE)
        
        if match:
            date_str = match.group(1).strip()
            # Basic date format check (YYYY-MM-DD)
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                self.warnings.append(f"{package_name}: Non-standard date format '{date_str}'")
                return f"Non-standard date format: '{date_str}' (expected YYYY-MM-DD)"
        
        return ""

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Validate that all changelogs have entries for the specified version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Validate using version from pubspec.yaml
  %(prog)s --version 1.2.3   # Validate specific version
"""
    )
    parser.add_argument(
        '--version',
        help='Version to validate (e.g., 1.2.3). If not provided, extracts from dart/pubspec.yaml',
        type=str
    )
    return parser.parse_args()

def main():
    """Main validation function"""
    # Parse arguments
    args = parse_args()
    
    # Ensure we're in the project root
    ensure_project_root()
    
    print_header("📋 Validating Changelogs")
    
    # Get version from args or pubspec
    if args.version:
        current_version = args.version
        print_color(Colors.BLUE, f"📌 Using provided version: v{current_version}")
    else:
        current_version = get_current_version()
        if not current_version:
            print_color(Colors.RED, "Error: Could not determine current version")
            sys.exit(1)
        print_color(Colors.BLUE, f"📌 Current version from pubspec: v{current_version}")
    
    print_color(Colors.GRAY, "🔍 Validating against Keep a Changelog standards...")
    print()
    
    # Create validator
    validator = ChangelogValidator()
    all_valid = True
    
    # Validate each changelog - including root CHANGELOG.md
    changelogs = [
        (ROOT_CHANGELOG, "Root"),
        (DART_CHANGELOG, "Dart"),
        (FLUTTER_CHANGELOG, "Flutter"),
        (RUST_CHANGELOG, "Rust")
    ]
    
    for changelog_file, package_name in changelogs:
        if not validator.validate_changelog(changelog_file, package_name, current_version):
            all_valid = False
        print()  # Empty line between packages
    
    # Summary
    print_header("Summary")
    
    if all_valid and not validator.warnings:
        print_color(Colors.GREEN, f"✅ All changelogs are valid for version v{current_version}")
        print_color(Colors.GREEN, "✅ Following Keep a Changelog best practices")
        return 0
    elif all_valid and validator.warnings:
        print_color(Colors.YELLOW, f"⚠️  All changelogs have entries but there are warnings:")
        for warning in validator.warnings:
            print_color(Colors.YELLOW, f"  • {warning}")
        print()
        print_color(Colors.BLUE, "📝 Changelogs are technically valid but could be improved.")
        return 0
    else:
        print_color(Colors.RED, "❌ Changelog validation failed")
        
        if validator.errors:
            print_color(Colors.RED, "\n🚨 Errors (must fix):")
            for error in validator.errors:
                print_color(Colors.RED, f"  • {error}")
        
        if validator.warnings:
            print_color(Colors.YELLOW, "\n⚠️  Warnings (should fix):")
            for warning in validator.warnings:
                print_color(Colors.YELLOW, f"  • {warning}")
        
        print()
        print_color(Colors.BLUE, "📚 Changelog Best Practices:")
        print_color(Colors.GRAY, "  • Use standard section names:")
        for section, description in validator.STANDARD_SECTIONS.items():
            print_color(Colors.GRAY, f"    - {section}: {description}")
        print_color(Colors.GRAY, "  • Avoid placeholder text (N/A, TODO, etc.)")
        print_color(Colors.GRAY, "  • Include meaningful descriptions of changes")
        print_color(Colors.GRAY, "  • Use YYYY-MM-DD date format")
        print_color(Colors.GRAY, "  • Don't duplicate version entries")
        
        print()
        print_color(Colors.BLUE, "📋 Example of a good changelog entry:")
        print_color(Colors.GRAY, "  ## [v1.2.3] - 2024-01-15")
        print_color(Colors.GRAY, "  ")
        print_color(Colors.GRAY, "  ### Added")
        print_color(Colors.GRAY, "  - New vector search algorithm for improved performance")
        print_color(Colors.GRAY, "  - Support for custom distance metrics")
        print_color(Colors.GRAY, "  ")
        print_color(Colors.GRAY, "  ### Changed")
        print_color(Colors.GRAY, "  - Updated default parameters for better accuracy")
        print_color(Colors.GRAY, "  - Improved error messages for invalid inputs")
        print_color(Colors.GRAY, "  ")
        print_color(Colors.GRAY, "  ### Fixed")
        print_color(Colors.GRAY, "  - Memory leak when processing large datasets")
        print_color(Colors.GRAY, "  - Incorrect results with negative vector values")
        print_color(Colors.GRAY, "  ")
        print_color(Colors.GRAY, "  ### Performance")
        print_color(Colors.GRAY, "  - Optimized indexing speed by 30%")
        print_color(Colors.GRAY, "  ")
        print_color(Colors.GRAY, "  ### Breaking Changes")
        print_color(Colors.GRAY, "  - Changed API method signature for search()")
        
        print()
        print_color(Colors.YELLOW, "🔧 To fix changelog issues:")
        print_color(Colors.YELLOW, "  1. Manually edit the changelog files to fix errors")
        print_color(Colors.YELLOW, "  2. Or use ./tooling/sync_changelogs.py to generate entries from git")
        print_color(Colors.YELLOW, "  3. Then run this validator again")
        
        return 1

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {e}")
        sys.exit(1)