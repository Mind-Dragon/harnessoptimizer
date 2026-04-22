# akta2 Project State Analysis

## Project Overview

**akta2** is an ESP32 CSI (Channel State Information) Network Node Migration Project with a major secondary workstream: **videoworks** — a MeshPose/3D human motion reconstruction pipeline for basketball video analysis.

Location: `/home/work/akta2`

---

## Primary Project: ESP32-S3 CSI Network Nodes (RuView)

### Purpose
Real-time basketball court tracking using 16 ESP32 devices with UWB (Ultra-Wideband) modules to track player positions via Channel State Information capture.

### Architecture
- **16 ESP32-S3 nodes** with UWB + WiFi, positioned around a FIBA court (28m x 15m)
- **Desktop Receiver App** (Python): UDP listener (port 5005), packet parser, SQLite DB, WebSocket server (port 8765)
- **Dashboard** (Node.js/Vite): Three.js 3D court visualization, real-time device markers
- **Firmware**: ESP-IDF based, with service manager, boot profiles, remote console (TCP port 2323)

### Key Features
- Binary UDP packet format with CRC32 validation
- Session lifecycle management (idle -> active -> stopped -> archived)
- Service manager with boot profiles: `minimal`, `wifi-only`, `full`
- Remote console access with authentication
- Cross-platform: macOS primary, Linux compatible

### Directory Structure
```
akta2/
├── firmware/esp32-csi-node/   # ESP-IDF firmware
├── apps/
│   ├── receiver/              # Python UDP receiver + WebSocket
│   └── dashboard/               # Three.js web dashboard
├── scripts/
│   └── esp32-csi-debug.py      # Primary diagnostic script
├── tests/                       # pytest suite
└── docs/                        # 20+ markdown docs
```

### Current State
- Firmware: ESP-IDF project structure present, appears to be in active development
- Receiver app: Python-based, SQLite with WAL mode
- Dashboard: Vite dev server on port 5173
- Debug-first strategy: comprehensive diagnostics before feature builds
- Git repo exists but appears to be a bare/object store (no HEAD/config/index files)

---

## Secondary Project: videoworks (MeshPose / Bell Pipeline)

### Purpose
Full-length 3D human motion reconstruction from basketball video, producing:
1. Per-frame mesh artifacts (JSON + GLB)
2. Side-by-side proof video (source left, overlay right)
3. Unreal Engine handoff bundle (FBX/GLB)

### Current Phase
**Phase 1b — In Progress** (single Bell video proof)

### Active Run Status (CRITICAL)
- **Run ID**: `2026-04-21-bell-proof-rerun-02`
- **Vast.ai Instance**: `35383952`
- **Engine**: SAT-HMR (Scale-Adaptive Transformer for Human Mesh Recovery)
- **GPU**: RTX 3090
- **Batch Size**: 4
- **Progress**: 10,000 / 25,089 frames (39.9%)
- **Chunks**: 10 of ~25 completed (0..9)
- **TMUX Session**: `bell-stage-a-r2`
- **Remote Log**: `/workspace/videoworks/artifacts/bell/2026-04-21-bell-proof-rerun-02/reports/step110_stage_a.log`
- **Status**: IN PROGRESS — Stage A inference running on live Vast worker

### Pipeline Architecture
```
Bell video (Christian Bell Age 13.mp4)
  -> Stage A: Preflight + Frame Layout + Person Detection + SAT-HMR Inference
     -> Per-frame JSON + mesh artifacts
  -> Stage B: Render Preflight + Overlay Renderer
     -> Side-by-side proof MP4
  -> Unreal Handoff Adapter
     -> FBX/GLB export bundle
```

### Key Documents
| File | Purpose |
|------|---------|
| `GUIDELINE.md` | Operational policy and phase boundaries (source of truth) |
| `ARCHITECTURE.md` | System shape and data flow |
| `TODO.md` | Live execution queue with 21 sequential steps |
| `BELLTEST.md` | Active execution spec for the current Bell run |

### Completed Steps (TODO)
- [x] 10 Freeze source clip as run truth
- [x] 20 Define Vast Bell run requirements
- [x] 30 Parallel subagent wave — provider + pipeline audits
- [x] 40 Select provider implementation
- [x] 50 Validate provider gates before launch
- [x] 60 Create a fresh Bell run root
- [x] 70 Launch worker and verify readiness
- [x] 80 Stage inputs and runtime payload
- [x] 90 Run mandatory frame-layout prepass
- [x] 100 Lock subject-selection and ball-handling policy
- [ ] 110 **Run Stage A truthful inference — IN PROGRESS**
- [ ] 120-210 Remaining steps (validation, rendering, QA, packaging, teardown)

### Known Issues from Prior Runs (BELLTEST.md)
1. **Import/path failure**: Flat `/workspace/videoworks` layout caused import resolution failures
2. **Opaque chunk runs**: SAT-HMR subprocess buffered output, looked frozen
3. **Stale state bookkeeping**: Manifest updates inconsistent after chunks
4. **Disk exhaustion**: Catastrophic failure on chunk 4 — `OSError: [Errno 28] No space left on device` (50G root, 33.9G used)
5. **Fake final video**: Prior side-by-side MP4 was byte-identical to overlay output (not a real render)

### Fix Applied for Current Run
- Patched `scripts/sathmr_inference.py` to fall back through python3.11 -> python3.10 -> python3 (worker image only has python3.10)
- Added regression test for the python version fallback
- Restarted Stage A successfully after patch

### Disk Budget (from BELLTEST.md)
- Source MP4: ~739 MB
- SAT-HMR JSON: ~20 MB
- GLB sequence: ~2.0 GB
- GLB squashfs: ~857 MB
- Prior partial remote tree: ~33.9 GB
- **Target**: 100G+ writable disk (safer: 150G+)

---

## Documentation Inventory

### RuView / ESP32 Docs (9 files)
- `docs/system-overview.md` — Comprehensive architecture (492 lines)
- `docs/user-guide.md` — Command reference
- `docs/service-developer-guide.md` — Adding new services
- `docs/troubleshooting.md` — Common issues
- `docs/development.md`, `docs/performance.md`, `docs/power.md`, `docs/protocol.md`
- `docs/quickstart.md`

### videoworks Docs (4 core + archive)
- `videoworks/GUIDELINE.md` — Operational source of truth
- `videoworks/ARCHITECTURE.md` — System architecture
- `videoworks/TODO.md` — Live execution queue
- `videoworks/BELLTEST.md` — Active run spec
- `docs/archive/legacy-phase-plans-2026-04-18/` — Retired plans

### DensePose Research Docs (6 files)
- Various analysis docs for DensePose/MeshPose research

---

## Git Status
- `.git/` directory exists with objects and refs but **missing HEAD, config, index files**
- This suggests a bare repo or corrupted worktree
- May need `git init` or worktree repair

---

## Immediate Action Items

### For videoworks (Priority)
1. **Monitor Stage A completion** — ~15,089 frames remaining at ~45 frames/min = ~5-6 hours ETA
2. **Validate Stage A outputs** when chunk 24 completes (step 120)
3. **Run Stage B render preflight** on GPU worker (step 130)
4. **Render full side-by-side proof** (step 140)
5. **Run QA checks** to prevent fake-final issue (step 150)

### For akta2 ESP32 (Background)
- Firmware build validation
- Receiver app integration tests
- Dashboard WebSocket connectivity tests

---

## Summary

The akta2 project has two active workstreams:
1. **RuView ESP32 system**: Hardware/firmware for real-time basketball court tracking (16 nodes, UWB+CSI)
2. **videoworks MeshPose pipeline**: 3D human motion reconstruction from video, currently running Stage A inference on a live Vast.ai RTX 3090 worker (39.9% complete)

The most critical current state is the **live Bell Stage A run** — it needs monitoring for completion, then validation, rendering, QA, and teardown. The project has excellent documentation discipline with clear separation of concerns (GUIDELINE > ARCHITECTURE > TODO > BELLTEST).
