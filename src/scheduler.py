"""Scheduler — APScheduler-based hourly/daily scheduling with error recovery."""

import sys
import time
import traceback
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.orchestrator import Orchestrator


class Scheduler:
    """Wraps APScheduler for the Pro-IAQ monitoring pipeline."""

    def __init__(self, orchestrator: Orchestrator, config: dict):
        self.orchestrator = orchestrator
        self.sched_config = config.get("scheduler", {})
        self.backoff_base = 1.0
        self.max_backoff = 3600.0  # 1 hour
        self.consecutive_failures = 0

    def start(self) -> None:
        """Start the scheduler in the background."""
        mode = self.sched_config.get("mode", "hourly")

        scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            }
        )

        if mode == "hourly":
            hours = self.sched_config.get("hourly_interval", 1)
            scheduler.add_job(
                self._scheduled_run,
                IntervalTrigger(hours=hours),
                id="proiaq_hourly",
                name=f"Pro-IAQ monitor (every {hours}h)",
            )
            logger.info(f"Scheduler started: every {hours} hour(s)")

        elif mode == "daily":
            daily_time = self.sched_config.get("daily_time", "09:00")
            hour, minute = daily_time.split(":")
            scheduler.add_job(
                self._scheduled_run,
                CronTrigger(hour=int(hour), minute=int(minute)),
                id="proiaq_daily",
                name=f"Pro-IAQ monitor (daily at {daily_time})",
            )
            logger.info(f"Scheduler started: daily at {daily_time}")

        elif mode == "once":
            logger.info("Mode is 'once' — running immediately then exiting")
            self._scheduled_run()
            return

        else:
            logger.error(f"Unknown scheduler mode: {mode}")
            sys.exit(1)

        scheduler.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted, shutting down...")
            scheduler.shutdown(wait=False)

    def _scheduled_run(self) -> None:
        """Execute one monitoring cycle with error recovery."""
        start = datetime.utcnow()
        logger.info("=" * 60)
        logger.info(f"Monitoring cycle starting at {start.isoformat()}")

        try:
            summary = self.orchestrator.run_once()
            self.consecutive_failures = 0
            self._log_summary(summary)

            # Optional Telegram notification
            self._maybe_notify(summary)

        except Exception as e:
            self.consecutive_failures += 1
            logger.error(
                f"Cycle failed (consecutive failures: {self.consecutive_failures}): {e}"
            )
            logger.error(traceback.format_exc())

            # Exponential backoff
            wait = min(
                self.backoff_base * (2 ** (self.consecutive_failures - 1)),
                self.max_backoff,
            )
            logger.warning(f"Backing off for {wait:.0f}s before next attempt...")
            time.sleep(wait)

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(f"Cycle completed in {elapsed:.1f}s")

    def _log_summary(self, summary: dict) -> None:
        """Log a readable summary of the run."""
        logger.info(
            f"Summary: {summary['platforms_scanned']} platforms, "
            f"{summary['posts_found']} posts, "
            f"{summary['replies_generated']} replies generated, "
            f"{summary['replies_posted']} posted, "
            f"{summary['errors']} errors "
            f"{'(DRY RUN)' if summary.get('dry_run') else ''}"
        )
        for detail in summary.get("details", []):
            status = "✓" if not detail.get("error") else "✗"
            logger.info(
                f"  {status} {detail['platform']}: "
                f"{detail['posts_found']} found, "
                f"{detail['replied']} replied, "
                f"{detail['skipped']} skipped"
                f"{' — ' + detail['error'] if detail.get('error') else ''}"
            )

    def _maybe_notify(self, summary: dict) -> None:
        """Send Telegram notification if configured."""
        import os
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return

        msg = (
            f"🤖 *Pro-IAQ Monitor Report*\n"
            f"Time: {summary['timestamp']}\n"
            f"Platforms: {summary['platforms_scanned']}\n"
            f"Posts found: {summary['posts_found']}\n"
            f"Replies posted: {summary['replies_posted']}\n"
            f"Errors: {summary['errors']}\n"
        )
        if summary.get("dry_run"):
            msg += "⚠️ DRY RUN — no actual posts made.\n"

        try:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Telegram notification failed: {e}")
