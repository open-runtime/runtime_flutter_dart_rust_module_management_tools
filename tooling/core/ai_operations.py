"""
Centralized AI operations for all CLI tools.
Provides a unified interface for AI interactions.
"""
import os
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from tooling.core.base_config import get_config
from tooling.core.logging import get_logger
from tooling.utils.prompts import PromptTemplates

# Import AI client if available
try:
    from tooling.core import ai_client
except ImportError:
    ai_client = None

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


class AIOperations:
    """Centralized AI operations for all tools"""
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or get_config()
        self.logger = logger
        self._client = None
    
    @property
    def client(self):
        """Lazy load AI client"""
        if self._client is None and ai_client:
            self._client = ai_client.get_client(self.config)
        return self._client
    
    def is_available(self) -> bool:
        """Check if AI functionality is available"""
        return ai_client is not None and self.config.check_api_key()
    
    def generate_commit_message(
        self,
        diff: str,
        context: Optional[Dict[str, Any]] = None,
        style: str = "conventional"
    ) -> Optional[AIResponse]:
        """Generate a commit message from diff"""
        try:
            if not self.is_available():
                logger.warning("AI not available, using fallback")
                return None
            
            # Build prompt
            if context and context.get('detailed'):
                prompt = PromptTemplates.get_commit_prompt(
                    diff,
                    enhanced=True,
                    **context
                )
            else:
                prompt = PromptTemplates.get_commit_prompt(diff)
            
            # Add style instructions
            if style == "conventional":
                prompt += "\n\nUse conventional commit format (type(scope): description)"
            elif style == "detailed":
                prompt += "\n\nInclude a detailed body explaining the changes"
            
            # Generate
            response = self.client.generate(prompt)
            
            return AIResponse(
                content=self._clean_response(response),
                provider=self._detect_provider(),
                model=self.config.get_model()
            )
            
        except Exception as e:
            logger.error(f"Failed to generate commit message: {e}")
            return None
    
    def analyze_code_changes(
        self,
        files: List[Dict[str, str]],
        purpose: str = "changelog"
    ) -> Optional[AIResponse]:
        """Analyze code changes for various purposes"""
        try:
            if not self.is_available():
                return None
            
            # Build analysis prompt based on purpose
            if purpose == "changelog":
                prompt = self._build_changelog_analysis_prompt(files)
            elif purpose == "review":
                prompt = self._build_code_review_prompt(files)
            elif purpose == "summary":
                prompt = self._build_summary_prompt(files)
            else:
                raise ValueError(f"Unknown analysis purpose: {purpose}")
            
            # Generate
            response = self.client.generate(prompt)
            
            return AIResponse(
                content=self._clean_response(response),
                provider=self._detect_provider(),
                model=self.config.get_model()
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze code changes: {e}")
            return None
    
    def generate_release_notes(
        self,
        changelog_content: str,
        version: str,
        stats: Optional[Dict[str, Any]] = None
    ) -> Optional[AIResponse]:
        """Generate release notes from changelog"""
        try:
            if not self.is_available():
                return None
            
            prompt = PromptTemplates.get_release_notes_prompt(
                version=version,
                changelog=changelog_content,
                **(stats or {})
            )
            
            response = self.client.generate(prompt)
            
            return AIResponse(
                content=self._clean_response(response),
                provider=self._detect_provider(),
                model=self.config.get_model()
            )
            
        except Exception as e:
            logger.error(f"Failed to generate release notes: {e}")
            return None
    
    def generate_pr_description(
        self,
        title: str,
        changes: str,
        commits: List[str],
        **kwargs
    ) -> Optional[AIResponse]:
        """Generate PR description"""
        try:
            if not self.is_available():
                return None
            
            prompt = PromptTemplates.get_pr_description_prompt(
                title=title,
                branch=kwargs.get('branch', 'feature'),
                changes=changes,
                commits='\n'.join(commits),
                target_branch=kwargs.get('target_branch', 'main')
            )
            
            response = self.client.generate(prompt)
            
            return AIResponse(
                content=self._clean_response(response),
                provider=self._detect_provider(),
                model=self.config.get_model()
            )
            
        except Exception as e:
            logger.error(f"Failed to generate PR description: {e}")
            return None
    
    def analyze_commits_for_changelog(self, commits: List[str]) -> Optional[AIResponse]:
        """Analyze commits and suggest changelog entries"""
        try:
            if not self.is_available():
                return None
            
            prompt = f"""Analyze these commits and suggest changelog entries.

Commits:
{chr(10).join(f'- {commit}' for commit in commits[:50])}

For each commit, determine:
1. The appropriate changelog section (Added, Changed, Fixed, etc.)
2. A user-friendly description
3. Whether it's a breaking change

Group similar changes together and write clear, concise entries suitable for a CHANGELOG.md file.
Format the response as a structured list."""
            
            response = self.client.generate(prompt)
            
            ai_response = AIResponse(
                content=self._clean_response(response),
                provider=self._detect_provider(),
                model=self.config.get_model()
            )
            
            # In a real implementation, we would parse the response and create ChangelogEntry objects
            # For now, we'll just add an empty entries list
            ai_response.entries = []  # Placeholder for parsed entries
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to analyze commits for changelog: {e}")
            return None
    
    def _build_changelog_analysis_prompt(self, files: List[Dict[str, str]]) -> str:
        """Build prompt for changelog analysis"""
        prompt = "Analyze these code changes and suggest changelog entries:\n\n"
        
        for file_info in files[:10]:  # Limit to 10 files
            prompt += f"File: {file_info['path']}\n"
            prompt += f"Changes:\n{file_info.get('diff', 'No diff available')}\n\n"
        
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
        
        for file_info in files[:5]:  # Limit to 5 files for review
            prompt += f"File: {file_info['path']}\n"
            prompt += f"```{file_info.get('language', '')}\n"
            prompt += f"{file_info.get('diff', 'No diff available')}\n"
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
        
        for file_info in files:
            prompt += f"- {file_info['path']}: {file_info.get('change_type', 'modified')}\n"
        
        prompt += "\nProvide a concise summary of what was changed and why."
        return prompt
    
    def _clean_response(self, response: str) -> str:
        """Clean up AI response"""
        if not response:
            return ""
        
        # Remove code block markers if present
        response = response.strip()
        if response.startswith('```') and response.endswith('```'):
            lines = response.split('\n')
            return '\n'.join(lines[1:-1])
        
        return response
    
    def _detect_provider(self) -> AIProvider:
        """Detect which AI provider is being used"""
        if not self.client:
            return AIProvider.LOCAL
        
        # This would need to be implemented based on the actual client
        # For now, assume Gemini if API key is set
        if os.environ.get('GEMINI_API_KEY'):
            return AIProvider.GEMINI
        elif os.environ.get('OPENAI_API_KEY'):
            return AIProvider.OPENAI
        elif os.environ.get('ANTHROPIC_API_KEY'):
            return AIProvider.ANTHROPIC
        else:
            return AIProvider.LOCAL


# Singleton instance for easy access
_ai_ops = None

def get_ai_operations(config: Optional[Any] = None) -> AIOperations:
    """Get or create AI operations instance"""
    global _ai_ops
    if _ai_ops is None:
        _ai_ops = AIOperations(config)
    return _ai_ops 