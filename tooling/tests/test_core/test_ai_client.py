"""
Tests for ai_client.py - Gemini SDK Client
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
import time
import json
import hashlib
from pathlib import Path
import sys

# Mock google.genai before importing ai_client
sys.modules['google'] = Mock()
sys.modules['google.genai'] = Mock()
sys.modules['google.genai.types'] = Mock()

from tooling.core.ai_client import (
    AIResponse, PromptTemplateEngine, ResponseCache, GeminiClient,
    get_default_client, generate_commit_message, generate_changelog_entry
)


class TestAIResponse:
    """Test AIResponse dataclass"""
    
    def test_ai_response_creation(self):
        """Test creating AIResponse"""
        response = AIResponse(
            text="Test response",
            model="gemini-pro",
            prompt_tokens=10,
            response_tokens=20,
            total_tokens=30,
            cached=False,
            duration=1.5
        )
        
        assert response.text == "Test response"
        assert response.model == "gemini-pro"
        assert response.total_tokens == 30
        assert response.cached is False
        assert response.duration == 1.5
    
    def test_ai_response_defaults(self):
        """Test AIResponse default values"""
        response = AIResponse(text="Test", model="test-model")
        
        assert response.prompt_tokens == 0
        assert response.response_tokens == 0
        assert response.total_tokens == 0
        assert response.cached is False
        assert response.duration == 0.0


class TestPromptTemplateEngine:
    """Test PromptTemplateEngine"""
    
    def test_init_default_template_dir(self):
        """Test initialization with default template directory"""
        engine = PromptTemplateEngine()
        assert engine.env is not None
    
    def test_init_custom_template_dir(self, tmp_path):
        """Test initialization with custom template directory"""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        
        engine = PromptTemplateEngine(template_dir)
        assert engine.env is not None
    
    def test_truncate_filter(self):
        """Test truncate filter"""
        engine = PromptTemplateEngine()
        
        # Short text
        assert engine._truncate_filter("Hello", 10) == "Hello"
        
        # Long text
        assert engine._truncate_filter("Hello World!", 5) == "Hello..."
    
    def test_escape_markdown_filter(self):
        """Test escape markdown filter"""
        engine = PromptTemplateEngine()
        
        text = "This has *bold* and _italic_ and [link](url)"
        escaped = engine._escape_markdown_filter(text)
        
        assert "\\*bold\\*" in escaped
        assert "\\_italic\\_" in escaped
        assert "\\[link\\]\\(url\\)" in escaped
    
    @patch('tooling.core.ai_client.FileSystemLoader')
    def test_render_template(self, mock_loader):
        """Test rendering a template"""
        engine = PromptTemplateEngine()
        
        # Mock template
        mock_template = Mock()
        mock_template.render.return_value = "Rendered content"
        engine.env.get_template = Mock(return_value=mock_template)
        
        result = engine.render("test.j2", var1="value1", var2="value2")
        
        assert result == "Rendered content"
        engine.env.get_template.assert_called_once_with("test.j2")
        mock_template.render.assert_called_once_with(var1="value1", var2="value2")
    
    def test_render_template_error(self):
        """Test template render error"""
        engine = PromptTemplateEngine()
        engine.env.get_template = Mock(side_effect=Exception("Template not found"))
        
        with pytest.raises(Exception):
            engine.render("missing.j2")


class TestResponseCache:
    """Test ResponseCache"""
    
    def test_init(self, tmp_path):
        """Test cache initialization"""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        assert cache.cache_dir.exists()
        assert cache.ttl == 3600
        assert cache._memory_cache == {}
    
    def test_get_cache_key(self):
        """Test cache key generation"""
        cache = ResponseCache()
        
        key1 = cache._get_cache_key("prompt1", "model1", {"temp": 0.7})
        key2 = cache._get_cache_key("prompt1", "model1", {"temp": 0.7})
        key3 = cache._get_cache_key("prompt2", "model1", {"temp": 0.7})
        
        # Same inputs = same key
        assert key1 == key2
        # Different inputs = different key
        assert key1 != key3
        # Key should be a hash
        assert len(key1) == 64  # SHA256 hex length
    
    def test_cache_miss(self, tmp_path):
        """Test cache miss"""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        
        result = cache.get("prompt", "model", {})
        assert result is None
    
    def test_cache_memory_hit(self, tmp_path):
        """Test memory cache hit"""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        
        # Create and cache response
        response = AIResponse(text="Test", model="model")
        cache.set("prompt", "model", {}, response)
        
        # Get from cache
        cached = cache.get("prompt", "model", {})
        assert cached is not None
        assert cached.text == "Test"
        assert cached.cached is True
    
    def test_cache_disk_hit(self, tmp_path):
        """Test disk cache hit"""
        cache = ResponseCache(cache_dir=tmp_path / "cache", ttl=3600)
        
        # Create and cache response
        response = AIResponse(text="Test", model="model")
        cache.set("prompt", "model", {}, response)
        
        # Clear memory cache
        cache._memory_cache.clear()
        
        # Get from disk cache
        cached = cache.get("prompt", "model", {})
        assert cached is not None
        assert cached.text == "Test"
        assert cached.cached is True
    
    def test_cache_ttl_expiry(self, tmp_path):
        """Test cache TTL expiry"""
        cache = ResponseCache(cache_dir=tmp_path / "cache", ttl=1)
        
        # Create and cache response
        response = AIResponse(text="Test", model="model")
        cache.set("prompt", "model", {}, response)
        
        # Wait for TTL to expire
        time.sleep(1.1)
        
        # Should get cache miss
        cached = cache.get("prompt", "model", {})
        assert cached is None
    
    def test_clear_cache(self, tmp_path):
        """Test clearing cache"""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        
        # Add items to cache
        response = AIResponse(text="Test", model="model")
        cache.set("prompt1", "model", {}, response)
        cache.set("prompt2", "model", {}, response)
        
        # Clear cache
        cache.clear()
        
        # Check memory cache cleared
        assert cache._memory_cache == {}
        
        # Check disk cache cleared
        assert list(cache.cache_dir.glob("*.pkl")) == []


class TestGeminiClient:
    """Test GeminiClient"""
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_init_with_api_key(self, mock_genai_client):
        """Test initialization with API key"""
        client = GeminiClient(api_key="test-key")
        
        assert client.api_key == "test-key"
        assert client.default_model == 'gemini-2.0-flash-001'
        assert client.cache is not None
        assert client.templates is not None
        mock_genai_client.assert_called_once_with(api_key="test-key")
    
    @patch('tooling.core.ai_client.genai.Client')
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'env-key'})
    def test_init_from_env(self, mock_genai_client):
        """Test initialization from environment variable"""
        client = GeminiClient()
        assert client.api_key == "env-key"
    
    def test_init_no_api_key(self):
        """Test initialization without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with patch('tooling.core.ai_client.ToolingConfig') as mock_config:
                # Mock config to not have an API key
                mock_config_instance = Mock()
                mock_config_instance.ai_api_key = None
                mock_config.return_value = mock_config_instance
                
                with pytest.raises(ValueError, match="Gemini API key not provided"):
                    GeminiClient()
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_init_no_cache(self, mock_genai_client):
        """Test initialization without cache"""
        client = GeminiClient(api_key="test-key", cache_enabled=False)
        assert client.cache is None
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_build_config(self, mock_genai_client):
        """Test building generation config"""
        # Mock the types module
        mock_config = Mock()
        with patch('tooling.core.ai_client.types.GenerateContentConfig', return_value=mock_config) as mock_config_class:
            client = GeminiClient(api_key="test-key")
            
            # Default config
            config = client._build_config()
            mock_config_class.assert_called_with(
                temperature=0.7,
                max_output_tokens=2000,
                top_p=0.95,
                top_k=40
            )
            
            # Custom config
            config = client._build_config(
                temperature=0.9,
                max_tokens=1000,
                system_instruction="Be helpful",
                stop_sequences=["STOP"]
            )
            mock_config_class.assert_called_with(
                temperature=0.9,
                max_output_tokens=1000,
                top_p=0.95,
                top_k=40,
                system_instruction="Be helpful",
                stop_sequences=["STOP"]
            )
    
    @pytest.mark.asyncio
    @patch('tooling.core.ai_client.genai.Client')
    async def test_generate_content_async(self, mock_genai_client):
        """Test async content generation"""
        # Setup mock client
        mock_client_instance = Mock()
        mock_aio = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = Mock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30
        )
        
        mock_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio.models = mock_models
        mock_client_instance.aio = mock_aio
        mock_genai_client.return_value = mock_client_instance
        
        # Create client and generate
        client = GeminiClient(api_key="test-key", cache_enabled=False)
        response = await client.generate_content_async("Test prompt")
        
        assert response.text == "Generated text"
        assert response.total_tokens == 30
        assert response.cached is False
    
    @pytest.mark.asyncio
    @patch('tooling.core.ai_client.genai.Client')
    async def test_generate_content_async_with_cache(self, mock_genai_client):
        """Test async content generation with cache"""
        # Setup mock
        mock_client_instance = Mock()
        mock_genai_client.return_value = mock_client_instance
        
        client = GeminiClient(api_key="test-key")
        
        # Mock cache hit
        cached_response = AIResponse(text="Cached text", model="test", cached=True)
        client.cache.get = Mock(return_value=cached_response)
        
        response = await client.generate_content_async("Test prompt")
        
        assert response.text == "Cached text"
        assert response.cached is True
    
    @pytest.mark.asyncio
    @patch('tooling.core.ai_client.genai.Client')
    async def test_generate_content_async_with_template(self, mock_genai_client):
        """Test async content generation with template"""
        # Setup mocks
        mock_client_instance = Mock()
        mock_aio = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Generated from template"
        mock_response.usage_metadata = None
        
        mock_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio.models = mock_models
        mock_client_instance.aio = mock_aio
        mock_genai_client.return_value = mock_client_instance
        
        # Create client
        client = GeminiClient(api_key="test-key", cache_enabled=False)
        
        # Mock template rendering
        client.templates.render = Mock(return_value="Rendered prompt")
        
        response = await client.generate_content_async(
            prompt="",
            template="test.j2",
            template_context={"var": "value"}
        )
        
        assert response.text == "Generated from template"
        client.templates.render.assert_called_once_with("test.j2", var="value")
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_generate_content_sync(self, mock_genai_client):
        """Test synchronous content generation"""
        # Setup mock
        mock_client_instance = Mock()
        mock_genai_client.return_value = mock_client_instance
        
        client = GeminiClient(api_key="test-key", cache_enabled=False)
        
        # Mock async method
        mock_response = AIResponse(text="Sync response", model="test")
        with patch.object(client, 'generate_content_async', new=AsyncMock(return_value=mock_response)):
            response = client.generate_content("Test prompt")
            
            assert response.text == "Sync response"
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_count_tokens(self, mock_genai_client):
        """Test token counting"""
        # Setup mock
        mock_client_instance = Mock()
        mock_models = Mock()
        mock_response = Mock(total_tokens=42)
        mock_models.count_tokens = Mock(return_value=mock_response)
        mock_client_instance.models = mock_models
        mock_genai_client.return_value = mock_client_instance
        
        client = GeminiClient(api_key="test-key")
        count = client.count_tokens("Test text")
        
        assert count == 42
        mock_models.count_tokens.assert_called_once()
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_clear_cache(self, mock_genai_client):
        """Test clearing cache"""
        mock_genai_client.return_value = Mock()
        
        client = GeminiClient(api_key="test-key")
        client.cache.clear = Mock()
        
        client.clear_cache()
        client.cache.clear.assert_called_once()
    
    @patch('tooling.core.ai_client.genai.Client')
    def test_clear_cache_no_cache(self, mock_genai_client):
        """Test clearing cache when cache is disabled"""
        mock_genai_client.return_value = Mock()
        
        client = GeminiClient(api_key="test-key", cache_enabled=False)
        client.clear_cache()  # Should not raise


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('tooling.core.ai_client.GeminiClient')
    def test_get_default_client(self, mock_client_class):
        """Test getting default client (singleton)"""
        # Clear cache
        get_default_client.cache_clear()
        
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance
        
        # First call
        client1 = get_default_client()
        assert client1 == mock_instance
        
        # Second call - should return same instance
        client2 = get_default_client()
        assert client2 == client1
        
        # Should only create one instance
        mock_client_class.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('tooling.core.ai_client.get_default_client')
    async def test_generate_commit_message(self, mock_get_client):
        """Test generate_commit_message helper"""
        # Setup mock client
        mock_client = Mock()
        mock_response = AIResponse(text="  feat: add new feature  ", model="test")
        mock_client.generate_content_async = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        # Generate commit message
        message = await generate_commit_message(
            files=["file1.py", "file2.py"],
            diff="+ added\n- removed",
            context={"type": "feat"}
        )
        
        assert message == "feat: add new feature"
        
        # Check template context
        call_args = mock_client.generate_content_async.call_args
        assert call_args.kwargs['template'] == "commit_message.j2"
        assert 'files' in call_args.kwargs['template_context']
        assert 'diff' in call_args.kwargs['template_context']
        assert call_args.kwargs['template_context']['type'] == "feat"
    
    @pytest.mark.asyncio
    @patch('tooling.core.ai_client.get_default_client')
    async def test_generate_changelog_entry(self, mock_get_client):
        """Test generate_changelog_entry helper"""
        # Setup mock client
        mock_client = Mock()
        mock_response = AIResponse(text="### Added\n- New feature", model="test")
        mock_client.generate_content_async = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        # Generate changelog
        commits = [
            {"hash": "abc123", "message": "feat: add feature"},
            {"hash": "def456", "message": "fix: bug fix"}
        ]
        
        entry = await generate_changelog_entry(
            commits=commits,
            package="test-package",
            version="1.0.0"
        )
        
        assert entry == "### Added\n- New feature"
        
        # Check template context
        call_args = mock_client.generate_content_async.call_args
        assert call_args.kwargs['template'] == "changelog_entry.j2"
        assert call_args.kwargs['template_context']['package'] == "test-package"
        assert call_args.kwargs['template_context']['version'] == "1.0.0" 