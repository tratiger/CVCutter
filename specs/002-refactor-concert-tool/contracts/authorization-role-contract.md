# Contract: Authorization Role Normalization

## Scope

Defines executable authorization semantics for this feature.

## Role Model

- Executable role: `operator` (only)
- Context labels: `editor`, `publisher` (descriptive labels only)

## Rules

1. Workflow permissions must not branch by `editor`/`publisher`.
2. Any executable action request with role other than `operator` is rejected.
3. UI may display `editor`/`publisher` terminology for scenario context, but the execution path remains `operator`.
4. Audit/event records should log normalized role as `operator` for executable actions.

## Validation

- Contract tests must verify no separate permission graph is created for `editor` or `publisher`.
- Traceability matrix must map all workflows to the single executable role contract.
