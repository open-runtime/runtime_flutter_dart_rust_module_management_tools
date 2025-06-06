#!/usr/bin/env python3
"""
Performance tracking utilities for monitoring and optimizing CLI tools.
"""

import time
import os
from functools import wraps
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from contextlib import contextmanager


@dataclass
class TimingResult:
    """Result of a timed operation"""
    operation: str
    duration: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceTracker:
    """Simple performance tracking for CLI operations"""
    
    _instance: Optional['PerformanceTracker'] = None
    _timings: Dict[str, List[TimingResult]] = {}
    
    def __new__(cls):
        """Singleton pattern for global performance tracking"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def track(cls, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Decorator to track operation timing"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                tracker = cls()
                start = time.time()
                success = True
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start
                    timing = TimingResult(
                        operation=operation,
                        duration=duration,
                        success=success,
                        metadata=metadata or {}
                    )
                    tracker.record(timing)
                    
                    if os.environ.get('PERF_DEBUG'):
                        status = "✓" if success else "✗"
                        print(f"[PERF] {status} {operation}: {duration:.2f}s")
            
            return wrapper
        return decorator
    
    def record(self, timing: TimingResult) -> None:
        """Record a timing result"""
        if timing.operation not in self._timings:
            self._timings[timing.operation] = []
        self._timings[timing.operation].append(timing)
    
    @contextmanager
    def measure(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for timing operations"""
        start = time.time()
        success = True
        
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start
            timing = TimingResult(
                operation=operation,
                duration=duration,
                success=success,
                metadata=metadata or {}
            )
            self.record(timing)
            
            if os.environ.get('PERF_DEBUG'):
                status = "✓" if success else "✗"
                print(f"[PERF] {status} {operation}: {duration:.2f}s")
    
    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for operations"""
        if operation:
            timings = self._timings.get(operation, [])
            if not timings:
                return {}
            
            durations = [t.duration for t in timings]
            successful = [t for t in timings if t.success]
            
            return {
                'operation': operation,
                'count': len(timings),
                'success_count': len(successful),
                'failure_count': len(timings) - len(successful),
                'total_time': sum(durations),
                'avg_time': sum(durations) / len(durations),
                'min_time': min(durations),
                'max_time': max(durations),
                'success_rate': len(successful) / len(timings) * 100
            }
        
        # Get stats for all operations
        all_stats = {}
        for op in self._timings:
            all_stats[op] = self.get_stats(op)
        return all_stats
    
    def report(self, detailed: bool = False) -> None:
        """Print performance report"""
        if not self._timings:
            print("No performance data collected")
            return
        
        print("\nPerformance Report")
        print("=" * 70)
        print(f"{'Operation':<30} {'Count':>8} {'Avg(s)':>10} {'Total(s)':>10} {'Success':>10}")
        print("-" * 70)
        
        all_stats = self.get_stats()
        for op, stats in sorted(all_stats.items()):
            if stats:
                print(f"{op:<30} {stats['count']:>8} {stats['avg_time']:>10.2f} "
                      f"{stats['total_time']:>10.2f} {stats['success_rate']:>9.1f}%")
        
        if detailed:
            print("\nDetailed Timings:")
            for op, timings in sorted(self._timings.items()):
                print(f"\n{op}:")
                for t in timings[-5:]:  # Show last 5
                    status = "✓" if t.success else "✗"
                    print(f"  {status} {t.duration:.2f}s at {t.timestamp.strftime('%H:%M:%S')}")
    
    def save_report(self, filepath: Optional[Path] = None) -> None:
        """Save performance report to file"""
        if filepath is None:
            filepath = Path(f"perf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.get_stats(),
            'timings': {
                op: [
                    {
                        'duration': t.duration,
                        'success': t.success,
                        'timestamp': t.timestamp.isoformat(),
                        'metadata': t.metadata
                    }
                    for t in timings
                ]
                for op, timings in self._timings.items()
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Performance report saved to: {filepath}")
    
    def reset(self) -> None:
        """Reset all timing data"""
        self._timings.clear()


# Convenience functions
def track_performance(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Decorator for tracking performance"""
    return PerformanceTracker.track(operation, metadata)


def measure_operation(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager for measuring operations"""
    return PerformanceTracker().measure(operation, metadata)


def get_performance_stats(operation: Optional[str] = None) -> Dict[str, Any]:
    """Get performance statistics"""
    return PerformanceTracker().get_stats(operation)


def print_performance_report(detailed: bool = False) -> None:
    """Print performance report"""
    PerformanceTracker().report(detailed)


 