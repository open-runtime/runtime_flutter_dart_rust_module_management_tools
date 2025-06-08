"""
Plugin system for Runtime Tools.

Provides dynamic loading of plugins to extend functionality:
- Auto-discovery of plugins
- Hook-based architecture
- Configuration integration
- Dependency management
"""
import importlib
import importlib.util
import inspect
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Type, Callable
from dataclasses import dataclass
from rich.console import Console

console = Console()


@dataclass
class PluginMetadata:
    """Plugin metadata"""
    name: str
    version: str
    description: str
    author: Optional[str] = None
    dependencies: List[str] = None
    config_schema: Optional[Dict[str, Any]] = None


class PluginHook:
    """Decorator for plugin hooks"""
    
    hooks: Dict[str, List[Callable]] = {}
    
    def __init__(self, hook_name: str):
        self.hook_name = hook_name
    
    def __call__(self, func: Callable) -> Callable:
        if self.hook_name not in self.hooks:
            self.hooks[self.hook_name] = []
        self.hooks[self.hook_name].append(func)
        return func
    
    @classmethod
    def trigger(cls, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger all functions registered for a hook"""
        results = []
        if hook_name in cls.hooks:
            for func in cls.hooks[hook_name]:
                try:
                    result = func(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    console.print(f"[red]Hook {hook_name} error in {func.__name__}: {e}[/red]")
        return results


class Plugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self):
        self._metadata = None
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def register_commands(self, router: Any) -> None:
        """Register plugin commands with the command router"""
        pass
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with configuration"""
        pass
    
    def cleanup(self) -> None:
        """Cleanup plugin resources"""
        pass
    
    def validate_dependencies(self) -> bool:
        """Check if all dependencies are satisfied"""
        if not self.metadata.dependencies:
            return True
        
        for dep in self.metadata.dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                console.print(f"[red]Plugin {self.metadata.name} missing dependency: {dep}[/red]")
                return False
        return True


class CommandPlugin(Plugin):
    """Plugin that provides CLI commands"""
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Return command definitions"""
        pass
    
    def register_commands(self, router: Any) -> None:
        """Register commands with router"""
        commands = self.get_commands()
        for name, definition in commands.items():
            router.register(name, definition)


class PluginManager:
    """Manages plugin discovery and loading"""
    
    _instance: Optional['PluginManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.plugins: Dict[str, Plugin] = {}
            self.plugin_paths: List[Path] = []
            self._setup_default_paths()
    
    def _setup_default_paths(self):
        """Setup default plugin search paths"""
        # Built-in plugins
        self.plugin_paths.append(Path(__file__).parent.parent / 'plugins')
        
        # User plugins
        user_plugin_dir = Path.home() / '.runtime-tools' / 'plugins'
        if user_plugin_dir.exists():
            self.plugin_paths.append(user_plugin_dir)
        
        # Project plugins
        project_plugin_dir = Path.cwd() / '.runtime_fdr_management_tools-plugins'
        if project_plugin_dir.exists():
            self.plugin_paths.append(project_plugin_dir)
        
        # Environment variable paths
        if env_paths := os.environ.get('RT_PLUGIN_PATH'):
            for path in env_paths.split(':'):
                self.plugin_paths.append(Path(path))
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins"""
        discovered = []
        
        for plugin_dir in self.plugin_paths:
            if not plugin_dir.exists():
                continue
            
            # Look for Python files
            for file_path in plugin_dir.glob('*.py'):
                if file_path.name.startswith('_'):
                    continue
                
                plugin_name = file_path.stem
                if self._is_valid_plugin(file_path):
                    discovered.append(plugin_name)
            
            # Look for plugin packages
            for dir_path in plugin_dir.iterdir():
                if dir_path.is_dir() and not dir_path.name.startswith('_'):
                    init_file = dir_path / '__init__.py'
                    if init_file.exists() and self._is_valid_plugin(init_file):
                        discovered.append(dir_path.name)
        
        return discovered
    
    def _is_valid_plugin(self, path: Path) -> bool:
        """Check if a path contains a valid plugin"""
        try:
            # Quick check for plugin class
            content = path.read_text()
            return 'class' in content and 'Plugin' in content
        except:
            return False
    
    def load_plugin(self, name: str) -> Optional[Plugin]:
        """Load a specific plugin by name"""
        if name in self.plugins:
            return self.plugins[name]
        
        for plugin_dir in self.plugin_paths:
            # Try as file
            file_path = plugin_dir / f"{name}.py"
            if file_path.exists():
                plugin = self._load_plugin_from_file(name, file_path)
                if plugin:
                    self.plugins[name] = plugin
                    return plugin
            
            # Try as package
            package_path = plugin_dir / name / '__init__.py'
            if package_path.exists():
                plugin = self._load_plugin_from_file(name, package_path)
                if plugin:
                    self.plugins[name] = plugin
                    return plugin
        
        console.print(f"[yellow]Plugin not found: {name}[/yellow]")
        return None
    
    def _load_plugin_from_file(self, name: str, path: Path) -> Optional[Plugin]:
        """Load plugin from a Python file"""
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(f"rt_plugin_{name}", path)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"rt_plugin_{name}"] = module
            spec.loader.exec_module(module)
            
            # Find Plugin classes
            for item_name, item in inspect.getmembers(module):
                if (inspect.isclass(item) and 
                    issubclass(item, Plugin) and 
                    item is not Plugin and
                    item is not CommandPlugin):
                    
                    # Create instance
                    plugin = item()
                    
                    # Validate dependencies
                    if not plugin.validate_dependencies():
                        console.print(f"[red]Plugin {name} has unmet dependencies[/red]")
                        return None
                    
                    console.print(f"[green]✓ Loaded plugin: {plugin.metadata.name}[/green]")
                    return plugin
            
            console.print(f"[yellow]No valid Plugin class found in {path}[/yellow]")
            return None
            
        except Exception as e:
            console.print(f"[red]Failed to load plugin {name}: {e}[/red]")
            if os.environ.get('DEBUG'):
                console.print_exception()
            return None
    
    def load_all_plugins(self, config: Dict[str, Any] = None) -> None:
        """Load all discovered plugins"""
        discovered = self.discover_plugins()
        
        for plugin_name in discovered:
            plugin = self.load_plugin(plugin_name)
            if plugin and config:
                # Initialize with config
                plugin_config = config.get('plugins', {}).get(plugin_name, {})
                plugin.initialize(plugin_config)
    
    def get_loaded_plugins(self) -> Dict[str, Plugin]:
        """Get all loaded plugins"""
        return self.plugins
    
    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin"""
        if name in self.plugins:
            plugin = self.plugins[name]
            plugin.cleanup()
            del self.plugins[name]
            
            # Remove from sys.modules
            module_name = f"rt_plugin_{name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            console.print(f"[yellow]Unloaded plugin: {name}[/yellow]")
            return True
        return False
    
    def reload_plugin(self, name: str) -> Optional[Plugin]:
        """Reload a plugin"""
        self.unload_plugin(name)
        return self.load_plugin(name)


# Example plugin implementation
class ExamplePlugin(CommandPlugin):
    """Example plugin showing how to create custom commands"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="example",
            version="1.0.0",
            description="Example plugin for Runtime Tools",
            author="Runtime Tools Team",
            dependencies=["rich", "click"]
        )
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        return {
            'example': {
                'description': '📚 Example custom command',
                'handler': self.example_command,
                'arguments': [
                    {'name': '--name', 'help': 'Your name', 'default': 'World'}
                ]
            }
        }
    
    def example_command(self, name: str = "World") -> int:
        """Example command implementation"""
        console.print(f"[cyan]Hello, {name}! This is an example plugin command.[/cyan]")
        return 0
    
    @PluginHook('before_commit')
    def before_commit_hook(self, files: List[str]) -> None:
        """Hook that runs before commits"""
        console.print("[dim]Example plugin: before_commit hook triggered[/dim]")
    
    @PluginHook('after_release')
    def after_release_hook(self, version: str) -> None:
        """Hook that runs after releases"""
        console.print(f"[dim]Example plugin: after_release hook triggered for {version}[/dim]")


# Global plugin manager instance
plugin_manager = PluginManager()


def load_plugins(config: Dict[str, Any] = None) -> PluginManager:
    """Load all plugins and return the manager"""
    plugin_manager.load_all_plugins(config)
    return plugin_manager


def trigger_hook(hook_name: str, *args, **kwargs) -> List[Any]:
    """Trigger a plugin hook"""
    return PluginHook.trigger(hook_name, *args, **kwargs)


# Decorator for registering hooks in external code
hook = PluginHook 