"""
Tests for retry logic and rate limiting.
"""
import pytest
import time
from unittest.mock import patch, MagicMock

from blucommand.utils import retry_with_backoff, RateLimiter, get_rate_limiter, StructuredFormatter
import logging


class TestRetryWithBackoff:
    """Test retry decorator."""
    
    def test_retry_succeeds_on_first_try(self):
        """Test that function succeeds without retries."""
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def success_func():
            return "success"
        
        assert success_func() == "success"
    
    def test_retry_succeeds_after_failures(self):
        """Test that function succeeds after retries."""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def retry_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Temporary failure")
            return "success"
        
        result = retry_func()
        assert result == "success"
        assert call_count[0] == 2
    
    def test_retry_fails_after_max_retries(self):
        """Test that function fails after max retries."""
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def fail_func():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            fail_func()
    
    def test_retry_only_catches_specified_exceptions(self):
        """Test that retry only catches specified exceptions."""
        @retry_with_backoff(max_retries=2, exceptions=(ValueError,), base_delay=0.01)
        def raise_key_error():
            raise KeyError("Not caught")
        
        with pytest.raises(KeyError):
            raise_key_error()
    
    def test_retry_exponential_backoff(self):
        """Test that retry uses exponential backoff."""
        delays = []
        call_count = [0]
        
        original_sleep = time.sleep
        def mock_sleep(delay):
            delays.append(delay)
            original_sleep(0)  # Don't actually wait
        
        @retry_with_backoff(max_retries=3, base_delay=0.1, max_delay=1.0)
        def retry_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        with patch('time.sleep', side_effect=mock_sleep):
            retry_func()
        
        assert len(delays) == 2  # Two retries
        assert delays[0] == 0.1  # First retry: base_delay
        assert delays[1] == 0.2  # Second retry: base_delay * 2
    
    def test_retry_respects_max_delay(self):
        """Test that retry respects max delay."""
        delays = []
        call_count = [0]
        
        original_sleep = time.sleep
        def mock_sleep(delay):
            delays.append(delay)
            original_sleep(0)
        
        @retry_with_backoff(max_retries=5, base_delay=1.0, max_delay=2.0)
        def retry_func():
            call_count[0] += 1
            if call_count[0] < 5:
                raise ValueError("Temporary failure")
            return "success"
        
        with patch('time.sleep', side_effect=mock_sleep):
            retry_func()
        
        # All delays should be capped at max_delay
        assert all(d <= 2.0 for d in delays)
    
    def test_retry_with_callback(self):
        """Test retry with callback function."""
        callbacks = []
        
        def on_retry(exc, attempt):
            callbacks.append((type(exc).__name__, attempt))
        
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, base_delay=0.01, on_retry=on_retry)
        def retry_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Temporary failure")
            return "success"
        
        retry_func()
        assert len(callbacks) == 1
        assert callbacks[0] == ("ValueError", 1)


class TestRateLimiter:
    """Test rate limiter."""
    
    def test_rate_limiter_waits_when_needed(self):
        """Test that rate limiter waits when operations are too fast."""
        limiter = RateLimiter(min_delay=0.1)
        
        start = time.time()
        limiter.wait_if_needed("device1")
        limiter.wait_if_needed("device1")  # Should wait ~0.1s
        elapsed = time.time() - start
        
        assert elapsed >= 0.1
    
    def test_rate_limiter_no_wait_when_slow(self):
        """Test that rate limiter doesn't wait when operations are slow enough."""
        limiter = RateLimiter(min_delay=0.01)
        
        limiter.wait_if_needed("device1")
        time.sleep(0.02)  # Wait longer than min_delay
        start = time.time()
        limiter.wait_if_needed("device1")
        elapsed = time.time() - start
        
        assert elapsed < 0.01  # Should not wait
    
    def test_rate_limiter_per_device(self):
        """Test that rate limiter tracks each device separately."""
        limiter = RateLimiter(min_delay=0.1)
        
        # First call to device1
        limiter.wait_if_needed("device1")
        
        # Immediate call to device2 should not wait
        start = time.time()
        limiter.wait_if_needed("device2")
        elapsed = time.time() - start
        
        assert elapsed < 0.05  # Should not wait for different device
    
    def test_rate_limiter_reset(self):
        """Test that rate limiter can be reset."""
        limiter = RateLimiter(min_delay=0.1)
        
        limiter.wait_if_needed("device1")
        limiter.reset("device1")
        
        # After reset, should not wait
        start = time.time()
        limiter.wait_if_needed("device1")
        elapsed = time.time() - start
        
        assert elapsed < 0.05
    
    def test_rate_limiter_reset_all(self):
        """Test that rate limiter can reset all devices."""
        limiter = RateLimiter(min_delay=0.1)
        
        limiter.wait_if_needed("device1")
        limiter.wait_if_needed("device2")
        limiter.reset()
        
        # After reset, should not wait
        start = time.time()
        limiter.wait_if_needed("device1")
        limiter.wait_if_needed("device2")
        elapsed = time.time() - start
        
        assert elapsed < 0.05
    
    def test_get_rate_limiter_returns_singleton(self):
        """Test that get_rate_limiter returns the same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2


class TestStructuredFormatter:
    """Test structured log formatter."""
    
    def test_structured_formatter_creates_json(self):
        """Test that structured formatter creates JSON output."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should be valid JSON
        import json
        data = json.loads(output)
        assert data['level'] == 'INFO'
        assert data['message'] == 'Test message'
        assert 'timestamp' in data
    
    def test_structured_formatter_includes_exception(self):
        """Test that structured formatter includes exception info."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=__import__('sys').exc_info()
            )
        
        output = formatter.format(record)
        
        import json
        data = json.loads(output)
        assert 'exception' in data
        assert 'ValueError' in data['exception']
    
    def test_structured_formatter_includes_extra_fields(self):
        """Test that structured formatter includes extra fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.device_ip = "192.168.1.100"
        record.operation = "play"
        
        output = formatter.format(record)
        
        import json
        data = json.loads(output)
        assert data['device_ip'] == "192.168.1.100"
        assert data['operation'] == "play"

