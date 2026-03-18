from __future__ import annotations


def low_confidence_threshold(job_profile: str) -> int:
    return 80 if job_profile == "strict" else 70
