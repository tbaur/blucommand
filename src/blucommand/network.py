#!/usr/bin/env python3
"""
Network I/O operations for Blucommand.

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
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error
import logging
from typing import Optional, Dict

from blucommand.constants import DEFAULT_TIMEOUT, MAX_XML_SIZE, MAX_RETRIES, RETRY_DELAY_BASE, MAX_RETRY_DELAY

logger = logging.getLogger("blucommand")


def _url_for_log(url: str) -> str:
    """
    Return a log-safe URL with userinfo credentials stripped.

    Never log request headers — callers may pass secrets (e.g. X-API-KEY).
    """
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "<redacted-url>"
    if not parts.username and not parts.password:
        return url
    hostname = parts.hostname or ""
    if parts.port:
        hostname = f"{hostname}:{parts.port}"
    return urllib.parse.urlunsplit(parts._replace(netloc=hostname))


class Network:
    """
    Centralized network I/O operations.
    
    NOTE: SSL Verification DISABLED for local IoT context.
    This is intentional for local network device communication.
    """
    # DOCUMENTED DEVIATION: SSL Verification DISABLED for local IoT context.
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
    
    @classmethod
    def _do_request(cls,
                    url: str,
                    method: str = "GET",
                    data: Optional[bytes] = None,
                    headers: Optional[Dict] = None,
                    timeout: int = DEFAULT_TIMEOUT) -> Optional[bytes]:
        """Single HTTP attempt. Raises URLError/TimeoutError on network failure."""
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=cls._SSL_CTX) as response:
                content = response.read(MAX_XML_SIZE + 1)
                if len(content) > MAX_XML_SIZE:
                    logger.warning(
                        "Payload exceeded size limit (%s)", _url_for_log(url)
                    )
                    return None
                return bytes(content)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read(200).decode("utf-8", "replace").replace("\n", " ")
            except Exception:
                detail = ""
            logger.debug(
                "HTTP error (%s): %s %s %s", _url_for_log(url), e.code, e.reason, detail
            )
            return None

    @classmethod
    def request(cls, 
                url: str, 
                method: str = "GET", 
                data: Optional[Dict] = None, 
                headers: Optional[Dict] = None,
                timeout: int = DEFAULT_TIMEOUT,
                max_retries: int = MAX_RETRIES) -> Optional[bytes]:
        """
        Make HTTP request with security, error handling, and optional retries.
        
        ``max_retries`` is the number of attempts (default from MAX_RETRIES).
        Use ``max_retries=1`` for local device polls so dead endpoints fail fast.
        """
        log_url = _url_for_log(url)

        if not url.startswith(('http://', 'https://')):
            logger.warning("Invalid URL scheme: %s", log_url)
            return None
        
        encoded_data = None
        if data:
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        attempts = max(1, int(max_retries))
        last_error: Optional[BaseException] = None

        for attempt in range(attempts):
            try:
                return cls._do_request(url, method, encoded_data, headers, timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last_error = e
                if attempt < attempts - 1:
                    delay = min(RETRY_DELAY_BASE * (2 ** attempt), MAX_RETRY_DELAY)
                    logger.debug(
                        "Retry %s/%s after %.2fs: %s",
                        attempt + 1, attempts, delay, e,
                    )
                    time.sleep(delay)
                    continue
                logger.debug("Network error after retries (%s): %s", log_url, e)
                return None
            except Exception as e:
                logger.debug("Unexpected error (%s): %s", log_url, e)
                return None

        if last_error:
            logger.debug("Network error after retries (%s): %s", log_url, last_error)
        return None
    
    @classmethod
    def get(cls, url: str, **kwargs) -> Optional[bytes]:
        """Make GET request."""
        return cls.request(url, method="GET", **kwargs)
    
    @classmethod
    def post(cls, url: str, data: Dict, **kwargs) -> Optional[bytes]:
        """Make POST request."""
        return cls.request(url, method="POST", data=data, **kwargs)
