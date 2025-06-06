"""
Async AI operations for improved performance with concurrent API calls.
"""
import asyncio
import httpx
from typing import List, Dict, Optional, Any, Tuple
import json
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential

from tooling.core.logging import get_logger
from tooling.core.base_config import get_config

logger = get_logger(__name__)


@dataclass
class AIResponse:
    """Response from AI API"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class AsyncAIClient:
    """Async AI client for concurrent API calls"""
    
    def __init__(self, config: Optional[Any] = None, max_concurrent: int = 5):
        self.config = config or get_config()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = httpx.Timeout(60.0, connect=5.0)
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_single(self, prompt: str, model: Optional[str] = None) -> AIResponse:
        """Generate response for a single prompt"""
        async with self._semaphore:
            if not self.client:
                self.client = httpx.AsyncClient(timeout=self.timeout)
            
            model = model or self.config.ai_model
            
            # Example with Google Gemini API
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.config.gemini_api_key:
                headers["x-goog-api-key"] = self.config.gemini_api_key
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048
                }
            }
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            
            try:
                response = await self.client.post(url, json=data, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                if "candidates" in result and result["candidates"]:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                    usage = result.get("usageMetadata")
                    
                    return AIResponse(
                        content=content,
                        model=model,
                        usage=usage
                    )
                else:
                    return AIResponse(
                        content="",
                        model=model,
                        error="No candidates in response"
                    )
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e}")
                return AIResponse(
                    content="",
                    model=model,
                    error=str(e)
                )
            except Exception as e:
                logger.error(f"API error: {e}")
                return AIResponse(
                    content="",
                    model=model,
                    error=str(e)
                )
    
    async def generate_batch(
        self,
        prompts: List[str],
        model: Optional[str] = None
    ) -> List[AIResponse]:
        """Generate responses for multiple prompts concurrently"""
        tasks = []
        for prompt in prompts:
            task = self.generate_single(prompt, model)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def analyze_code_parallel(
        self,
        files: Dict[str, str],
        analysis_prompt_template: str
    ) -> Dict[str, str]:
        """Analyze multiple code files in parallel"""
        prompts = []
        file_paths = []
        
        for file_path, content in files.items():
            prompt = analysis_prompt_template.format(
                file_path=file_path,
                content=content
            )
            prompts.append(prompt)
            file_paths.append(file_path)
        
        # Generate all analyses in parallel
        responses = await self.generate_batch(prompts)
        
        # Map results back to file paths
        results = {}
        for file_path, response in zip(file_paths, responses):
            if response.error:
                logger.warning(f"Failed to analyze {file_path}: {response.error}")
                results[file_path] = ""
            else:
                results[file_path] = response.content
        
        return results
    
    async def generate_with_fallback(
        self,
        prompt: str,
        models: List[str]
    ) -> AIResponse:
        """Try multiple models with fallback"""
        for model in models:
            response = await self.generate_single(prompt, model)
            if not response.error:
                return response
            
            logger.warning(f"Model {model} failed: {response.error}")
        
        # All models failed
        return AIResponse(
            content="",
            model=models[-1],
            error="All models failed"
        )


class AsyncCommitAnalyzer:
    """Analyze git commits using async AI"""
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or get_config()
        self.ai_client = AsyncAIClient(config)
    
    async def analyze_commits_batch(
        self,
        commit_batches: List[List[Dict[str, str]]],
        package_name: str
    ) -> List[str]:
        """Analyze multiple commit batches in parallel"""
        prompts = []
        
        for commits in commit_batches:
            prompt = self._build_commit_prompt(commits, package_name)
            prompts.append(prompt)
        
        async with self.ai_client as client:
            responses = await client.generate_batch(prompts)
        
        analyses = []
        for response in responses:
            if response.error:
                logger.error(f"Failed to analyze commits: {response.error}")
                analyses.append("")
            else:
                analyses.append(response.content)
        
        return analyses
    
    def _build_commit_prompt(
        self,
        commits: List[Dict[str, str]],
        package_name: str
    ) -> str:
        """Build prompt for commit analysis"""
        commit_list = "\n".join([
            f"- {c['hash'][:8]}: {c['subject']}"
            for c in commits
        ])
        
        return f"""Analyze these commits for {package_name} and provide a summary:

{commit_list}

Provide a concise summary of the changes and their impact."""


class ParallelChangelogGenerator:
    """Generate changelogs using parallel AI processing"""
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or get_config()
        self.ai_client = AsyncAIClient(config)
        self.commit_analyzer = AsyncCommitAnalyzer(config)
    
    async def generate_for_packages(
        self,
        packages: Dict[str, List[Dict[str, str]]]
    ) -> Dict[str, str]:
        """Generate changelogs for multiple packages in parallel"""
        tasks = []
        package_names = []
        
        async with self.ai_client as client:
            for package_name, commits in packages.items():
                task = self._generate_package_changelog(
                    package_name,
                    commits,
                    client
                )
                tasks.append(task)
                package_names.append(package_name)
            
            changelogs = await asyncio.gather(*tasks)
        
        return dict(zip(package_names, changelogs))
    
    async def _generate_package_changelog(
        self,
        package_name: str,
        commits: List[Dict[str, str]],
        client: AsyncAIClient
    ) -> str:
        """Generate changelog for a single package"""
        # Split commits into batches
        batch_size = 20
        commit_batches = [
            commits[i:i + batch_size]
            for i in range(0, len(commits), batch_size)
        ]
        
        # Analyze batches in parallel
        analyses = await self.commit_analyzer.analyze_commits_batch(
            commit_batches,
            package_name
        )
        
        # Combine analyses
        combined_analysis = "\n\n".join(analyses)
        
        # Generate final changelog
        prompt = f"""Based on this commit analysis for {package_name}, generate a changelog entry:

{combined_analysis}

Format the changelog according to Keep a Changelog standards with sections:
- Added
- Changed
- Fixed
- Removed

Be concise and focus on user-facing changes."""
        
        response = await client.generate_single(prompt)
        
        if response.error:
            logger.error(f"Failed to generate changelog: {response.error}")
            return ""
        
        return response.content


# Convenience functions for migration
async def analyze_code_async(
    files: Dict[str, str],
    prompt_template: str,
    config: Optional[Any] = None
) -> Dict[str, str]:
    """Analyze code files asynchronously"""
    async with AsyncAIClient(config) as client:
        return await client.analyze_code_parallel(files, prompt_template)


async def generate_changelogs_async(
    packages: Dict[str, List[Dict[str, str]]],
    config: Optional[Any] = None
) -> Dict[str, str]:
    """Generate changelogs for multiple packages asynchronously"""
    generator = ParallelChangelogGenerator(config)
    return await generator.generate_for_packages(packages) 