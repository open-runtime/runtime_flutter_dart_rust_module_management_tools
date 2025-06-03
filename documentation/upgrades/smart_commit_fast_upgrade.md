# Upgrade Plan: smart_commit_fast.py

## Overview
Ultra-fast AI-powered commit message generator with advanced context analysis. Currently uses subprocess for AI calls and manual parsing.

## Current State
- **Dependencies**: Standard library + concurrent.futures
- **Performance**: 2-3s quick mode, 15-20s max mode
- **Key Features**: Multi-stage analysis, symbol extraction, parallel processing

## Recommended Upgrades

### 1. Async AI Integration
```python
# Replace subprocess gemini-cli with async HTTP
import aiohttp
from aiohttp import ClientTimeout
import backoff

class AsyncGeminiClient:
    def __init__(self, api_key: str):
        self.session = None
        self.api_key = api_key
        
    async def generate(self, prompt: str) -> str:
        timeout = ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Direct API call instead of subprocess
            return await self._call_api(prompt)
```

### 2. Advanced Code Parsing
```python
# Replace regex-based symbol extraction
from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_rust

class UniversalSymbolExtractor:
    def __init__(self):
        self.parsers = {
            '.py': Parser(Language(tree_sitter_python.language())),
            '.js': Parser(Language(tree_sitter_javascript.language())),
            '.rs': Parser(Language(tree_sitter_rust.language())),
        }
```

### 3. Distributed Caching
```python
# Add Redis for cross-session caching
import redis
from redis.asyncio import Redis
import pickle
import hashlib

class DistributedCache:
    def __init__(self):
        self.redis = Redis(decode_responses=False)
        
    async def get_or_compute(self, key: str, compute_fn):
        cached = await self.redis.get(key)
        if cached:
            return pickle.loads(cached)
        result = await compute_fn()
        await self.redis.setex(key, 3600, pickle.dumps(result))
        return result
```

### 4. Enhanced Progress Tracking
```python
# Replace manual progress with rich
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console
from rich.table import Table

console = Console()

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    task = progress.add_task("Analyzing changes...", total=None)
```

### 5. Structured Output
```python
# Use pydantic for commit metadata
from pydantic import BaseModel
from typing import List, Optional

class CommitContext(BaseModel):
    files_changed: List[str]
    symbols_modified: List[str]
    dependencies_affected: List[str]
    suggested_reviewers: Optional[List[str]]
    risk_score: float
    
class CommitSuggestion(BaseModel):
    title: str
    body: str
    type: str  # feat, fix, docs, etc.
    breaking_change: bool
    metadata: CommitContext
```

## Dependencies to Add
```toml
[project.dependencies]
aiohttp = "^3.9.0"
tree-sitter = "^0.20.4"
tree-sitter-python = "^0.20.4"
tree-sitter-javascript = "^0.20.3"
tree-sitter-rust = "^0.20.4"
redis = {extras = ["hiredis"], version = "^5.0.1"}
backoff = "^2.2.1"
rich = "^13.7.0"
pydantic = "^2.5.0"
```

## Performance Optimizations
1. **Parallel Symbol Extraction**: Use asyncio instead of ProcessPoolExecutor
2. **Streaming Analysis**: Process files as they're read
3. **Smart Caching**: Cache analysis results by file hash
4. **Batch API Calls**: Group related prompts
5. **Progressive Enhancement**: Start with basic message, enhance async

## Migration Strategy
1. Add async infrastructure alongside existing code
2. Create feature flag for new parser
3. Implement caching layer with fallback
4. Gradually migrate to tree-sitter parsing
5. A/B test performance improvements

## Expected Benefits
- **Performance**: 50% faster in quick mode, 70% faster in max mode
- **Accuracy**: Better symbol extraction with tree-sitter
- **Reliability**: Retry logic and circuit breakers
- **Scalability**: Distributed caching for teams
- **Developer Experience**: Rich progress indicators