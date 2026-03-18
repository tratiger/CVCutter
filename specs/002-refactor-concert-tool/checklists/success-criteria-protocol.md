# Success Criteria Protocol

Defines SC-001..SC-010 measurement approach, run identifiers, and operator recording templates.

## Run Metadata Template

- Run ID:
- Date:
- Build/Commit:
- Operator:
- Dataset/Profile:

## Measurement Plan

| SC | Metric Source | Execution Method | Evidence Artifact |
|---|---|---|---|
| SC-001 | Resume/recovery correctness | `tests/integration/workflows/test_resume_from_first_incomplete_stage.py` + interruption scenario runs | `success-criteria-report.md` |
| SC-002 | Memory-bound sync behavior | Validation-profile sync runs with peak RSS capture | `success-criteria-report.md` |
| SC-003 | Segment acceptance ratio | Segmentation validation set + manual review sheet | `plan.md` Manual Test Protocol + `success-criteria-report.md` |
| SC-004 | First-time operator setup success | Timed onboarding/setup usability sessions (>=10 participants) | `success-criteria-report.md` |
| SC-005 | Publish retry recovery + dedup | `tests/integration/publishing/test_publish_dedup_retry.py` + transient injection runs | `success-criteria-report.md` |
| SC-006 | Transparency/guidance rating | Post-run operator survey (>=10 responses) | `success-criteria-report.md` |
| SC-007 | Install/open success for non-engineers | Clean-machine install sessions (>=10 participants) | `success-criteria-report.md` |
| SC-008 | Sync median alignment error | 20-run sync validation set with error metrics | `success-criteria-report.md` |
| SC-009 | Content-based classification acceptance | Validation dataset with >=200 attempts | `success-criteria-report.md` |
| SC-010 | Keyboard-only + contrast | Accessibility integration tests + operator verification set | `success-criteria-report.md` |

## Status Categories

- **Pass**: Success criterion fully satisfied with required sample size and evidence.
- **Provisional Pass**: Automated regression evidence is green, but required field sample size/manual study is incomplete.
- **Pending Manual Execution**: Requires human-judgment or participant study not yet executed.
- **Fail**: Required metric was measured and did not satisfy threshold.
