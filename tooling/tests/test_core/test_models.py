"""
Tests for core models
"""
import pytest
from unittest.mock import patch, Mock
from datetime import datetime

from tooling.core.models import (
    AnalysisMode, ConventionalCommit, GitCommit, VersionEntry,
    AnalysisMetrics, CONVENTIONAL_TYPES, CHANGELOG_SECTIONS
)


class TestAnalysisMode:
    """Test AnalysisMode enum"""
    
    def test_analysis_mode_values(self):
        """Test AnalysisMode enum values"""
        assert AnalysisMode.CURRENT_BRANCH.value == "current-branch-only"
        assert AnalysisMode.SMART_HISTORICAL.value == "smart-historical"
        assert AnalysisMode.REBUILD_ALL.value == "rebuild-all"


class TestConventionalCommit:
    """Test ConventionalCommit dataclass"""
    
    def test_conventional_commit_creation(self):
        """Test creating ConventionalCommit"""
        commit = ConventionalCommit(
            type="feat",
            scope="api",
            breaking=False,
            description="add new endpoint",
            body="This adds a new REST endpoint",
            footers={"Reviewed-by": "john"}
        )
        
        assert commit.type == "feat"
        assert commit.scope == "api"
        assert commit.breaking is False
        assert commit.description == "add new endpoint"
        assert commit.body == "This adds a new REST endpoint"
        assert commit.footers == {"Reviewed-by": "john"}
    
    def test_conventional_commit_minimal(self):
        """Test creating minimal ConventionalCommit"""
        commit = ConventionalCommit(
            type="fix",
            scope=None,
            breaking=False,
            description="fix bug",
            body=None,
            footers={}
        )
        
        assert commit.type == "fix"
        assert commit.scope is None
        assert commit.body is None


class TestGitCommit:
    """Test GitCommit dataclass"""
    
    def test_git_commit_creation(self):
        """Test creating GitCommit"""
        commit = GitCommit(
            hash="abc123def456",
            short_hash="abc123",
            message="feat: add new feature",
            author_name="John Doe",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM EST",
            files=["file1.py", "file2.py"],
            pr_number=42
        )
        
        assert commit.hash == "abc123def456"
        assert commit.short_hash == "abc123"
        assert commit.message == "feat: add new feature"
        assert commit.pr_number == 42
        assert len(commit.files) == 2
    
    def test_parse_conventional_commit_basic(self):
        """Test parsing basic conventional commit"""
        commit = GitCommit(
            hash="abc123",
            short_hash="abc",
            message="feat: add new feature",
            author_name="John",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        assert commit.conventional is not None
        assert commit.conventional.type == "feat"
        assert commit.conventional.scope is None
        assert commit.conventional.breaking is False
        assert commit.conventional.description == "add new feature"
    
    def test_parse_conventional_commit_with_scope(self):
        """Test parsing conventional commit with scope"""
        commit = GitCommit(
            hash="abc123",
            short_hash="abc",
            message="fix(api): fix endpoint bug",
            author_name="John",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        assert commit.conventional.type == "fix"
        assert commit.conventional.scope == "api"
        assert commit.conventional.description == "fix endpoint bug"
    
    def test_parse_conventional_commit_breaking(self):
        """Test parsing breaking change conventional commit"""
        commit = GitCommit(
            hash="abc123",
            short_hash="abc",
            message="feat!: breaking API change",
            author_name="John",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        assert commit.conventional.breaking is True
    
    def test_parse_conventional_commit_with_body_and_footers(self):
        """Test parsing conventional commit with body and footers"""
        message = """fix: fix critical bug

This is the body of the commit
with multiple lines

Reviewed-by: Jane
BREAKING-CHANGE: This breaks the API
Closes: #123"""
        
        commit = GitCommit(
            hash="abc123",
            short_hash="abc",
            message=message,
            author_name="John",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        assert commit.conventional.type == "fix"
        assert "This is the body" in commit.conventional.body
        assert commit.conventional.breaking is True  # Should be True due to BREAKING-CHANGE footer
        assert "BREAKING-CHANGE" in commit.conventional.footers  # Footer key is captured
        assert commit.conventional.footers["BREAKING-CHANGE"] == "This breaks the API"
        assert commit.conventional.footers["Reviewed-by"] == "Jane"
        assert commit.conventional.footers["Closes"] == "#123"
    
    def test_parse_non_conventional_commit(self):
        """Test parsing non-conventional commit"""
        commit = GitCommit(
            hash="abc123",
            short_hash="abc",
            message="Just a regular commit message",
            author_name="John",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        assert commit.conventional is None
    
    def test_get_attribution_with_remote_url(self):
        """Test generating attribution with remote URL"""
        commit = GitCommit(
            hash="abc123def456",
            short_hash="abc123",
            message="fix: bug",
            author_name="John Doe",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM EST",
            files=[],
            pr_number=42
        )
        
        attribution = commit.get_attribution("https://github.com/user/repo")
        
        assert "[@john-doe]" in attribution
        assert "2025-06-07" in attribution
        assert "10:30AM EST" in attribution
        assert "[abc123](https://github.com/user/repo/commit/abc123def456)" in attribution
        assert "PR [#42](https://github.com/user/repo/pull/42)" in attribution
    
    def test_get_attribution_without_remote_url(self):
        """Test generating attribution without remote URL"""
        commit = GitCommit(
            hash="abc123def456",
            short_hash="abc123",
            message="fix: bug",
            author_name="John Doe",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM EST",
            files=[],
            pr_number=42
        )
        
        attribution = commit.get_attribution("")
        
        assert "@john-doe" in attribution
        assert "abc123" in attribution
        assert "PR #42" in attribution
        assert "https://" not in attribution
    
    def test_extract_github_username_noreply(self):
        """Test extracting GitHub username from noreply email"""
        commit = GitCommit(
            hash="abc",
            short_hash="a",
            message="test",
            author_name="John",
            author_email="12345+johndoe@users.noreply.github.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        username = commit._extract_github_username()
        assert username == "johndoe"
    
    def test_extract_github_username_plus_notation(self):
        """Test extracting GitHub username from + notation email"""
        commit = GitCommit(
            hash="abc",
            short_hash="a",
            message="test",
            author_name="John",
            author_email="user+johndoe@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        username = commit._extract_github_username()
        assert username == "johndoe"
    
    def test_extract_github_username_fallback(self):
        """Test extracting GitHub username fallback to author name"""
        commit = GitCommit(
            hash="abc",
            short_hash="a",
            message="test",
            author_name="John Doe",
            author_email="john@example.com",
            commit_date="2025-06-07",
            commit_time="10:30AM",
            files=[]
        )
        
        username = commit._extract_github_username()
        assert username == "john-doe"


class TestVersionEntry:
    """Test VersionEntry dataclass"""
    
    def test_version_entry_creation(self):
        """Test creating VersionEntry"""
        entry = VersionEntry(
            version="1.2.3",
            date="2025-06-07",
            content="### Added\n- New feature",
            is_empty=False
        )
        
        assert entry.version == "1.2.3"
        assert entry.date == "2025-06-07"
        assert "New feature" in entry.content
        assert entry.is_empty is False
    
    def test_version_entry_empty(self):
        """Test creating empty VersionEntry"""
        entry = VersionEntry(
            version="1.2.3",
            date="2025-06-07",
            content="",
            is_empty=True
        )
        
        assert entry.is_empty is True


class TestAnalysisMetrics:
    """Test AnalysisMetrics dataclass"""
    
    def test_analysis_metrics_creation(self):
        """Test creating AnalysisMetrics"""
        metrics = AnalysisMetrics(
            total_commits=100,
            total_files=50,
            cache_hits=80,
            cache_misses=20,
            llm_calls=15,
            processing_time=45.5
        )
        
        assert metrics.total_commits == 100
        assert metrics.total_files == 50
        assert metrics.cache_hits == 80
        assert metrics.cache_misses == 20
        assert metrics.llm_calls == 15
        assert metrics.processing_time == 45.5
    
    def test_analysis_metrics_defaults(self):
        """Test AnalysisMetrics default values"""
        metrics = AnalysisMetrics()
        
        assert metrics.total_commits == 0
        assert metrics.total_files == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.llm_calls == 0
        assert metrics.processing_time == 0.0
    
    @patch('tooling.cli.cli_utils.print_info')
    @patch('tooling.cli.cli_utils.print_header')
    def test_print_summary(self, mock_print_header, mock_print_info):
        """Test printing metrics summary"""
        metrics = AnalysisMetrics(
            total_commits=100,
            total_files=50,
            cache_hits=80,
            cache_misses=20,
            llm_calls=15,
            processing_time=45.5
        )
        
        metrics.print_summary()
        
        mock_print_header.assert_called_once_with("Analysis Metrics")
        assert mock_print_info.call_count >= 5
        
        # Check cache hit rate calculation
        info_calls = [str(call) for call in mock_print_info.call_args_list]
        assert any("80.0%" in call for call in info_calls)
    
    @patch('tooling.cli.cli_utils.print_info')
    @patch('tooling.cli.cli_utils.print_header')
    def test_print_summary_empty(self, mock_print_header, mock_print_info):
        """Test printing empty metrics summary"""
        metrics = AnalysisMetrics()
        
        metrics.print_summary()
        
        # Should not print anything for empty metrics
        mock_print_header.assert_not_called()
        mock_print_info.assert_not_called()


class TestConstants:
    """Test module constants"""
    
    def test_conventional_types(self):
        """Test CONVENTIONAL_TYPES mapping"""
        assert CONVENTIONAL_TYPES["feat"] == "Added"
        assert CONVENTIONAL_TYPES["fix"] == "Fixed"
        assert CONVENTIONAL_TYPES["docs"] == "Changed"
        assert CONVENTIONAL_TYPES["breaking"] == "Changed"
        assert "security" in CONVENTIONAL_TYPES
    
    def test_changelog_sections(self):
        """Test CHANGELOG_SECTIONS order"""
        assert CHANGELOG_SECTIONS[0] == "Added"
        assert CHANGELOG_SECTIONS[1] == "Changed"
        assert CHANGELOG_SECTIONS[-1] == "Security"
        assert len(CHANGELOG_SECTIONS) == 6 