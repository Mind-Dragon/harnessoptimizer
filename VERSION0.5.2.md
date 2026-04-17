# Hermes Optimizer Release 0.5.2

## Status

Planned. Vault operational iteration — live validation, broader sources, actual writes, rotation execution.

## Goal

Make the vault operational: move from read-only inventory and planning to live credential validation, broader source format support, actual write-back execution, and rotation automation.

## What v0.5.1 delivered

- vault package with inventory, fingerprinting, validation, dedup, rotation tracking, bridge planning
- `vault-audit` CLI command
- Hermes vault workflow skill
- provider-validation adapter hook (ready for live backends)
- target-format-aware write-back planning (.env and YAML)
- tests for read-only contract

## What v0.5.2 adds

### Live provider validation
- implement status_provider backends for major providers (AWS, GCP, Azure, or HTTP-based checks)
- call live APIs to verify credentials actually work
- mark credentials as active/expired/degraded based on real responses
- cache validation results with timestamps

### Broader source parsing
- parse YAML config files (nested key resolution)
- parse JSON config files
- parse shell profile exports (~/.bashrc, ~/.zshrc, ~/.profile)
- parse CSV files (key-value pairs, labeled columns)
- parse TXT files (regex-based key=value detection)
- parse DOCX files via Docling (structured document extraction)
- parse PDF files via Docling (text + table extraction)
- parse images/screenshots via Docling OCR (credential photos, scans)
- keep .env parsing as the baseline

### Docling integration
- use Docling for document and image-based credential extraction
- support for DOCX, PDF, and image formats (PNG, JPG)
- OCR fallback for screenshot-based credentials
- structured output mapping to VaultEntry format
- regex filtering for key pattern detection (API_KEY=, SECRET=, etc.)

### Actual write-back execution
- implement write-back for .env format (opt-in, with confirmation)
- implement write-back for YAML format (opt-in, with confirmation)
- add `--confirm` flag for safe changes
- preserve existing files by default
- log all mutations for audit trail

### Rotation automation
- add rotation execution hooks (not just detection)
- provider-specific rotation adapters (AWS, GCP, etc.)
- rotation event logging with timestamps
- rollback support for failed rotations

## Safety contract

- live validation does not store plaintext secrets
- write-back requires explicit opt-in and confirmation
- rotation automation is opt-in per-provider
- all mutations are logged for audit
- rollback is available for rotation operations

## v0.5.2 focus

1. implement live provider validation backends
2. extend source parsing to YAML, JSON, shell profiles
3. implement write-back execution with confirmation flow
4. add rotation automation hooks
5. expand tests for all new surfaces

## Source of truth

- `TODO.md` for the active execution queue
- `ROADMAP.md` for the release sequence
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and gates
- v0.5.1 vault package as the foundation
