from __future__ import annotations


def low_confidence_threshold(job_profile: str) -> float:
    return 0.75 if job_profile == "strict" else 0.6
