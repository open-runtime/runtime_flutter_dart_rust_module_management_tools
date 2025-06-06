#!/usr/bin/env python3
"""
Gemini SDK Client Wrapper
Provides a unified interface for AI operations using the Google Gemini SDK
with built-in caching, retry logic, and prompt engineering.
"""

import os
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator, Union
from dataclasses import dataclass
from functools import lru_cache
import pickle

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from jinja2 import Environment, FileSystemLoader

from tooling.core.logging import get_logger, ProgressLogger
from tooling.core.base_config import ToolingConfig

logger = get_logger(__name__)


@dataclass
class AIResponse:
    """Structured response from AI operations"""
    text: str
    model: str
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    cached: bool = False
    duration: float = 0.0


class PromptTemplateEngine:
    """Manages prompt templates for consistent AI interactions"""
    
    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent.parent / "templates" / "prompts"
        
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Register custom filters
        self.env.filters['truncate'] = self._truncate_filter
        self.env.filters['escape_markdown'] = self._escape_markdown_filter
    
    @staticmethod
    def _truncate_filter(text: str, length: int = 1000) -> str:
        """Truncate text to specified length"""
        if len(text) <= length:
            return text
        return text[:length] + "..."
    
    @staticmethod
    def _escape_markdown_filter(text: str) -> str:
        """Escape markdown special characters"""
        chars = ['*', '_', '[', ']', '(', ')', '#', '>', '`']
        for char in chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def render(self, template_name: str, **context) -> str:
        """Render a prompt template with context"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error("template_render_error", template=template_name, error=str(e))
            raise


class ResponseCache:
    """Caching layer for AI responses"""
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl: int = 3600):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "gemini_sdk"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._memory_cache = {}
    
    def _get_cache_key(self, prompt: str, model: str, config: Dict[str, Any]) -> str:
        """Generate cache key from prompt and config"""
        cache_data = {
            'prompt': prompt,
            'model': model,
            'config': config
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    def get(self, prompt: str, model: str, config: Dict[str, Any]) -> Optional[AIResponse]:
        """Get cached response if available"""
        key = self._get_cache_key(prompt, model, config)
        
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                logger.debug("cache_hit_memory", key=key[:8])
                response = entry['response']
                response.cached = True
                return response
        
        # Check disk cache
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    entry = pickle.load(f)
                
                if time.time() - entry['timestamp'] < self.ttl:
                    logger.debug("cache_hit_disk", key=key[:8])
                    response = entry['response']
                    response.cached = True
                    
                    # Update memory cache
                    self._memory_cache[key] = entry
                    
                    return response
            except Exception as e:
                logger.warning("cache_read_error", error=str(e))
        
        return None
    
    def set(self, prompt: str, model: str, config: Dict[str, Any], response: AIResponse):
        """Cache a response"""
        key = self._get_cache_key(prompt, model, config)
        
        entry = {
            'response': response,
            'timestamp': time.time()
        }
        
        # Update memory cache
        self._memory_cache[key] = entry
        
        # Write to disk
        cache_file = self.cache_dir / f"{key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(entry, f)
            logger.debug("cache_write", key=key[:8])
        except Exception as e:
            logger.warning("cache_write_error", error=str(e))
    
    def clear(self):
        """Clear all caches"""
        self._memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.info("cache_cleared")


class GeminiClient:
    """
    Unified Gemini SDK client with caching, retry logic, and prompt engineering.
    
    Features:
    - Direct SDK usage (no subprocess calls)
    - Response caching to reduce API calls
    - Retry logic with exponential backoff
    - Streaming support for real-time output
    - Prompt template management
    - Performance tracking
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[ToolingConfig] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        self.config = config or ToolingConfig()
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or self.config.ai_api_key
        
        if not self.api_key:
            raise ValueError("Gemini API key not provided. Set GEMINI_API_KEY environment variable.")
        
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)
        self.default_model = 'gemini-2.0-flash-001'
        
        # Initialize components
        self.cache = ResponseCache(ttl=cache_ttl) if cache_enabled else None
        self.templates = PromptTemplateEngine()
        
        logger.info("gemini_client_initialized", model=self.default_model, cache=cache_enabled)
    
    def _build_config(self, **kwargs) -> types.GenerateContentConfig:
        """Build generation config from kwargs"""
        config_dict = {
            'temperature': kwargs.get('temperature', 0.7),
            'max_output_tokens': kwargs.get('max_tokens', 2000),
            'top_p': kwargs.get('top_p', 0.95),
            'top_k': kwargs.get('top_k', 40),
        }
        
        if 'system_instruction' in kwargs:
            config_dict['system_instruction'] = kwargs['system_instruction']
        
        if 'stop_sequences' in kwargs:
            config_dict['stop_sequences'] = kwargs['stop_sequences']
        
        return types.GenerateContentConfig(**config_dict)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def generate_content_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        template: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs
    ) -> AIResponse:
        """
        Generate content asynchronously with retry logic.
        
        Args:
            prompt: The prompt text or template name
            model: Model to use (defaults to gemini-2.0-flash-001)
            template: Template name to render
            template_context: Context for template rendering
            use_cache: Whether to use caching
            **kwargs: Additional generation config
        
        Returns:
            AIResponse with generated text and metadata
        """
        start_time = time.time()
        model = model or self.default_model
        
        # Render template if provided
        if template:
            prompt = self.templates.render(template, **(template_context or {}))
        
        # Check cache
        if use_cache and self.cache:
            cached_response = self.cache.get(prompt, model, kwargs)
            if cached_response:
                return cached_response
        
        try:
            logger.debug("generating_content", model=model, prompt_length=len(prompt))
            
            config = self._build_config(**kwargs)
            
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            
            # Extract token counts if available
            usage = response.usage_metadata if hasattr(response, 'usage_metadata') else None
            
            ai_response = AIResponse(
                text=response.text,
                model=model,
                prompt_tokens=usage.prompt_token_count if usage else 0,
                response_tokens=usage.candidates_token_count if usage else 0,
                total_tokens=usage.total_token_count if usage else 0,
                cached=False,
                duration=time.time() - start_time
            )
            
            # Cache response
            if use_cache and self.cache:
                self.cache.set(prompt, model, kwargs, ai_response)
            
            logger.info(
                "content_generated",
                model=model,
                tokens=ai_response.total_tokens,
                duration=ai_response.duration,
                cached=False
            )
            
            return ai_response
            
        except Exception as e:
            logger.error("generation_error", error=str(e), model=model)
            raise
    
    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        template: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs
    ) -> AIResponse:
        """Synchronous wrapper for generate_content_async"""
        return asyncio.run(self.generate_content_async(
            prompt=prompt,
            model=model,
            template=template,
            template_context=template_context,
            use_cache=use_cache,
            **kwargs
        ))
    
    def generate_content_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        template: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream content generation for real-time output.
        
        Yields:
            Text chunks as they're generated
        """
        model = model or self.default_model
        
        # Render template if provided
        if template:
            prompt = self.templates.render(template, **(template_context or {}))
        
        logger.debug("streaming_content", model=model, prompt_length=len(prompt))
        
        config = self._build_config(**kwargs)
        
        for chunk in self.client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config
        ):
            yield chunk.text
    
    async def generate_content_stream_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        template: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Async version of streaming content generation"""
        model = model or self.default_model
        
        # Render template if provided
        if template:
            prompt = self.templates.render(template, **(template_context or {}))
        
        logger.debug("streaming_content_async", model=model, prompt_length=len(prompt))
        
        config = self._build_config(**kwargs)
        
        async for chunk in await self.client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config
        ):
            yield chunk.text
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in text"""
        model = model or self.default_model
        
        response = self.client.models.count_tokens(
            model=model,
            contents=text
        )
        
        return response.total_tokens
    
    def clear_cache(self):
        """Clear response cache"""
        if self.cache:
            self.cache.clear()


# Convenience functions for common operations
@lru_cache(maxsize=1)
def get_default_client() -> GeminiClient:
    """Get or create default client instance"""
    return GeminiClient()


async def generate_commit_message(
    files: List[str],
    diff: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Generate a commit message using the default client"""
    client = get_default_client()
    
    template_context = {
        'files': files,
        'diff': diff[:2000],  # Truncate large diffs
        **(context or {})
    }
    
    response = await client.generate_content_async(
        prompt="",  # Will be replaced by template
        template="commit_message.j2",
        template_context=template_context,
        temperature=0.7,
        max_tokens=200
    )
    
    return response.text.strip()


async def generate_changelog_entry(
    commits: List[Dict[str, Any]],
    package: str,
    version: str
) -> str:
    """Generate a changelog entry using the default client"""
    client = get_default_client()
    
    template_context = {
        'commits': commits[:50],  # Limit commits
        'package': package,
        'version': version
    }
    
    response = await client.generate_content_async(
        prompt="",  # Will be replaced by template
        template="changelog_entry.j2",
        template_context=template_context,
        temperature=0.5,
        max_tokens=1000
    )
    
    return response.text.strip()


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize client
        client = GeminiClient()
        
        # Test basic generation
        response = await client.generate_content_async(
            "Explain what a git commit message should contain in 2 sentences."
        )
        print(f"Response: {response.text}")
        print(f"Tokens: {response.total_tokens}")
        print(f"Cached: {response.cached}")
        
        # Test with template
        response = await client.generate_content_async(
            prompt="",
            template="commit_message.j2",
            template_context={
                'files': ['test.py', 'README.md'],
                'diff': '+ def new_function():\n+     pass'
            }
        )
        print(f"\nCommit message: {response.text}")
        
        # Test streaming
        print("\nStreaming response:")
        async for chunk in client.generate_content_stream_async(
            "Write a haiku about Python programming"
        ):
            print(chunk, end='', flush=True)
        print()
    
    asyncio.run(main()) 