"""
Unit tests for CLI tools base class.
"""
import pytest
import argparse
from unittest.mock import Mock, patch, MagicMock
from tooling.cli.cli_tools_base import CLITool, ClickCLITool, InteractiveCLITool


class TestCLITool(CLITool):
    """Test implementation of CLITool"""
    
    @property
    def name(self) -> str:
        return "test_tool"
    
    @property
    def description(self) -> str:
        return "Test tool for unit testing"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--test-arg', help='Test argument')
        parser.add_argument('--flag', action='store_true', help='Test flag')
    
    def execute(self) -> int:
        if self.args.test_arg == "fail":
            raise ValueError("Test failure")
        return 0 if self.args.test_arg == "success" else 1


class TestCLIToolBase:
    """Test suite for CLITool base class"""
    
    def test_initialization(self):
        """Test tool initialization"""
        tool = TestCLITool()
        assert tool.name == "test_tool"
        assert tool.description == "Test tool for unit testing"
        assert tool.console is not None
        assert tool.config is not None
        assert tool.logger is None
        assert tool.args is None
    
    def test_setup_parser(self):
        """Test parser setup"""
        tool = TestCLITool()
        parser = tool.setup_parser()
        
        # Check common arguments are added
        assert any(action.dest == 'verbose' for action in parser._actions)
        assert any(action.dest == 'debug' for action in parser._actions)
        assert any(action.dest == 'quiet' for action in parser._actions)
        assert any(action.dest == 'json' for action in parser._actions)
        assert any(action.dest == 'no_color' for action in parser._actions)
        assert any(action.dest == 'dry_run' for action in parser._actions)
        
        # Check tool-specific arguments
        assert any(action.dest == 'test_arg' for action in parser._actions)
        assert any(action.dest == 'flag' for action in parser._actions)
    
    @patch('tooling.cli.cli_tools_base.setup_cli_logging')
    @patch('tooling.cli.cli_tools_base.trigger_hook')
    def test_main_success(self, mock_trigger_hook, mock_setup_logging):
        """Test successful execution"""
        tool = TestCLITool()
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        result = tool.main(['--test-arg', 'success'])
        
        assert result == 0
        assert tool.args.test_arg == 'success'
        assert tool.logger == mock_logger
        
        # Check hooks were called
        mock_trigger_hook.assert_any_call('before_test_tool', tool.args)
        mock_trigger_hook.assert_any_call('after_test_tool', tool.args, 0)
    
    @patch('tooling.cli.cli_tools_base.setup_cli_logging')
    def test_main_failure(self, mock_setup_logging):
        """Test failed execution"""
        tool = TestCLITool()
        mock_setup_logging.return_value = Mock()
        
        result = tool.main(['--test-arg', 'failure'])
        
        assert result == 1
    
    @patch('tooling.cli.cli_tools_base.setup_cli_logging')
    def test_main_exception(self, mock_setup_logging):
        """Test exception handling"""
        tool = TestCLITool()
        mock_setup_logging.return_value = Mock()
        
        result = tool.main(['--test-arg', 'fail'])
        
        # Should catch exception and return 1
        assert result == 1
    
    def test_validate_args(self):
        """Test argument validation"""
        tool = TestCLITool()
        assert tool.validate_args() is True
    
    def test_show_banner(self):
        """Test banner display"""
        tool = TestCLITool()
        with patch.object(tool.console, 'print') as mock_print:
            tool.show_banner()
            mock_print.assert_called_once()
            # Check panel was created
            args = mock_print.call_args[0]
            assert len(args) == 1
            assert hasattr(args[0], 'renderable')  # Panel object
    
    def test_create_status_table(self):
        """Test status table creation"""
        tool = TestCLITool()
        table = tool.create_status_table("Test Status")
        
        assert table.title == "Test Status"
        assert table.title_style == "bold cyan"
        assert table.header_style == "bold"
    
    @patch('rich.prompt.Confirm.ask')
    def test_confirm_action(self, mock_confirm):
        """Test confirmation prompt"""
        tool = TestCLITool()
        tool.config = Mock()
        tool.config.development.dry_run = False
        
        mock_confirm.return_value = True
        result = tool.confirm_action("Test question?")
        
        assert result is True
        mock_confirm.assert_called_once_with("Test question?", default=False)
    
    def test_confirm_action_dry_run(self):
        """Test confirmation in dry run mode"""
        tool = TestCLITool()
        tool.config = Mock()
        tool.config.development.dry_run = True
        
        with patch.object(tool.console, 'print') as mock_print:
            result = tool.confirm_action("Test question?")
            
            assert result is False
            mock_print.assert_called_once()
    
    @patch('tooling.cli.cli_utils.select_choice')
    def test_select_option(self, mock_select):
        """Test option selection"""
        tool = TestCLITool()
        mock_select.return_value = "option2"
        
        result = tool.select_option("Choose:", ["option1", "option2", "option3"])
        
        assert result == "option2"
        mock_select.assert_called_once_with("Choose:", ["option1", "option2", "option3"], None)
    
    @patch('rich.prompt.Prompt.ask')
    def test_get_input(self, mock_prompt):
        """Test text input"""
        tool = TestCLITool()
        mock_prompt.return_value = "user input"
        
        result = tool.get_input("Enter text:")
        
        assert result == "user input"
        mock_prompt.assert_called_once_with("Enter text:", default=None, password=False)
    
    @patch('rich.progress.Progress')
    def test_show_progress(self, mock_progress_class):
        """Test progress display"""
        tool = TestCLITool()
        
        # Create a mock progress context manager
        mock_progress = MagicMock()
        mock_progress_class.return_value.__enter__.return_value = mock_progress
        
        # Mock task
        mock_task_id = 1
        mock_progress.add_task.return_value = mock_task_id
        
        # Test function
        def test_func(x, y):
            return x + y
        
        result = tool.show_progress("Testing...", test_func, 2, 3)
        
        assert result == 5
        mock_progress.add_task.assert_called_once_with("Testing...", total=None)
        mock_progress.update.assert_called_once()


class TestInteractiveCLITool:
    """Test suite for InteractiveCLITool"""
    
    class TestInteractiveTool(InteractiveCLITool):
        """Test implementation"""
        
        @property
        def name(self) -> str:
            return "test_interactive"
        
        @property
        def description(self) -> str:
            return "Test interactive tool"
        
        def add_arguments(self, parser):
            pass
        
        def get_commands(self):
            return {
                'test': self.test_command,
                'echo': self.echo_command
            }
        
        def test_command(self):
            """Test command"""
            return "test executed"
        
        def echo_command(self, *args):
            """Echo command"""
            return ' '.join(args)
    
    def test_initialization(self):
        """Test interactive tool initialization"""
        tool = self.TestInteractiveTool()
        assert tool.session is None
    
    @patch('prompt_toolkit.PromptSession')
    def test_setup_session(self, mock_prompt_session):
        """Test session setup"""
        tool = self.TestInteractiveTool()
        mock_session = Mock()
        mock_prompt_session.return_value = mock_session
        
        tool.setup_session()
        
        assert tool.session == mock_session
        mock_prompt_session.assert_called_once()
    
    def test_show_help(self):
        """Test help display"""
        tool = self.TestInteractiveTool()
        commands = tool.get_commands()
        
        with patch.object(tool.console, 'print') as mock_print:
            tool.show_help(commands)
            mock_print.assert_called_once()
            
            # Check table was created
            args = mock_print.call_args[0]
            assert len(args) == 1
            # Should be a Table object


class TestClickCLITool:
    """Test suite for ClickCLITool"""
    
    class TestClickTool(ClickCLITool):
        """Test implementation"""
        
        @property
        def name(self) -> str:
            return "test_click"
        
        @property
        def description(self) -> str:
            return "Test Click tool"
        
        def get_click_command(self):
            import click
            @click.command()
            @click.option('--count', default=1)
            def test_cmd(count):
                click.echo(f"Count: {count}")
                return 0
            
            return test_cmd
    
    def test_execute_success(self):
        """Test Click command execution"""
        tool = self.TestClickTool()
        tool.args = Mock()
        
        # Mock the click command
        mock_cmd = Mock()
        mock_cmd.invoke = Mock()
        
        with patch.object(tool, 'get_click_command', return_value=mock_cmd):
            with patch('click.Context') as mock_context_class:
                mock_ctx = Mock()
                mock_context_class.return_value = mock_ctx
                
                result = tool.execute()
                
                # Should create context and invoke command
                mock_context_class.assert_called_once_with(mock_cmd)
                mock_cmd.invoke.assert_called_once_with(mock_ctx)
                assert result == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 