# Contract: Storage Safety Policy

## Scope

Defines runtime free-storage checks and mandatory safety behavior.

## Thresholds

- Warning threshold: free storage `<20 GB`
- Start block threshold: free storage `<10 GB`
- Safe pause threshold: free storage `<5 GB`

## Behavior Contract

1. `<20 GB`:
   - Running jobs continue.
   - Warning event emitted and UI warning shown.
2. `<10 GB`:
   - New job starts are blocked.
   - Existing running job may continue unless `<5 GB` is reached.
3. `<5 GB`:
   - Active job transitions to safe paused state.
   - Resume/start remains blocked until storage recovers above block threshold and operator confirms retry.

## Event Contract

The following structured events must be emitted:

- `storage.threshold_warning`
- `storage.threshold_block`
- `storage.threshold_pause`

Each event includes:

- `job_id` (if applicable)
- `free_gb`
- `threshold_gb`
- `action_taken`
- `occurred_at`

## Validation

- Tests must cover all three thresholds and transition behavior.
- Resume behavior after cleanup must preserve checkpoint integrity.
