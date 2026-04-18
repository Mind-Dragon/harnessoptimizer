from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
import json
import re

from .classify import classify_key
from .fingerprint import fingerprint_secret

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Docling integration
# ---------------------------------------------------------------------------

#: Regex pattern to detect key=value lines in documents/images.
#: Matches KEY=value or KEY="value" or KEY='value'.
_KEY_VALUE_RE = re.compile(
    r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$'
)


def _extract_entries_from_text(
    text: str,
    source_path: Path,
    source_kind: str,
) -> list[VaultEntry]:
    """Extract VaultEntry records from raw text using key=value regex."""
    entries: list[VaultEntry] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _KEY_VALUE_RE.match(line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            # Strip surrounding quotes from value
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if key and value:
                classification = classify_key(key)
                is_encrypted = classification == "secret"
                plaintext_value = None if is_encrypted else value
                entries.append(
                    VaultEntry(
                        source_path=source_path,
                        source_kind=source_kind,
                        key_name=key,
                        fingerprint=fingerprint_secret(value),
                        is_encrypted=is_encrypted,
                        plaintext_value=plaintext_value,
                    )
                )
    return entries


def _parse_docx_file(path: Path) -> list[VaultEntry]:
    """Parse a DOCX file for KEY=value pairs via Docling text extraction."""
    from docling.document_converter import DocumentConverter

    entries: list[VaultEntry] = []
    if not path.exists():
        return entries
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        text = result.document.export_to_text()
        entries = _extract_entries_from_text(text, path, "docx")
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
    return entries


def _parse_pdf_file(path: Path) -> list[VaultEntry]:
    """Parse a PDF file for KEY=value pairs via Docling text extraction."""
    from docling.document_converter import DocumentConverter

    entries: list[VaultEntry] = []
    if not path.exists():
        return entries
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        text = result.document.export_to_text()
        entries = _extract_entries_from_text(text, path, "pdf")
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
    return entries


def _parse_image_file(path: Path) -> list[VaultEntry]:
    """Parse an image file for KEY=value pairs via Docling OCR."""
    from docling.document_converter import DocumentConverter

    entries: list[VaultEntry] = []
    if not path.exists():
        return entries
    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        text = result.document.export_to_text()
        entries = _extract_entries_from_text(text, path, "image")
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
    return entries


@dataclass(frozen=True, slots=True)
class VaultEntry:
    source_path: Path
    source_kind: str
    key_name: str
    fingerprint: str
    is_encrypted: bool = False
    encrypted_value: str | None = None
    plaintext_value: str | None = None


@dataclass(slots=True)
class VaultInventory:
    roots: list[Path] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    entries: list[VaultEntry] = field(default_factory=list)


def default_vault_roots(home: Path | None = None) -> list[Path]:
    base = home or Path.home()
    return [base / ".vault"]


def discover_vault_files(
    roots: Iterable[Path],
    *,
    skip_dirs: frozenset[str] = frozenset({'.venv', '.git', '__pycache__', 'node_modules', '.pytest_cache', '.tox', '.mypy_cache'}),
) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            # Skip paths where any path component is in skip_dirs
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)


def _parse_env_file(path: Path) -> list[VaultEntry]:
    entries: list[VaultEntry] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        classification = classify_key(key)
        is_encrypted = classification == "secret"
        plaintext_value = None if is_encrypted else value
        entries.append(
            VaultEntry(
                source_path=path,
                source_kind="env",
                key_name=key,
                fingerprint=fingerprint_secret(value),
                is_encrypted=is_encrypted,
                plaintext_value=plaintext_value,
            )
        )
    return entries


def _parse_yaml_file(path: Path) -> list[VaultEntry]:
    """Parse YAML files for key-value pairs. Handles nested keys via dot notation."""
    import yaml

    entries: list[VaultEntry] = []
    content = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return entries

    if not isinstance(data, dict):
        return entries

    def extract_keys(obj: dict, prefix: str = "") -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        if not isinstance(obj, dict):
            return pairs
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                pairs.extend(extract_keys(value, full_key))
            elif isinstance(value, str) and value:
                # Skip non-secret-looking values
                if value.lower() in ("true", "false", "null", "none"):
                    continue
                if value.startswith("/") or value.startswith("./"):
                    continue
                pairs.append((full_key, value))
        return pairs

    for key, value in extract_keys(data):
        classification = classify_key(key)
        is_encrypted = classification == "secret"
        plaintext_value = None if is_encrypted else value
        entries.append(
            VaultEntry(
                source_path=path,
                source_kind="yaml",
                key_name=key,
                fingerprint=fingerprint_secret(value),
                is_encrypted=is_encrypted,
                plaintext_value=plaintext_value,
            )
        )
    return entries


def _parse_json_file(path: Path) -> list[VaultEntry]:
    """Parse JSON files for string key-value pairs. Handles nested keys via dot notation."""
    entries: list[VaultEntry] = []
    content = path.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return entries

    # Guard: skip if root is not a dict (e.g., JSON list-root files)
    if not isinstance(data, dict):
        return entries

    def extract_keys(obj: dict, prefix: str = "") -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                pairs.extend(extract_keys(value, full_key))
            elif isinstance(value, str) and value:
                # Skip non-secret-looking values
                if value.lower() in ("true", "false", "null", "none"):
                    continue
                if value.startswith("/") or value.startswith("./"):
                    continue
                pairs.append((full_key, value))
        return pairs
    
    for key, value in extract_keys(data):
        classification = classify_key(key)
        is_encrypted = classification == "secret"
        plaintext_value = None if is_encrypted else value
        entries.append(
            VaultEntry(
                source_path=path,
                source_kind="json",
                key_name=key,
                fingerprint=fingerprint_secret(value),
                is_encrypted=is_encrypted,
                plaintext_value=plaintext_value,
            )
        )
    return entries


def _parse_toml_file(path: Path) -> list[VaultEntry]:
    """Parse TOML files for key-value pairs. Handles nested tables via dot notation."""
    import tomllib

    entries: list[VaultEntry] = []
    content = path.read_bytes()
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except Exception:
        return entries

    def extract_keys(obj: dict, prefix: str = "") -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        if not isinstance(obj, dict):
            return pairs
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                # Check if it's a table (has nested content) or just a value
                pairs.extend(extract_keys(value, full_key))
            elif isinstance(value, str) and value:
                # Skip non-secret-looking values
                if value.lower() in ("true", "false", "null", "none"):
                    continue
                if value.startswith("/") or value.startswith("./"):
                    continue
                pairs.append((full_key, value))
        return pairs

    for key, value in extract_keys(data):
        classification = classify_key(key)
        is_encrypted = classification == "secret"
        plaintext_value = None if is_encrypted else value
        entries.append(
            VaultEntry(
                source_path=path,
                source_kind="toml",
                key_name=key,
                fingerprint=fingerprint_secret(value),
                is_encrypted=is_encrypted,
                plaintext_value=plaintext_value,
            )
        )
    return entries


def _parse_shell_profile(path: Path) -> list[VaultEntry]:
    """Parse shell profile files for export statements (export KEY=value)."""
    entries: list[VaultEntry] = []
    content = path.read_text(encoding="utf-8")
    
    # Match export KEY=value or export KEY="value" or export KEY='value'
    export_pattern = re.compile(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']?([^"\']*)["\']?\s*$')
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = export_pattern.match(line)
        if match:
            key = match.group(1)
            value = match.group(2)
            if key and value:
                classification = classify_key(key)
                is_encrypted = classification == "secret"
                plaintext_value = None if is_encrypted else value
                entries.append(
                    VaultEntry(
                        source_path=path,
                        source_kind="shell",
                        key_name=key,
                        fingerprint=fingerprint_secret(value),
                        is_encrypted=is_encrypted,
                        plaintext_value=plaintext_value,
                    )
                )
    return entries


def _parse_csv_file(path: Path) -> list[VaultEntry]:
    """Parse CSV files for key-value pairs with labeled columns.
    
    Expects a header row with at least two columns: one labeled 'key' (or similar)
    and one labeled 'secret' (or similar). Values in the secret column are used
    as the secret values. Supports quoted values.
    """
    entries: list[VaultEntry] = []
    if not path.exists():
        return entries
    
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    if len(lines) < 2:
        return entries
    
    # Find header row - skip comment and empty lines
    header_idx = None
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Found the header row
        header_idx = i
        header = line.split(",")
        header = [h.strip().strip('"').strip("'").lower() for h in header]
        break
    
    if header_idx is None:
        return entries
    
    # Find key and secret column indices
    key_idx = None
    secret_idx = None
    for i, col in enumerate(header):
        if col in ("key", "name", "variable", "env"):
            key_idx = i
        elif col in ("secret", "value", "password", "pass", "token", "cred", "access_key", "api_key", "apikey", "private_key", "secret_key"):
            secret_idx = i
    
    if key_idx is None or secret_idx is None:
        return entries
    
    # Parse data rows (skip header row and any comment/empty lines)
    # When labeled columns are detected, the column labels establish the contract:
    # no extra heuristic filtering (value length, key name patterns) is needed.
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Simple CSV parsing - handle quoted values
        cols = _split_csv_line(line)
        if len(cols) > max(key_idx, secret_idx):
            key = cols[key_idx].strip().strip('"').strip("'")
            value = cols[secret_idx].strip().strip('"').strip("'")
            if key and value:
                classification = classify_key(key)
                is_encrypted = classification == "secret"
                plaintext_value = None if is_encrypted else value
                entries.append(
                    VaultEntry(
                        source_path=path,
                        source_kind="csv",
                        key_name=key,
                        fingerprint=fingerprint_secret(value),
                        is_encrypted=is_encrypted,
                        plaintext_value=plaintext_value,
                    )
                )
    return entries


def _split_csv_line(line: str) -> list[str]:
    """Split a CSV line, respecting quoted values."""
    result: list[str] = []
    current = ""
    in_quotes = False
    quote_char = None
    for char in line:
        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
        elif char == "," and not in_quotes:
            result.append(current)
            current = ""
        else:
            current += char
    result.append(current)
    return result


def _parse_txt_file(
    path: Path,
    key_pattern: re.Pattern[str] | None = None,
) -> list[VaultEntry]:
    """Parse TXT files for KEY=value pairs via regex-based detection.

    Uses a configurable key_pattern regex to determine what counts as a credential key.
    The pattern should have at least one capture group for the key name; if a second
    capture group is present it will be used as the value, otherwise the value is
    extracted after the '=' character.

    Args:
        path: Path to the TXT file to parse.
        key_pattern: Optional regex pattern for key detection. If None, uses the
            default _KEY_VALUE_RE pattern. The pattern should match lines of the form
            KEY=value and capture the key name. Example: r'^(API_[A-Z0-9_]+)\\s*=\\s*(.+)$'
    """
    entries: list[VaultEntry] = []
    if not path.exists():
        return entries

    content = path.read_text(encoding="utf-8")

    # Use provided pattern or default
    pattern = key_pattern if key_pattern is not None else _KEY_VALUE_RE

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        # Determine key and value based on number of capture groups
        if match.lastindex and match.lastindex >= 2:
            # Two groups: group(1)=key, group(2)=value
            key = match.group(1)
            value = match.group(2)
            # Strip surrounding quotes from value
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
        else:
            # Single group: extract key from line, use group(1) as value
            if "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            value = match.group(1)
            # Strip quotes from value
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
        if not key or not value:
            continue
        classification = classify_key(key)
        is_encrypted = classification == "secret"
        plaintext_value = None if is_encrypted else value
        entries.append(
            VaultEntry(
                source_path=path,
                source_kind="txt",
                key_name=key,
                fingerprint=fingerprint_secret(value),
                is_encrypted=is_encrypted,
                plaintext_value=plaintext_value,
            )
        )
    return entries


def build_vault_inventory(
    roots: Iterable[Path],
    *,
    key_pattern: re.Pattern[str] | None = None,
) -> VaultInventory:
    root_list = [Path(root) for root in roots]
    files = discover_vault_files(root_list)
    entries: list[VaultEntry] = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".env":
            entries.extend(_parse_env_file(path))
        elif suffix in (".yaml", ".yml"):
            entries.extend(_parse_yaml_file(path))
        elif suffix == ".json":
            entries.extend(_parse_json_file(path))
        elif suffix == ".toml":
            entries.extend(_parse_toml_file(path))
        elif suffix == ".csv":
            entries.extend(_parse_csv_file(path))
        elif suffix == ".txt":
            entries.extend(_parse_txt_file(path, key_pattern=key_pattern))
        elif path.name in (".bashrc", ".zshrc", ".profile", ".bash_profile"):
            entries.extend(_parse_shell_profile(path))
        elif suffix == ".docx":
            entries.extend(_parse_docx_file(path))
        elif suffix == ".pdf":
            entries.extend(_parse_pdf_file(path))
        elif suffix in (".png", ".jpg", ".jpeg"):
            entries.extend(_parse_image_file(path))
    return VaultInventory(roots=root_list, files=files, entries=entries)
