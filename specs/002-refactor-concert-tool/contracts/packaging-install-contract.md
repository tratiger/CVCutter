# Contract: Packaging and Installation

## Scope

Defines installer/runtime expectations for non-engineering users.

## Distribution Targets

- Windows 10/11 (64-bit) desktop
- macOS 13+ desktop (Apple Silicon and Intel)

## Packaging Contract

1. Release artifacts provide end-user install flow without requiring Python/uv installation.
2. Installer validates OS compatibility before install.
3. Unsupported environments are blocked with explicit supported-platform guidance.
4. First launch must present onboarding to create first job draft.

## Runtime Contract

- Bundled runtime includes required dependencies for baseline operation.
- Missing optional acceleration does not block execution (CPU fallback path required).
- Required local model availability checks run before model-dependent stages with reduced-confidence fallback semantics where applicable.

## Validation

- Clean-machine install test (supported OS): install + first launch success.
- Unsupported-machine install test: install blocked with guidance.
- First-launch onboarding test: first job draft creation without developer tools.
