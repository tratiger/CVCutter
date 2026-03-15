# Quickstart: CVCutter End-to-End Refactor (Planning Validation)

## 1. Developer Planning Validation Prerequisites

- Windows 10/11 (64-bit) or macOS 13+ (Apple Silicon/Intel)
- Python 3.11+
- `uv` installed
- FFmpeg available in runtime environment

## 2. Developer Setup

```bash
uv sync
```

## 3. Development Quality Gates

Run these commands for every delivery candidate:

```bash
uv run ruff check .
uv run pyright
uv run pytest --cov
```

## 4. Planned Runtime Entry (Developer Build)

```bash
uv run cvcutter
```

## 5. Packaging & Install Validation (End-User Path, FR-020/FR-027)

1. Prepare packaged desktop artifact (installer/single executable) from CI/release build.
2. On clean supported workstation, run installer without preinstalled Python/uv.
3. Verify first launch succeeds without developer setup.
4. On unsupported environment, verify installer blocks with supported-OS guidance.

## 6. Core Workflow Validation (Target Behavior)

1. Create a job draft with required baseline metadata and strategy-specific inputs.
2. Start processing and verify stage-level events/checkpoints are written.
3. Force interruption after at least one completed stage.
4. Restart app and verify stale-state transition (`running -> paused -> resumable`) before resume.
5. Resume from first incomplete stage and confirm no duplicate outputs.
6. Execute publish with transient-failure injection and verify retry policy (`Retry-After` priority, backoff+jitter, 15-minute manual escalation).
7. Run multi-instance launch test and verify cross-process single-active-job and draft-lock enforcement.
8. Verify storage threshold behavior: `<20 GB` warning, `<10 GB` new-start block, `<5 GB` safe pause + cleanup guidance, and explicit operator confirmation is required before resume/unblock after recovery.
9. Verify metadata compatibility matrix:
   - missing `schema_version` -> rejected
   - previous version -> accepted via compatibility mapping
   - unknown future version -> rejected with remediation guidance
   - mixed-version CSV rows in one import -> rejected
   - malformed required fields / invalid enum / out-of-range length -> rejected
   - JSON top-level vs per-record `schema_version` mismatch -> rejected
   - unknown fields -> warning with deterministic handling
10. Verify classification decision rules:
    - confidence requires top score `>=70` and margin `>=10`
    - single-candidate confident path requires score `>=70`
    - no-confident-match triggers strategy-switch/adjust-input guidance
    - timestamp strategy blocks when recording-time/event-window validity fails
11. Verify role model: all executable workflows run under `operator`; `editor`/`publisher` remain labels only.
12. Verify FR-021 dependency map behavior by changing configuration after checkpoint creation and confirming resume is blocked until explicit invalidate-or-cancel decision is recorded.
13. Verify FR-038 cleanup behavior:
    - operator can delete non-audit artifacts from UI
    - deletion of protected minimal audit records is blocked with guidance
14. Verify append-only event ledger behavior by asserting historical event records cannot be mutated or deleted during normal operations.
15. Verify gating behavior before export/publish:
    - export/publish is blocked while low-confidence segment confirmations are pending
    - publish is blocked while sync outputs flagged for manual correction remain unresolved
16. Verify CR-010 by executing core business-logic test suites in a GUI-free context (presentation layer dependency unavailable) and confirming all core tests pass.

## 7. Manual-Judgment Test Protocol (Constitution CR-003)

Before running human-judgment validations (for example segmentation quality review), create/update a reviewer-visible artifact section titled `Manual Test Protocol` (in plan/task/PR artifact), and record:

- Approver identity (requesting user or designated domain reviewer, not implementer)
- Date
- Procedures
- Required test materials
- Acceptance criteria

After execution, append to the **same artifact**:

- Observed results
- Pass/fail determination date

## 8. Supported Interface Scope

- Input video: `MP4`/`MOV`/`MKV`/`MTS`
- Input audio: `WAV`/`FLAC`/`AAC`
- Metadata import: `CSV`/`JSON` (UTF-8, requires `schema_version`)
- Output media: `MP4` container with `AAC` audio
- Approved integrations: YouTube API, Google Forms API, configured AI provider API
