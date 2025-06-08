#!/usr/bin/env python3
"""
Performance benchmarking and profiling utilities

Provides tools for measuring and optimizing Runtime Tools performance.
"""

import time
import os
from functools import wraps
from typing import Dict, List, Callable, Optional, Any, TypeVar
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from contextlib import contextmanager
import functools
import statistics
import psutil

from tooling.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class BenchmarkResult:
    """Result of a benchmark run"""
    name: str
    duration: float  # seconds
    memory_start: float  # MB
    memory_peak: float  # MB
    memory_end: float  # MB
    iterations: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def memory_used(self) -> float:
        """Memory used during execution (MB)"""
        return self.memory_peak - self.memory_start
    
    @property
    def average_duration(self) -> float:
        """Average duration per iteration"""
        return self.duration / self.iterations if self.iterations > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'duration': self.duration,
            'average_duration': self.average_duration,
            'memory_start': self.memory_start,
            'memory_peak': self.memory_peak,
            'memory_end': self.memory_end,
            'memory_used': self.memory_used,
            'iterations': self.iterations,
            'metadata': self.metadata,
            'timestamp': datetime.now().isoformat()
        }


class PerformanceTracker:
    """Track performance metrics across multiple runs"""
    
    def __init__(self, name: str = "runtime_tools"):
        self.name = name
        self.results: List[BenchmarkResult] = []
        self._start_time: Optional[float] = None
        self._start_memory: Optional[float] = None
        self._peak_memory: Optional[float] = None
    
    def start(self) -> None:
        """Start tracking performance"""
        self._start_time = time.time()
        self._start_memory = self._get_memory_usage()
        self._peak_memory = self._start_memory
    
    def stop(self, name: str, iterations: int = 1, **metadata) -> BenchmarkResult:
        """Stop tracking and record result"""
        if self._start_time is None:
            raise RuntimeError("Tracker not started")
        
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        result = BenchmarkResult(
            name=name,
            duration=end_time - self._start_time,
            memory_start=self._start_memory,
            memory_peak=self._peak_memory,
            memory_end=end_memory,
            iterations=iterations,
            metadata=metadata
        )
        
        self.results.append(result)
        self._reset()
        
        return result
    
    def _reset(self) -> None:
        """Reset tracker state"""
        self._start_time = None
        self._start_memory = None
        self._peak_memory = None
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # Update peak memory if tracking
        if self._peak_memory is not None:
            self._peak_memory = max(self._peak_memory, memory_mb)
        
        return memory_mb
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all results"""
        if not self.results:
            return {'name': self.name, 'results': 0}
        
        durations = [r.duration for r in self.results]
        memory_used = [r.memory_used for r in self.results]
        
        return {
            'name': self.name,
            'results': len(self.results),
            'duration': {
                'total': sum(durations),
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'min': min(durations),
                'max': max(durations),
                'stdev': statistics.stdev(durations) if len(durations) > 1 else 0
            },
            'memory': {
                'mean': statistics.mean(memory_used),
                'median': statistics.median(memory_used),
                'min': min(memory_used),
                'max': max(memory_used),
                'stdev': statistics.stdev(memory_used) if len(memory_used) > 1 else 0
            }
        }
    
    def save_results(self, file_path: Path) -> None:
        """Save results to JSON file"""
        data = {
            'name': self.name,
            'summary': self.get_summary(),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("performance_results_saved", path=str(file_path), count=len(self.results))


def benchmark(name: Optional[str] = None, iterations: int = 1, **metadata) -> Callable[[T], T]:
    """
    Decorator to benchmark function execution
    
    Args:
        name: Name for the benchmark (defaults to function name)
        iterations: Number of iterations to run
        **metadata: Additional metadata to store
    
    Example:
        @benchmark(iterations=100)
        def my_function():
            # ... code to benchmark
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        benchmark_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            tracker = PerformanceTracker(benchmark_name)
            tracker.start()
            
            result = None
            for _ in range(iterations):
                result = func(*args, **kwargs)
            
            benchmark_result = tracker.stop(
                name=benchmark_name,
                iterations=iterations,
                **metadata
            )
            
            logger.debug(
                "benchmark_complete",
                name=benchmark_name,
                duration=benchmark_result.average_duration,
                memory_used=benchmark_result.memory_used
            )
            
            return result
        
        return wrapper
    
    return decorator


def profile_memory(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to profile memory usage of a function
    
    Example:
        @profile_memory
        def my_function():
            # ... code to profile
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        process = psutil.Process(os.getpid())
        
        # Get initial memory
        mem_before = process.memory_info().rss / 1024 / 1024
        
        # Run function
        result = func(*args, **kwargs)
        
        # Get final memory
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_used = mem_after - mem_before
        
        logger.info(
            "memory_profile",
            function=func.__name__,
            memory_before=f"{mem_before:.2f} MB",
            memory_after=f"{mem_after:.2f} MB",
            memory_used=f"{mem_used:.2f} MB"
        )
        
        return result
    
    return wrapper


class TimingContext:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str = "operation", log_level: str = "info"):
        self.name = name
        self.log_level = log_level
        self.start_time: Optional[float] = None
        self.duration: Optional[float] = None
    
    def __enter__(self) -> 'TimingContext':
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            self.duration = time.time() - self.start_time
            
            log_func = getattr(logger, self.log_level, logger.info)
            log_func(
                "timing",
                operation=self.name,
                duration=f"{self.duration:.3f}s"
            )


# Global tracker for overall application performance
_global_tracker = PerformanceTracker("global")


def track_operation(name: str, **metadata) -> TimingContext:
    """
    Track a named operation's performance
    
    Example:
        with track_operation("changelog_sync", package="my-package"):
            # ... operation code
    """
    class TrackingContext(TimingContext):
        def __enter__(self):
            super().__enter__()
            _global_tracker.start()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            super().__exit__(exc_type, exc_val, exc_tb)
            if exc_type is None:  # Only track successful operations
                _global_tracker.stop(name, **metadata)
    
    return TrackingContext(name)


def get_performance_report() -> Dict[str, Any]:
    """Get performance report for the current session"""
    return _global_tracker.get_summary()


def save_performance_report(file_path: Path) -> None:
    """Save performance report to file"""
    _global_tracker.save_results(file_path)


# Utility functions for common performance patterns
def measure_time(func: Callable[..., T]) -> Callable[..., tuple[T, float]]:
    """
    Wrapper that returns both result and execution time
    
    Example:
        timed_func = measure_time(my_function)
        result, duration = timed_func(arg1, arg2)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> tuple[T, float]:
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        return result, duration
    
    return wrapper


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying operations with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay on each retry
        max_delay: Maximum delay between retries
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            delay=delay,
                            error=str(e)
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
            
            # All attempts failed
            logger.error(
                "retry_failed",
                function=func.__name__,
                attempts=max_attempts,
                error=str(last_exception)
            )
            raise last_exception
        
        return wrapper
    
    return decorator


# Add track method to PerformanceTracker for backward compatibility
def track(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Class method decorator for tracking performance"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with track_operation(operation, **(metadata or {})):
                return func(*args, **kwargs)
        return wrapper
    return decorator

# Add as class method for backward compatibility
PerformanceTracker.track = classmethod(lambda cls, operation, metadata=None: track(operation, metadata))

# Add measure method for backward compatibility  
PerformanceTracker.measure = lambda self, operation, metadata=None: track_operation(operation, **(metadata or {}))

# Add get_stats method for backward compatibility
def get_stats_method(self, operation: Optional[str] = None) -> Dict[str, Any]:
    """Get statistics for operations"""
    if operation:
        results = [r for r in self.results if r.name == operation]
    else:
        results = self.results
    
    if not results:
        return {}
    
    durations = [r.duration for r in results]
    return {
        'operation': operation or 'all',
        'count': len(results),
        'total_time': sum(durations),
        'avg_time': sum(durations) / len(durations) if durations else 0,
        'min_time': min(durations) if durations else 0,
        'max_time': max(durations) if durations else 0
    }

PerformanceTracker.get_stats = get_stats_method

# Add report method for backward compatibility
def report_method(self, detailed: bool = False) -> None:
    """Print performance report"""
    stats = self.get_summary()
    print(f"\nPerformance Report: {stats}")

PerformanceTracker.report = report_method

# Convenience functions
def track_performance(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Decorator for tracking performance"""
    return track(operation, metadata)


def measure_operation(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager for measuring operations"""
    return track_operation(operation, **(metadata or {}))


def get_performance_stats(operation: Optional[str] = None) -> Dict[str, Any]:
    """Get performance statistics"""
    return _global_tracker.get_stats(operation)


def print_performance_report(detailed: bool = False) -> None:
    """Print performance report"""
    _global_tracker.report(detailed)


def save_performance_report(file_path: Path) -> None:
    """Save performance report to file"""
    _global_tracker.save_results(file_path)


 