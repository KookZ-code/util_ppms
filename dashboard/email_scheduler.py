"""APScheduler cron jobs for shift-end email summaries.

Day shift email:   19:05 daily
Night shift email: 07:05 daily
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

_scheduler = None


def start_scheduler():
    """Start the email scheduler (call once on app startup)."""
    global _scheduler
    if _scheduler is not None:
        return

    from shift_email import send_shift_summary

    _scheduler = BackgroundScheduler(daemon=True)

    # Day shift ends at 19:00 → send summary at 19:05
    _scheduler.add_job(
        send_shift_summary,
        'cron',
        hour=19, minute=5,
        args=['Day'],
        id='day-shift-email',
        name='Day Shift Email Summary',
        misfire_grace_time=300,
    )

    # Night shift ends at 07:00 → send summary at 07:05
    _scheduler.add_job(
        send_shift_summary,
        'cron',
        hour=7, minute=5,
        args=['Night'],
        id='night-shift-email',
        name='Night Shift Email Summary',
        misfire_grace_time=300,
    )

    # Daily morning summary at 07:30 (before 08:15 meeting)
    from daily_report import send_daily_report
    _scheduler.add_job(
        send_daily_report,
        'cron',
        hour=7, minute=30,
        id='daily-report',
        name='Daily Morning Meeting Report',
        misfire_grace_time=600,
    )

    _scheduler.start()
    log.info("Email scheduler started: Day@19:05, Night@07:05, Daily@07:30")
    print("Email scheduler started: Day @19:05, Night @07:05, Daily Summary @07:30")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
