"""
Tests for the modularized changelog components.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from tooling.utils.changelog import (
    ChangelogParser, ChangelogGenerator, CommitAnalyzer, FileAnalyzer,
    GitCommit, ConventionalCommit, VersionEntry
)


class TestChangelogParser:
    """Test the ChangelogParser class"""
    
    def test_parse_empty_changelog(self, tmp_path):
        """Test parsing an empty changelog"""
        changelog_path = tmp_path / "CHANGELOG.md"
        parser = ChangelogParser(changelog_path)
        
        assert parser.content.startswith("# Changelog")
        assert len(parser.versions) == 0
    
    def test_parse_existing_changelog(self, tmp_path):
        """Test parsing an existing changelog"""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = """# Changelog

## [1.0.0] - 2024-01-01

### Added
- New feature

## [0.9.0] - 2023-12-01

### Fixed
- Bug fix
"""
        changelog_path.write_text(content)
        
        parser = ChangelogParser(changelog_path)
        assert len(parser.versions) == 2
        assert "1.0.0" in parser.versions
        assert "0.9.0" in parser.versions
        assert parser.versions["1.0.0"].date == "2024-01-01"
        assert "New feature" in parser.versions["1.0.0"].content
    
    def test_detect_empty_versions(self, tmp_path):
        """Test detecting empty version entries"""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = """# Changelog

## [1.0.0] - 2024-01-01

N/A

## [0.9.0] - 2023-12-01

### Added
- Real content
"""
        changelog_path.write_text(content)
        
        parser = ChangelogParser(changelog_path)
        empty_versions = parser.get_empty_versions()
        assert "1.0.0" in empty_versions
        assert "0.9.0" not in empty_versions
    
    def test_merge_sections(self, tmp_path):
        """Test merging changelog sections"""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = """# Changelog

## [1.0.0] - 2024-01-01

### Added
- Feature A
"""
        changelog_path.write_text(content)
        
        parser = ChangelogParser(changelog_path)
        
        new_content = """### Added
- Feature B

### Fixed
- Bug fix
"""
        
        parser.merge_version("1.0.0", "2024-01-01", new_content)
        
        # Check merged content
        assert "Feature A" in parser.versions["1.0.0"].content
        assert "Feature B" in parser.versions["1.0.0"].content
        assert "Bug fix" in parser.versions["1.0.0"].content


class TestCommitAnalyzer:
    """Test the CommitAnalyzer class"""
    
    def test_analyze_empty_commits(self):
        """Test analyzing empty commit list"""
        analyzer = CommitAnalyzer("test-package")
        result = analyzer.analyze_commits([])
        assert result == "No commits to analyze."
    
    def test_analyze_conventional_commits(self):
        """Test analyzing conventional commits"""
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="feat: add new feature",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=["test.py"]
            ),
            GitCommit(
                hash="def456",
                short_hash="def456",
                message="fix: resolve bug",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="1:00PM EST",
                files=["bug.py"]
            )
        ]
        
        analyzer = CommitAnalyzer("test-package")
        result = analyzer.analyze_commits(commits)
        
        assert "Analyzed 2 commits" in result
        assert "Features:" in result
        assert "Bug Fixes:" in result


class TestFileAnalyzer:
    """Test the FileAnalyzer class"""
    
    def test_analyze_no_files(self):
        """Test analyzing when no files changed"""
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="test commit",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=[]
            )
        ]
        
        analyzer = FileAnalyzer("root", commits)
        files, context = analyzer.analyze_files("1.0.0")
        
        assert len(files) == 0
        assert "No files changed" in context
    
    @patch('tooling.utils.changelog.analyzer.subprocess.run')
    def test_filter_by_package(self, mock_run):
        """Test filtering files by package"""
        # Mock git check-ignore to return non-zero (not gitignored)
        mock_run.return_value.returncode = 1
        
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="test commit",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=["README.md", "dart/lib/main.dart", "flutter/lib/app.dart"]
            )
        ]
        
        # Test root package
        analyzer = FileAnalyzer("root", commits)
        files, context = analyzer.analyze_files("1.0.0")
        assert "README.md" in files
        assert "dart/lib/main.dart" not in files
        
        # Test dart package
        analyzer = FileAnalyzer("dart", commits)
        files, context = analyzer.analyze_files("1.0.0")
        assert "dart/lib/main.dart" in files
        assert "README.md" not in files
    
    def test_prioritize_files(self):
        """Test file prioritization"""
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="test commit",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=[
                    "test_something.py",
                    "README.md",
                    "src/main.py",
                    "deep/nested/folder/file.txt",
                    "setup.py"
                ]
            )
        ]
        
        analyzer = FileAnalyzer("root", commits)
        files, context = analyzer.analyze_files("1.0.0")
        
        # High priority files should come first
        assert files[0] in ["README.md", "setup.py"]  # Special files
        assert files.index("src/main.py") < files.index("test_something.py")  # src > test
        assert files[-1] == "deep/nested/folder/file.txt"  # Deeply nested last


class TestChangelogGenerator:
    """Test the ChangelogGenerator class"""
    
    def test_generate_from_conventional_commits(self):
        """Test generating changelog from conventional commits"""
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="feat: add new feature",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=["feature.py"]
            ),
            GitCommit(
                hash="def456",
                short_hash="def456",
                message="fix: resolve critical bug",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="1:00PM EST",
                files=["bug.py"]
            )
        ]
        
        generator = ChangelogGenerator("test-package", "1.0.0")
        content = generator.generate(commits, [], "", "", "")
        
        assert "### Added" in content
        assert "Add new feature" in content
        assert "### Fixed" in content
        assert "Resolve critical bug" in content
    
    def test_generate_from_non_conventional_commits(self):
        """Test generating changelog from regular commits"""
        commits = [
            GitCommit(
                hash="abc123",
                short_hash="abc123",
                message="Add awesome new feature",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="12:00PM EST",
                files=["feature.py"]
            ),
            GitCommit(
                hash="def456",
                short_hash="def456",
                message="Fix critical bug in parser",
                author_name="Test Author",
                author_email="test@example.com",
                commit_date="2024-01-01",
                commit_time="1:00PM EST",
                files=["parser.py"]
            )
        ]
        
        generator = ChangelogGenerator("test-package", "1.0.0")
        content = generator.generate(commits, [], "", "", "")
        
        assert "### Added" in content
        assert "Add awesome new feature" in content
        assert "### Fixed" in content
        assert "Fix critical bug in parser" in content
    
    def test_detect_similar_entries(self):
        """Test detection of similar/duplicate entries"""
        generator = ChangelogGenerator("test-package", "1.0.0")
        
        # Test exact match
        assert generator._similar_entries("- Fix bug", "- Fix bug")
        
        # Test with different formatting
        assert generator._similar_entries("- **Fix** bug", "- Fix bug")
        
        # Test with hash
        assert generator._similar_entries("- Fix bug (abc123)", "- Fix bug (def456)")
        
        # Test different entries
        assert not generator._similar_entries("- Fix bug", "- Add feature") 