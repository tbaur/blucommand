#!/usr/bin/env python3
"""
Utility functions for Blucommand.

Copyright 2025 tbaur

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, Callable, Type, TypeVar, Tuple
from functools import wraps
from datetime import datetime

logger = logging.getLogger("blucommand")

T = TypeVar('T')


def format_bytes(size: float) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def format_rate(bytes_per_sec: float) -> str:
    """Format bytes per second into human-readable rate."""
    bits = int(bytes_per_sec) * 8
    if bits >= 1_000_000:
        return f"{bits/1_000_000:.2f} Mbps"
    elif bits >= 1_000:
        return f"{bits/1_000:.0f} Kbps"
    return f"{bits} bps"


def format_uptime(seconds: int) -> str:
    """Format seconds into human-readable uptime."""
    try:
        s = int(seconds)
        if s < 0:
            return "0m"  # Negative values return 0m
        d, s = divmod(s, 86400)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        if d > 0:
            return f"{d}d {h}h"
        elif h > 0:
            return f"{h}h {m}m"
        return f"{m}m"
    except (ValueError, TypeError):
        return "N/A"


def atomic_write(filepath: str, data: Dict[str, Any]) -> None:
    """Writes JSON to file atomically."""
    tmp_path = f"{filepath}.tmp"
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f)
        os.replace(tmp_path, filepath)
    except OSError as e:
        logger.error(f"Atomic write failed for {filepath}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def setup_logging(debug: bool = False, structured: bool = False) -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        debug: Enable debug logging
        structured: Use JSON structured logging format
        
    Returns:
        Configured logger instance
    """
    log_level = logging.DEBUG if debug else logging.WARNING
    logger_instance = logging.getLogger("blucommand")
    logger_instance.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger_instance.handlers[:]:
        logger_instance.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    console_formatter: logging.Formatter
    if structured:
        console_formatter = StructuredFormatter()
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    console_handler.setFormatter(console_formatter)
    logger_instance.addHandler(console_handler)
    
    # File handler (always structured for better parsing)
    from constants import LOG_FILE
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = StructuredFormatter()
    file_handler.setFormatter(file_formatter)
    logger_instance.addHandler(file_handler)
    
    return logger_instance


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info'):
                log_data[key] = value
        
        return json.dumps(log_data)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[Callable[[BaseException, int], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry on
        on_retry: Optional callback function called on each retry (exception, attempt_num)
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        if on_retry:
                            on_retry(e, attempt + 1)
                        else:
                            logger.debug(f"Retry {attempt + 1}/{max_retries} after {delay:.2f}s: {e}")
                        time.sleep(delay)
                        continue
                    raise
            if last_exception:
                raise last_exception
            raise Exception("Retry failed")
        return wrapper
    return decorator


class RateLimiter:
    """Rate limiter for device operations."""
    
    def __init__(self, min_delay: float = 0.1):
        """
        Initialize rate limiter.
        
        Args:
            min_delay: Minimum delay between operations in seconds
        """
        self.min_delay = min_delay
        self.last_call: Dict[str, float] = {}
    
    def wait_if_needed(self, key: str) -> None:
        """
        Wait if needed to respect rate limit.
        
        Args:
            key: Unique key for the rate limit (e.g., device IP)
        """
        now = time.time()
        if key in self.last_call:
            elapsed = now - self.last_call[key]
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
        self.last_call[key] = time.time()
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset rate limiter for a key or all keys.
        
        Args:
            key: Key to reset, or None to reset all
        """
        if key:
            self.last_call.pop(key, None)
        else:
            self.last_call.clear()


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter

