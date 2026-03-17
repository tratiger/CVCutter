from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SetupWizardViewModel:
    source_path: str = ""
    output_path: str = ""

    def validate(self) -> bool:
        return bool(self.source_path and self.output_path)
