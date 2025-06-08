"""
Centralized AI operations for all CLI tools.
Provides a unified interface for AI interactions with both sync and async support.
Enhanced with model rotation, better error handling, and performance optimizations.
"""
import os
import asyncio
import httpx
import time
import json
from typing import Optional, Dict, List, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from functools import lru_cache

from tooling.core.base_config import get_config, ToolingConfig
from tooling.core.logging import get_logger
from tooling.utils.prompts import PromptTemplates

# Import AI client if available
try:
    from tooling.core import ai_client
    from tooling.core.ai_client import GeminiClient
    GEMINI_AVAILABLE = True
except ImportError:
    ai_client = None
    GeminiClient = None
    GEMINI_AVAILABLE = False

logger = get_logger(__name__)


class AIProvider(Enum):
    """Supported AI providers"""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


@dataclass
class AIResponse:
    """Standardized AI response"""
    content: str
    provider: AIProvider
    model: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    cached: bool = False
    duration: float = 0.0
    prompt_tokens: int = 0
    response_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used"""
        if self.tokens_used:
            return self.tokens_used
        return self.prompt_tokens + self.response_tokens


@dataclass 
class ModelConfig:
    """Configuration for a specific AI model"""
    name: str
    provider: AIProvider
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.95
    top_k: int = 40
    rate_limit: int = 10  # requests per minute
    priority: int = 0  # Higher priority models tried first
    enabled: bool = True
    fallback: bool = False  # Is this a fallback model


class ModelRotator:
    """Advanced model rotation with rate limiting and fallback"""
    
    DEFAULT_MODELS = [
        ModelConfig(
            name="gemini-2.5-pro-preview-06-05",
            provider=AIProvider.GEMINI,
            priority=100,
            rate_limit=5
        ),
        ModelConfig(
            name="gemini-2.5-pro-preview-05-06",
            provider=AIProvider.GEMINI,
            priority=90,
            rate_limit=5
        ),
        ModelConfig(
            name="gemini-2.5-flash-preview-04-17",
            provider=AIProvider.GEMINI,
            priority=80,
            rate_limit=10,
            temperature=0.5
        ),
        ModelConfig(
            name="gemini-2.0-flash",
            provider=AIProvider.GEMINI,
            priority=50,
            rate_limit=20,
            fallback=True
        )
    ]
    
    def __init__(self, models: Optional[List[ModelConfig]] = None):
        self.models = models or self.DEFAULT_MODELS
        self.models.sort(key=lambda x: x.priority, reverse=True)
        
        self.model_failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.failure_cooldown = 300  # 5 minutes
        self.request_counts: Dict[str, int] = {}
        self.request_windows: Dict[str, float] = {}
        
    def get_available_model(self) -> Optional[ModelConfig]:
        """Get next available model respecting rate limits and failures"""
        current_time = time.time()
        
        for model in self.models:
            if not model.enabled:
                continue
                
            # Check if model is in cooldown
            if model.name in self.last_failure_time:
                time_since_failure = current_time - self.last_failure_time[model.name]
                if time_since_failure < self.failure_cooldown:
                    continue
            
            # Check rate limit
            if self._is_rate_limited(model.name, model.rate_limit):
                continue
                
            return model
        
        # If all models rate limited, return fallback
        fallback_models = [m for m in self.models if m.fallback]
        return fallback_models[0] if fallback_models else None
    
    def _is_rate_limited(self, model_name: str, limit: int) -> bool:
        """Check if model is rate limited"""
        current_time = time.time()
        window_start = self.request_windows.get(model_name, 0)
        
        # Reset window if expired
        if current_time - window_start > 60:
            self.request_counts[model_name] = 0
            self.request_windows[model_name] = current_time
            return False
        
        # Check count
        count = self.request_counts.get(model_name, 0)
        return count >= limit
    
    def record_request(self, model_name: str):
        """Record a request for rate limiting"""
        self.request_counts[model_name] = self.request_counts.get(model_name, 0) + 1
    
    def record_failure(self, model_name: str, error: Exception):
        """Record a model failure"""
        self.model_failures[model_name] = self.model_failures.get(model_name, 0) + 1
        self.last_failure_time[model_name] = time.time()
        
        error_str = str(error).lower()
        if any(term in error_str for term in ['rate limit', 'quota', 'too many']):
            logger.warning(f"Model {model_name} hit rate limit")
        else:
            logger.warning(f"Model {model_name} failed: {error}")


class AsyncAIClient:
    """Enhanced async AI client with model rotation and batching"""
    
    def __init__(self, config: Optional[ToolingConfig] = None, max_concurrent: int = 5):
        self.config = config or get_config()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = httpx.Timeout(60.0, connect=5.0)
        self.model_rotator = ModelRotator()
        self._clients: Dict[str, Any] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AI clients for each provider"""
        if GEMINI_AVAILABLE and self.config.gemini_api_key:
            # Initialize Gemini clients for each model
            for model_config in self.model_rotator.models:
                if model_config.provider == AIProvider.GEMINI:
                    try:
                        client = GeminiClient(
                            api_key=self.config.gemini_api_key,
                            config=self.config,
                            cache_enabled=True
                        )
                        client.default_model = model_config.name
                        self._clients[model_config.name] = client
                        logger.debug(f"Initialized {model_config.name}")
                    except Exception as e:
                        logger.warning(f"Failed to initialize {model_config.name}: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Cleanup if needed
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def generate_single(self, prompt: str, 
                            model: Optional[str] = None,
                            **kwargs) -> AIResponse:
        """Generate response for a single prompt with automatic fallback"""
        start_time = time.time()
        
        async with self._semaphore:
            # Get available model
            model_config = self.model_rotator.get_available_model()
            if not model_config:
                return AIResponse(
                    content="",
                    provider=AIProvider.LOCAL,
                    model="none",
                    error="All models rate limited"
                )
            
            model = model or model_config.name
            client = self._clients.get(model)
            
            if not client:
                return AIResponse(
                    content="",
                    provider=model_config.provider,
                    model=model,
                    error="Client not initialized"
                )
            
            try:
                # Record request
                self.model_rotator.record_request(model)
                
                # Merge kwargs with model config
                generation_kwargs = {
                    'temperature': kwargs.get('temperature', model_config.temperature),
                    'max_tokens': kwargs.get('max_tokens', model_config.max_tokens),
                    'top_p': kwargs.get('top_p', model_config.top_p),
                    'top_k': kwargs.get('top_k', model_config.top_k),
                }
                
                # Generate response
                response = await client.generate_content_async(
                    prompt=prompt,
                    model=model,
                    **generation_kwargs
                )
                
                return AIResponse(
                    content=response.text,
                    provider=model_config.provider,
                    model=model,
                    prompt_tokens=response.prompt_tokens,
                    response_tokens=response.response_tokens,
                    tokens_used=response.total_tokens,
                    cached=response.cached,
                    duration=time.time() - start_time
                )
                
            except Exception as e:
                self.model_rotator.record_failure(model, e)
                
                # Try fallback model
                fallback_config = next(
                    (m for m in self.model_rotator.models if m.fallback), 
                    None
                )
                
                if fallback_config and fallback_config.name != model:
                    logger.info(f"Falling back from {model} to {fallback_config.name}")
                    return await self.generate_single(
                        prompt, 
                        model=fallback_config.name, 
                        **kwargs
                    )
                
                return AIResponse(
                    content="",
                    provider=model_config.provider,
                    model=model,
                    error=str(e),
                    duration=time.time() - start_time
                )
    
    async def generate_batch(self, prompts: List[str], 
                           model: Optional[str] = None,
                           batch_size: int = 5,
                           **kwargs) -> List[AIResponse]:
        """Generate responses for multiple prompts with batching"""
        responses = []
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i+batch_size]
            
            # Create tasks for batch
            tasks = [
                self.generate_single(prompt, model, **kwargs)
                for prompt in batch
            ]
            
            # Execute batch
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for response in batch_responses:
                if isinstance(response, Exception):
                    responses.append(AIResponse(
                        content="",
                        provider=AIProvider.LOCAL,
                        model=model or "unknown",
                        error=str(response)
                    ))
                else:
                    responses.append(response)
            
            # Small delay between batches
            if i + batch_size < len(prompts):
                await asyncio.sleep(0.5)
        
        return responses
    
    async def generate_streaming(self, prompt: str,
                               model: Optional[str] = None,
                               **kwargs):
        """Generate streaming response"""
        model_config = self.model_rotator.get_available_model()
        if not model_config:
            yield "Error: All models rate limited"
            return
        
        model = model or model_config.name
        client = self._clients.get(model)
        
        if not client:
            yield "Error: Client not initialized"
            return
        
        try:
            self.model_rotator.record_request(model)
            
            async for chunk in client.generate_content_stream_async(
                prompt=prompt,
                model=model,
                **kwargs
            ):
                yield chunk
                
        except Exception as e:
            self.model_rotator.record_failure(model, e)
            yield f"Error: {str(e)}"
    
    def get_model_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all models"""
        status = {}
        current_time = time.time()
        
        for model in self.model_rotator.models:
            model_status = {
                'enabled': model.enabled,
                'priority': model.priority,
                'rate_limit': model.rate_limit,
                'current_requests': self.model_rotator.request_counts.get(model.name, 0),
                'failures': self.model_rotator.model_failures.get(model.name, 0),
                'status': 'available'
            }
            
            # Check if in cooldown
            if model.name in self.model_rotator.last_failure_time:
                time_since_failure = current_time - self.model_rotator.last_failure_time[model.name]
                if time_since_failure < self.model_rotator.failure_cooldown:
                    model_status['status'] = f'cooldown ({self.model_rotator.failure_cooldown - time_since_failure:.0f}s left)'
            
            # Check if rate limited
            elif self.model_rotator._is_rate_limited(model.name, model.rate_limit):
                model_status['status'] = 'rate_limited'
            
            status[model.name] = model_status
        
        return status


class AIOperations:
    """Enhanced centralized AI operations"""
    
    def __init__(self, config: Optional[ToolingConfig] = None):
        self.config = config or get_config()
        self.logger = logger
        self._client = None
        self._async_client = None
    
    @property
    def client(self):
        """Lazy load AI client"""
        if self._client is None and GEMINI_AVAILABLE:
            self._client = GeminiClient(
                api_key=self.config.gemini_api_key,
                config=self.config
            )
        return self._client
    
    @property
    def async_client(self) -> AsyncAIClient:
        """Lazy load async AI client"""
        if self._async_client is None:
            self._async_client = AsyncAIClient(self.config)
        return self._async_client
    
    def is_available(self) -> bool:
        """Check if AI functionality is available"""
        return GEMINI_AVAILABLE and bool(self.config.gemini_api_key)
    
    # Synchronous methods
    def generate_commit_message(self,
                              diff: str,
                              context: Optional[Dict[str, Any]] = None,
                              style: str = "conventional") -> Optional[AIResponse]:
        """Generate a commit message from diff"""
        if not self.is_available():
            return None
            
        return asyncio.run(self.generate_commit_message_async(diff, context, style))
    
    def analyze_code_changes(self,
                           files: List[Dict[str, str]],
                           purpose: str = "changelog") -> Optional[AIResponse]:
        """Analyze code changes for various purposes"""
        if not self.is_available():
            return None
            
        return asyncio.run(self.analyze_code_changes_async(files, purpose))
    
    # Async methods
    async def generate_commit_message_async(self,
                                          diff: str,
                                          context: Optional[Dict[str, Any]] = None,
                                          style: str = "conventional") -> Optional[AIResponse]:
        """Async version of generate_commit_message"""
        try:
            if not self.is_available():
                return None
            
            # Build prompt
            prompt = PromptTemplates.get_commit_prompt(
                diff,
                enhanced=context and context.get('detailed', False),
                **(context or {})
            )
            
            # Add style instructions
            if style == "conventional":
                prompt += "\n\nUse conventional commit format (type(scope): description)"
            elif style == "detailed":
                prompt += "\n\nInclude a detailed body explaining the changes"
            
            # Generate
            async with self.async_client as client:
                response = await client.generate_single(prompt)
            
            if response.error:
                logger.error(f"AI generation failed: {response.error}")
                return None
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate commit message: {e}")
            return None
    
    async def analyze_code_changes_async(self,
                                       files: List[Dict[str, str]],
                                       purpose: str = "changelog") -> Optional[AIResponse]:
        """Async version of analyze_code_changes"""
        try:
            if not self.is_available():
                return None
            
            # Build analysis prompt
            if purpose == "changelog":
                prompt = self._build_changelog_analysis_prompt(files)
            elif purpose == "review":
                prompt = self._build_code_review_prompt(files)
            elif purpose == "summary":
                prompt = self._build_summary_prompt(files)
            else:
                raise ValueError(f"Unknown analysis purpose: {purpose}")
            
            # Generate
            async with self.async_client as client:
                response = await client.generate_single(prompt)
            
            if response.error:
                logger.error(f"AI analysis failed: {response.error}")
                return None
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to analyze code changes: {e}")
            return None
    
    async def analyze_code_parallel(self,
                                  files: Dict[str, str],
                                  analysis_prompt_template: str,
                                  batch_size: int = 5) -> Dict[str, str]:
        """Analyze multiple code files in parallel"""
        prompts = []
        file_paths = []
        
        for file_path, content in files.items():
            prompt = analysis_prompt_template.format(
                file_path=file_path,
                content=content[:3000]  # Limit content size
            )
            prompts.append(prompt)
            file_paths.append(file_path)
        
        # Generate analyses in batches
        async with self.async_client as client:
            responses = await client.generate_batch(
                prompts, 
                batch_size=batch_size
            )
        
        # Map results
        results = {}
        for file_path, response in zip(file_paths, responses):
            if response.error:
                logger.warning(f"Failed to analyze {file_path}: {response.error}")
                results[file_path] = ""
            else:
                results[file_path] = response.content
        
        return results
    
    async def generate_changelogs_parallel(self,
                                         packages: Dict[str, List[Dict[str, str]]],
                                         batch_size: int = 3) -> Dict[str, str]:
        """Generate changelogs for multiple packages in parallel"""
        prompts = []
        package_names = []
        
        for package_name, commits in packages.items():
            # Build prompt
            commit_list = "\n".join([
                f"- {c['hash'][:8]}: {c['subject']}"
                for c in commits[:50]
            ])
            
            prompt = f"""Analyze these commits for {package_name} and generate a changelog entry:

{commit_list}

Format the changelog according to Keep a Changelog standards with sections:
- Added
- Changed  
- Fixed
- Removed

Be concise and focus on user-facing changes."""
            
            prompts.append(prompt)
            package_names.append(package_name)
        
        # Generate in batches
        async with self.async_client as client:
            responses = await client.generate_batch(
                prompts,
                batch_size=batch_size
            )
        
        # Build results
        results = {}
        for package_name, response in zip(package_names, responses):
            if response.error:
                logger.error(f"Failed to generate changelog for {package_name}: {response.error}")
                results[package_name] = ""
            else:
                results[package_name] = response.content
        
        return results
    
    async def analyze_contributors_batch(self,
                                       contributors: List[Dict[str, Any]],
                                       template: str = "contributor_analysis.j2",
                                       batch_size: int = 5) -> List[Dict[str, Any]]:
        """Analyze multiple contributors in parallel"""
        prompts = []
        
        for contributor in contributors:
            # Use template or build prompt
            if template and self.client:
                prompt = self.client.templates.render(
                    template,
                    contributor=contributor
                )
            else:
                prompt = self._build_contributor_analysis_prompt(contributor)
            
            prompts.append(prompt)
        
        # Process in batches
        async with self.async_client as client:
            responses = await client.generate_batch(
                prompts,
                batch_size=batch_size,
                temperature=0.3  # Lower temp for consistency
            )
        
        # Parse responses
        results = []
        for contributor, response in zip(contributors, responses):
            if response.error:
                logger.warning(f"Failed to analyze {contributor.get('username')}: {response.error}")
                results.append({
                    'username': contributor.get('username'),
                    'analysis': 'Analysis failed',
                    'error': response.error
                })
            else:
                try:
                    analysis_data = json.loads(response.content)
                    analysis_data['username'] = contributor.get('username')
                    results.append(analysis_data)
                except json.JSONDecodeError:
                    results.append({
                        'username': contributor.get('username'),
                        'analysis': response.content,
                        'raw_response': True
                    })
        
        return results
    
    def _build_changelog_analysis_prompt(self, files: List[Dict[str, str]]) -> str:
        """Build prompt for changelog analysis"""
        prompt = "Analyze these code changes and suggest changelog entries:\n\n"
        
        for file_info in files[:10]:
            prompt += f"File: {file_info['path']}\n"
            prompt += f"Changes:\n{file_info.get('diff', 'No diff available')[:1000]}\n\n"
        
        prompt += """
Categorize changes into:
- Added: new features
- Changed: changes in existing functionality
- Deprecated: soon-to-be removed features
- Removed: now removed features
- Fixed: bug fixes
- Security: security fixes

Be concise and user-focused.
"""
        return prompt
    
    def _build_code_review_prompt(self, files: List[Dict[str, str]]) -> str:
        """Build prompt for code review"""
        prompt = "Review these code changes:\n\n"
        
        for file_info in files[:5]:
            prompt += f"File: {file_info['path']}\n"
            prompt += f"```{file_info.get('language', '')}\n"
            prompt += f"{file_info.get('diff', 'No diff available')[:1500]}\n"
            prompt += "```\n\n"
        
        prompt += """
Provide feedback on:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance considerations
4. Security concerns
5. Suggestions for improvement
"""
        return prompt
    
    def _build_summary_prompt(self, files: List[Dict[str, str]]) -> str:
        """Build prompt for summary generation"""
        prompt = f"Summarize the changes in these {len(files)} files:\n\n"
        
        for file_info in files[:20]:
            prompt += f"- {file_info['path']}: {file_info.get('change_type', 'modified')}\n"
        
        prompt += "\nProvide a concise summary of what was changed and why."
        return prompt
    
    def _build_contributor_analysis_prompt(self, contributor: Dict[str, Any]) -> str:
        """Build prompt for contributor analysis"""
        return f"""Analyze this GitHub contributor:

Username: {contributor.get('username')}
Total Commits: {contributor.get('total_commits', 0)}
Active Repositories: {contributor.get('repositories', [])}
Primary Languages: {contributor.get('languages', [])}

Provide a JSON response with:
- Technical skill assessment
- Contribution patterns
- Areas of expertise
- Recommended improvement areas
"""

    def get_status(self) -> Dict[str, Any]:
        """Get AI operations status"""
        status = {
            'available': self.is_available(),
            'provider': 'Gemini' if self.is_available() else 'None',
            'models': {}
        }
        
        if self._async_client:
            status['models'] = self._async_client.get_model_status()
        
        return status


# Singleton instance
_ai_ops: Optional[AIOperations] = None

def get_ai_operations(config: Optional[ToolingConfig] = None) -> AIOperations:
    """Get or create AI operations instance"""
    global _ai_ops
    if _ai_ops is None:
        _ai_ops = AIOperations(config)
    return _ai_ops


# Convenience functions
async def analyze_code_async(files: Dict[str, str],
                           prompt_template: str,
                           config: Optional[ToolingConfig] = None,
                           batch_size: int = 5) -> Dict[str, str]:
    """Analyze code files asynchronously"""
    ai_ops = get_ai_operations(config)
    return await ai_ops.analyze_code_parallel(files, prompt_template, batch_size)


async def generate_changelogs_async(packages: Dict[str, List[Dict[str, str]]],
                                  config: Optional[ToolingConfig] = None,
                                  batch_size: int = 3) -> Dict[str, str]:
    """Generate changelogs for multiple packages asynchronously"""
    ai_ops = get_ai_operations(config)
    return await ai_ops.generate_changelogs_parallel(packages, batch_size)


async def analyze_contributors_async(contributors: List[Dict[str, Any]],
                                   config: Optional[ToolingConfig] = None,
                                   batch_size: int = 5) -> List[Dict[str, Any]]:
    """Analyze multiple contributors asynchronously"""
    ai_ops = get_ai_operations(config)
    return await ai_ops.analyze_contributors_batch(contributors, batch_size=batch_size)