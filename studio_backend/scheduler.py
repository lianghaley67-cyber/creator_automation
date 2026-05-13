from __future__ import annotations

from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class StudioScheduler:
    def __init__(self, job_callback: Callable[[str], None]) -> None:
        self._job_callback = job_callback
        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def sync(self, schedules: list[dict[str, Any]]) -> None:
        self.start()
        existing_ids = {job.id for job in self._scheduler.get_jobs()}
        desired_ids = {str(schedule.get("id")) for schedule in schedules if schedule.get("enabled")}

        for job_id in existing_ids - desired_ids:
            self._scheduler.remove_job(job_id)

        for schedule in schedules:
            if not schedule.get("enabled"):
                continue
            schedule_id = str(schedule["id"])
            hour_text, minute_text = str(schedule.get("time_of_day", "08:30")).split(":", 1)
            weekdays = ",".join(schedule.get("weekdays") or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
            trigger = CronTrigger(
                day_of_week=weekdays,
                hour=int(hour_text),
                minute=int(minute_text),
                timezone="Asia/Shanghai",
            )
            self._scheduler.add_job(
                self._job_callback,
                trigger=trigger,
                args=[schedule_id],
                id=schedule_id,
                replace_existing=True,
                misfire_grace_time=600,
            )

    def next_run_for(self, schedule_id: str) -> str | None:
        job = self._scheduler.get_job(schedule_id)
        if job and job.next_run_time:
            return job.next_run_time.isoformat(timespec="seconds")
        return None
