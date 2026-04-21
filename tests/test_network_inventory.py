"""Tests for network inventory management."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hermesoptimizer.catalog import init_db
from hermesoptimizer.network.inventory import (
    reserve_port,
    forbid_port,
    release_port,
    list_ports,
    is_port_allowed,
    add_ip,
    list_ips,
    is_localhost,
    ensure_forbidden_ports,
)


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    init_db(path)
    yield path
    path.unlink(missing_ok=True)


class TestForbiddenPorts:
    def test_forbid_port_3000(self, db_path: Path) -> None:
        r = forbid_port(db_path, 3000)
        assert r.port == 3000
        assert r.status == "forbidden"

    def test_forbid_port_8080(self, db_path: Path) -> None:
        r = forbid_port(db_path, 8080)
        assert r.port == 8080
        assert r.status == "forbidden"

    def test_reserve_forbidden_port_3000_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="Port 3000 is permanently forbidden"):
            reserve_port(db_path, 3000)

    def test_reserve_forbidden_port_8080_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="Port 8080 is permanently forbidden"):
            reserve_port(db_path, 8080)

    def test_release_forbidden_port_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="Port 3000 is permanently forbidden"):
            release_port(db_path, 3000)

    def test_is_port_allowed_forbidden(self, db_path: Path) -> None:
        ensure_forbidden_ports(db_path)
        assert is_port_allowed(db_path, 3000) is False
        assert is_port_allowed(db_path, 8080) is False

    def test_list_ports_includes_forbidden(self, db_path: Path) -> None:
        ports = list_ports(db_path)
        values = {p.port for p in ports}
        assert 3000 in values
        assert 8080 in values


class TestReservePort:
    def test_reserve_available_port(self, db_path: Path) -> None:
        r = reserve_port(db_path, 9200, purpose="test server")
        assert r.port == 9200
        assert r.status == "reserved"
        assert r.purpose == "test server"

    def test_reserve_out_of_range_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="out of allowed range"):
            reserve_port(db_path, 1024)
        with pytest.raises(ValueError, match="out of allowed range"):
            reserve_port(db_path, 70000)

    def test_reserve_twice_upserts(self, db_path: Path) -> None:
        reserve_port(db_path, 9201, purpose="first")
        reserve_port(db_path, 9201, purpose="second")
        ports = list_ports(db_path, status="reserved")
        assert len(ports) == 1
        assert ports[0].purpose == "second"

    def test_release_port(self, db_path: Path) -> None:
        reserve_port(db_path, 9202)
        release_port(db_path, 9202)
        assert is_port_allowed(db_path, 9202) is True

    def test_is_port_allowed_reserved(self, db_path: Path) -> None:
        reserve_port(db_path, 9203)
        assert is_port_allowed(db_path, 9203) is False

    def test_is_port_allowed_available(self, db_path: Path) -> None:
        ensure_forbidden_ports(db_path)
        assert is_port_allowed(db_path, 9204) is True

    def test_list_ports_filter_status(self, db_path: Path) -> None:
        reserve_port(db_path, 9205)
        reserved = list_ports(db_path, status="reserved")
        forbidden = list_ports(db_path, status="forbidden")
        assert len(reserved) == 1
        assert reserved[0].port == 9205
        assert 3000 in {p.port for p in forbidden}


class TestIPManagement:
    def test_add_ip(self, db_path: Path) -> None:
        ip = add_ip(db_path, "192.168.1.100", ip_type="local_v4", purpose="LAN")
        assert ip.ip == "192.168.1.100"
        assert ip.ip_type == "local_v4"

    def test_list_ips(self, db_path: Path) -> None:
        add_ip(db_path, "10.0.0.5", ip_type="vpn", purpose="VPN")
        add_ip(db_path, "203.0.113.1", ip_type="public", purpose="Public")
        all_ips = list_ips(db_path)
        assert len(all_ips) == 2

    def test_list_ips_filter_type(self, db_path: Path) -> None:
        add_ip(db_path, "10.0.0.5", ip_type="vpn", purpose="VPN")
        add_ip(db_path, "192.168.1.1", ip_type="local_v4", purpose="LAN")
        vpn_ips = list_ips(db_path, ip_type="vpn")
        assert len(vpn_ips) == 1
        assert vpn_ips[0].ip == "10.0.0.5"


class TestIsLocalhost:
    def test_localhost(self) -> None:
        assert is_localhost("localhost") is True
        assert is_localhost("127.0.0.1") is True
        assert is_localhost("127.0.0.2") is True
        assert is_localhost("::1") is True

    def test_not_localhost(self) -> None:
        assert is_localhost("192.168.1.1") is False
        assert is_localhost("10.0.0.1") is False
        assert is_localhost("0.0.0.0") is False
