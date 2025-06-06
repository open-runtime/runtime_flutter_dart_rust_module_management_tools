import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from intelligent_commit_analyzer import (
    CommitContext,
    ClaudeCodeAnalyzer,
    GeminiAnalyzer,
    CommitAnalysisOrchestrator,
    Config
)

@pytest.fixture
def sample_context():
    """Create sample commit context for testing."""
    return CommitContext(
        files_changed=['src/main.py', 'tests/test_main.py'],
        additions=50,
        deletions=10,
        diff_content="+ def new_feature():\n+     return 'hello'",
        previous_commits=[
            {'sha': 'abc123', 'message': 'feat: add authentication'},
            {'sha': 'def456', 'message': 'fix: resolve memory leak'}
        ],
        related_issues=[
            {'number': 42, 'title': 'Add new feature', 'state': 'open'}
        ]
    )

@pytest.mark.asyncio
async def test_claude_analyzer(sample_context):
    """Test Claude Code analyzer."""
    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
        # Mock subprocess response
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b'{"type": "message", "content": "Analysis complete"}',
            b''
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        analyzer = ClaudeCodeAnalyzer(api_key='test-key')
        result = await analyzer.analyze(sample_context)
        
        assert result.tool == AIToolType.CLAUDE
        assert not result.error
        assert result.execution_time > 0

@pytest.mark.asyncio
async def test_orchestrator_synthesis():
    """Test result synthesis in orchestrator."""
    config = Config(
        claude_api_key='test',
        openai_api_key='test', 
        google_api_key='test'
    )
    
    orchestrator = CommitAnalysisOrchestrator(config)
    
    # Mock analyzers
    orchestrator.analyzers = [
        AsyncMock(analyze=AsyncMock(return_value=AnalysisResult(
            tool=AIToolType.CLAUDE,
            content="Implemented new authentication system",
            metadata={'commit_type': 'feat', 'scope': 'auth'}
        ))),
        AsyncMock(analyze=AsyncMock(return_value=AnalysisResult(
            tool=AIToolType.GEMINI,
            content="Added OAuth2 support", 
            metadata={'commit_type': 'feat', 'breaking': False}
        )))
    ]
    
    with patch.object(orchestrator, '_build_context', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = sample_context
        
        result = await orchestrator.analyze_changes()
        
        assert result['status'] == 'success'
        assert 'feat' in result['commit_message']
        assert result['details']['type'] == 'feat'