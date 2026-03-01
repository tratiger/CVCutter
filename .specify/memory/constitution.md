<!--
Sync Impact Report
- Version change: template (unversioned) -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. Domain-Centered Modular Design (NON-NEGOTIABLE)
  - Template Principle 2 -> II. Test-First Delivery and Regression Safety (NON-NEGOTIABLE)
  - Template Principle 3 -> III. Deterministic Processing, Observability, and Resume
  - Template Principle 4 -> IV. Local-First Media Intelligence and Resource Efficiency
  - Template Principle 5 -> V. Standardized Engineering Toolchain and Quality Gates
- Added sections:
  - Engineering Constraints
  - Delivery Workflow & Quality Gates
- Removed sections:
  - None
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md
  - ✅ .specify/templates/spec-template.md
  - ✅ .specify/templates/tasks-template.md
  - ⚠ .specify/templates/commands/*.md (directory absent; no files to update)
- Deferred items:
  - None
-->
# CVCutter Constitution

## Core Principles

### I. Domain-Centered Modular Design (NON-NEGOTIABLE)
CVCutter MUST separate presentation, application orchestration, domain logic, and
infrastructure adapters. Domain logic MUST NOT depend directly on UI frameworks or
third-party SDK implementations; integrations MUST be hidden behind interfaces.
Any module exceeding 1000 lines MUST be split into cohesive subpackages.
Rationale: strict boundaries keep the media pipeline maintainable and independently
testable.

### II. Test-First Delivery and Regression Safety (NON-NEGOTIABLE)
Every behavior change MUST start with failing automated tests (red), followed by the
minimum implementation (green), and then refactoring. Every production defect MUST
gain a regression test before the fix is merged. Cross-module workflows MUST be covered
by integration tests in addition to unit tests.
Rationale: failure-first development prevents regressions in long-running media
workflows.

### III. Deterministic Processing, Observability, and Resume
Video segmentation, audio synchronization, and mapping decisions MUST be reproducible
from recorded inputs and persisted metadata. Long-running operations MUST emit
structured logs and checkpoints sufficient for audit and resume. Resume behavior MUST
continue from the latest valid checkpoint unless inputs or configuration changed.
Rationale: deterministic and observable processing is required for trust and recovery.

### IV. Local-First Media Intelligence and Resource Efficiency
Core media analysis and synchronization MUST execute locally and MUST NOT require
external APIs to function. External AI services MAY assist metadata enrichment but MUST
be optional, explicitly failure-aware, and manually overridable. Implementations MUST
prefer memory-efficient processing and SHOULD leverage validated hardware acceleration.
Rationale: local-first execution improves reliability, cost control, and privacy.

### V. Standardized Engineering Toolchain and Quality Gates
Python dependency management and execution MUST use uv. Changes are mergeable only
when ruff, pyright, and pytest with coverage reporting pass in CI or equivalent local
validation. Code MUST follow DRY, KISS, OOP, and domain-driven boundaries defined by
this constitution.
Rationale: a uniform toolchain and objective gates keep quality predictable.

## Engineering Constraints

CVCutter remains an integrated tool for concert video splitting, audio synchronization,
metadata mapping, and YouTube upload orchestration. Refactoring MAY replace existing
implementations wholesale when this reduces complexity and improves reliability.
Obsolete files and dead paths MUST be removed as part of such refactors. Backward
compatibility is not required by default; when storage or metadata formats change,
the change MUST include explicit migration or regeneration instructions.

## Delivery Workflow & Quality Gates

Work MUST follow this order for each component: investigation and plan, failing tests,
implementation, passing tests, refactoring, and code review. Before merge, reviewers
MUST confirm constitution compliance and quality-gate evidence. Code review MUST include
independent review perspectives and MUST resolve material issues before completion.
The minimum validation command set is: uv run ruff check ., uv run pyright, and
uv run pytest --cov.

## Governance

This constitution supersedes conflicting local conventions for engineering execution.
Amendments MUST be documented in pull requests that include: the proposed text, impact
analysis, and synchronization updates for related templates or guidance files.
Versioning follows semantic rules: MAJOR for incompatible governance redefinition or
principle removal, MINOR for new principles or materially expanded obligations, and
PATCH for clarifications that do not alter obligations. Compliance MUST be reviewed
during planning, task generation, implementation review, and pre-merge validation.

**Version**: 1.0.0 | **Ratified**: 2026-03-01 | **Last Amended**: 2026-03-01
