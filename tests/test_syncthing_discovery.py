"""Tests for Syncthing Local Discovery Protocol decoding."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import the module directly to avoid triggering services/__init__.py
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "syncthing_service",
    os.path.join(os.path.dirname(__file__), "..", "src", "services", "syncthing_service.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SyncthingService = _mod.SyncthingService


def test_decode_varint_single_byte():
    """Single-byte varints (0-127) decode correctly."""
    data = bytes([0x20])
    value, consumed = SyncthingService._decode_varint(data, 0)
    assert value == 0x20
    assert consumed == 1


def test_decode_varint_multi_byte():
    """Multi-byte varints decode correctly."""
    # 300 = 0xAC 0x02
    data = bytes([0xAC, 0x02])
    value, consumed = SyncthingService._decode_varint(data, 0)
    assert value == 300
    assert consumed == 2


import struct


def test_decode_ldp_announce_valid():
    """Valid LDP packet decodes to device ID bytes + addresses."""
    device_id_bytes = bytes(range(32))
    address = b"tcp://192.168.1.50:22000"

    proto = b"\x0A" + bytes([len(device_id_bytes)]) + device_id_bytes
    proto += b"\x12" + bytes([len(address)]) + address

    packet = struct.pack(">I", 0x2EA7D90B) + proto

    result = SyncthingService.decode_ldp_announce(packet)
    assert result is not None
    raw_id, addresses = result
    assert raw_id == device_id_bytes
    assert addresses == ["tcp://192.168.1.50:22000"]


def test_decode_ldp_announce_bad_magic():
    """Packet with wrong magic number returns None."""
    packet = struct.pack(">I", 0xDEADBEEF) + b"\x0A\x20" + bytes(32)
    result = SyncthingService.decode_ldp_announce(packet)
    assert result is None


def test_decode_ldp_announce_skips_unknown_fields():
    """Packet with field 3 (instance_id) is decoded without error."""
    device_id_bytes = bytes(range(32))
    address = b"tcp://10.0.0.1:22000"

    proto = b"\x0A" + bytes([len(device_id_bytes)]) + device_id_bytes
    proto += b"\x12" + bytes([len(address)]) + address
    proto += b"\x18\x05"  # instance_id = 5

    packet = struct.pack(">I", 0x2EA7D90B) + proto

    result = SyncthingService.decode_ldp_announce(packet)
    assert result is not None
    raw_id, addresses = result
    assert raw_id == device_id_bytes
    assert addresses == ["tcp://10.0.0.1:22000"]


def test_decode_device_id_format():
    """Raw 32 bytes encode to Syncthing's XXXXXXX-XXXXXXX-... format."""
    raw = bytes(32)
    result = SyncthingService.decode_device_id(raw)
    # 8 groups of 7 chars separated by dashes = 56 chars + 7 dashes = 63 chars
    parts = result.split("-")
    assert len(parts) == 8
    assert len(result) == 63
    import re
    assert re.match(r"^[A-Z2-7]{7}(-[A-Z2-7]{7}){7}$", result)


def test_decode_device_id_known_value():
    """Verify against a known Syncthing device ID encoding."""
    import hashlib
    raw = hashlib.sha256(b"").digest()
    result = SyncthingService.decode_device_id(raw)
    # Known correct value for SHA-256("") device ID
    assert result == "4OYMIQU-Y7QOBJR-GX36TEJ-S35ZEQD-T24QPEM-SNZGTFB-ESWMRW6-CSXBKQD"


def test_extract_ip_from_addresses_ipv4():
    """Extracts IPv4 address from tcp:// address list."""
    addresses = ["tcp://192.168.1.50:22000", "quic://192.168.1.50:22000"]
    ip = SyncthingService._extract_ip(addresses)
    assert ip == "192.168.1.50"


def test_extract_ip_skips_ipv6():
    """IPv6 addresses are skipped, returns first IPv4."""
    addresses = [
        "tcp://[fe80::1%25eth0]:22000",
        "tcp://10.0.0.5:22000",
    ]
    ip = SyncthingService._extract_ip(addresses)
    assert ip == "10.0.0.5"


def test_extract_ip_empty():
    """Empty address list returns empty string."""
    assert SyncthingService._extract_ip([]) == ""


def test_extract_ip_skips_zero_address():
    """Addresses like tcp://0.0.0.0:22000 are skipped."""
    addresses = ["tcp://0.0.0.0:22000", "tcp://192.168.1.5:22000"]
    ip = SyncthingService._extract_ip(addresses)
    assert ip == "192.168.1.5"


import socket
from unittest.mock import patch, MagicMock


def test_discover_local_devices_filters_own_id():
    """Own device ID is excluded from results."""
    device_id_bytes = bytes(range(32))
    address = b"tcp://192.168.1.50:22000"
    proto = b"\x0A" + bytes([len(device_id_bytes)]) + device_id_bytes
    proto += b"\x12" + bytes([len(address)]) + address
    packet = struct.pack(">I", 0x2EA7D90B) + proto

    own_id = SyncthingService.decode_device_id(device_id_bytes)

    mock_sock = MagicMock()
    mock_sock.recvfrom = MagicMock(
        side_effect=[(packet, ("192.168.1.50", 21027)), socket.timeout]
    )

    with patch("socket.socket", return_value=mock_sock):
        results = SyncthingService.discover_local_devices(
            timeout=1, own_device_id=own_id
        )

    assert len(results) == 0


def test_discover_local_devices_returns_found_device():
    """Discovered device appears in results with device_id and ip."""
    device_id_bytes = bytes(range(32))
    address = b"tcp://192.168.1.99:22000"
    proto = b"\x0A" + bytes([len(device_id_bytes)]) + device_id_bytes
    proto += b"\x12" + bytes([len(address)]) + address
    packet = struct.pack(">I", 0x2EA7D90B) + proto

    mock_sock = MagicMock()
    mock_sock.recvfrom = MagicMock(
        side_effect=[(packet, ("192.168.1.99", 21027)), socket.timeout]
    )

    with patch("socket.socket", return_value=mock_sock):
        results = SyncthingService.discover_local_devices(
            timeout=1, own_device_id="DIFFERENT-DEVICE-ID"
        )

    assert len(results) == 1
    assert results[0]["ip"] == "192.168.1.99"
    assert results[0]["device_id"] == SyncthingService.decode_device_id(device_id_bytes)


def test_discover_local_devices_deduplicates():
    """Duplicate broadcasts from same device produce single result."""
    device_id_bytes = bytes(range(32))
    address = b"tcp://192.168.1.99:22000"
    proto = b"\x0A" + bytes([len(device_id_bytes)]) + device_id_bytes
    proto += b"\x12" + bytes([len(address)]) + address
    packet = struct.pack(">I", 0x2EA7D90B) + proto

    mock_sock = MagicMock()
    mock_sock.recvfrom = MagicMock(
        side_effect=[
            (packet, ("192.168.1.99", 21027)),
            (packet, ("192.168.1.99", 21027)),
            socket.timeout,
        ]
    )

    with patch("socket.socket", return_value=mock_sock):
        results = SyncthingService.discover_local_devices(
            timeout=1, own_device_id="DIFFERENT-DEVICE-ID"
        )

    assert len(results) == 1
