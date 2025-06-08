"""
Tests for interactive mode functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock
from io import StringIO
import sys
from rich.console import Console

from tooling.cli.interactive_mode import InteractiveMode, SmartCompleter


@pytest.fixture
def mock_console():
    """Create a mock console object"""
    console = Mock(spec=Console)
    console.get_time = Mock(return_value=0.0)
    return console


@pytest.fixture
def mock_commands():
    """Create mock commands dictionary"""
    return {
        'commit': {
            'description': 'Create commits',
            'module': 'tooling.cli.commit_tools',
            'class': 'CommitTool'
        },
        'release': {
            'description': 'Manage releases',
            'module': 'tooling.cli.release_tools',
            'class': 'ReleaseTool'
        },
        'changelog': {
            'description': 'Manage changelogs',
            'module': 'tooling.cli.changelog_tools',
            'class': 'ChangelogTool'
        }
    }


@pytest.fixture
def interactive_mode(mock_console, mock_commands):
    """Create interactive mode instance with mocks"""
    return InteractiveMode(console=mock_console, commands=mock_commands)


class TestSmartCompleter:
    """Test the smart completer"""
    
    def test_init(self, mock_commands):
        """Test completer initialization"""
        completer = SmartCompleter(mock_commands)
        assert completer.commands == mock_commands
        assert 'commit' in completer.base_commands
        assert 'release' in completer.base_commands
    
    def test_get_completions_empty(self, mock_commands):
        """Test completions for empty input"""
        completer = SmartCompleter(mock_commands)
        
        # Mock document
        document = Mock()
        document.text_before_cursor = ""
        
        completions = list(completer.get_completions(document, None))
        assert len(completions) == len(mock_commands)
        assert any(c.text == 'commit' for c in completions)
    
    def test_get_completions_partial(self, mock_commands):
        """Test completions for partial command"""
        completer = SmartCompleter(mock_commands)
        
        # Mock document with partial command
        document = Mock()
        document.text_before_cursor = "com"
        
        completions = list(completer.get_completions(document, None))
        assert len(completions) == 1
        assert completions[0].text == 'commit'
    
    def test_get_completions_subcommand(self, mock_commands):
        """Test completions for subcommands"""
        completer = SmartCompleter(mock_commands)
        
        # Mock document with command and partial subcommand
        document = Mock()
        document.text_before_cursor = "commit gen"
        
        completions = list(completer.get_completions(document, None))
        assert any(c.text == 'generate' for c in completions)


class TestInteractiveMode:
    """Test the interactive mode functionality"""
    
    def test_init(self, mock_console, mock_commands):
        """Test interactive mode initialization"""
        mode = InteractiveMode(console=mock_console, commands=mock_commands)
        assert mode.console == mock_console
        assert mode.commands == mock_commands
        assert mode.context == 'start'
        assert mode.last_command is None
        assert mode.session is not None
    
    def test_create_style(self, interactive_mode):
        """Test style creation"""
        style = interactive_mode._create_style()
        assert style is not None
        # Check that prompt style is defined
        class_names = [item[0] for item in style.class_names_and_attrs]
        assert any('prompt' in class_name for class_name in class_names)
    
    @patch('subprocess.run')
    def test_get_prompt(self, mock_subprocess, interactive_mode):
        """Test prompt generation"""
        # Mock git branch command
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='main\n'
        )
        
        prompt = interactive_mode._get_prompt()
        assert prompt is not None
        # Prompt should be HTML formatted
        assert 'main' in str(prompt)
    
    def test_show_suggestions(self, interactive_mode):
        """Test showing suggestions"""
        interactive_mode._show_suggestions()
        
        # Should print suggestions
        interactive_mode.console.print.assert_called()
    
    def test_update_context_after_commit(self, interactive_mode):
        """Test context update after commit"""
        interactive_mode._update_context('commit')
        assert interactive_mode.context == 'after_commit'
    
    def test_update_context_after_changes(self, interactive_mode):
        """Test context update after file changes"""
        interactive_mode._update_context('add file.py')
        assert interactive_mode.context == 'after_changes'
    
    @patch('subprocess.run')
    def test_update_context_status_with_changes(self, mock_subprocess, interactive_mode):
        """Test context update after status check with changes"""
        # Mock git status showing changes
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='M file.py\n'
        )
        
        interactive_mode._update_context('status')
        assert interactive_mode.context == 'after_changes'
    
    @pytest.mark.asyncio
    async def test_execute_command_exit(self, interactive_mode):
        """Test executing exit command"""
        result = await interactive_mode._execute_command('exit')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_execute_command_help(self, interactive_mode):
        """Test executing help command"""
        with patch.object(interactive_mode, '_show_help') as mock_help:
            result = await interactive_mode._execute_command('help')
            assert result is True
            mock_help.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_command_clear(self, interactive_mode):
        """Test executing clear command"""
        result = await interactive_mode._execute_command('clear')
        assert result is True
        interactive_mode.console.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_command_status(self, interactive_mode):
        """Test executing status command"""
        with patch.object(interactive_mode, '_show_status') as mock_status:
            result = await interactive_mode._execute_command('status')
            assert result is True
            mock_status.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('importlib.import_module')
    @patch('tooling.cli.interactive_mode.Progress')
    async def test_execute_command_runtime(self, mock_progress_class, mock_import, interactive_mode):
        """Test executing runtime command"""
        # Mock the Progress context manager
        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=None)
        mock_progress.add_task = MagicMock(return_value=1)
        mock_progress.update = MagicMock()
        mock_progress_class.return_value = mock_progress
        
        # Mock the command module
        mock_module = Mock()
        mock_tool_class = Mock()
        mock_tool_instance = Mock()
        mock_tool_instance.main = Mock(return_value=0)
        mock_tool_class.return_value = mock_tool_instance
        mock_module.CommitTool = mock_tool_class
        mock_import.return_value = mock_module
        
        result = await interactive_mode._execute_command('commit generate')
        assert result is True
        mock_tool_instance.main.assert_called_once_with(['generate'])
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_execute_command_shell(self, mock_subprocess, interactive_mode):
        """Test executing shell command"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        result = await interactive_mode._execute_command('ls -la')
        assert result is True
        mock_subprocess.assert_called_once_with('ls -la', shell=True, text=True)
    
    def test_show_help(self, interactive_mode):
        """Test help display"""
        interactive_mode._show_help()
        
        # Should print help panel
        interactive_mode.console.print.assert_called()
        # Check that a Panel was printed (Rich panel for help)
        call_args = interactive_mode.console.print.call_args[0][0]
        from rich.panel import Panel
        assert isinstance(call_args, Panel)
    
    @patch('subprocess.run')
    def test_show_status_clean(self, mock_subprocess, interactive_mode):
        """Test status display with clean working directory"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout=''
        )
        
        interactive_mode._show_status()
        
        # Should show clean message
        interactive_mode.console.print.assert_called_with(
            "[green]✓ Working directory clean[/green]"
        )
    
    @patch('subprocess.run')
    def test_show_status_with_changes(self, mock_subprocess, interactive_mode):
        """Test status display with changes"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='A  new_file.py\nM  modified.py\n?? untracked.py\n'
        )
        
        interactive_mode._show_status()
        
        # Should show status table
        assert interactive_mode.console.print.called
    
    @patch('tooling.cli.interactive_mode.PromptSession')
    def test_run(self, mock_prompt_session_class, interactive_mode):
        """Test running interactive mode"""
        # Mock the prompt session
        mock_session = Mock()
        mock_session.prompt = Mock(side_effect=['help', 'exit'])
        mock_prompt_session_class.return_value = mock_session
        
        # Replace the session
        interactive_mode.session = mock_session
        
        with patch.object(interactive_mode, '_execute_command', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = [True, False]  # help returns True, exit returns False
            
            interactive_mode.run()
        
        # Should have prompted twice
        assert mock_session.prompt.call_count == 2
        # Should print welcome and goodbye
        assert interactive_mode.console.print.call_count >= 2
    
    @patch('tooling.cli.interactive_mode.PromptSession')
    def test_run_keyboard_interrupt(self, mock_prompt_session_class, interactive_mode):
        """Test handling keyboard interrupt"""
        # Mock the prompt session
        mock_session = Mock()
        mock_session.prompt = Mock(side_effect=[KeyboardInterrupt(), 'exit'])
        mock_prompt_session_class.return_value = mock_session
        
        # Replace the session
        interactive_mode.session = mock_session
        
        with patch.object(interactive_mode, '_execute_command', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = False  # exit
            
            interactive_mode.run()
        
        # Should handle interrupt gracefully
        assert any(
            'Use \'exit\' to quit' in str(call)
            for call in interactive_mode.console.print.call_args_list
        )
    
    @patch('tooling.cli.interactive_mode.PromptSession')
    def test_run_eof_error(self, mock_prompt_session_class, interactive_mode):
        """Test handling EOF error"""
        # Mock the prompt session
        mock_session = Mock()
        mock_session.prompt = Mock(side_effect=EOFError())
        mock_prompt_session_class.return_value = mock_session
        
        # Replace the session
        interactive_mode.session = mock_session
        
        interactive_mode.run()
        
        # Should exit gracefully
        assert any(
            'Thanks for using' in str(call)
            for call in interactive_mode.console.print.call_args_list
        ) 