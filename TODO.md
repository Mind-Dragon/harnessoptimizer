# Hermes Optimizer /todo — v0.5.1 Vault Follow-up (closed)

**Status: Closed.** This queue completed the v0.5.1 vault follow-up slice.

## Source of truth
- `ROADMAP.md` v0.5.0/v0.5.1 vault-management section
- `ARCHITECTURE.md` for system shape and file layout expectations
- `GUIDELINE.md` for release gates and success criteria
- `VERSION0.5.1.md` for the archived release-note / transition note

## What closed in v0.5.0
- vault package skeleton exists under `src/hermesoptimizer/vault/`
- inventory, fingerprinting, validation, dedup, rotation hints, and bridge planning exist
- tests cover the current read-only contract
- `tmp/.vault` is the repo-local fixture area and `~/.vault` remains off-limits

## v0.5.1 goal
Turn the existing vault primitives into a harness-usable workflow with clearer docs, a dedicated skill, and a usable CLI surface while preserving the non-destructive contract.

## Scope
- document how the vault works end to end
- explain how Hermes loads and uses a vault skill
- add a user-facing vault audit/report path
- harden validation and bridge planning boundaries
- keep the real vault read-only by default

## Vault safety contract
- production installs read from `~/.vault`
- tests and prototype work use repo-local `tmp/.vault` or temp fixtures
- the code must never delete the user's `~/.vault`
- any write-back path must be opt-in and preserve existing files by default

## Acceptance criteria
- v0.5.0 is explicitly closed out in the release docs
- v0.5.1 docs explain inventory, fingerprinting, validation, dedup, rotation, and bridge planning
- a Hermes skill exists for vault workflows and says when to load it
- the CLI exposes a vault audit/report path that does not require importing internals by hand
- provider validation points are clearly named and remain non-destructive
- write-back planning stays opt-in and format-specific
- tests cover the no-touch `~/.vault` contract and the supported source shapes

## Non-goals
- auto-rotation
- mutating vault files without explicit operator opt-in
- replacing dedicated secret managers
- storing plaintext secrets in the catalog

## Completed tasks
1. archive the v0.5.0 release note and point the active queue at v0.5.1
2. write the v0.5.1 vault contract docs
3. create the Hermes vault skill
4. add CLI wiring for vault audit/report flows
5. tighten provider-validation and write-back boundaries
6. expand tests around source shapes and the no-touch contract
7. run `pytest -q` and keep `git diff --check` clean

All seven items are now complete and verified.

## v0.5.2 completion status

### Completed
- live provider validation backends (HTTP-based, mockable)
- broader source parsing (YAML, JSON, shell profiles, CSV, TXT, DOCX, PDF, images via Docling)
- rotation automation hooks (adapter interface, executor, rollback support)
- **concrete rotation adapters: StubRotationAdapter (testing/demonstration) and EnvFileRotationAdapter (env file rotation)**
- regex filtering for credential detection
- expanded test coverage (33 test files)
- write-back execution with fingerprint placeholders (security: no plaintext written)

### Known gaps
- 2 tests skipped (docling OCR/PDF fixture limitations; tests are correctly marked skip):
  - `test_parse_pdf_file_skips_non_key_lines` (PDF fixture does not produce OCR-keyed content)
  - `test_parse_image_file_skips_non_key_content` (image fixture does not produce OCR-keyed content)

## v0.5.2 + v0.5.3 queue

### v0.5.2 (planned)
- live provider validation backends (AWS, GCP, Azure, or HTTP checks)
- broader source parsing (YAML, JSON, shell profiles, CSV, TXT, DOCX, PDF, images via Docling)
- actual write-back execution with --confirm flow
- rotation automation hooks (not just detection)
- expanded tests for all new surfaces
- Docling integration for document/image-based credential extraction

### v0.5.3 (done)
- add `caveman_mode` config support with safe default OFF
- add `python -m hermesoptimizer caveman` toggle path
- keep safety-critical responses in full mode for mutations, credentials, and destructive ops
- wire caveman skill/rules into Hermes-wide workflow as optional add-on
- document caveman behavior, non-goals, and safety guardrails

## v0.6.0 queue

### v0.6.0 (planned)
- add SSH bootstrap/session reuse for remote runs so the agent does not SSH for every command
- add tmux session management for persistent remote workflows
- establish private/VPN IP defaults instead of localhost
- establish port range conventions for dev servers (not just 8000/3000)
- add default install skills for common dev environments
- keep the OpenClaw gateway/config diagnosis work in scope
- verify remote smoke run behavior and session reuse logs
