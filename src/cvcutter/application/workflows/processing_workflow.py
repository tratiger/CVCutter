from __future__ import annotations

from dataclasses import dataclass

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.processing_job import ProcessingJob


class WorkflowExecutionError(RuntimeError):
    def __init__(self, message: str, events: list[ProcessingEvent]) -> None:
        super().__init__(message)
        self.events = events


@dataclass(slots=True)
class ProcessingWorkflow:
    def run_until_complete(self, job: ProcessingJob) -> list[ProcessingEvent]:
        event_log: list[ProcessingEvent] = []
        job.start()
        event_log.append(
            ProcessingEvent.new(
                "job.created",
                job.job_id,
                {"state": job.state.value},
                severity="info",
                attempt=1,
            )
        )
        while job.state.value == "running":
            stage_name = "unknown"
            try:
                stage = job.stages[job.stage_index]
                stage_name = stage.value
                event_log.append(
                    ProcessingEvent.new(
                        "stage.started",
                        job.job_id,
                        {"state": job.state.value},
                        stage_name=stage_name,
                        attempt=1,
                    )
                )
                completed_stage = job.complete_current_stage()
            except Exception as error:
                job.fail()
                event_log.append(
                    ProcessingEvent.new(
                        "stage.failed",
                        job.job_id,
                        {"state": job.state.value},
                        severity="error",
                        stage_name=stage_name,
                        attempt=1,
                    )
                )
                event_log.append(
                    ProcessingEvent.new(
                        "job.state_changed",
                        job.job_id,
                        {"stage": stage_name, "state": job.state.value},
                        severity="error",
                        attempt=1,
                    )
                )
                raise WorkflowExecutionError(str(error), list(event_log)) from error
            event_log.append(
                ProcessingEvent.new(
                    "stage.completed",
                    job.job_id,
                    {"state": job.state.value},
                    stage_name=completed_stage.value,
                    attempt=1,
                )
            )
            event_log.append(
                ProcessingEvent.new(
                    "job.state_changed",
                    job.job_id,
                    {"stage": completed_stage.value, "state": job.state.value},
                    attempt=1,
                )
            )
        return event_log

    def resume(self, job: ProcessingJob) -> str:
        next_stage = select_first_incomplete_stage(job.completed_stages)
        return "done" if next_stage is None else next_stage.value
