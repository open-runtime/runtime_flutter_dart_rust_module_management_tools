#!/usr/bin/env python3
"""
Tests for ContributorAnalyzer CLI tool
"""
import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, AsyncMock
import argparse

# Patch Google API imports to avoid dependency issues
import sys
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.generativeai.types'] = MagicMock()

from tooling.cli.contributor_analyzer import (
    ContributorAnalyzer, 
    ContributorProfile, 
    ModelRotator
)


class TestContributorAnalyzerCLI:
    """Test cases for contributor analyzer CLI"""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_fdr_project):
        """Set up test environment"""
        self.project_root = mock_fdr_project
        # Mock config to avoid initialization errors
        mock_config = MagicMock()
        mock_config.use_color = True
        mock_config.quiet = False
        mock_config.verbose = False
        mock_config.debug = False
        mock_config.dry_run = False
        mock_config.project_root = self.project_root
        mock_config.gemini_api_key = "test-key"
        mock_config.get_table_style.return_value = None
        
        with patch('tooling.cli.cli_tools_base.get_config', return_value=mock_config):
            self.tool = ContributorAnalyzer()
            self.tool.config = mock_config
    
    def test_tool_properties(self):
        """Test tool properties"""
        assert self.tool.name == "contributors"
        assert "GitHub organizations" in self.tool.description
    
    def test_add_arguments(self):
        """Test that arguments are added correctly"""
        parser = argparse.ArgumentParser()
        self.tool.add_arguments(parser)
        
        # Parse with minimal args
        args = parser.parse_args(['--organizations', 'test-org'])
        assert hasattr(args, 'organizations')
        assert hasattr(args, 'repositories')
        assert hasattr(args, 'since')
        assert hasattr(args, 'profiles_dir')
        assert hasattr(args, 'from_scratch')
        assert hasattr(args, 'update')
        assert hasattr(args, 'analysis_dir')
        assert hasattr(args, 'max_files_per_contributor')
        assert hasattr(args, 'skip_code_analysis')
        # Note: dry_run is added by base CLITool class, not our custom arguments
        assert args.organizations == ['test-org']


class TestContributorProfile:
    """Test ContributorProfile dataclass"""
    
    def test_profile_initialization(self):
        """Test profile initialization with defaults"""
        profile = ContributorProfile(username="test-user")
        
        assert profile.username == "test-user"
        assert profile.name is None
        assert profile.email is None
        assert profile.total_commits == 0
        assert profile.total_prs == 0
        assert profile.total_issues == 0
        assert isinstance(profile.repositories, set)
        assert isinstance(profile.languages, set)
        assert isinstance(profile.notable_contributions, list)
        assert isinstance(profile.skill_assessment, dict)
        assert isinstance(profile.activity_pattern, dict)
        assert profile.first_contribution is None
        assert profile.last_contribution is None
        assert profile.contribution_frequency == 0.0
        assert profile.avg_pr_size == 0.0
        assert profile.code_review_count == 0
    
    def test_profile_with_data(self):
        """Test profile with actual data"""
        now = datetime.now()
        profile = ContributorProfile(
            username="jane-dev",
            name="Jane Developer", 
            email="jane@example.com",
            total_commits=150,
            total_prs=25,
            first_contribution=now - timedelta(days=365),
            last_contribution=now
        )
        
        assert profile.username == "jane-dev"
        assert profile.name == "Jane Developer"
        assert profile.email == "jane@example.com"
        assert profile.total_commits == 150
        assert profile.total_prs == 25
        assert profile.first_contribution == now - timedelta(days=365)
        assert profile.last_contribution == now


class TestModelRotator:
    """Test model rotation and rate limiting"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = MagicMock()
        config.gemini_api_key = "test-key"
        return config
    
    def test_model_preference_order(self, mock_config):
        """Test models are in correct preference order"""
        with patch('tooling.cli.contributor_analyzer.GeminiClient'):
            rotator = ModelRotator(mock_config)
            
            # Should prefer better models first
            assert rotator.MODELS[0] == "gemini-2.5-pro-preview-06-05"
            assert rotator.MODELS[1] == "gemini-2.5-pro-preview-05-06"
            assert rotator.MODELS[2] == "gemini-2.5-flash-preview-04-17"
            assert rotator.MODELS[3] == "gemini-2.0-flash"
            assert rotator.FALLBACK_MODEL == "gemini-2.0-flash"
    
    @patch('tooling.cli.contributor_analyzer.GeminiClient')
    def test_client_initialization(self, mock_client_class, mock_config):
        """Test client initialization"""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        rotator = ModelRotator(mock_config)
        
        # Check clients were created for each model
        assert len(rotator.clients) == len(rotator.MODELS)
        for model in rotator.MODELS:
            assert model in rotator.clients
    
    @patch('tooling.cli.contributor_analyzer.GeminiClient')
    def test_get_next_client_success(self, mock_client_class, mock_config):
        """Test getting next client when all models available"""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        rotator = ModelRotator(mock_config)
        
        client, model = rotator.get_next_client()
        
        # Should return best model first
        assert model == "gemini-2.5-pro-preview-06-05"
        assert client == mock_client_instance
    
    @patch('tooling.cli.contributor_analyzer.GeminiClient')
    def test_model_failure_tracking(self, mock_client_class, mock_config):
        """Test model failure tracking and cooldown"""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        rotator = ModelRotator(mock_config)
        
        # Mark first model as failed
        test_error = Exception("Rate limit exceeded")
        rotator.mark_model_failure("gemini-2.5-pro-preview-06-05", test_error)
        
        # Should skip failed model and use next
        client, model = rotator.get_next_client()
        assert model == "gemini-2.5-pro-preview-05-06"
        
        # Check failure tracking
        assert "gemini-2.5-pro-preview-06-05" in rotator.model_failures
        assert "gemini-2.5-pro-preview-06-05" in rotator.last_failure_time
        assert rotator.model_failures["gemini-2.5-pro-preview-06-05"] == 1
    
    @patch('tooling.cli.contributor_analyzer.GeminiClient')
    def test_fallback_to_stable_model(self, mock_client_class, mock_config):
        """Test fallback to stable model when all preview models fail"""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        rotator = ModelRotator(mock_config)
        
        # Mark all preview models as failed
        for model in rotator.MODELS[:-1]:  # All except fallback
            rotator.mark_model_failure(model, Exception("Rate limit"))
        
        client, model = rotator.get_next_client()
        
        # Should use fallback model
        assert model == "gemini-2.0-flash"
    
    @patch('tooling.cli.contributor_analyzer.GeminiClient')
    def test_model_status_reporting(self, mock_client_class, mock_config):
        """Test model status reporting"""
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        rotator = ModelRotator(mock_config)
        
        # Initial status - all available
        status = rotator.get_model_status()
        for model in rotator.MODELS:
            assert status[model] == "available"
        
        # Mark one model as failed
        rotator.mark_model_failure("gemini-2.5-pro-preview-06-05", Exception("Test error"))
        
        status = rotator.get_model_status()
        assert "cooling down" in status["gemini-2.5-pro-preview-06-05"]


class TestContributorAnalyzerUnit:
    """Unit tests for ContributorAnalyzer functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_fdr_project):
        """Set up test environment"""
        self.project_root = mock_fdr_project
        self.mock_config = MagicMock()
        self.mock_config.project_root = self.project_root
        self.mock_config.gemini_api_key = "test-key"
        self.mock_config.dry_run = False
        self.mock_config.debug = False
        self.mock_config.verbose = False
        
        with patch('tooling.cli.cli_tools_base.get_config', return_value=self.mock_config):
            self.analyzer = ContributorAnalyzer()
            self.analyzer.config = self.mock_config
            self.analyzer.console = MagicMock()
            self.analyzer.git_ops = AsyncMock()
            self.analyzer.file_ops = AsyncMock()
            self.analyzer.contributors = {}
            self.analyzer.since_date = datetime.now() - timedelta(days=30)
    
    def test_since_date_parsing(self):
        """Test date parsing for various formats"""
        # Test relative formats
        result = self.analyzer._parse_since_date("1week")
        assert result is not None
        assert isinstance(result, datetime)
        
        result = self.analyzer._parse_since_date("30days")
        assert result is not None
        
        result = self.analyzer._parse_since_date("6months")
        assert result is not None
        
        # Test absolute date
        result = self.analyzer._parse_since_date("2024-01-01")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        
        # Test invalid format
        result = self.analyzer._parse_since_date("invalid")
        assert result is None
    
    @patch('subprocess.run')
    def test_github_cli_check_success(self, mock_run):
        """Test GitHub CLI availability check - success"""
        mock_run.return_value.returncode = 0
        result = self.analyzer._check_github_cli()
        assert result is True
        
        # Should check both version and auth
        assert mock_run.call_count == 2
    
    @patch('subprocess.run')
    def test_github_cli_check_not_installed(self, mock_run):
        """Test GitHub CLI check when not installed"""
        mock_run.return_value.returncode = 1
        result = self.analyzer._check_github_cli()
        assert result is False
    
    @patch('subprocess.run')
    def test_github_cli_check_not_authenticated(self, mock_run):
        """Test GitHub CLI check when not authenticated"""
        # First call (version check) succeeds, second (auth check) fails
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1)
        ]
        result = self.analyzer._check_github_cli()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_repository_discovery(self):
        """Test repository discovery via GitHub CLI"""
        # Mock args
        self.analyzer.args = MagicMock()
        self.analyzer.args.organizations = ["test-org"]
        self.analyzer.args.repositories = None
        
        # Mock GitHub CLI response
        mock_response = Mock()
        mock_response.success = True
        mock_response.stdout = json.dumps([
            {"name": "repo1"},
            {"name": "repo2"},
            {"name": "repo3"}
        ])
        
        self.analyzer.git_ops.run_command.return_value = mock_response
        
        repos = await self.analyzer._get_repositories_to_analyze()
        
        assert "test-org" in repos
        assert repos["test-org"] == ["repo1", "repo2", "repo3"]
        
        # Check GitHub CLI was called correctly
        self.analyzer.git_ops.run_command.assert_called_with([
            'gh', 'repo', 'list', 'test-org', '--json', 'name', '--limit', '1000'
        ])
    
    @pytest.mark.asyncio
    async def test_repository_discovery_with_filter(self):
        """Test repository discovery with repository filter"""
        # Mock args with specific repositories
        self.analyzer.args = MagicMock()
        self.analyzer.args.organizations = ["test-org"]
        self.analyzer.args.repositories = ["test-org/repo1", "repo2"]
        
        repos = await self.analyzer._get_repositories_to_analyze()
        
        assert "test-org" in repos
        assert repos["test-org"] == ["repo1", "repo2"]
        
        # Should not call GitHub CLI when repositories are specified
        self.analyzer.git_ops.run_command.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_contributor_discovery(self):
        """Test contributor discovery across repositories"""
        repos = {"test-org": ["repo1", "repo2"]}
        
        # Mock contributor responses
        mock_response = Mock()
        mock_response.success = True
        mock_response.stdout = json.dumps([
            {"login": "user1"},
            {"login": "user2"},
            {"login": "user3"}
        ])
        
        self.analyzer.git_ops.run_command.return_value = mock_response
        
        # Mock progress and args
        progress = Mock()
        task_id = "test-task"
        self.analyzer.args = MagicMock()
        self.analyzer.args.max_workers = 5
        
        contributors = await self.analyzer._discover_contributors(repos, progress, task_id)
        
        assert len(contributors) == 3
        assert "user1" in contributors
        assert "user2" in contributors
        assert "user3" in contributors
        
        # Should have called API for each repo
        assert self.analyzer.git_ops.run_command.call_count == 2
    
    def test_ai_prompt_building(self):
        """Test AI analysis prompt building"""
        profile = ContributorProfile(
            username="test-user",
            total_commits=150,
            total_prs=30,
            contribution_frequency=4.2
        )
        profile.repositories.add("test-org/repo1")
        profile.repositories.add("test-org/repo2")
        profile.first_contribution = datetime(2024, 1, 1)
        profile.last_contribution = datetime(2024, 1, 30)
        
        prompt = self.analyzer._build_ai_analysis_prompt(profile)
        
        # Check prompt includes key information
        assert "test-user" in prompt
        assert "150" in prompt  # total commits
        assert "30" in prompt   # total prs
        assert "4.2" in prompt  # contribution frequency
        assert "test-org/repo1" in prompt
        assert "JSON format" in prompt
    
    def test_ai_response_parsing_json(self):
        """Test AI response parsing for JSON"""
        json_response = json.dumps({
            "analysis": "Test analysis",
            "skills": {"backend": "advanced", "frontend": "intermediate"},
            "summary": "Test summary"
        })
        
        parsed = self.analyzer._parse_ai_response(json_response)
        assert parsed["analysis"] == "Test analysis"
        assert parsed["skills"]["backend"] == "advanced"
        assert parsed["skills"]["frontend"] == "intermediate"
        assert parsed["summary"] == "Test summary"
    
    def test_ai_response_parsing_plain_text(self):
        """Test AI response parsing for plain text fallback"""
        plain_response = "This is plain text analysis"
        parsed = self.analyzer._parse_ai_response(plain_response)
        assert parsed["analysis"] == "This is plain text analysis"
        assert parsed["skills"] == {}
        assert parsed["summary"] == "AI analysis available"
    
    def test_profile_markdown_generation(self):
        """Test markdown profile generation"""
        profile = ContributorProfile(
            username="test-user",
            name="Test User",
            email="test@example.com",
            total_commits=100,
            total_prs=20
        )
        profile.repositories.add("test-org/repo1")
        profile.repositories.add("test-org/repo2")
        profile.skill_assessment = {"backend": "advanced", "frontend": "intermediate"}
        profile.ai_analysis = "Consistent contributor with strong technical skills"
        profile.first_contribution = datetime(2024, 1, 1)
        profile.last_contribution = datetime(2024, 1, 30)
        profile.contribution_frequency = 3.5
        
        content = self.analyzer._generate_profile_markdown(profile)
        
        # Check content includes key information
        assert "# Test User (@test-user)" in content
        assert "Total Commits | 100" in content
        assert "Total Pull Requests | 20" in content
        assert "`test-org/repo1`" in content
        assert "`test-org/repo2`" in content
        assert "Backend | Advanced" in content
        assert "Frontend | Intermediate" in content
        assert "Consistent contributor with strong technical skills" in content
        assert "2024-01-01" in content  # first contribution
        assert "2024-01-30" in content  # last contribution
        assert "3.5" in content  # frequency
    
    def test_validation_conflicting_modes(self):
        """Test validation with conflicting modes"""
        self.analyzer.args = MagicMock()
        self.analyzer.args.from_scratch = True
        self.analyzer.args.update = True
        
        result = self.analyzer.validate_args()
        assert result is False
    
    def test_validation_default_update_mode(self):
        """Test validation defaults to update mode"""
        self.analyzer.args = MagicMock()
        self.analyzer.args.from_scratch = False
        self.analyzer.args.update = False
        
        with patch.object(self.analyzer, '_check_github_cli', return_value=True):
            with patch.object(self.analyzer, '_parse_since_date', return_value=datetime.now()):
                result = self.analyzer.validate_args()
                assert result is True
                assert self.analyzer.args.update is True
    
    def test_code_file_detection(self):
        """Test code file detection logic"""
        # Test valid code files
        assert self.analyzer._is_code_file("src/main.py") is True
        assert self.analyzer._is_code_file("components/Button.tsx") is True
        assert self.analyzer._is_code_file("lib/utils.js") is True
        assert self.analyzer._is_code_file("app.dart") is True
        
        # Test files to skip
        assert self.analyzer._is_code_file("node_modules/package/index.js") is False
        assert self.analyzer._is_code_file("dist/bundle.js") is False
        assert self.analyzer._is_code_file("README.md") is False
        assert self.analyzer._is_code_file(".git/config") is False
    
    def test_language_detection(self):
        """Test programming language detection"""
        test_cases = [
            ("main.py", "Python"),
            ("app.js", "JavaScript"),
            ("component.tsx", "React TypeScript"),
            ("service.dart", "Dart"),
            ("utils.go", "Go"),
            ("core.rs", "Rust"),
            ("unknown.xyz", "Unknown")
        ]
        
        for file_path, expected_lang in test_cases:
            result = self.analyzer._detect_language(file_path)
            assert result == expected_lang
    
    @pytest.mark.asyncio
    async def test_repository_cloning(self):
        """Test repository cloning functionality"""
        repos = {"test-org": ["repo1", "repo2"]}
        
        # Mock successful clone results
        mock_result = Mock()
        mock_result.success = True
        mock_result.stderr = ""
        self.analyzer.git_ops.run_command.return_value = mock_result
        
        # Mock args
        self.analyzer.args = MagicMock()
        self.analyzer.args.max_workers = 2
        self.analyzer.args.analysis_dir = Path("/tmp/test_analysis")
        
        progress = Mock()
        task_id = "test-task"
        
        with patch('pathlib.Path.exists', return_value=False):
            cloned_repos = await self.analyzer._clone_repositories(repos, progress, task_id)
            
            # Should attempt to clone both repos
            assert self.analyzer.git_ops.run_command.call_count == 2
            
            # Check clone commands were correct
            calls = self.analyzer.git_ops.run_command.call_args_list
            for call in calls:
                args = call[0][0]
                assert args[0] == 'gh'
                assert args[1] == 'repo'
                assert args[2] == 'clone'
                assert '--depth' in args
    
    @pytest.mark.asyncio
    async def test_code_quality_analysis(self):
        """Test code quality analysis functionality"""
        # Setup test contributor with code samples
        profile = ContributorProfile(username="test-user")
        profile.recent_code_samples = [
            {
                'file': 'main.py',
                'content': 'def hello_world():\n    print("Hello, World!")',
                'language': 'Python',
                'repository': 'test-org/repo1',
                'commit': 'abc12345'
            }
        ]
        
        self.analyzer.contributors = {"test-user": profile}
        
        # Mock AI client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = json.dumps({
            "quality_score": 8.5,
            "patterns": ["clean functions", "good naming"],
            "style_assessment": "Professional coding style",
            "architectural_work": ["designed API layer"]
        })
        mock_client.generate_content_async.return_value = mock_response
        
        mock_rotator = Mock()
        mock_rotator.get_next_client.return_value = (mock_client, "gemini-2.5-pro-preview-06-05")
        self.analyzer.model_rotator = mock_rotator
        
        # Run analysis
        await self.analyzer._ai_analyze_code_quality(profile)
        
        # Check results were applied
        assert profile.code_quality_score == 8.5
        assert "clean functions" in profile.code_patterns
        assert profile.code_style_assessment == "Professional coding style"
        assert "designed API layer" in profile.architectural_contributions
    
    def test_code_analysis_prompt_building(self):
        """Test code analysis prompt building"""
        profile = ContributorProfile(username="test-dev")
        profile.recent_code_samples = [
            {
                'file': 'utils.py',
                'content': 'def calculate(x, y):\n    return x + y',
                'language': 'Python',
                'repository': 'test-org/utils',
                'commit': 'def456'
            }
        ]
        profile.primary_languages = {"Python": 5, "JavaScript": 2}
        
        prompt = self.analyzer._build_code_analysis_prompt(profile)
        
        # Check prompt includes key information
        assert "test-dev" in prompt
        assert "utils.py" in prompt
        assert "Python" in prompt
        assert "calculate" in prompt
        assert "JSON format" in prompt
        assert "quality_score" in prompt
    
    def test_code_analysis_response_parsing(self):
        """Test parsing of AI code analysis responses"""
        # Test valid JSON response
        json_response = json.dumps({
            "quality_score": 7.2,
            "patterns": ["uses type hints", "proper error handling"],
            "style_assessment": "Good coding practices",
            "architectural_work": ["implemented caching"]
        })
        
        parsed = self.analyzer._parse_code_analysis_response(json_response)
        assert parsed["quality_score"] == 7.2
        assert "uses type hints" in parsed["patterns"]
        assert parsed["style_assessment"] == "Good coding practices"
        
        # Test fallback for invalid JSON
        invalid_response = "This is not valid JSON"
        parsed = self.analyzer._parse_code_analysis_response(invalid_response)
        assert parsed["quality_score"] == 5.0
        assert parsed["patterns"] == []
        assert "This is not valid JSON" in parsed["style_assessment"]


class TestContributorAnalyzerIntegration:
    """Integration tests for full workflow"""
    
    @pytest.mark.asyncio
    async def test_dry_run_workflow(self):
        """Test dry run workflow"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config = MagicMock()
            mock_config.project_root = Path(temp_dir)
            mock_config.gemini_api_key = "test-key"
            
            with patch('tooling.cli.cli_tools_base.get_config', return_value=mock_config):
                analyzer = ContributorAnalyzer()
                analyzer.config = mock_config
                analyzer.console = MagicMock()
                
                # Mock args for dry run
                analyzer.args = MagicMock()
                analyzer.args.organizations = ["test-org"]
                analyzer.args.repositories = None
                analyzer.args.dry_run = True
                analyzer.args.profiles_dir = Path(temp_dir) / "profiles"
                analyzer.args.rate_limit = 60
                
                # Mock repository discovery for dry run
                with patch.object(analyzer, '_get_repositories_to_analyze') as mock_get_repos:
                    mock_get_repos.return_value = {"test-org": ["repo1", "repo2"]}
                    
                    # Patch asyncio.run to avoid event loop issues in tests
                    with patch('asyncio.run') as mock_run:
                        mock_run.return_value = {"test-org": ["repo1", "repo2"]}
                        
                        result = analyzer._dry_run_analysis()
                        
                        assert result == 0
                        analyzer.console.print.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 