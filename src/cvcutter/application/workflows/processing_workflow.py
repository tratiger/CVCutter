from __future__ import annotations

from dataclasses import dataclass, field

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.processing_job import ProcessingJob


@dataclass(slots=True)
class ProcessingWorkflow:
    event_log: list[ProcessingEvent] = field(default_factory=list)

    def run_until_complete(self, job: ProcessingJob) -> list[ProcessingEvent]:
        job.start()
        self.event_log.append(ProcessingEvent("job.created", job.job_id, {"state": job.state.value}))
        while job.state.value == "running":
            stage = job.complete_current_stage()
            self.event_log.append(ProcessingEvent("job.state_changed", job.job_id, {"stage": stage.value}))
        return self.event_log

    def resume(self, job: ProcessingJob) -> str:
        next_stage = select_first_incomplete_stage(job.completed_stages)
        return "done" if next_stage is None else next_stage.value
