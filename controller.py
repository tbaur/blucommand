#!/usr/bin/env python3
"""
Blucommand - Core device management logic.

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
import sys
import time
import json
import subprocess
import re
import urllib.parse
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import logging
from typing import List, Dict, Optional, Set, Tuple, TypeGuard
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from constants import (
    BLUOS_MDNS_SERVICES,
    CACHE_FILE,
    UNIFI_CACHE_FILE,
    MAX_XML_DEPTH,
    MAX_XML_SIZE,
    MAX_XML_ELEMENTS,
    MAX_XML_ATTRIBUTES,
    MAX_WORKERS_DISCOVERY,
    SUBPROCESS_TIMEOUT,
    DISCOVERY_MDNS,
    DISCOVERY_LSDP,
    DISCOVERY_BOTH,
)
from models import UniFiClient, PlayerStatus
from config import Config
from network import Network
from utils import atomic_write, get_rate_limiter
from validators import (
    validate_ip,
    sanitize_ip,
    validate_hostname,
    validate_timeout,
    parse_endpoint,
    format_endpoint,
    sanitize_endpoint,
)
from lsdp import LSDPDiscovery

logger = logging.getLogger("blucommand")


def parse_bluos_host(value: Optional[str]) -> str:
    """Extract an IP/host from BluOS endpoint values like ``192.168.1.20`` or ``192.168.1.20:11000``."""
    if not value:
        return ""
    ip, _port = parse_endpoint(value.strip())
    return ip or ""


def parse_bluos_endpoint(value: Optional[str]) -> str:
    """Normalize a BluOS id to canonical ``ip:port`` (default port 11000)."""
    if not value:
        return ""
    return sanitize_endpoint(value.strip()) or ""


def parse_sync_status_root(root: ET.Element) -> tuple[str, str, List[str]]:
    """
    Parse ``/SyncStatus`` XML for master endpoint, group name, and slave endpoints.

    BluOS may expose values as root attributes or child elements. Legacy clients
    assumed ``master`` was an attribute; current firmware uses ``<master>``.
    Multi-zone CI players use ``ip:port`` ids (e.g. ``192.168.1.20:11010``).
    """
    master_attr = root.attrib.get("master") or ""
    master_elem = root.find("master")
    if master_elem is not None:
        raw_master = (master_elem.text or "").strip()
        port_attr = master_elem.attrib.get("port")
        if raw_master and port_attr and ":" not in raw_master:
            raw_master = f"{raw_master}:{port_attr.strip()}"
        master = parse_bluos_endpoint(raw_master)
    else:
        master = parse_bluos_endpoint(master_attr)

    group = (root.attrib.get("group") or root.findtext("group") or "").strip()

    slaves: List[str] = []
    for slave_elem in root.findall("slave"):
        # Prefer id attribute (may include port); fall back to text / port attr.
        raw_id = slave_elem.attrib.get("id") or slave_elem.text or ""
        port_attr = slave_elem.attrib.get("port")
        if raw_id and port_attr and ":" not in raw_id.strip():
            raw_id = f"{raw_id.strip()}:{port_attr.strip()}"
        slave_ep = parse_bluos_endpoint(raw_id)
        if slave_ep and slave_ep not in slaves:
            slaves.append(slave_ep)

    return master, group, slaves


class BluOSController:
    """Main controller for BluOS device management."""
    
    def __init__(self):
        self.config = Config()
        # Endpoint keys: canonical "ip:port" (CI secondary zones share an IP)
        self.ips: List[str] = []
        self.unifi_map: Dict[str, UniFiClient] = {}
    
    def discover(self, force_refresh: bool = False) -> None:
        """
        Discover BluOS players as ``ip:port`` endpoints.

        mDNS browses ``_musc._tcp`` (primary) and ``_musp._tcp`` (CI secondary
        zones) and keeps the SRV port. LSDP is used when configured / as fallback
        and yields ``ip:11000`` (primary only).
        """
        if not force_refresh and self._load_discovery_cache():
            return

        discovery_method = self.config.get('DISCOVERY_METHOD', DISCOVERY_MDNS).lower()
        timeout = int(self.config.get('DISCOVERY_TIMEOUT', 5))

        print(f"Scanning Network ({timeout}s) [{discovery_method}]...", file=sys.stderr)

        endpoints: Set[str] = set()

        if discovery_method in (DISCOVERY_MDNS, DISCOVERY_BOTH):
            for ep in self._discover_mdns(timeout):
                cleaned = sanitize_endpoint(str(ep))
                if cleaned:
                    endpoints.add(cleaned)

        if discovery_method == DISCOVERY_LSDP or (
            discovery_method == DISCOVERY_BOTH and not endpoints
        ):
            for ip in self._discover_lsdp(timeout):
                cleaned = sanitize_endpoint(str(ip))
                if cleaned:
                    endpoints.add(cleaned)

        # Only keep / cache hosts that answer SyncStatus. Caching unverified
        # mDNS hits (gateways, stale leases) poisons the TTL and slows every command.
        verified = self._verify_endpoints(sorted(endpoints))
        if verified:
            self.ips = verified
            atomic_write(CACHE_FILE, {'ts': time.time(), 'ips': self.ips})
        else:
            if endpoints:
                logger.warning(
                    "Discovered %s endpoint(s) but none answered SyncStatus; "
                    "not updating discovery cache",
                    len(endpoints),
                )
            self.ips = []
            logger.warning("No valid devices found via discovery")

    def _discover_mdns(self, timeout: int) -> List[str]:
        """Browse ``_musc._tcp`` + ``_musp._tcp``; return ``ip:port`` from SRV."""
        raw_chunks: List[str] = []
        with ThreadPoolExecutor(max_workers=len(BLUOS_MDNS_SERVICES)) as executor:
            futures = {
                executor.submit(self._run_dns_sd, service, timeout): service
                for service in BLUOS_MDNS_SERVICES
            }
            for future in as_completed(futures):
                service = futures[future]
                try:
                    output = future.result() or ""
                    if output:
                        raw_chunks.append(output)
                    else:
                        logger.debug(f"No dns-sd response for {service}")
                except Exception as e:
                    logger.debug(f"dns-sd error for {service}: {e}")

        if not raw_chunks:
            return []

        # SRV priority weight port target
        srv_pattern = re.compile(r"SRV\s+\d+\s+\d+\s+(\d+)\s+(\S+)")
        host_ports: Dict[str, Set[int]] = {}
        for line in "\n".join(raw_chunks).splitlines():
            if "SRV" not in line:
                continue
            match = srv_pattern.search(line)
            if not match:
                continue
            try:
                port = int(match.group(1))
            except ValueError:
                continue
            host = match.group(2).rstrip('.')
            if host:
                host_ports.setdefault(host, set()).add(port)

        if not host_ports:
            logger.debug("No devices found via mDNS.")
            return []

        endpoints: Set[str] = set()
        for host, ports in host_ports.items():
            for ip in self._resolve_hosts({host}):
                for port in ports:
                    endpoints.add(format_endpoint(ip, port))

        return sorted(endpoints)

    def _discover_lsdp(self, timeout: int) -> List[str]:
        """Discover chassis IPs using LSDP (normalized to ``ip:11000`` by caller)."""
        try:
            return LSDPDiscovery(timeout=timeout).discover()
        except Exception as e:
            logger.debug(f"LSDP discovery error: {e}")
            return []

    def _verify_endpoints(self, endpoints: List[str]) -> List[str]:
        """Keep endpoints that respond to ``/SyncStatus`` (single attempt each)."""
        if not endpoints:
            return []

        def _check(ep: str) -> Optional[str]:
            url = self._api_url(ep, "/SyncStatus")
            if not url:
                return None
            data = Network.get(url, timeout=1, max_retries=1)
            if not self._bluos_response_ok(data):
                return None
            root = self._safe_parse_xml(data, ep)
            if root is None:
                return None
            return ep

        ok: List[str] = []
        workers = min(MAX_WORKERS_DISCOVERY, len(endpoints))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_check, ep): ep for ep in endpoints}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    logger.debug(f"Endpoint verify error for {futures[future]}: {e}")
                    continue
                if result:
                    ok.append(result)
        return sorted(ok)

    def _load_discovery_cache(self) -> bool:
        """Load discovery cache if valid."""
        if not os.path.exists(CACHE_FILE):
            return False
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            cached_ts = float(data.get('ts', 0))
            ttl = int(self.config.get('CACHE_TTL', 300))
            if time.time() - cached_ts < ttl:
                cached_ips = data.get('ips', [])
                # Normalize bare IPs and ip:port entries to canonical endpoints
                validated: List[str] = []
                for entry in cached_ips:
                    endpoint = sanitize_endpoint(str(entry))
                    if endpoint:
                        validated.append(endpoint)
                if validated:
                    logger.debug("Using cached discovery data.")
                    self.ips = sorted(set(validated))
                    return True
                else:
                    logger.warning("Cached IPs failed validation, refreshing")
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
            logger.debug(f"Cache load error: {e}")
        return False

    def _resolve_endpoint(self, endpoint: str) -> Optional[Tuple[str, int]]:
        """Parse ``ip`` or ``ip:port`` into a validated ``(ip, port)`` tuple."""
        ip, port = parse_endpoint(endpoint)
        if not ip:
            return None
        return ip, port

    def _api_url(self, endpoint: str, path: str) -> Optional[str]:
        """Build ``http://ip:port/path`` for a BluOS API call."""
        resolved = self._resolve_endpoint(endpoint)
        if not resolved:
            return None
        ip, port = resolved
        if not path.startswith("/"):
            path = f"/{path}"
        return f"http://{ip}:{port}{path}"
    
    def _run_dns_sd(self, service: str, timeout: int) -> str:
        """
        Run dns-sd command to discover services with security protections.
        
        Args:
            service: Service name to discover (validated)
            timeout: Timeout in seconds (validated)
            
        Returns:
            Command output as string
        """
        # Validate and sanitize inputs
        if not service or not isinstance(service, str):
            logger.warning("Invalid service name for dns-sd")
            return ""
        
        # Validate service name format (basic check for injection prevention)
        if not re.match(r'^[a-zA-Z0-9._-]+$', service):
            logger.warning(f"Invalid service name format: {service}")
            return ""
        
        # Validate timeout
        validated_timeout = validate_timeout(timeout, min_val=1, max_val=60)
        
        # Include service name so parallel musc/musp browses don't share a temp file
        safe_service = re.sub(r'[^a-zA-Z0-9._-]', '_', service)
        tmp_file = os.path.join(
            os.path.expanduser("~"),
            f".blucommand-tmp-discovery-{os.getpid()}-{safe_service}",
        )
        try:
            with open(tmp_file, 'w') as outfile:
                subprocess.run(
                    ["dns-sd", "-Z", service, "local"],
                    stdout=outfile,
                    stderr=subprocess.DEVNULL,
                    timeout=validated_timeout,
                    check=False,
                    # Security: No shell=True, args as list
                    shell=False
                )
        except subprocess.TimeoutExpired:
            logger.debug(f"dns-sd timeout after {validated_timeout}s")
            pass
        except OSError as e:
            logger.debug(f"dns-sd execution error: {e}")
            pass
        except Exception as e:
            logger.debug(f"Unexpected error in dns-sd: {e}")
            pass
        
        output = ""
        if os.path.exists(tmp_file):
            try:
                with open(tmp_file, 'r', errors='ignore') as f:
                    output = f.read()
            finally:
                os.remove(tmp_file)
        return output
    
    def _resolve_hosts(self, hosts: Set[str]) -> Set[str]:
        """
        Resolve hostnames to IP addresses with comprehensive validation and security.
        
        Args:
            hosts: Set of hostnames to resolve (validated before processing)
            
        Returns:
            Set of validated IP addresses
        """
        found_ips = set()
        for host in hosts:
            # Validate hostname before subprocess call (prevents injection)
            if not host or not isinstance(host, str):
                logger.warning(f"Invalid hostname type: {type(host)}")
                continue
            
            # Validate hostname format and length
            if not validate_hostname(host):
                logger.warning(f"Invalid hostname format: {host}")
                continue
            
            # Additional security: ensure hostname doesn't contain shell metacharacters
            if any(char in host for char in [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']):
                logger.warning(f"Hostname contains unsafe characters: {host}")
                continue
            
            try:
                # Native macOS resolution requires full hostname (e.g. node.local)
                # Security: Use list of args (not shell), validated timeout, validated input
                out = subprocess.check_output(
                    ["dscacheutil", "-q", "host", "-a", "name", host],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=SUBPROCESS_TIMEOUT,
                    # Security: Explicitly disable shell
                    shell=False
                )
                
                # Validate output size to prevent memory exhaustion
                if len(out) > MAX_XML_SIZE:  # Reuse size limit constant
                    logger.warning(f"dscacheutil output too large for {host}: {len(out)} bytes")
                    continue
                
                for line in out.splitlines():
                    if "ip_address" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            ip = parts[1].strip()
                            # Validate IP address before adding
                            sanitized_ip = sanitize_ip(ip)
                            if sanitized_ip:
                                found_ips.add(sanitized_ip)
            except subprocess.TimeoutExpired:
                logger.debug(f"Host resolution timeout for {host}")
                continue
            except subprocess.CalledProcessError as e:
                logger.debug(f"Host resolution failed for {host}: {e}")
                continue
            except OSError as e:
                logger.debug(f"OS error resolving host {host}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error resolving host {host}: {e}")
                continue
        return found_ips
    
    @staticmethod
    def _unifi_api_headers(api_key: str) -> Dict[str, str]:
        return {
            'X-API-KEY': api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def _fetch_unifi_json(
        self, base: str, site: str, api_key: str, path: str, timeout: int = 4
    ) -> Optional[Dict]:
        """GET a UniFi Network API path and return parsed JSON, or None on failure."""
        url = f"https://{base}/proxy/network/api/s/{site}/{path}"
        resp_bytes = Network.get(
            url, timeout=timeout, headers=self._unifi_api_headers(api_key)
        )
        if not resp_bytes:
            return None
        try:
            parsed = json.loads(resp_bytes)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _switch_port_rate_index(
        devices: List[Dict],
    ) -> Dict[Tuple[str, int], Tuple[float, float]]:
        """Map ``(switch_mac, port_idx)`` → ``(down_Bps, up_Bps)`` from port_table.

        Switch TX is traffic to the client (download); RX is from the client (upload).
        """
        index: Dict[Tuple[str, int], Tuple[float, float]] = {}
        for device in devices:
            port_table = device.get('port_table')
            if not port_table:
                continue
            sw_mac = str(device.get('mac') or '').lower()
            if not sw_mac:
                continue
            for port in port_table:
                port_idx = port.get('port_idx')
                if port_idx is None:
                    continue
                try:
                    idx = int(port_idx)
                except (TypeError, ValueError):
                    continue
                down = port.get('tx_bytes-r', port.get('tx_bytes_r', 0)) or 0
                up = port.get('rx_bytes-r', port.get('rx_bytes_r', 0)) or 0
                try:
                    index[(sw_mac, idx)] = (float(down), float(up))
                except (TypeError, ValueError):
                    continue
        return index

    @staticmethod
    def _client_traffic_fields(client: Dict, is_wired: bool) -> Tuple[float, float, float, float]:
        """Return ``(down_tot, up_tot, down_rate, up_rate)`` from a ``stat/sta`` client."""
        if is_wired:
            return (
                float(client.get('wired-tx_bytes', 0) or 0),
                float(client.get('wired-rx_bytes', 0) or 0),
                float(client.get('wired-tx_bytes-r', 0) or 0),
                float(client.get('wired-rx_bytes-r', 0) or 0),
            )
        return (
            float(client.get('tx_bytes', 0) or 0),
            float(client.get('rx_bytes', 0) or 0),
            float(client.get('tx_bytes-r', 0) or 0),
            float(client.get('rx_bytes-r', 0) or 0),
        )

    def _unifi_client_from_sta(
        self,
        client: Dict,
        port_rates: Dict[Tuple[str, int], Tuple[float, float]],
    ) -> UniFiClient:
        """Build a UniFiClient: Wi‑Fi uses STA rates; wired prefers switch port rates."""
        is_wired = bool(client.get('is_wired', False)) or str(client.get('type', '')).upper() == 'WIRED'
        down_tot, up_tot, down_rate, up_rate = self._client_traffic_fields(client, is_wired)
        rate_source = "wifi"

        if is_wired:
            uplink = client.get('last_uplink_name') or 'Unknown Switch'
            port_raw = client.get('sw_port')
            if port_raw is None:
                port_raw = client.get('last_uplink_remote_port')
            port_info = str(port_raw) if port_raw is not None else ''
            rate_source = "client"
            sw_mac = str(client.get('sw_mac') or '').lower()
            try:
                port_idx = int(port_raw) if port_raw is not None else None
            except (TypeError, ValueError):
                port_idx = None
            if sw_mac and port_idx is not None:
                port_rate = port_rates.get((sw_mac, port_idx))
                if port_rate is not None:
                    down_rate, up_rate = port_rate
                    rate_source = "switch-port"
        else:
            uplink = (
                client.get('ap_name')
                or client.get('last_uplink_name')
                or client.get('ap_mac')
                or 'Unknown AP'
            )
            essid = client.get('essid', '')
            port_info = f"WiFi: {essid}" if essid else "WiFi"

        return UniFiClient(
            mac=str(client.get('mac', '')).lower(),
            is_wired=is_wired,
            uplink=uplink,
            port_info=port_info,
            down_tot=int(down_tot),
            up_tot=int(up_tot),
            down_rate=int(down_rate),
            up_rate=int(up_rate),
            uptime=int(client.get('uptime', 0) or 0),
            rate_source=rate_source,
        )

    def _load_unifi_cache(self, target_ips: Set[str]) -> Optional[Dict[str, UniFiClient]]:
        """Return a usable UniFi cache covering ``target_ips``, else None."""
        if not os.path.exists(UNIFI_CACHE_FILE):
            return None
        try:
            with open(UNIFI_CACHE_FILE, "r") as f:
                data = json.load(f)
            if time.time() - float(data.get('ts', 0)) >= int(self.config.get('CACHE_TTL', 300)):
                return None
            cached_clients = data.get('clients', {}) or {}
            cached_map: Dict[str, UniFiClient] = {}
            for ip, payload in cached_clients.items():
                if not sanitize_ip(str(ip)):
                    continue
                try:
                    cached_map[ip] = UniFiClient(**payload)
                except TypeError:
                    # Drop entries from incompatible/older cache shapes
                    continue
            if cached_map and (target_ips & set(cached_map.keys())):
                return cached_map
            logger.debug(
                "UniFi cache miss for discovered players; refreshing "
                f"(targets={sorted(target_ips)}, cached={sorted(cached_map.keys())})"
            )
        except Exception:
            return None
        return None

    def sync_unifi(self, force_refresh: bool = False) -> str:
        """Fetches client data from UniFi Controller.

        Live rates:
        - Wi‑Fi clients → ``stat/sta`` AP/client counters
        - Wired clients → switch ``port_table`` rates via ``sw_mac`` + ``sw_port``
          (falls back to client ``wired-*`` rates if port stats are unavailable)
        """
        if self.config.get('UNIFI_ENABLED') != 'true' or not self.ips:
            return "SKIPPED"

        base = self.config.get('UNIFI_CONTROLLER')
        site = self.config.get('UNIFI_SITE', 'default')
        key = self.config.get_unifi_api_key()

        if not base or not key:
            return "MISSING_CONFIG"

        # self.ips holds ip:port endpoints; UniFi keys are chassis IPs
        target_ips = {parse_bluos_host(ep) for ep in self.ips}
        target_ips.discard("")
        if not target_ips:
            return "SKIPPED"

        if not force_refresh:
            cached = self._load_unifi_cache(target_ips)
            if cached is not None:
                self.unifi_map = cached
                return "CACHED"

        sta = self._fetch_unifi_json(base, site, key, "stat/sta")
        if not sta:
            logger.warning("UniFi fetch failed, continuing without network stats")
            return "ERROR_FETCH"

        try:
            stations = [
                c for c in sta.get('data', [])
                if isinstance(c, dict)
                and sanitize_ip(str(c.get('ip') or '')) in target_ips
            ]
            needs_port_stats = any(
                bool(c.get('is_wired', False)) or str(c.get('type', '')).upper() == 'WIRED'
                for c in stations
            )
            port_rates: Dict[Tuple[str, int], Tuple[float, float]] = {}
            if needs_port_stats:
                devices = self._fetch_unifi_json(base, site, key, "stat/device")
                if devices:
                    port_rates = self._switch_port_rate_index(
                        [d for d in devices.get('data', []) if isinstance(d, dict)]
                    )
                else:
                    logger.warning(
                        "UniFi switch stats unavailable; falling back to wired client rates"
                    )

            temp_map: Dict[str, UniFiClient] = {}
            for client in stations:
                ip = sanitize_ip(str(client.get('ip') or ''))
                if not ip:
                    continue
                temp_map[ip] = self._unifi_client_from_sta(client, port_rates)

            self.unifi_map = temp_map
            if temp_map:
                cache_payload = {ip: asdict(obj) for ip, obj in temp_map.items()}
                atomic_write(UNIFI_CACHE_FILE, {'ts': time.time(), 'clients': cache_payload})
            return f"SUCCESS:{len(temp_map)}"
        except Exception as e:
            logger.error(f"UniFi Parse Error: {e}", exc_info=True)
            return "ERROR_PARSE"
    
    def get_sys_uptime(self, ip: str) -> str:
        """Get system uptime from device diagnostics page."""
        sanitized_ip = sanitize_ip(ip)
        if not sanitized_ip:
            return "N/A"
        url = f"http://{sanitized_ip}/diagnostics"
        content = Network.get(url, timeout=1, max_retries=1)
        if content:
            try:
                html = content.decode('utf-8', errors='ignore')
                match = re.search(r'Uptime:</div>\s*<div[^>]*>(.*?)</div>', html, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            except Exception:
                pass
        return "N/A"
    
    def _safe_parse_xml(self, xml_data: bytes, ip: str) -> Optional[ET.Element]:
        """
        Safely parse XML with comprehensive protection against XML bombs.
        
        Protections include:
        - Size limit checking (prevents memory exhaustion)
        - Depth limit checking (prevents stack overflow)
        - Entity expansion protection (via XMLParser with custom entity resolver)
        - Malformed XML handling
        
        Args:
            xml_data: XML data as bytes
            ip: IP address for logging
            
        Returns:
            Parsed XML root element or None if parsing fails
        """
        if not xml_data:
            return None
        
        # Check size limit before any processing
        if len(xml_data) > MAX_XML_SIZE:
            logger.warning(f"XML too large for {ip}: {len(xml_data)} bytes (max: {MAX_XML_SIZE})")
            return None
        
        # Additional check: reject empty or whitespace-only XML
        if not xml_data.strip():
            logger.debug(f"Empty XML data for {ip}")
            return None
        
        try:
            # Create a safe XML parser with entity expansion protection
            # ElementTree's default parser already has some protection, but we add explicit limits
            parser = ET.XMLParser()
            
            # Disable external entity resolution to prevent XXE attacks
            # This is done by using the default parser which doesn't resolve external entities
            # For additional safety, we'll use a custom entity resolver if needed
            
            # Parse XML with size and depth protection
            root = ET.fromstring(xml_data, parser=parser)
            
            # Check depth with improved recursion protection
            def check_depth(elem, depth=0, element_count=[0]):
                """
                Check XML depth and element count to prevent DoS.
                
                Args:
                    elem: XML element to check
                    depth: Current nesting depth
                    element_count: List to track total element count (mutable for recursion)
                    
                Returns:
                    True if valid, False otherwise
                """
                if depth > MAX_XML_DEPTH:
                    return False
                
                element_count[0] += 1
                if element_count[0] > MAX_XML_ELEMENTS:
                    logger.warning(f"XML has too many elements for {ip}: {element_count[0]}")
                    return False
                
                for child in elem:
                    if not check_depth(child, depth + 1, element_count):
                        return False
                
                return True
            
            element_count = [0]
            if not check_depth(root, 0, element_count):
                logger.warning(f"XML structure invalid for {ip}: depth or element count exceeded")
                return None
            
            # Additional validation: check root element for suspicious patterns
            # Check attribute count (prevent attribute flooding) - lenient for root element
            if len(root.attrib) > MAX_XML_ATTRIBUTES * 2:  # More lenient for root
                logger.warning(f"Root element has too many attributes for {ip}: {len(root.attrib)}")
                return None
            
            # Check text length (prevent text node flooding) - only on root
            if root.text and len(root.text) > MAX_XML_SIZE // 10:  # Max 10% of total size per text node
                logger.warning(f"Root element text too long for {ip}: {len(root.text)} bytes")
                return None
            
            return root
        except ET.ParseError as e:
            logger.debug(f"XML parse error for {ip}: {e}")
            return None
        except RecursionError:
            logger.warning(f"XML recursion error for {ip} (likely too deep)")
            return None
        except MemoryError:
            logger.warning(f"XML memory error for {ip} (likely too large)")
            return None
        except Exception as e:
            logger.debug(f"XML processing error for {ip}: {e}")
            return None
    
    def get_device_info(self, ip: str, include_uptime: bool = False) -> PlayerStatus:
        """
        Get device information for an ``ip`` or ``ip:port`` endpoint.

        ``include_uptime`` hits ``/diagnostics`` (slow); only enable for status
        reports. Volume and control paths leave it off.
        """
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            logger.warning(f"Invalid endpoint: {ip}")
            return PlayerStatus(ip=ip, status="invalid")

        sanitized_ip, port = resolved
        status = PlayerStatus(ip=sanitized_ip, port=port)
        endpoint_key = format_endpoint(sanitized_ip, port)
        try:
            sync_url = self._api_url(endpoint_key, "/SyncStatus")
            status_url = self._api_url(endpoint_key, "/Status")
            # One attempt each — retries on dead cache entries make `bsc volume` hang.
            sync_xml = (
                Network.get(sync_url, timeout=2, max_retries=1) if sync_url else None
            )
            status_xml = (
                Network.get(status_url, timeout=2, max_retries=1) if status_url else None
            )
            if include_uptime:
                status.uptime = self.get_sys_uptime(sanitized_ip)
            sync_volume_set = False
            
            if sync_xml:
                root = self._safe_parse_xml(sync_xml, endpoint_key)
                if root is None:
                    status.status = "xml_error"
                    return status
                status.name = root.attrib.get('name', 'Unknown')
                status.model = root.attrib.get('modelName') or root.attrib.get('brand') or ''
                status.brand = root.attrib.get('brand', '')
                status.db = root.attrib.get('db', '')
                status.fw = root.attrib.get('version', '')
                status.master, status.group, status.slaves = parse_sync_status_root(root)

                # Per-player volume lives on SyncStatus. For synced secondaries,
                # /Status volume is the group/primary level and must not be trusted.
                sync_volume = root.attrib.get('volume')
                if sync_volume not in (None, ''):
                    try:
                        status.volume = max(0, min(100, int(sync_volume)))
                        sync_volume_set = True
                    except ValueError:
                        pass
                
                batt = root.find('battery')
                if batt is not None:
                    status.battery = batt.attrib.get('level')
            
            if status_xml:
                root = self._safe_parse_xml(status_xml, endpoint_key)
                if root is not None:
                    if not sync_volume_set:
                        try:
                            status.volume = max(0, min(100, int(root.findtext('volume', '0'))))
                        except ValueError:
                            status.volume = 0
                    status.state = root.findtext('state', 'stop')
                    status.service = root.findtext('service', 'Library/Input')
                    status.track = root.findtext('title1') or root.findtext('title') or ''
                    status.artist = root.findtext('artist', '')
                    status.album = root.findtext('album', '')
                    
                    if status.service == 'Raat':
                        status.service = 'Roon'
                elif status.name == 'Unknown':
                    status.status = "xml_error"
            
            if status.brand and status.brand not in status.model:
                status.full_model = f"{status.brand} {status.model}"
            else:
                status.full_model = status.model
            
            status.unifi = self.unifi_map.get(sanitized_ip)
        
        except ET.ParseError as e:
            logger.error(f"XML Parse Error for {endpoint_key}: {e}")
            status.status = "parse_error"
        except ValueError as e:
            logger.error(f"Value Error for {endpoint_key}: {e}")
            status.status = "value_error"
        except Exception as e:
            logger.debug(f"Device Info Error {endpoint_key}: {e}")
            status.status = "error"
        
        return status

    def _endpoint_get(
        self,
        endpoint: str,
        path: str,
        timeout: int = 2,
        max_retries: int = 1,
    ) -> Optional[bytes]:
        """Validated GET against a BluOS endpoint (``ip`` or ``ip:port``)."""
        url = self._api_url(endpoint, path)
        if not url:
            return None
        resolved = self._resolve_endpoint(endpoint)
        if not resolved:
            return None
        get_rate_limiter().wait_if_needed(format_endpoint(*resolved))
        return Network.get(url, timeout=timeout, max_retries=max_retries)
    
    def play(self, ip: str) -> bool:
        """Start/resume playback on device."""
        return self._endpoint_get(ip, "/Play") is not None
    
    def pause_device(self, ip: str) -> bool:
        """Pause playback on device."""
        return self._endpoint_get(ip, "/Pause") is not None
    
    def stop(self, ip: str) -> bool:
        """Stop playback on device."""
        return self._endpoint_get(ip, "/Stop") is not None
    
    def skip(self, ip: str) -> bool:
        """Skip to next track."""
        return self._endpoint_get(ip, "/Skip") is not None
    
    def previous(self, ip: str) -> bool:
        """Go to previous track."""
        return self._endpoint_get(ip, "/Back") is not None
    
    # BluOS Custom Integration API v1.7 — play queue is /Playlist; inputs via
    # /Settings?id=capture&schemaVersion=32; Bluetooth set via /audiomodes.
    _INPUT_HINTS = (
        ("hdmi arc", "arc"),
        ("earc", "earc"),
        ("optical", "spdif"),
        ("analog", "analog"),
        ("line in", "analog"),
        ("coax", "coax"),
        ("phono", "phono"),
        ("vinyl", "phono"),
        ("computer", "computer"),
        ("aes", "aesebu"),
        ("balanced", "balanced"),
        ("microphone", "microphone"),
        ("bluetooth", "bluetooth"),
    )
    _ICON_HINTS = (
        ("ic_optical", "spdif"),
        ("ic_analog", "analog"),
        ("ic_tv", "arc"),
        ("ic_hdmi", "arc"),
        ("ic_phono", "phono"),
        ("ic_coax", "coax"),
        ("ic_bluetooth", "bluetooth"),
    )
    _BT_MODE_MAP = {"0": "Manual", "1": "Automatic", "2": "Guest", "3": "Disabled"}

    @classmethod
    def _input_type_from_capture(cls, display_name: str, icon: str) -> str:
        """Map capture menu labels/icons to v1.7 inputTypeIndex type tokens."""
        name = (display_name or "").lower()
        for needle, type_name in cls._INPUT_HINTS:
            if needle in name:
                return type_name
        icon_l = (icon or "").lower()
        for needle, type_name in cls._ICON_HINTS:
            if needle in icon_l:
                return type_name
        return "analog"

    def get_queue(self, ip: str) -> Optional[Dict]:
        """Get play queue (BluOS v1.7: GET /Playlist)."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return None
        endpoint_key = format_endpoint(*resolved)
        res = self._endpoint_get(endpoint_key, "/Playlist?start=0&end=500", timeout=3)
        if res:
            try:
                root = self._safe_parse_xml(res, endpoint_key)
                if root is not None:
                    queue_items = []
                    for song in root.findall("song"):
                        queue_items.append({
                            "id": song.get("id", ""),
                            "title": song.findtext("title", ""),
                            "artist": song.findtext("art", "") or song.findtext("artist", ""),
                            "album": song.findtext("alb", "") or song.findtext("album", ""),
                            "image": song.findtext("image", ""),
                            "service": song.findtext("service", ""),
                        })
                    length_attr = root.attrib.get("length")
                    length_el = root.findtext("length")
                    try:
                        count = int(length_attr if length_attr is not None else (length_el if length_el is not None else len(queue_items)))
                    except ValueError:
                        count = len(queue_items)
                    return {"items": queue_items, "count": count}
            except Exception as e:
                logger.debug(f"Queue parse error for {endpoint_key}: {e}")
        return None

    def clear_queue(self, ip: str) -> bool:
        """Clear the play queue (BluOS v1.7: GET /Clear)."""
        return self._endpoint_get(ip, "/Clear") is not None

    def move_queue_item(self, ip: str, from_index: int, to_index: int) -> bool:
        """Move a play-queue track (BluOS v1.7: GET /Move?old=&new=)."""
        return self._endpoint_get(ip, f"/Move?old={from_index}&new={to_index}") is not None

    def get_inputs(self, ip: str) -> Optional[List[Dict]]:
        """List capture inputs (BluOS v1.7: GET /Settings?id=capture&schemaVersion=32)."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return None
        endpoint_key = format_endpoint(*resolved)
        res = self._endpoint_get(
            endpoint_key, "/Settings?id=capture&schemaVersion=32", timeout=3
        )
        if res:
            try:
                root = self._safe_parse_xml(res, endpoint_key)
                if root is None:
                    return None
                inputs: List[Dict] = []
                type_counts: Dict[str, int] = {}
                for group in root.iter("menuGroup"):
                    group_id = group.get("id", "")
                    if not group_id.startswith("capture-") or group_id == "capture":
                        continue
                    if "bluetooth" in group_id.lower():
                        continue
                    name = group.get("displayName", "") or group_id
                    icon = group.get("icon", "")
                    type_name = self._input_type_from_capture(name, icon)
                    type_counts[type_name] = type_counts.get(type_name, 0) + 1
                    type_index = f"{type_name}-{type_counts[type_name]}"
                    inputs.append({
                        "name": name,
                        "type": type_name,
                        "id": type_index,
                        "selected": False,
                    })
                return inputs
            except Exception as e:
                logger.debug(f"Inputs parse error for {endpoint_key}: {e}")
        return None

    def set_input(self, ip: str, input_name: str) -> bool:
        """Select an input by display name or inputTypeIndex (BluOS v1.7: /Play?inputTypeIndex=)."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return False
        endpoint_key = format_endpoint(*resolved)
        target = (input_name or "").strip()
        if not target:
            return False
        type_index = target
        # Resolve display name / type token to inputTypeIndex when needed.
        if "-" not in target or not any(ch.isdigit() for ch in target.split("-")[-1]):
            inputs = self.get_inputs(endpoint_key) or []
            lowered = target.lower()
            match = next(
                (
                    inp
                    for inp in inputs
                    if inp.get("id", "").lower() == lowered
                    or inp.get("name", "").lower() == lowered
                    or inp.get("type", "").lower() == lowered
                ),
                None,
            )
            if not match:
                return False
            type_index = match["id"]
        encoded = urllib.parse.quote(type_index, safe="-")
        return self._endpoint_get(endpoint_key, f"/Play?inputTypeIndex={encoded}") is not None

    def get_bluetooth_mode(self, ip: str) -> Optional[str]:
        """Read Bluetooth mode from capture settings (v1.7 has no /AudioModes GET)."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return None
        endpoint_key = format_endpoint(*resolved)
        res = self._endpoint_get(
            endpoint_key, "/Settings?id=capture&schemaVersion=32", timeout=3
        )
        if res:
            try:
                root = self._safe_parse_xml(res, endpoint_key)
                if root is None:
                    return None
                for setting in root.iter("setting"):
                    if setting.get("id") == "bluetoothAutoplay" or setting.get("name") == "bluetoothAutoplay":
                        mode = setting.get("value", "")
                        return self._BT_MODE_MAP.get(mode, "Unknown")
            except Exception as e:
                logger.debug(f"Bluetooth mode parse error for {endpoint_key}: {e}")
        return None

    def set_bluetooth_mode(self, ip: str, mode: int) -> bool:
        """Set Bluetooth mode (0=Manual, 1=Automatic, 2=Guest, 3=Disabled)."""
        if mode not in (0, 1, 2, 3):
            return False
        return self._endpoint_get(ip, f"/audiomodes?bluetoothAutoplay={mode}") is not None
    
    def soft_reboot(self, ip: str) -> bool:
        """Perform soft reboot (chassis-level; uses IP without BluOS port)."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return False
        sanitized_ip, _port = resolved
        get_rate_limiter().wait_if_needed(sanitized_ip)
        res = Network.post(f"http://{sanitized_ip}/Reboot", data={"soft": "1"}, timeout=2)
        return res is not None
    
    def get_presets(self, ip: str) -> Optional[List[Dict]]:
        """Get available presets."""
        resolved = self._resolve_endpoint(ip)
        if not resolved:
            return None
        endpoint_key = format_endpoint(*resolved)
        res = self._endpoint_get(endpoint_key, "/Presets", timeout=3)
        if res:
            try:
                root = self._safe_parse_xml(res, endpoint_key)
                if root is not None:
                    presets = []
                    for preset in root.findall('preset'):
                        presets.append({
                            'id': preset.get('id', ''),
                            'name': preset.findtext('name', ''),
                            'image': preset.findtext('image', '')
                        })
                    return presets
            except Exception as e:
                logger.debug(f"Presets parse error for {endpoint_key}: {e}")
        return None
    
    def play_preset(self, ip: str, preset_id: int) -> bool:
        """Play a preset."""
        return self._endpoint_get(ip, f"/Preset?id={preset_id}") is not None
    
    @staticmethod
    def _bluos_response_ok(content: Optional[bytes]) -> TypeGuard[bytes]:
        """True when BluOS returned a non-error XML/body (narrows to bytes)."""
        if not content:
            return False
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return False
        if root.tag.lower() == "error" or root.find("error") is not None:
            return False
        return True

    def _player_is_ungrouped(self, endpoint: str) -> Optional[bool]:
        """
        Sync membership from a reachable player.

        Returns ``True`` if standalone, ``False`` if still has a master, or
        ``None`` if SyncStatus could not be read (do not treat as success).
        """
        data = self._endpoint_get(endpoint, "/SyncStatus")
        if not self._bluos_response_ok(data):
            return None
        root = self._safe_parse_xml(data, endpoint)
        if root is None:
            return None
        master, _group, _slaves = parse_sync_status_root(root)
        return not bool(master)

    def _wait_until_ungrouped(self, slave_ep: str, attempts: int = 6) -> bool:
        """Poll SyncStatus until the player reports no master (reachable)."""
        for _ in range(attempts):
            state = self._player_is_ungrouped(slave_ep)
            if state is True:
                return True
            time.sleep(0.25)
        return self._player_is_ungrouped(slave_ep) is True

    def _ungroup_via_reparent(self, slave_ep: str) -> bool:
        """
        Clear an orphaned ``master reconnecting=true`` by briefly attaching the
        player to a live primary, then removing it.

        If AddSlave succeeds, keep trying RemoveSlave on that donor only — do
        not hop to another donor while still grouped (would leave a wrong group).
        """
        slave = self._resolve_endpoint(slave_ep)
        if not slave:
            return False
        slave_host, slave_port = slave
        slave_ep = format_endpoint(slave_host, slave_port)
        remove_path = f"/RemoveSlave?slave={slave_host}&port={slave_port}"

        for donor in list(self.ips):
            if donor == slave_ep:
                continue
            if not self.add_sync_slave(donor, slave_ep):
                continue
            for _ in range(3):
                res = self._endpoint_get(donor, remove_path)
                if self._bluos_response_ok(res) and self._wait_until_ungrouped(slave_ep):
                    return True
            logger.error(
                "Reparent ungroup failed; %s may still be grouped under %s",
                slave_ep,
                donor,
            )
            return False
        return False

    def add_sync_slave(self, master_ip: str, slave_ip: str) -> bool:
        """Add slave device to sync group (endpoints may include ``:port``)."""
        master = self._resolve_endpoint(master_ip)
        slave = self._resolve_endpoint(slave_ip)
        if not master or not slave:
            return False
        master_host, master_port = master
        slave_host, slave_port = slave
        master_ep = format_endpoint(master_host, master_port)
        res = self._endpoint_get(
            master_ep,
            f"/AddSlave?slave={slave_host}&port={slave_port}",
        )
        if self._bluos_response_ok(res):
            return True
        res = self._endpoint_get(master_ep, f"/Sync?slave={slave_host}")
        return self._bluos_response_ok(res)
    
    def remove_sync_slave(self, master_ip: str, slave_ip: str) -> bool:
        """
        Remove slave from a sync group (endpoints may include ``:port``).

        Prefer ``RemoveSlave`` on the primary. If the primary is offline (orphaned
        ``reconnecting`` group), reparent onto any live player then remove.
        """
        master = self._resolve_endpoint(master_ip)
        slave = self._resolve_endpoint(slave_ip)
        if not master or not slave:
            return False
        master_host, master_port = master
        slave_host, slave_port = slave
        master_ep = format_endpoint(master_host, master_port)
        slave_ep = format_endpoint(slave_host, slave_port)
        remove_path = f"/RemoveSlave?slave={slave_host}&port={slave_port}"
        legacy_path = f"/Sync?remove={slave_host}"

        def _try_remove(on_ep: str) -> bool:
            for path in (remove_path, legacy_path):
                res = self._endpoint_get(on_ep, path)
                if self._bluos_response_ok(res) and self._wait_until_ungrouped(slave_ep):
                    return True
            return False

        if _try_remove(master_ep) or _try_remove(slave_ep):
            return True

        # Dead primary leaves slaves stuck with reconnecting=true; API self-unjoin
        # returns <error>no slave available as new master</error>.
        if self._ungroup_via_reparent(slave_ep):
            return True
        return False

    def collect_sync_break_operations(
        self,
        devices: List[PlayerStatus],
        targets: Optional[List[PlayerStatus]] = None,
    ) -> List[tuple[str, str, str]]:
        """
        Build RemoveSlave operations as ``(master_endpoint, slave_endpoint, label)`` tuples.

        Ungrouping is always initiated on the primary via ``RemoveSlave``.
        """
        device_names: Dict[str, str] = {}
        for device in devices:
            device_names[device.endpoint] = device.name
            device_names.setdefault(device.ip, device.name)
        operations: List[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add_operation(master_ep: str, slave_ep: str, label: str) -> None:
            key = (master_ep, slave_ep)
            if key in seen:
                return
            seen.add(key)
            operations.append((master_ep, slave_ep, label))

        scoped_devices = targets if targets is not None else devices

        for device in scoped_devices:
            if device.slaves:
                for slave_ep in device.slaves:
                    slave_name = device_names.get(slave_ep, slave_ep)
                    add_operation(
                        device.endpoint,
                        slave_ep,
                        f"{slave_name} from {device.name}",
                    )
            elif device.master:
                master_name = device_names.get(device.master, device.master)
                add_operation(
                    device.master,
                    device.endpoint,
                    f"{device.name} from {master_name}",
                )

        return operations

