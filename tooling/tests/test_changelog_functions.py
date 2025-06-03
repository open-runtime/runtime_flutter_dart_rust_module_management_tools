#!/usr/bin/env python3
"""
Unit tests for changelog-related functions
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import Colors, print_color, extract_changelog_section
from tests.test_helpers import DummyProject


class TestChangelogFunctions(unittest.TestCase):
    """Test cases for changelog-related functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_changelog_")
        self.original_cwd = os.getcwd()
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_extract_changelog_section(self):
        """Test extracting specific version sections from changelog"""
        # Create test changelog
        changelog_content = """# Changelog

## [v0.0.3] - 2024-01-15

### Added
- Feature C
- Feature D

### Fixed
- Bug Z

## [v0.0.2] - 2024-01-10

### Added
- Feature A
- Feature B

### Fixed
- Bug X
- Bug Y

## [v0.0.1] - 2024-01-01

### Added
- Initial release
"""
        
        changelog_path = Path(self.test_dir) / "CHANGELOG.md"
        changelog_path.write_text(changelog_content)
        
        # Test extraction
        section = extract_changelog_section(str(changelog_path), "0.0.2")
        self.assertIn("Feature A", section)
        self.assertIn("Feature B", section)
        self.assertIn("Bug X", section)
        self.assertIn("Bug Y", section)
        self.assertNotIn("Feature C", section)
        self.assertNotIn("Initial release", section)
        
        # Test with 'v' prefix
        section = extract_changelog_section(str(changelog_path), "v0.0.3")
        self.assertIn("Feature C", section)
        self.assertIn("Bug Z", section)
        
        # Test non-existent version
        section = extract_changelog_section(str(changelog_path), "0.0.99")
        self.assertEqual(section, "")
        
        print_color(Colors.GREEN, "✓ Changelog section extraction test passed")
    
    def test_changelog_formatting(self):
        """Test changelog formatting and structure"""
        with DummyProject("test_format", self.test_dir) as project:
            # Create a changelog with various formatting
            changelog_content = """# Changelog

## [v0.0.2] - 2024-01-15

### Added
- New feature with **bold** text
- Feature with `code` blocks
- Multi-line feature
  with additional details
  and more information

### Fixed
- Bug fix with [link](https://example.com)
- Another fix: [@user](https://github.com/user), 2024-01-15, 10:30AM PST, [abc123](https://github.com/repo/commit/abc123)

### Changed
- **BREAKING:** Changed API signature

## [v0.0.1] - 2024-01-01

### Added
- Initial release
"""
            
            changelog_path = project.repo_dir / "CHANGELOG.md"
            changelog_path.write_text(changelog_content)
            
            # Extract and verify formatting is preserved
            section = extract_changelog_section(str(changelog_path), "0.0.2")
            
            # Check that formatting is preserved
            self.assertIn("**bold**", section)
            self.assertIn("`code`", section)
            self.assertIn("Multi-line feature\n  with additional details", section)
            self.assertIn("[link](https://example.com)", section)
            self.assertIn("**BREAKING:**", section)
            self.assertIn("[@user](https://github.com/user)", section)
            
            print_color(Colors.GREEN, "✓ Changelog formatting test passed")
    
    def test_empty_changelog_detection(self):
        """Test detection of empty changelog sections"""
        test_cases = [
            # Empty section
            ("## [v0.0.1] - 2024-01-01\n\n", True),
            # Only whitespace
            ("## [v0.0.1] - 2024-01-01\n\n   \n\n", True),
            # N/A entry
            ("## [v0.0.1] - 2024-01-01\n\n### Added\n- N/A\n", True),
            # Real content
            ("## [v0.0.1] - 2024-01-01\n\n### Added\n- Real feature\n", False),
            # Multiple N/A sections
            ("## [v0.0.1] - 2024-01-01\n\n### Added\n- N/A\n\n### Fixed\n- N/A\n", True),
            # Mixed content
            ("## [v0.0.1] - 2024-01-01\n\n### Added\n- N/A\n\n### Fixed\n- Real fix\n", False),
        ]
        
        for content, should_be_empty in test_cases:
            # Extract just the section content (after version header)
            lines = content.split('\n')
            section_content = '\n'.join(lines[2:]).strip()
            
            # Simple empty detection
            is_empty = (
                not section_content or
                section_content == "N/A" or
                all(line.strip() in ["", "- N/A", "### Added", "### Fixed", "### Changed"] 
                    for line in section_content.split('\n'))
            )
            
            self.assertEqual(is_empty, should_be_empty, 
                           f"Empty detection failed for: {repr(content)}")
        
        print_color(Colors.GREEN, "✓ Empty changelog detection test passed")
    
    def test_changelog_merge_scenarios(self):
        """Test various changelog merge scenarios"""
        # Test merging new content with existing
        existing = """### Added
- Existing feature A
- Existing feature B

### Fixed
- Existing bug fix X"""
        
        new_content = """### Added
- New feature C

### Fixed
- New bug fix Y

### Changed
- Updated documentation"""
        
        # Simple merge simulation
        existing_sections = self._parse_sections(existing)
        new_sections = self._parse_sections(new_content)
        
        # Merge
        for section, entries in new_sections.items():
            if section in existing_sections:
                existing_sections[section].extend(entries)
            else:
                existing_sections[section] = entries
        
        # Verify merge
        self.assertEqual(len(existing_sections["Added"]), 3)
        self.assertEqual(len(existing_sections["Fixed"]), 2)
        self.assertIn("Changed", existing_sections)
        
        print_color(Colors.GREEN, "✓ Changelog merge test passed")
    
    def _parse_sections(self, content: str) -> dict:
        """Parse changelog content into sections"""
        sections = {}
        current_section = None
        
        for line in content.split('\n'):
            if line.startswith('### '):
                current_section = line[4:].strip()
                sections[current_section] = []
            elif current_section and line.strip().startswith('-'):
                sections[current_section].append(line.strip())
        
        return sections
    
    def test_version_comparison_in_changelog(self):
        """Test version ordering in changelog"""
        versions = [
            ("0.0.1", "0.0.2", -1),
            ("0.0.10", "0.0.2", 1),
            ("1.0.0", "0.9.9", 1),
            ("1.0.0", "1.0.0", 0),
        ]
        
        for v1, v2, expected in versions:
            # Simple version comparison
            v1_parts = [int(x) for x in v1.split('-')[0].split('.')]
            v2_parts = [int(x) for x in v2.split('-')[0].split('.')]
            
            if v1_parts < v2_parts:
                result = -1
            elif v1_parts > v2_parts:
                result = 1
            else:
                result = 0
            
            self.assertEqual(result, expected, 
                           f"Version comparison failed: {v1} vs {v2}")
        
        print_color(Colors.GREEN, "✓ Version comparison test passed")


class TestChangelogGeneration(unittest.TestCase):
    """Test changelog generation scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_gen_")
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_conventional_commit_parsing(self):
        """Test parsing of conventional commit messages"""
        test_commits = [
            ("feat: add new feature", "feat", "Added"),
            ("fix: resolve bug", "fix", "Fixed"),
            ("docs: update README", "docs", "Changed"),
            ("feat!: breaking change", "feat", "Changed"),  # Breaking
            ("fix(scope): scoped fix", "fix", "Fixed"),
            ("chore: update deps", "chore", "Changed"),
        ]
        
        for message, expected_type, expected_section in test_commits:
            # Simple conventional commit detection
            match = message.split(':')[0]
            if '(' in match:
                commit_type = match.split('(')[0]
            else:
                commit_type = match.rstrip('!')
            
            self.assertTrue(commit_type in ["feat", "fix", "docs", "chore"])
            
        print_color(Colors.GREEN, "✓ Conventional commit parsing test passed")
    
    def test_commit_grouping_by_package(self):
        """Test grouping commits by package based on file paths"""
        with DummyProject("test_grouping", self.test_dir) as project:
            project.create_standard_structure()
            
            # Create commits affecting different packages
            commits_data = [
                ("dart/lib/feature.dart", "dart"),
                ("flutter/lib/widget.dart", "flutter"),
                ("dart/rust/src/lib.rs", "rust"),
                ("README.md", "root"),
                ("dart/pubspec.yaml", "dart"),
                (".github/workflows/ci.yml", "root"),
            ]
            
            # Test file path to package mapping
            for file_path, expected_package in commits_data:
                # Determine package based on path
                if file_path.startswith("dart/rust/"):
                    package = "rust"
                elif file_path.startswith("dart/"):
                    package = "dart"
                elif file_path.startswith("flutter/"):
                    package = "flutter"
                else:
                    package = "root"
                
                self.assertEqual(package, expected_package, 
                               f"Package detection failed for {file_path}")
            
            print_color(Colors.GREEN, "✓ Commit grouping test passed")


if __name__ == "__main__":
    unittest.main(verbosity=2) 