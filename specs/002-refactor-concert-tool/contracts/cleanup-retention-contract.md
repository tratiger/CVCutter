# Contract: Cleanup and Retention Boundaries

## Scope

Defines what operators can delete manually and what records must remain protected.

## Retention Classes

### Non-deletable (Protected Minimal Audit Ledger)

- Job identifier and creation event
- Stage transition events
- Retry outcome events
- Terminal outcomes (`completed`, `failed`, `canceled`)
- Timestamps associated with the above records

Deletion requests against this class must be rejected with clear guidance.

### Deletable (Operator Cleanup Scope)

- Intermediate media artifacts
- Non-audit diagnostic files
- Re-creatable derived outputs not part of protected ledger records
- UI-visible run-history detail records outside the protected minimal audit class

## Cleanup Operation Contract

1. Cleanup is operator-triggered only (no automatic purge).
2. UI provides direct actions for selecting deletable records/files.
3. Cleanup action emits structured event with actor, target class, and outcome.
4. Cleanup never mutates protected minimal audit records.

## Validation

- Positive test: selected deletable artifacts are removed through UI action.
- Negative test: deletion attempt on protected minimal audit entries is blocked.
- Regression test: protected ledger integrity remains intact after cleanup operations.
