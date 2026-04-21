"""Tests for network config validation."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hermesoptimizer.catalog import init_db
from hermesoptimizer.network.validator import validate_config_ports, validate_config_ips
from hermesoptimizer.network.inventory import reserve_port


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    init_db(path)
    yield path
    path.unlink(missing_ok=True)


class TestValidateConfigPorts:
    def test_detects_port_3000(self, db_path: Path) -> None:
        config = {"server": {"port": 3000}}
        findings = validate_config_ports(config, db_path)
        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"
        assert findings[0].kind == "forbidden_port"

    def test_detects_port_8080(self, db_path: Path) -> None:
        config = {"app": {"listen": 8080}}
        findings = validate_config_ports(config, db_path)
        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"

    def test_detects_reserved_port(self, db_path: Path) -> None:
        reserve_port(db_path, 9200, purpose="test")
        config = {"server": {"port": 9200}}
        findings = validate_config_ports(config, db_path)
        assert len(findings) == 1
        assert findings[0].kind == "reserved_port"

    def test_detects_port_in_string(self, db_path: Path) -> None:
        config = {"url": "http://localhost:3000/path"}
        findings = validate_config_ports(config, db_path)
        assert any(f.kind == "forbidden_port" for f in findings)

    def test_allows_good_port(self, db_path: Path) -> None:
        config = {"server": {"port": 9201}}
        findings = validate_config_ports(config, db_path)
        assert len(findings) == 0

    def test_warns_out_of_range(self, db_path: Path) -> None:
        config = {"server": {"port": 1024}}
        findings = validate_config_ports(config, db_path)
        assert len(findings) == 1
        assert findings[0].kind == "out_of_range_port"


class TestValidateConfigIPs:
    def test_detects_localhost(self) -> None:
        config = {"host": "localhost"}
        findings = validate_config_ips(config)
        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"
        assert findings[0].kind == "localhost_forbidden"

    def test_detects_127_0_0_1(self) -> None:
        config = {"server": {"bind": "127.0.0.1"}}
        findings = validate_config_ips(config)
        assert len(findings) == 1
        assert findings[0].kind == "localhost_forbidden"

    def test_detects_127_x_x_x(self) -> None:
        config = {"host": "127.0.0.2"}
        findings = validate_config_ips(config)
        assert len(findings) == 1

    def test_detects_localhost_in_url(self) -> None:
        config = {"api": {"base_url": "http://localhost:8080/api"}}
        findings = validate_config_ips(config)
        assert any(f.kind == "localhost_in_url" for f in findings)

    def test_allows_real_ip(self) -> None:
        config = {"host": "192.168.1.100"}
        findings = validate_config_ips(config)
        assert len(findings) == 0

    def test_allows_vpn_ip(self) -> None:
        config = {"host": "10.0.0.5"}
        findings = validate_config_ips(config)
        assert len(findings) == 0
