"""
Tests for changelog utility functions.
"""

import unittest
import tempfile
from pathlib import Path
from datetime import date

from tooling.utils.changelog_utils import (
    ChangelogSection, ChangelogEntry, ChangelogVersion, Changelog,
    ChangelogParser, ChangelogGenerator, ChangelogValidator,
    ChangelogError, InvalidChangelogError,
    parse_changelog, extract_version_content, validate_changelog_file
)


class TestChangelogSection(unittest.TestCase):
    """Test ChangelogSection enum."""
    
    def test_from_string(self):
        """Test converting string to enum."""
        self.assertEqual(ChangelogSection.from_string("Added"), ChangelogSection.ADDED)
        self.assertEqual(ChangelogSection.from_string("added"), ChangelogSection.ADDED)
        self.assertEqual(ChangelogSection.from_string("ADDED"), ChangelogSection.ADDED)
        
        # Breaking changes variations
        self.assertEqual(ChangelogSection.from_string("Breaking"), ChangelogSection.BREAKING)
        self.assertEqual(ChangelogSection.from_string("Breaking Changes"), ChangelogSection.BREAKING)
        self.assertEqual(ChangelogSection.from_string("breaking_changes"), ChangelogSection.BREAKING)
        
        # Unknown section
        self.assertIsNone(ChangelogSection.from_string("Unknown"))
    
    def test_all_sections(self):
        """Test getting all section names."""
        sections = ChangelogSection.all_sections()
        self.assertIn("Added", sections)
        self.assertIn("Fixed", sections)
        self.assertIn("Breaking Changes", sections)


class TestChangelogEntry(unittest.TestCase):
    """Test ChangelogEntry class."""
    
    def test_format_basic(self):
        """Test formatting basic entry."""
        entry = ChangelogEntry(
            text="Added new feature",
            section=ChangelogSection.ADDED
        )
        self.assertEqual(entry.format(), "- Added new feature")
    
    def test_format_with_metadata(self):
        """Test formatting entry with metadata."""
        entry = ChangelogEntry(
            text="Fixed bug",
            section=ChangelogSection.FIXED,
            pr_number=123,
            author="johndoe"
        )
        self.assertEqual(entry.format(include_metadata=True), "- Fixed bug (#123, @johndoe)")
        self.assertEqual(entry.format(include_metadata=False), "- Fixed bug")


class TestChangelogVersion(unittest.TestCase):
    """Test ChangelogVersion class."""
    
    def test_add_entry(self):
        """Test adding entries to version."""
        version = ChangelogVersion(version="1.2.3", date=date(2024, 1, 15))
        
        entry1 = ChangelogEntry("Feature 1", ChangelogSection.ADDED)
        entry2 = ChangelogEntry("Bug fix 1", ChangelogSection.FIXED)
        
        version.add_entry(entry1)
        version.add_entry(entry2)
        
        self.assertEqual(len(version.sections[ChangelogSection.ADDED]), 1)
        self.assertEqual(len(version.sections[ChangelogSection.FIXED]), 1)
    
    def test_is_empty(self):
        """Test checking if version is empty."""
        version = ChangelogVersion(version="1.2.3")
        self.assertTrue(version.is_empty())
        
        version.add_entry(ChangelogEntry("Feature", ChangelogSection.ADDED))
        self.assertFalse(version.is_empty())
    
    def test_format(self):
        """Test formatting version section."""
        version = ChangelogVersion(version="1.2.3", date=date(2024, 1, 15))
        version.add_entry(ChangelogEntry("New feature", ChangelogSection.ADDED))
        version.add_entry(ChangelogEntry("Bug fix", ChangelogSection.FIXED))
        
        formatted = version.format()
        
        self.assertIn("## [1.2.3] - 2024-01-15", formatted)
        self.assertIn("### Added", formatted)
        self.assertIn("- New feature", formatted)
        self.assertIn("### Fixed", formatted)
        self.assertIn("- Bug fix", formatted)


class TestChangelog(unittest.TestCase):
    """Test Changelog class."""
    
    def test_get_version(self):
        """Test getting specific version."""
        changelog = Changelog()
        
        v1 = ChangelogVersion(version="1.2.3")
        v2 = ChangelogVersion(version="v1.2.4")  # With 'v' prefix
        
        changelog.add_version(v1)
        changelog.add_version(v2)
        
        # Should find with or without 'v' prefix
        self.assertEqual(changelog.get_version("1.2.3"), v1)
        self.assertEqual(changelog.get_version("v1.2.3"), v1)
        self.assertEqual(changelog.get_version("1.2.4"), v2)
        self.assertEqual(changelog.get_version("v1.2.4"), v2)
        
        # Non-existent version
        self.assertIsNone(changelog.get_version("2.0.0"))
    
    def test_version_sorting(self):
        """Test that versions are sorted correctly."""
        changelog = Changelog()
        
        # Add versions out of order
        changelog.add_version(ChangelogVersion(version="1.0.0"))
        changelog.add_version(ChangelogVersion(version="1.2.0"))
        changelog.add_version(ChangelogVersion(version="1.1.0"))
        changelog.add_version(ChangelogVersion(version="Unreleased"))
        
        # Check order (Unreleased first, then descending)
        versions = [v.version for v in changelog.versions]
        self.assertEqual(versions[0], "Unreleased")
        self.assertEqual(versions[1], "1.2.0")
        self.assertEqual(versions[2], "1.1.0")
        self.assertEqual(versions[3], "1.0.0")


class TestChangelogParser(unittest.TestCase):
    """Test ChangelogParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = ChangelogParser()
    
    def test_parse_basic_changelog(self):
        """Test parsing basic changelog."""
        content = """# Changelog

## [1.2.0] - 2024-01-15

### Added
- New feature X
- Support for Y

### Fixed
- Bug in component Z

## [1.1.0] - 2024-01-01

### Added
- Initial implementation
"""
        
        changelog = self.parser.parse_content(content)
        
        self.assertEqual(len(changelog.versions), 2)
        self.assertEqual(changelog.versions[0].version, "1.2.0")
        self.assertEqual(changelog.versions[0].date, date(2024, 1, 15))
        self.assertEqual(len(changelog.versions[0].sections[ChangelogSection.ADDED]), 2)
        self.assertEqual(len(changelog.versions[0].sections[ChangelogSection.FIXED]), 1)
    
    def test_parse_entry_with_metadata(self):
        """Test parsing entries with PR numbers and authors."""
        content = """# Changelog

## [1.0.0] - 2024-01-01

### Added
- Feature with PR (#123)
- Feature by author (@johndoe)
- Complex feature (#456, @janedoe)
"""
        
        changelog = self.parser.parse_content(content)
        entries = changelog.versions[0].sections[ChangelogSection.ADDED]
        
        self.assertEqual(entries[0].pr_number, 123)
        self.assertIsNone(entries[0].author)
        
        self.assertIsNone(entries[1].pr_number)
        self.assertEqual(entries[1].author, "johndoe")
        
        self.assertEqual(entries[2].pr_number, 456)
        self.assertEqual(entries[2].author, "janedoe")
    
    def test_parse_no_versions(self):
        """Test parsing changelog with no versions."""
        content = """# Changelog

This is a changelog that hasn't been started yet.
"""
        
        changelog = self.parser.parse_content(content)
        
        self.assertEqual(len(changelog.versions), 0)
        self.assertIn("This is a changelog", changelog.header)
    
    def test_parse_file(self):
        """Test parsing from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Changelog\n\n## [1.0.0] - 2024-01-01\n\n### Added\n- Feature")
            temp_path = f.name
        
        try:
            changelog = self.parser.parse_file(temp_path)
            self.assertEqual(len(changelog.versions), 1)
        finally:
            Path(temp_path).unlink()


class TestChangelogGenerator(unittest.TestCase):
    """Test ChangelogGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = ChangelogGenerator()
    
    def test_generate_from_conventional_commit(self):
        """Test generating entry from conventional commit."""
        # Feature commit
        commit = {
            'subject': 'feat: add new API endpoint',
            'body': '',
            'hash': 'abc123',
            'author_name': 'John Doe'
        }
        entry = self.generator.generate_entry_from_commit(commit)
        
        self.assertEqual(entry.section, ChangelogSection.ADDED)
        self.assertEqual(entry.text, "add new API endpoint")
        
        # Fix with scope
        commit = {
            'subject': 'fix(api): resolve memory leak',
            'body': '',
            'hash': 'def456',
            'author_name': 'Jane Doe'
        }
        entry = self.generator.generate_entry_from_commit(commit)
        
        self.assertEqual(entry.section, ChangelogSection.FIXED)
        self.assertEqual(entry.text, "**api**: resolve memory leak")
    
    def test_generate_breaking_change(self):
        """Test generating breaking change entry."""
        # Breaking change with !
        commit = {
            'subject': 'feat!: change API format',
            'body': '',
            'hash': 'abc123',
            'author_name': 'John Doe'
        }
        entry = self.generator.generate_entry_from_commit(commit)
        
        self.assertEqual(entry.section, ChangelogSection.BREAKING)
        
        # Breaking change in body
        commit = {
            'subject': 'feat: update config',
            'body': 'BREAKING CHANGE: config format changed',
            'hash': 'def456',
            'author_name': 'Jane Doe'
        }
        entry = self.generator.generate_entry_from_commit(commit)
        
        self.assertEqual(entry.section, ChangelogSection.BREAKING)
    
    def test_generate_from_non_conventional_commit(self):
        """Test generating entry from non-conventional commit."""
        # Add keyword
        commit = {'subject': 'Add new feature for users', 'body': ''}
        entry = self.generator.generate_entry_from_commit(commit)
        self.assertEqual(entry.section, ChangelogSection.ADDED)
        
        # Fix keyword
        commit = {'subject': 'Fix bug in login process', 'body': ''}
        entry = self.generator.generate_entry_from_commit(commit)
        self.assertEqual(entry.section, ChangelogSection.FIXED)
        
        # Default to changed
        commit = {'subject': 'Update documentation', 'body': ''}
        entry = self.generator.generate_entry_from_commit(commit)
        self.assertEqual(entry.section, ChangelogSection.CHANGED)
    
    def test_group_entries_by_section(self):
        """Test grouping entries by section."""
        entries = [
            ChangelogEntry("Feature 1", ChangelogSection.ADDED),
            ChangelogEntry("Feature 2", ChangelogSection.ADDED),
            ChangelogEntry("Bug fix", ChangelogSection.FIXED),
            ChangelogEntry("Security update", ChangelogSection.SECURITY),
        ]
        
        grouped = self.generator.group_entries_by_section(entries)
        
        self.assertEqual(len(grouped[ChangelogSection.ADDED]), 2)
        self.assertEqual(len(grouped[ChangelogSection.FIXED]), 1)
        self.assertEqual(len(grouped[ChangelogSection.SECURITY]), 1)


class TestChangelogValidator(unittest.TestCase):
    """Test ChangelogValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = ChangelogValidator()
    
    def test_validate_empty_version(self):
        """Test validating empty version."""
        version = ChangelogVersion(version="1.0.0")
        errors = self.validator.validate_version(version)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("no entries", errors[0])
    
    def test_validate_placeholder_entries(self):
        """Test detecting placeholder entries."""
        version = ChangelogVersion(version="1.0.0")
        
        # Add placeholder entries
        placeholders = ["TODO", "tbd", "...", "n/a", "pending"]
        for text in placeholders:
            version.add_entry(ChangelogEntry(text, ChangelogSection.ADDED))
        
        errors = self.validator.validate_version(version)
        
        # Should detect all placeholders
        self.assertEqual(len(errors), len(placeholders))
        for error in errors:
            self.assertIn("Placeholder entry", error)
    
    def test_validate_duplicate_versions(self):
        """Test detecting duplicate versions."""
        changelog = Changelog()
        changelog.add_version(ChangelogVersion(version="1.0.0"))
        changelog.add_version(ChangelogVersion(version="1.0.0"))  # Duplicate
        
        errors = self.validator.validate_changelog(changelog)
        
        self.assertTrue(any("Duplicate versions" in e for e in errors))
    
    def test_validate_file(self):
        """Test validating changelog file."""
        content = """# Changelog

## [1.0.0] - 2024-01-01

### Added
- TODO
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            errors = self.validator.validate_file(temp_path)
            self.assertTrue(any("Placeholder entry" in e for e in errors))
        finally:
            Path(temp_path).unlink()


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_extract_version_content(self):
        """Test extracting version content."""
        content = """# Changelog

## [1.2.0] - 2024-01-15

### Added
- Feature X

### Fixed
- Bug Y

## [1.1.0] - 2024-01-01

### Added
- Feature Z
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # Extract with 'v' prefix
            version_content = extract_version_content(temp_path, "v1.2.0")
            self.assertIn("Feature X", version_content)
            self.assertIn("Bug Y", version_content)
            
            # Extract without prefix
            version_content = extract_version_content(temp_path, "1.1.0")
            self.assertIn("Feature Z", version_content)
            
            # Non-existent version
            version_content = extract_version_content(temp_path, "2.0.0")
            self.assertIsNone(version_content)
        finally:
            Path(temp_path).unlink()


if __name__ == '__main__':
    unittest.main()