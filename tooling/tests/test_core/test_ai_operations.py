"""
Tests for AI operations module.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, List, Any

from tooling.core.ai_operations import (
    AIOperations, AsyncAIClient, AIResponse, AIProvider,
    get_ai_operations, analyze_code_async, generate_changelogs_async
)


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = Mock()
    config.gemini_api_key = "test-key"
    config.ai_model = "gemini-pro"
    config.check_api_key = Mock(return_value=True)
    config.get_model = Mock(return_value="gemini-pro")
    return config


@pytest.fixture
def ai_ops(mock_config):
    """Create AI operations instance with mock config"""
    return AIOperations(config=mock_config)


class TestAIOperations:
    """Test the synchronous AI operations"""
    
    def test_init(self, mock_config):
        """Test AI operations initialization"""
        ai_ops = AIOperations(config=mock_config)
        assert ai_ops.config == mock_config
        assert ai_ops._client is None
    
    def test_is_available_with_client(self, ai_ops, mock_config):
        """Test availability check when AI client is available"""
        with patch('tooling.core.ai_operations.ai_client'):
            assert ai_ops.is_available() is True
            mock_config.check_api_key.assert_called_once()
    
    def test_is_available_without_client(self, ai_ops):
        """Test availability check when AI client is not available"""
        with patch('tooling.core.ai_operations.ai_client', None):
            assert ai_ops.is_available() is False
    
    @patch('tooling.core.ai_operations.ai_client')
    def test_generate_commit_message_success(self, mock_ai_client, ai_ops, mock_config):
        """Test successful commit message generation"""
        # Setup mock client
        mock_client = Mock()
        mock_client.generate = Mock(return_value="feat: add new feature\n\nDetailed description")
        mock_ai_client.get_client = Mock(return_value=mock_client)
        
        # Test
        response = ai_ops.generate_commit_message("diff content", style="conventional")
        
        assert response is not None
        assert response.content == "feat: add new feature\n\nDetailed description"
        assert response.provider == AIProvider.GEMINI
        assert response.model == "gemini-pro"
    
    def test_generate_commit_message_no_ai(self, ai_ops):
        """Test commit message generation when AI is not available"""
        with patch('tooling.core.ai_operations.ai_client', None):
            response = ai_ops.generate_commit_message("diff content")
            assert response is None
    
    @patch('tooling.core.ai_operations.ai_client')
    def test_analyze_code_changes_changelog(self, mock_ai_client, ai_ops):
        """Test code analysis for changelog generation"""
        # Setup mock
        mock_client = Mock()
        mock_client.generate = Mock(return_value="### Added\n- New feature")
        mock_ai_client.get_client = Mock(return_value=mock_client)
        
        # Test
        files = [
            {"path": "test.py", "diff": "+ new code"}
        ]
        response = ai_ops.analyze_code_changes(files, purpose="changelog")
        
        assert response is not None
        assert "Added" in response.content
        assert response.provider == AIProvider.GEMINI
    
    @patch('tooling.core.ai_operations.ai_client')
    def test_analyze_code_changes_review(self, mock_ai_client, ai_ops):
        """Test code analysis for code review"""
        # Setup mock
        mock_client = Mock()
        mock_client.generate = Mock(return_value="Code looks good. Consider adding tests.")
        mock_ai_client.get_client = Mock(return_value=mock_client)
        
        # Test
        files = [
            {"path": "test.py", "diff": "+ new code", "language": "python"}
        ]
        response = ai_ops.analyze_code_changes(files, purpose="review")
        
        assert response is not None
        assert "Consider adding tests" in response.content
    
    def test_analyze_code_changes_invalid_purpose(self, ai_ops):
        """Test code analysis with invalid purpose"""
        with patch('tooling.core.ai_operations.ai_client'):
            files = [{"path": "test.py"}]
            response = ai_ops.analyze_code_changes(files, purpose="invalid")
            assert response is None
    
    @patch('tooling.core.ai_operations.ai_client')
    def test_generate_release_notes(self, mock_ai_client, ai_ops):
        """Test release notes generation"""
        # Setup mock
        mock_client = Mock()
        mock_client.generate = Mock(return_value="## Release Notes v1.0.0\n\nMajor release...")
        mock_ai_client.get_client = Mock(return_value=mock_client)
        
        # Test
        response = ai_ops.generate_release_notes(
            "### Added\n- Feature",
            "1.0.0",
            {"commits": 10}
        )
        
        assert response is not None
        assert "Release Notes" in response.content
        assert response.model == "gemini-pro"
    
    @patch('tooling.core.ai_operations.ai_client')
    def test_generate_pr_description(self, mock_ai_client, ai_ops):
        """Test PR description generation"""
        # Setup mock
        mock_client = Mock()
        mock_client.generate = Mock(return_value="## Summary\n\nThis PR adds...")
        mock_ai_client.get_client = Mock(return_value=mock_client)
        
        # Test
        response = ai_ops.generate_pr_description(
            "Add new feature",
            "Added feature X",
            ["feat: add feature X"],
            branch="feature/x"
        )
        
        assert response is not None
        assert "Summary" in response.content
    
    def test_clean_response(self, ai_ops):
        """Test response cleaning"""
        # Test removing code blocks
        assert ai_ops._clean_response("```\ncode\n```") == "code"
        assert ai_ops._clean_response("normal text") == "normal text"
        assert ai_ops._clean_response("") == ""
        assert ai_ops._clean_response(None) == ""
    
    def test_detect_provider(self, ai_ops):
        """Test provider detection"""
        # First ensure client is initialized to avoid LOCAL default
        with patch('tooling.core.ai_operations.ai_client') as mock_ai_client:
            mock_client = Mock()
            mock_ai_client.get_client = Mock(return_value=mock_client)
            
            # Force client initialization
            _ = ai_ops.client
            
            # Test with Gemini key
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'key'}):
                assert ai_ops._detect_provider() == AIProvider.GEMINI
            
            # Test with OpenAI key
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'key'}, clear=True):
                assert ai_ops._detect_provider() == AIProvider.OPENAI
            
            # Test with no keys
            with patch.dict('os.environ', {}, clear=True):
                ai_ops.config.gemini_api_key = None
                assert ai_ops._detect_provider() == AIProvider.LOCAL


class TestAsyncAIClient:
    """Test the async AI client"""
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config):
        """Test async context manager"""
        client = AsyncAIClient(config=mock_config)
        
        async with client as c:
            assert c.client is not None
            assert isinstance(c.client, MagicMock) or hasattr(c.client, 'aclose')
    
    @pytest.mark.asyncio
    async def test_generate_single_success(self, mock_config):
        """Test successful single prompt generation"""
        client = AsyncAIClient(config=mock_config)
        
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json = Mock(return_value={
            "candidates": [{
                "content": {
                    "parts": [{"text": "AI response"}]
                }
            }],
            "usageMetadata": {"totalTokens": 100}
        })
        mock_response.raise_for_status = Mock()
        
        with patch.object(client, 'client') as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            
            response = await client.generate_single("test prompt")
            
            assert response.content == "AI response"
            assert response.provider == AIProvider.GEMINI
            assert response.usage == {"totalTokens": 100}
            assert response.error is None
    
    @pytest.mark.asyncio
    async def test_generate_single_error(self, mock_config):
        """Test error handling in single prompt generation"""
        client = AsyncAIClient(config=mock_config)
        
        with patch.object(client, 'client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("API Error"))
            
            response = await client.generate_single("test prompt")
            
            assert response.content == ""
            assert response.error == "API Error"
    
    @pytest.mark.asyncio
    async def test_generate_batch(self, mock_config):
        """Test batch generation"""
        client = AsyncAIClient(config=mock_config)
        
        # Mock responses
        responses = [
            AIResponse(content=f"Response {i}", provider=AIProvider.GEMINI, model="gemini-pro")
            for i in range(3)
        ]
        
        with patch.object(client, 'generate_single', new=AsyncMock(side_effect=responses)):
            results = await client.generate_batch(["prompt1", "prompt2", "prompt3"])
            
            assert len(results) == 3
            assert results[0].content == "Response 0"
            assert results[2].content == "Response 2"


class TestAsyncMethods:
    """Test async methods in AIOperations"""
    
    @pytest.mark.asyncio
    async def test_generate_commit_message_async(self, ai_ops):
        """Test async commit message generation"""
        with patch.object(ai_ops, 'is_available', return_value=True):
            with patch('tooling.core.ai_operations.AsyncAIClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AIResponse(
                    content="feat: async commit",
                    provider=AIProvider.GEMINI,
                    model="gemini-pro"
                )
                mock_client.generate_single = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client
                
                response = await ai_ops.generate_commit_message_async("diff", style="conventional")
                
                assert response is not None
                assert response.content == "feat: async commit"
    
    @pytest.mark.asyncio
    async def test_analyze_code_parallel(self, ai_ops):
        """Test parallel code analysis"""
        files = {
            "file1.py": "code1",
            "file2.py": "code2"
        }
        template = "Analyze {file_path}: {content}"
        
        with patch('tooling.core.ai_operations.AsyncAIClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_responses = [
                AIResponse(content="Analysis 1", provider=AIProvider.GEMINI, model="gemini-pro"),
                AIResponse(content="Analysis 2", provider=AIProvider.GEMINI, model="gemini-pro")
            ]
            mock_client.generate_batch = AsyncMock(return_value=mock_responses)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            results = await ai_ops.analyze_code_parallel(files, template)
            
            assert len(results) == 2
            assert results["file1.py"] == "Analysis 1"
            assert results["file2.py"] == "Analysis 2"
    
    @pytest.mark.asyncio
    async def test_generate_changelogs_parallel(self, ai_ops):
        """Test parallel changelog generation"""
        packages = {
            "package1": [
                {"hash": "abc123", "subject": "feat: feature 1"}
            ],
            "package2": [
                {"hash": "def456", "subject": "fix: bug fix"}
            ]
        }
        
        with patch('tooling.core.ai_operations.AsyncAIClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_responses = [
                AIResponse(content="### Added\n- Feature 1", provider=AIProvider.GEMINI, model="gemini-pro"),
                AIResponse(content="### Fixed\n- Bug fix", provider=AIProvider.GEMINI, model="gemini-pro")
            ]
            
            # Mock gather to return responses in order
            async def mock_gather(*tasks):
                return mock_responses
            
            mock_client.generate_single = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            with patch('asyncio.gather', new=mock_gather):
                results = await ai_ops.generate_changelogs_parallel(packages)
            
            assert len(results) == 2
            assert "Feature 1" in results["package1"]
            assert "Bug fix" in results["package2"]


class TestConvenienceFunctions:
    """Test module-level convenience functions"""
    
    def test_get_ai_operations(self):
        """Test singleton pattern for AI operations"""
        ai_ops1 = get_ai_operations()
        ai_ops2 = get_ai_operations()
        assert ai_ops1 is ai_ops2
    
    @pytest.mark.asyncio
    async def test_analyze_code_async(self):
        """Test convenience function for async code analysis"""
        files = {"test.py": "code"}
        template = "Analyze: {file_path}"
        
        with patch('tooling.core.ai_operations.get_ai_operations') as mock_get:
            mock_ops = Mock()
            mock_ops.analyze_code_parallel = AsyncMock(return_value={"test.py": "analysis"})
            mock_get.return_value = mock_ops
            
            result = await analyze_code_async(files, template)
            assert result == {"test.py": "analysis"}
    
    @pytest.mark.asyncio
    async def test_generate_changelogs_async(self):
        """Test convenience function for async changelog generation"""
        packages = {"pkg": [{"hash": "123", "subject": "test"}]}
        
        with patch('tooling.core.ai_operations.get_ai_operations') as mock_get:
            mock_ops = Mock()
            mock_ops.generate_changelogs_parallel = AsyncMock(return_value={"pkg": "changelog"})
            mock_get.return_value = mock_ops
            
            result = await generate_changelogs_async(packages)
            assert result == {"pkg": "changelog"} 