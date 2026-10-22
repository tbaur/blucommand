#!/usr/bin/env python3
"""Tests for BluOS sync status parsing and group operations."""
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from blucommand.controller import (
    BluOSController,
    parse_bluos_host,
    parse_bluos_endpoint,
    parse_sync_status_root,
)
from blucommand.models import PlayerStatus


class TestParseBluosHost:
    """Test BluOS host/IP parsing."""

    def test_plain_ip(self):
        assert parse_bluos_host("192.168.1.32") == "192.168.1.32"

    def test_ip_with_port(self):
        assert parse_bluos_host("192.168.1.32:11000") == "192.168.1.32"

    def test_empty(self):
        assert parse_bluos_host("") == ""
        assert parse_bluos_host(None) == ""


class TestParseBluosEndpoint:
    """Test BluOS endpoint normalization."""

    def test_plain_ip_defaults_port(self):
        assert parse_bluos_endpoint("192.168.1.32") == "192.168.1.32:11000"

    def test_ip_with_port(self):
        assert parse_bluos_endpoint("192.168.1.32:11010") == "192.168.1.32:11010"

    def test_empty(self):
        assert parse_bluos_endpoint("") == ""
        assert parse_bluos_endpoint(None) == ""


class TestParseSyncStatusRoot:
    """Test SyncStatus XML parsing."""

    def test_primary_with_group_and_slaves(self):
        root = ET.fromstring(
            b'<SyncStatus group="Zone One+Player A" name="Zone One">'
            b'<slave id="192.168.1.20" port="11000"/>'
            b"</SyncStatus>"
        )
        master, group, slaves = parse_sync_status_root(root)
        assert master == ""
        assert group == "Zone One+Player A"
        assert slaves == ["192.168.1.20:11000"]

    def test_ci_secondary_slave_port(self):
        root = ET.fromstring(
            b'<SyncStatus name="Zone One">'
            b'<slave id="192.168.1.30" port="11010"/>'
            b"</SyncStatus>"
        )
        _master, _group, slaves = parse_sync_status_root(root)
        assert slaves == ["192.168.1.30:11010"]

    def test_slave_with_master_child_element(self):
        root = ET.fromstring(
            b'<SyncStatus name="Player A">'
            b'<master port="11000">192.168.1.32</master>'
            b"</SyncStatus>"
        )
        master, group, slaves = parse_sync_status_root(root)
        assert master == "192.168.1.32:11000"
        assert group == ""
        assert slaves == []

    def test_legacy_master_attribute(self):
        root = ET.fromstring(b'<sync name="Slave" master="192.168.1.100"/>')
        master, group, slaves = parse_sync_status_root(root)
        assert master == "192.168.1.100:11000"
        assert group == ""
        assert slaves == []


class TestCollectSyncBreakOperations:
    """Test sync break operation planning."""

    @pytest.fixture
    def controller(self):
        with patch("blucommand.controller.Config"):
            return BluOSController()

    def test_break_all_from_primary(self, controller):
        devices = [
            PlayerStatus(
                ip="192.168.1.32",
                name="Zone One",
                group="Zone One+Player A",
                slaves=["192.168.1.20:11000"],
            ),
            PlayerStatus(
                ip="192.168.1.20",
                name="Player A",
                master="192.168.1.32:11000",
            ),
        ]

        operations = controller.collect_sync_break_operations(devices)
        assert operations == [
            (
                "192.168.1.32:11000",
                "192.168.1.20:11000",
                "Player A from Zone One",
            ),
        ]

    def test_break_single_slave_target(self, controller):
        devices = [
            PlayerStatus(
                ip="192.168.1.32",
                name="Zone One",
                slaves=["192.168.1.20:11000"],
            ),
            PlayerStatus(
                ip="192.168.1.20",
                name="Player A",
                master="192.168.1.32:11000",
            ),
        ]
        target = [devices[1]]

        operations = controller.collect_sync_break_operations(devices, target)
        assert operations == [
            (
                "192.168.1.32:11000",
                "192.168.1.20:11000",
                "Player A from Zone One",
            ),
        ]

    def test_break_primary_target(self, controller):
        devices = [
            PlayerStatus(
                ip="192.168.1.32",
                name="Zone One",
                slaves=["192.168.1.20:11000"],
            ),
            PlayerStatus(
                ip="192.168.1.20",
                name="Player A",
                master="192.168.1.32:11000",
            ),
        ]
        target = [devices[0]]

        operations = controller.collect_sync_break_operations(devices, target)
        assert operations == [
            (
                "192.168.1.32:11000",
                "192.168.1.20:11000",
                "Player A from Zone One",
            ),
        ]

    @patch("blucommand.controller.Network.get")
    def test_get_device_info_reads_master_child(self, mock_network, controller):
        sync_xml = (
            b'<SyncStatus name="Player A">'
            b"<master>192.168.1.32:11000</master>"
            b"</SyncStatus>"
        )
        status_xml = b"<status><volume>20</volume><state>play</state></status>"
        mock_network.side_effect = [sync_xml, status_xml, None]

        status = controller.get_device_info("192.168.1.20")
        assert status.master == "192.168.1.32:11000"
        assert status.group == ""
        assert status.slaves == []
        assert status.port == 11000
        assert status.endpoint == "192.168.1.20:11000"

    @patch("blucommand.controller.Network.get")
    def test_get_device_info_ci_secondary_port(self, mock_network, controller):
        sync_xml = (
            b'<SyncStatus name="Player A" modelName="CI S2" brand="NAD" '
            b'id="192.168.1.30:11010" channelMode="mono"/>'
        )
        status_xml = b"<status><volume>49</volume><state>stream</state></status>"
        mock_network.side_effect = [sync_xml, status_xml, None]

        status = controller.get_device_info("192.168.1.30:11010")
        assert status.name == "Player A"
        assert status.port == 11010
        assert status.endpoint == "192.168.1.30:11010"
        assert status.volume == 49
