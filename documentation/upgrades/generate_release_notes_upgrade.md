# Upgrade Plan: generate_release_notes.py

## Overview
Generates polished release notes from changelog files using AI. Currently uses subprocess for Gemini CLI and manual markdown generation.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: AI summarization, GitHub release formatting, multi-package support
- **Limitations**: Synchronous AI calls, manual markdown building

## Recommended Upgrades

### 1. Configuration Management
```python
# Use Pydantic for structured config
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, List
from pathlib import Path

class ReleaseConfig(BaseModel):
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+')
    artifact_version: str
    output_path: Path
    is_tag_release: bool = False
    pr_number: Optional[int] = Field(None, ge=1)
    pr_url: Optional[HttpUrl] = None
    commit_sha: Optional[str] = Field(None, min_length=7)
    package_names: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            Path: str,
            HttpUrl: str
        }

class AIConfig(BaseModel):
    model: str = "gemini-1.5-flash"
    temperature: float = Field(0.7, ge=0, le=1)
    max_tokens: int = Field(2000, ge=100)
    api_key: str = Field(..., env='GEMINI_API_KEY')
```

### 2. Template-Based Generation
```python
# Use Jinja2 for flexible templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

class ReleaseNotesTemplateEngine:
    def __init__(self, template_dir: Path = Path('templates')):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['markdown_escape'] = self.markdown_escape
        self.env.filters['github_link'] = self.github_link
    
    def render_release_notes(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """Render release notes from template"""
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    @staticmethod
    def markdown_escape(text: str) -> str:
        """Escape special markdown characters"""
        chars_to_escape = ['*', '_', '[', ']', '(', ')', '#', '+', '-', '!']
        for char in chars_to_escape:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def github_link(text: str, url: str) -> str:
        """Create GitHub-style link"""
        return f"[{text}]({url})"
```

### 3. Async AI Integration
```python
# Direct API calls instead of subprocess
import aiohttp
from typing import AsyncIterator
import backoff

class AsyncGeminiClient:
    def __init__(self, api_key: str, config: AIConfig):
        self.api_key = api_key
        self.config = config
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
    @backoff.on_exception(
        backoff.expo,
        aiohttp.ClientError,
        max_tries=3
    )
    async def generate_summary(
        self,
        changelogs: Dict[str, str],
        stream: bool = False
    ) -> Union[str, AsyncIterator[str]]:
        """Generate AI summary with retry logic"""
        prompt = self._build_prompt(changelogs)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {
                    'temperature': self.config.temperature,
                    'maxOutputTokens': self.config.max_tokens
                }
            }
            
            if stream:
                return self._stream_response(session, headers, payload)
            else:
                async with session.post(
                    f"{self.base_url}/models/{self.config.model}:generateContent",
                    headers=headers,
                    json=payload
                ) as response:
                    data = await response.json()
                    return data['candidates'][0]['content']['parts'][0]['text']
    
    async def _stream_response(
        self,
        session: aiohttp.ClientSession,
        headers: Dict,
        payload: Dict
    ) -> AsyncIterator[str]:
        """Stream response for real-time display"""
        async with session.post(
            f"{self.base_url}/models/{self.config.model}:streamGenerateContent",
            headers=headers,
            json=payload
        ) as response:
            async for line in response.content:
                if line:
                    yield line.decode('utf-8')
```

### 4. Markdown Builder
```python
# Structured markdown generation
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class MarkdownSection:
    title: str
    content: str
    level: int = 2
    
class MarkdownBuilder:
    def __init__(self):
        self.sections: List[MarkdownSection] = []
        self.toc_enabled = True
    
    def add_header(self, text: str, level: int = 1) -> 'MarkdownBuilder':
        """Add header with automatic anchor"""
        anchor = self._create_anchor(text)
        header = f"{'#' * level} {text} {{#{anchor}}}"
        self.sections.append(MarkdownSection(text, header, level))
        return self
    
    def add_section(self, title: str, content: str, level: int = 2) -> 'MarkdownBuilder':
        """Add section with title and content"""
        self.sections.append(MarkdownSection(title, content, level))
        return self
    
    def add_table(self, headers: List[str], rows: List[List[str]]) -> 'MarkdownBuilder':
        """Add markdown table"""
        table_lines = []
        
        # Headers
        table_lines.append('| ' + ' | '.join(headers) + ' |')
        table_lines.append('|' + '|'.join(['-' * (len(h) + 2) for h in headers]) + '|')
        
        # Rows
        for row in rows:
            table_lines.append('| ' + ' | '.join(row) + ' |')
        
        self.sections.append(MarkdownSection('', '\n'.join(table_lines), 0))
        return self
    
    def add_collapsible(
        self,
        summary: str,
        content: str
    ) -> 'MarkdownBuilder':
        """Add collapsible section"""
        collapsible = f"""<details>
<summary>{summary}</summary>

{content}

</details>"""
        self.sections.append(MarkdownSection('', collapsible, 0))
        return self
    
    def generate_toc(self) -> str:
        """Generate table of contents"""
        toc_lines = ["## Table of Contents\n"]
        
        for section in self.sections:
            if section.level > 0 and section.level <= 3:
                indent = '  ' * (section.level - 1)
                anchor = self._create_anchor(section.title)
                toc_lines.append(f"{indent}- [{section.title}](#{anchor})")
        
        return '\n'.join(toc_lines)
    
    def build(self) -> str:
        """Build final markdown"""
        parts = []
        
        if self.toc_enabled and len(self.sections) > 3:
            parts.append(self.generate_toc())
            parts.append('')
        
        for section in self.sections:
            if section.level > 0:
                parts.append(f"{'#' * section.level} {section.title}")
            if section.content:
                parts.append(section.content)
            parts.append('')
        
        return '\n'.join(parts).strip()
    
    @staticmethod
    def _create_anchor(text: str) -> str:
        """Create GitHub-compatible anchor"""
        return text.lower().replace(' ', '-').replace('.', '')
```

### 5. Changelog Analysis
```python
# Enhanced changelog parsing and analysis
from typing import List, Dict, Tuple
import re
from collections import defaultdict

class ChangelogAnalyzer:
    def __init__(self):
        self.patterns = {
            'breaking': re.compile(r'BREAKING|breaking change', re.I),
            'feature': re.compile(r'^[\s*-]*(?:feat|feature|add|new):', re.I | re.M),
            'fix': re.compile(r'^[\s*-]*(?:fix|bug|patch):', re.I | re.M),
            'performance': re.compile(r'^[\s*-]*(?:perf|performance):', re.I | re.M),
            'dependency': re.compile(r'(?:update|upgrade|bump|dependency)', re.I)
        }
    
    def analyze_changelog(self, content: str) -> Dict[str, Any]:
        """Analyze changelog content for patterns"""
        analysis = {
            'has_breaking_changes': bool(self.patterns['breaking'].search(content)),
            'feature_count': len(self.patterns['feature'].findall(content)),
            'fix_count': len(self.patterns['fix'].findall(content)),
            'performance_improvements': len(self.patterns['performance'].findall(content)),
            'dependency_updates': len(self.patterns['dependency'].findall(content)),
            'categories': self._categorize_changes(content)
        }
        
        return analysis
    
    def _categorize_changes(self, content: str) -> Dict[str, List[str]]:
        """Categorize changes by type"""
        categories = defaultdict(list)
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith(('- ', '* ')):
                for category, pattern in self.patterns.items():
                    if pattern.search(line):
                        categories[category].append(line[2:])  # Remove bullet
                        break
                else:
                    categories['other'].append(line[2:])
        
        return dict(categories)
    
    def generate_statistics(
        self,
        changelogs: Dict[str, str]
    ) -> Dict[str, Any]:
        """Generate statistics across all changelogs"""
        stats = {
            'total_changes': 0,
            'by_package': {},
            'by_type': defaultdict(int)
        }
        
        for package, content in changelogs.items():
            analysis = self.analyze_changelog(content)
            
            package_total = sum([
                analysis['feature_count'],
                analysis['fix_count'],
                analysis['performance_improvements']
            ])
            
            stats['total_changes'] += package_total
            stats['by_package'][package] = analysis
            
            for category, items in analysis['categories'].items():
                stats['by_type'][category] += len(items)
        
        return stats
```

### 6. Download Link Generator
```python
# Smart download link generation
from typing import List, Dict
from urllib.parse import urljoin

class DownloadLinkGenerator:
    def __init__(self, repo_url: str, cdn_url: Optional[str] = None):
        self.repo_url = repo_url.rstrip('/')
        self.cdn_url = cdn_url
        
    def generate_artifact_links(
        self,
        version: str,
        artifacts: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """Generate download links for artifacts"""
        links = {}
        
        for artifact in artifacts:
            name = artifact['name']
            path = artifact['path']
            
            # Direct GitHub release link
            github_url = f"{self.repo_url}/releases/download/v{version}/{name}"
            
            # CDN link if available
            cdn_url = None
            if self.cdn_url:
                cdn_url = urljoin(self.cdn_url, f"{version}/{name}")
            
            links[name] = {
                'github': github_url,
                'cdn': cdn_url,
                'size': artifact.get('size', 'Unknown'),
                'checksum': artifact.get('checksum', '')
            }
        
        return links
    
    def format_download_section(
        self,
        links: Dict[str, Dict[str, str]]
    ) -> str:
        """Format download section with multiple mirrors"""
        lines = ["## Downloads\n"]
        
        for artifact, urls in links.items():
            lines.append(f"### {artifact}")
            
            # Primary download
            lines.append(f"- [Download from GitHub]({urls['github']})")
            
            # CDN mirror if available
            if urls['cdn']:
                lines.append(f"- [Download from CDN]({urls['cdn']}) (faster)")
            
            # Metadata
            if urls['size'] != 'Unknown':
                lines.append(f"- Size: {urls['size']}")
            if urls['checksum']:
                lines.append(f"- SHA256: `{urls['checksum']}`")
            
            lines.append("")
        
        return '\n'.join(lines)
```

## Dependencies to Add
```toml
[project.dependencies]
jinja2 = "^3.1.2"
aiohttp = "^3.9.0"
pydantic = "^2.5.0"
markdown = "^3.5.1"
backoff = "^2.2.1"
rich = "^13.7.0"
python-frontmatter = "^1.0.1"
```

## Migration Strategy
1. Create template system alongside existing code
2. Add async AI client with fallback to subprocess
3. Implement structured markdown builder
4. Add comprehensive testing
5. Gradually migrate to new components

## Expected Benefits
- **Flexibility**: Template-based generation
- **Performance**: Async AI calls (2-3x faster)
- **Reliability**: Retry logic and error handling
- **Maintainability**: Structured code with clear separation
- **Features**: Advanced markdown formatting options