# Hermes Optimizer Release 0.6.0

## Status

Planned. OpenClaw gateway work plus remote dev workflow hardening (tmux + SSH session reuse, private IP defaults, port conventions, install skills).

## Goal

Teach Hermes to use a proper remote dev workflow: tmux-based SSH sessions that persist across commands, private/VPN IP defaults instead of localhost, sensible port ranges, and default install skills for common environments.

## What v0.6.0 adds

### SSH + tmux workflow
- one SSH connection per remote session, not per command
- tmux session bootstrap on first connect
- commands run inside tmux panes/windows
- session reuse across multiple commands
- graceful degradation to one-off SSH when tmux unavailable

### Private/VPN IP defaults
- prefer host private IP or VPN IP over localhost/127.0.0.1
- document common private IP ranges for dev hosts
- fallback to localhost only when no private IP is configured

### Port range conventions
- establish port allocation ranges per project type
- avoid defaulting to 8000 or 3000 for everything
- examples:
  - 8000-8099: Python backends
  - 8100-8199: Go services
  - 8200-8299: Node/TS services
  - 8300-8399: Rust services
  - 8400-8499: databases
  - 8500-8599: caches/queues
- per-project port assignment within ranges

### Default install skills
- tmux setup and session management
- sshpass installation and usage
- build toolchains (Go, Rust, Node, Python)
- language runtimes and version managers
- common dev dependencies (docker, make, git)

## Safety contract

- SSH reuse is opt-in per workflow or run mode
- local-only work stays local
- remote command execution should not silently fan out new SSH sessions
- session reuse must degrade safely to explicit SSH when needed
- private IP usage requires explicit host configuration
- port ranges are conventions, not hard limits

## v0.6.0 focus

1. add SSH bootstrap/session reuse for remote runs
2. add tmux session management for persistent remote workflows
3. establish private/VPN IP defaults
4. establish port range conventions
5. add default install skills for common environments
6. validate the remote run path with a smoke test
7. keep OpenClaw gateway/config diagnosis work in scope

## Source of truth

- `TODO.md` for the active execution queue
- `ROADMAP.md` for the release sequence
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and gates
