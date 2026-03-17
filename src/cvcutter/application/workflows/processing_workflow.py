from __future__ import annotations

from dataclasses import dataclass

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.processing_job import ProcessingJob


@dataclass(slots=True)
class ProcessingWorkflow:
    def run_until_complete(self, job: ProcessingJob) -> list[ProcessingEvent]:
        event_log: list[ProcessingEvent] = []
        job.start()
        event_log.append(ProcessingEvent("job.created", job.job_id, {"state": job.state.value}))
        while job.state.value == "running":
            stage = job.complete_current_stage()
            event_log.append(ProcessingEvent("job.state_changed", job.job_id, {"stage": stage.value}))
        return event_log

    def resume(self, job: ProcessingJob) -> str:
        next_stage = select_first_incomplete_stage(job.completed_stages)
        return "done" if next_stage is None else next_stage.value
